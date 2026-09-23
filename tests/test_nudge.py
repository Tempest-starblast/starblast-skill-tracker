# -*- coding: utf-8 -*-
"""Nobody is warned about a name that already reaches their account."""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="nudge")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa._load_api_keys = lambda: {"k"}
HDR = {"X-API-Key": "k"}
N = fa.normalize_name
ok = fail = 0

DOM = "\u0110\u00d8M\u0197\u0141\u0197\u023b\ua740"      # ĐØMƗŁƗȻꝀ
L7 = "\u01417"                                            # Ł7
TAGGED = "(%s)%s" % (L7, DOM)
SYS = 2887


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


# UTC, because the app compares its timestamps against SQLite's
# datetime('now') and the production server runs UTC. A local-time fixture
# makes a fresh check-in look hours old on any machine west of Greenwich.
now = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
cn = sqlite3.connect(fa.DB_PATH)
for t in ("players", "clans", "clan_tag_styles", "appearances",
          "live_lobbies", "checkins", "checkin_nudges"):
    try:
        cn.execute("DELETE FROM %s" % t)
    except sqlite3.OperationalError:
        pass
cn.execute("INSERT INTO clans(tag, display_tag, created_by, created_at) "
           "VALUES ('L7', ?, 'x', datetime('now'))", (L7,))
cn.execute("INSERT INTO clan_tag_styles(clan, shown, created_by, created_at) "
           "VALUES ('L7', ?, 'x', ?)", (L7, fa._stamp()))
# Dom: his own name, his clan's tag saved as his play name, NOT protected.
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,clan,"
           "game_name,strict_mode) VALUES (?,?,1800,40,10,'discord:dom','L7',?,0)",
           (DOM, N(DOM), TAGGED))
# A protected player, flying under their own name with no check-in.
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,strict_mode) "
           "VALUES ('GUARDED',?,1700,30,10,'discord:g',1)", (N("GUARDED"),))
# Two accounts that declared the SAME play name, so it reaches neither.
for who in ("TWINA", "TWINB"):
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,game_name) "
               "VALUES (?,?,1600,20,10,?, 'SHAREDNAME')", (who, N(who), "discord:" + who))
cn.execute("INSERT INTO live_lobbies(sys_id, name, players, age, updated_at) "
           "VALUES (?,?,?,?,?)", (SYS, "4 Elelaemar", 20, 300, now))
for nm in (TAGGED, "GUARDED", "SHAREDNAME"):
    cn.execute("INSERT INTO appearances(sys_id, ship_id, name, region, at) "
               "VALUES (?,?,?,?,?)", (SYS, 1, nm, 'america', now))
cn.commit()
cn.close()

c = sqlite3.connect(fa.DB_PATH).cursor()
print("\n--- the name really does reach him ---")
check("(L7)DOM resolves to Dom's account",
      fa.account_for_ingame_name(c, TAGGED, SYS), DOM)
check("and the clan-tag rule alone would too",
      fa.clan_member_for_tagged_name(c, TAGGED), DOM)

print("\n--- so he is not warned ---")
r = fa.app.test_client().get("/api/bot/checkin/nudge", headers=HDR)
check("the endpoint answers", r.status_code, 200)
nudges = (r.get_json() or {}).get("nudges") or []
who = {n["account"]: n["reason"] for n in nudges}
check("Dom gets no nudge", DOM in who, False)

print("\n--- but the warnings that are real still fire ---")
check("the protected player is still told", who.get("GUARDED"), "protected")
check("and a play name that reaches nobody is still told",
      "playname" in who.values(), True)
check("exactly those two, nobody else", len(nudges), 2)

print("\n--- and a check-in silences it, as before ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO checkins(player, sub, sys_id, created_at) "
           "VALUES ('GUARDED','discord:g',?,?)", (SYS, now))
cn.commit()
cn.close()
r = fa.app.test_client().get("/api/bot/checkin/nudge", headers=HDR)
who2 = {n["account"]: n["reason"] for n in (r.get_json() or {}).get("nudges") or []}
check("the protected player, once checked in, is quiet", "GUARDED" in who2, False)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
