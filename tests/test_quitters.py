# -*- coding: utf-8 -*-
"""The site half: a winner the scorer struck out is recorded, not rated."""
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="quitters")
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


# The real cast of match #91.
STAYED = ["FAFA", "THE STOAT", "WHITE"]
LEFT = ["PAUL", "SEMNOME"]
LOSERS = ["EDISON", "ZOEN21", "ANONYMOUS", "GG", "AILOVIU", "FEAR"]
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM held_results")
for nm in STAYED + LEFT + LOSERS:
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub) "
               "VALUES (?,?,1500,20,20,?)", (nm, N(nm), "sub:" + nm))
cn.commit()
cn.close()
c0 = sqlite3.connect(fa.DB_PATH).cursor()
before = {nm: c0.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                         (N(nm),)).fetchone() for nm in STAYED + LEFT}

# The scorer has already removed the leavers from winning_team; it only
# names them in left_losing so the site can explain itself.
payload = {
    "match_id": "test-quit-1", "sys_id": 91, "region": "america",
    "winning_team": STAYED, "losing_team_1": LOSERS, "losing_team_2": [],
    "scores": dict([(n, 20000) for n in STAYED] + [(n, 15000) for n in LOSERS]),
    "presence": dict((n, 1.0) for n in STAYED + LOSERS),
    "watch_s": 4440, "tracked_reads": 1307,
    "left_losing": LEFT,
}
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload),
                              content_type="application/json", headers=HDR)
print("\n--- the result landed ---")
check("game_end accepted it", r.status_code in (200, 201), True)

c = sqlite3.connect(fa.DB_PATH).cursor()
print("\n--- the ones who stayed were paid ---")
for nm in STAYED:
    elo, w, l = c.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                          (N(nm),)).fetchone()
    check("%s gained rating" % nm, elo > before[nm][0], True)
    check("%s got the win" % nm, w, before[nm][1] + 1)

print("\n--- the ones who walked got nothing, either way ---")
for nm in LEFT:
    elo, w, l = c.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                          (N(nm),)).fetchone()
    check("%s rating untouched" % nm, round(elo, 4), round(before[nm][0], 4))
    check("%s got no win" % nm, w, before[nm][1])
    check("%s got no loss" % nm, l, before[nm][2])

print("\n--- but the match is on record for them ---")
rows = {r[0]: r[1] for r in c.execute(
    "SELECT name, reason FROM held_results WHERE reason = 'left-while-losing'")}
for nm in LEFT:
    check("%s has a held result" % nm, rows.get(nm), "left-while-losing")
check("and nobody else does", len(rows), len(LEFT))

print("\n--- and they are told why, in words ---")
cl2 = fa.app.test_client()
with cl2.session_transaction() as sess:
    sess["google_sub"] = "sub:SEMNOME"
body = cl2.get("/api/my/held").get_data(as_text=True)
check("the held endpoint answers", "left-while-losing" in body, True)
check("with the explanation, not the fallback",
      "one-in-four" in body and "set aside for review" not in body, True)

print("\n--- and leaving a side that LOSES still costs the loss ---")
# The scorer only ever strikes names off the WINNING roster. This guards the
# site half: even when left_losing names somebody on a losing side, the loss
# lands. Nobody should ever "tidy" this into symmetry - leaving must not be
# an escape from a defeat, only a forfeit of a comeback.
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM held_results")
for nm in ["WINNER1", "WINNER2", "BAILER", "STAYER"]:
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub) "
               "VALUES (?,?,1500,20,20,?)", (nm, N(nm), "sub:" + nm))
cn.commit()
cn.close()
c2 = sqlite3.connect(fa.DB_PATH).cursor()
was = {nm: c2.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                      (N(nm),)).fetchone() for nm in ("BAILER", "STAYER")}
p2 = {
    "match_id": "test-quit-2", "sys_id": 92, "region": "america",
    "winning_team": ["WINNER1", "WINNER2"],
    "losing_team_1": ["BAILER", "STAYER"], "losing_team_2": [],
    "scores": {"WINNER1": 20000, "WINNER2": 19000, "BAILER": 9000, "STAYER": 11000},
    "presence": {"WINNER1": 1.0, "WINNER2": 1.0, "BAILER": 0.3, "STAYER": 1.0},
    "watch_s": 4000, "tracked_reads": 1200,
    "left_losing": ["BAILER"],
}
fa.app.test_client().post("/api/game_end", data=json.dumps(p2),
                          content_type="application/json", headers=HDR)
c2 = sqlite3.connect(fa.DB_PATH).cursor()
for nm in ("BAILER", "STAYER"):
    elo, w, l = c2.execute("SELECT elo, wins, losses FROM players WHERE norm_name=?",
                           (N(nm),)).fetchone()
    check("%s took the loss" % nm, l, was[nm][2] + 1)
    check("%s lost rating" % nm, elo < was[nm][0], True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
