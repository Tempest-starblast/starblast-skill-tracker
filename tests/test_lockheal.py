# -*- coding: utf-8 -*-
"""Two guards from the 24 Sep outage (9.77.0).

1. A write lock that stays stuck gets the web app reloaded - the manual fix
   that ended the outage - after LOCK_HEAL_AFTER_S of lock failures with no
   quiet minute, at most once per LOCK_HEAL_COOLDOWN_S.
2. A result posted twice is counted once: the scorer now retries failed
   posts, and a post that timed out on its end may already have landed."""
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="lockheal")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.LOCK_HEAL_STATE = os.path.join(TMP, "lock_heal.json")
fa.LOCK_HEAL_LOG = os.path.join(TMP, "lock_heal.log")
fa.WSGI_FILE = os.path.join(TMP, "wsgi.py")
open(fa.WSGI_FILE, "w").close()
fa.init_db()
fa._load_api_keys = lambda: {"k"}
HDR = {"X-API-Key": "k"}
N = fa.normalize_name
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


# A route that fails the way every page did during the outage. Registered
# before the first request, as Flask requires.
@fa.app.route("/__test_locked")
def _locked():
    raise sqlite3.OperationalError("database is locked")


def mtime():
    return os.path.getmtime(fa.WSGI_FILE)


def reset():
    for p in (fa.LOCK_HEAL_STATE, fa.LOCK_HEAL_LOG):
        if os.path.exists(p):
            os.remove(p)
    os.utime(fa.WSGI_FILE, (1, 1))


print("\n--- a steady lock streak reloads once, at three minutes ---")
reset()
calls = [fa.note_lock_failure(now=1000 + s) for s in range(0, 180, 20)]
check("nothing before three minutes", any(calls), False)
check("  and the wsgi file untouched", mtime(), 1)
check("at three minutes it reloads", fa.note_lock_failure(now=1180), True)
check("  by touching the wsgi file", mtime() > 1, True)
check("  and says so in its log", "reloading the web app" in open(fa.LOCK_HEAL_LOG).read(), True)
os.utime(fa.WSGI_FILE, (1, 1))
check("still locked right after: no second reload (cooldown)",
      any(fa.note_lock_failure(now=1180 + s) for s in range(20, 600, 20)), False)
check("  wsgi untouched through the cooldown", mtime(), 1)
check("after the cooldown, a lock still stuck reloads again",
      any(fa.note_lock_failure(now=1780 + s) for s in range(0, 320, 20)), True)

print("\n--- ordinary contention never reloads ---")
reset()
t, fired = 5000, False
for burst in range(10):                  # a few failures, then a quiet minute, again and again
    for s in (0, 5, 10):
        fired = fired or fa.note_lock_failure(now=t + s)
    t += 10 + 61
check("bursts with quiet minutes between them never reload", fired, False)
check("  wsgi untouched", mtime(), 1)

print("\n--- the error page feeds it ---")
reset()
fa.app.config["TESTING"] = False
fa.app.config["PROPAGATE_EXCEPTIONS"] = False
r = fa.app.test_client().get("/__test_locked")
check("a lock failure still shows the error page", (r.status_code, b"Something broke" in r.data), (500, True))
st = json.load(open(fa.LOCK_HEAL_STATE)) if os.path.exists(fa.LOCK_HEAL_STATE) else {}
check("  and was counted toward a stuck lock", bool(st.get("last")), True)
fa.app.config["TESTING"] = True
fa.app.config["PROPAGATE_EXCEPTIONS"] = None

print("\n--- a result posted twice is counted once ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
for nm in ("DUPWIN1", "DUPWIN2", "DUPLOSE1", "DUPLOSE2"):
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES (?,?,1500,20,20)", (nm, N(nm)))
cn.commit()
cn.close()
payload = {"match_id": "test-dup-1", "sys_id": 4242, "region": "europe",
           "winning_team": ["DUPWIN1", "DUPWIN2"], "losing_team_1": ["DUPLOSE1", "DUPLOSE2"],
           "losing_team_2": [], "scores": {"DUPWIN1": 9000, "DUPWIN2": 9000, "DUPLOSE1": 9000, "DUPLOSE2": 9000},
           "presence": {"DUPWIN1": 1, "DUPWIN2": 1, "DUPLOSE1": 1, "DUPLOSE2": 1},
           "watch_s": 2400, "tracked_reads": 700}


def state():
    c = sqlite3.connect(fa.DB_PATH)
    r = c.execute("SELECT norm_name, ROUND(elo,2), wins, losses FROM players ORDER BY norm_name").fetchall()
    c.close()
    return r


tc = fa.app.test_client()
r1 = tc.post("/api/game_end", data=json.dumps(payload), content_type="application/json", headers=HDR)
after_one = state()
check("the first post lands", r1.status_code in (200, 201), True)
check("  and moves ratings", after_one != [(N(n), 1500.0, 20, 20) for n in ("DUPLOSE1", "DUPLOSE2", "DUPWIN1", "DUPWIN2")], True)
r2 = tc.post("/api/game_end", data=json.dumps(payload), content_type="application/json", headers=HDR)
check("the second is answered 'already recorded'",
      (r2.status_code, (r2.get_json() or {}).get("status")), (200, "already recorded"))
check("  and moves nothing", state(), after_one)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
