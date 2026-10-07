# -*- coding: utf-8 -*-
"""The finishing order the scorer records (9.82.1): stored with each result, and
the source of a clan's 2nd-place points - ahead of the scoreboard guess."""
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
TMP = tempfile.mkdtemp(prefix="finplaces")
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


print("\n--- reading the scorer's order ---")
check("a clean three-team order", fa._team_places({"places": {"win": 1, "lose1": 3, "lose2": 2}}), {"win": 1, "lose1": 3, "lose2": 2})
check("the other way", fa._team_places({"places": {"win": 1, "lose1": 2, "lose2": 3}}), {"win": 1, "lose1": 2, "lose2": 3})
check("a two-team match keeps the loser's second place", fa._team_places({"places": {"win": 1, "lose1": 2}}), {"win": 1, "lose1": 2})
check("an unknown order is just the winner", fa._team_places({"places": {"win": 1}}), {"win": 1})
check("two teams both claiming second is refused", fa._team_places({"places": {"win": 1, "lose1": 2, "lose2": 2}}), {"win": 1})
check("nonsense places are refused", fa._team_places({"places": {"win": 1, "lose1": 7, "lose2": "x"}}), {"win": 1})
check("no places at all", (fa._team_places({}), fa._team_places({"places": "no"}), fa._team_places(None)), ({}, {}, {}))

print("\n--- the recorded order beats the scoreboard guess ---")
applied = [("W1", 1, 5.0), ("B1", 0, -5.0), ("C1", 0, -5.0)]
T = {"B1": "lose1", "C1": "lose2"}
S = {"B1": 9000, "C1": 100}
check("the scoreboard alone says team 1 was second", fa._second_place_team(applied, T, S), {"B1"})
check("the recorded order says team 2 was", fa._second_place_team(applied, T, S, {"win": 1, "lose1": 3, "lose2": 2}), {"C1"})
check("and when it says team 1, team 1", fa._second_place_team(applied, T, {"B1": 1, "C1": 5000}, {"win": 1, "lose1": 2, "lose2": 3}), {"B1"})
check("with no order, the old guess still works", fa._second_place_team(applied, T, S, {"win": 1}), {"B1"})
check("a recorded second whose rivals had nobody rated still counts",
      fa._second_place_team([("W1", 1, 5.0), ("B1", 0, -5.0)], {"B1": "lose1"}, {"B1": 10}, {"win": 1, "lose1": 2, "lose2": 3}), {"B1"})

print("\n--- end to end: a match posted with its order ---")
cn = sqlite3.connect(fa.DB_PATH)
for t in ("players", "clan_points", "gem_ledger", "matches", "match_players", "held_results"):
    cn.execute("DELETE FROM %s" % t)
cn.execute("DELETE FROM clans")
cn.execute("INSERT INTO clans (tag, created_by, created_at, gems) VALUES ('TST','x','2026-01-01',0)")
names = ["FPW1", "FPW2", "FPL1", "FPL2", "FPM1", "FPM2"]
for n in names:
    cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan) VALUES (?,?,1500,20,20,?)",
               (n, N(n), "TST" if n in ("FPW1", "FPL1", "FPL2") else None))
cn.commit()
cn.close()
score = dict((n, 9000) for n in names)
score.update({"FPL1": 9000, "FPM1": 9000, "FPL2": 400, "FPM2": 400})     # the scoreboard favours team 1
payload = {"match_id": "fp-1", "sys_id": 4242, "region": "america",
           "winning_team": ["FPW1", "FPW2"], "losing_team_1": ["FPL1", "FPL2"], "losing_team_2": ["FPM1", "FPM2"],
           "scores": score, "peak_scores": dict((n, 9000) for n in names),
           "presence": dict((n, 1.0) for n in names), "watch_s": 2400, "tracked_reads": 700,
           "places": {"win": 1, "lose1": 3, "lose2": 2}, "team_out_s": {"0": None, "1": 900.5, "2": 1500.0},
           "order_basis": "elimination"}
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload), content_type="application/json",
                              headers={"X-API-Key": "k"})
check("accepted", r.status_code in (200, 201), True)
c = sqlite3.connect(fa.DB_PATH)
places = dict(c.execute("SELECT mp.norm_name, mp.place FROM match_players mp JOIN matches m ON m.id = mp.match_row "
                        "WHERE m.match_id = 'fp-1'").fetchall())
check("each result carries its place", places, {N("FPW1"): 1, N("FPW2"): 1, N("FPL1"): 3, N("FPL2"): 3, N("FPM1"): 2, N("FPM2"): 2})
check("the match records how it knew", c.execute("SELECT order_basis, team_out_s FROM matches WHERE match_id='fp-1'").fetchone(),
      ("elimination", json.dumps({"0": None, "1": 900.5, "2": 1500.0})))
pts = dict(c.execute("SELECT norm_name, SUM(points) FROM clan_points GROUP BY norm_name").fetchall())
check("the clan's points: the winner 10, and the team that really came second", pts.get(N("FPW1")), 10)
check("team 2 finished second but has no clan member: nobody gets 2nd-place points", pts.get(N("FPL1")), None)
c.close()

print("\n--- the clan member who finished second is paid, whatever the scoreboard said ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET clan = 'TST' WHERE norm_name IN (?, ?)", (N("FPM1"), N("FPM2")))
cn.execute("UPDATE players SET clan = NULL WHERE norm_name IN (?, ?)", (N("FPL1"), N("FPL2")))
cn.commit()
cn.close()
payload2 = dict(payload, match_id="fp-2", sys_id=4243)
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload2), content_type="application/json",
                              headers={"X-API-Key": "k"})
c = sqlite3.connect(fa.DB_PATH)
pts = dict(c.execute("SELECT norm_name, SUM(points) FROM clan_points WHERE ref LIKE 'fp-2#%' GROUP BY norm_name").fetchall())
check("team 2 (recorded second) got 5 each", (pts.get(N("FPM1")), pts.get(N("FPM2"))), (5, 5))
check("team 1 (higher on the scoreboard, recorded third) got none", (pts.get(N("FPL1")), pts.get(N("FPL2"))), (None, None))
c.close()

print("\n--- a match with no order still works as before ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET clan = 'TST' WHERE norm_name IN (?, ?)", (N("FPL1"), N("FPL2")))
cn.execute("UPDATE players SET clan = NULL WHERE norm_name IN (?, ?)", (N("FPM1"), N("FPM2")))
cn.commit()
cn.close()
payload3 = dict(payload, match_id="fp-3", sys_id=4244)
for k in ("places", "team_out_s", "order_basis"):
    payload3.pop(k)
payload3["scores"] = dict(score, FPL2=500)          # 9500 against 9400: team 1 is ahead
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload3), content_type="application/json",
                              headers={"X-API-Key": "k"})
check("accepted", r.status_code in (200, 201), True)
c = sqlite3.connect(fa.DB_PATH)
check("results carry no place", c.execute("SELECT COUNT(*) FROM match_players mp JOIN matches m ON m.id = mp.match_row "
                                           "WHERE m.match_id='fp-3' AND mp.place IS NOT NULL").fetchone()[0], 0)
pts = dict(c.execute("SELECT norm_name, SUM(points) FROM clan_points WHERE ref LIKE 'fp-3#%' GROUP BY norm_name").fetchall())
check("the scoreboard guess is used (team 1 scored higher): 5 points", (pts.get(N("FPL1")), pts.get(N("FPL2"))), (5, 5))
c.close()

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
