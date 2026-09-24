# -*- coding: utf-8 -*-
"""The site half of the two-ships rule (9.76.0).

The scorer strikes a winner whose name a second ship flew at the same time,
under forty minutes after the name was first seen, and names them in
doubled_win. The site must rate nobody for them, record a duplicate-name
hold for an account holder, explain it in words, and still charge a loss to
anyone the scorer left on a losing side."""
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
TMP = tempfile.mkdtemp(prefix="doubled")
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


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


# Trappist-1 #7142's shape: TRAXOMIA on the winning side with a second ship
# on his name 26 minutes in; FAFA on a losing side, doubled 35 minutes in.
WINNERS = ["SPUNK", "DEEZ NUTS", "JOVI"]
DOUBLED = ["TRAXOMIA"]             # struck by the scorer, has an account
STRANGER = ["FUK U"]               # struck by the scorer, no account
LOSERS = ["FAFA", "LEVI", "JOHN"]
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM held_results")
for nm in WINNERS + DOUBLED + LOSERS:
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub) "
               "VALUES (?,?,1500,20,20,?)", (nm, N(nm), "sub:" + nm))
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES (?,?,1500,20,20)",
           (STRANGER[0], N(STRANGER[0])))
cn.commit()
cn.close()
c0 = sqlite3.connect(fa.DB_PATH).cursor()
before = {nm: c0.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                         (N(nm),)).fetchone() for nm in WINNERS + DOUBLED + STRANGER + LOSERS}

payload = {
    "match_id": "test-doubled-1", "sys_id": 7142, "region": "america",
    "winning_team": WINNERS, "losing_team_1": LOSERS, "losing_team_2": [],
    "scores": dict((n, 20000) for n in WINNERS + LOSERS),
    "peak_scores": dict((n, 20000) for n in WINNERS + LOSERS),
    "presence": dict((n, 1.0) for n in WINNERS + LOSERS),
    "watch_s": 2966, "tracked_reads": 914,
    "doubled_win": DOUBLED + STRANGER,
    "dup_names": {"2": {"FAFA": 2}},
}
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload),
                              content_type="application/json", headers=HDR)
print("\n--- the result landed ---")
check("game_end accepted it", r.status_code in (200, 201), True)

c = sqlite3.connect(fa.DB_PATH).cursor()


def now(nm):
    return c.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                     (N(nm),)).fetchone()


print("\n--- the winners who flew alone were paid ---")
for nm in WINNERS:
    check("%s got the win" % nm, now(nm)[1], before[nm][1] + 1)

print("\n--- a doubled winner gets nothing either way ---")
for nm in DOUBLED + STRANGER:
    elo, w, l = now(nm)
    check("%s rating untouched" % nm, round(elo, 4), round(before[nm][0], 4))
    check("%s no win" % nm, w, before[nm][1])
    check("%s no loss" % nm, l, before[nm][2])

print("\n--- the losing side still pays, doubled or not ---")
for nm in LOSERS:
    elo, w, l = now(nm)
    check("%s took the loss" % nm, l, before[nm][2] + 1)
    check("%s lost rating" % nm, elo < before[nm][0], True)

print("\n--- the account holder has it on record, the stranger does not ---")
rows = {r[0]: (r[1], r[2]) for r in c.execute(
    "SELECT name, reason, won FROM held_results WHERE match_id = 'test-doubled-1'")}
check("TRAXOMIA held as a duplicate-name win", rows.get("TRAXOMIA"), ("duplicate-name", 1))
check("no row for a name nobody owns", "FUK U" in rows, False)
check("nobody else held", sorted(rows), ["TRAXOMIA"])

print("\n--- and is told why, in words ---")
cl = fa.app.test_client()
with cl.session_transaction() as sess:
    sess["google_sub"] = "sub:TRAXOMIA"
body = cl.get("/api/my/held").get_data(as_text=True)
check("the held endpoint answers", "duplicate-name" in body, True)
check("it names the forty minutes", "forty" in body, True)
check("and says a loss still counts", "A loss still counts" in body, True)

print("\n--- a payload without the field behaves as before ---")
p2 = dict(payload, match_id="test-doubled-2", sys_id=7143)
p2.pop("doubled_win")
r = fa.app.test_client().post("/api/game_end", data=json.dumps(p2),
                              content_type="application/json", headers=HDR)
check("accepted", r.status_code in (200, 201), True)
check("no new holds", c.execute("SELECT COUNT(*) FROM held_results WHERE match_id = "
                                "'test-doubled-2'").fetchone()[0], 0)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
