# -*- coding: utf-8 -*-
"""A match cut at a flood: the side that was ahead is paid, the sides the
swarm landed on take nothing."""
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
TMP = tempfile.mkdtemp(prefix="flood")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa._load_api_keys = lambda: {"testkey"}
KEY = {"X-API-Key": "testkey", "Content-Type": "application/json"}
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


WIN = ["Wina", "Winb"]
L1 = ["Lonea", "Loneb"]
L2 = ["Ltwoa", "Ltwob"]
ALL = WIN + L1 + L2


def seed():
    cn = sqlite3.connect(fa.DB_PATH)
    cn.execute("DELETE FROM players")
    cn.execute("DELETE FROM matches")
    cn.execute("DELETE FROM match_players")
    for n in ALL:
        cn.execute("INSERT INTO players(name, norm_name, elo, wins, losses) "
                   "VALUES (?,?,?,?,?)", (n, N(n), 1400, 30, 30))
    cn.commit()
    cn.close()


def elos():
    cn = sqlite3.connect(fa.DB_PATH)
    r = {n: cn.execute("SELECT elo, wins, losses FROM players WHERE norm_name = ?",
                       (N(n),)).fetchone() for n in ALL}
    cn.close()
    return r


def send(flood_cut=None, mid="m1"):
    body = {"match_id": mid, "sys_id": 4242, "region": "america",
            "lobby_name": "Testaria", "tracked_reads": 40,
            "winning_team": WIN, "losing_team_1": L1, "losing_team_2": L2,
            "scores": {n: 9000 for n in ALL}, "peak_scores": {n: 9000 for n in ALL}}
    if flood_cut:
        body["flood_cut"] = flood_cut
    return fa.app.test_client().post("/api/game_end", headers=KEY, data=json.dumps(body))


print("\n--- an ordinary match, for the shape of it ---")
seed()
before = elos()
r = send()
check("it is accepted", r.status_code in (200, 201), True)
after = elos()
won = [n for n in ALL if after[n][0] > before[n][0]]
lost = [n for n in ALL if after[n][0] < before[n][0]]
check("the winners gain", sorted(won), sorted(WIN))
check("and both losing sides pay", sorted(lost), sorted(L1 + L2))

print("\n--- the same match, cut at a flood ---")
seed()
before = elos()
r = send({"at": "2026-09-20 04:00:00", "name": "SWARM", "ships": 62, "team": 3,
          "impact": ["station core lost", "real players down by a third"]}, mid="m2")
check("it is accepted too", r.status_code in (200, 201), True)
after = elos()
check("the side that was ahead is still paid",
      [n for n in WIN if after[n][0] > before[n][0]], WIN)
check("neither swarmed side loses a point",
      [n for n in L1 + L2 if after[n][0] != before[n][0]], [])
check("and neither takes a recorded loss",
      [n for n in L1 + L2 if after[n][2] != before[n][2]], [])
check("the winners' wins still count",
      [n for n in WIN if after[n][1] == before[n][1] + 1], WIN)

print("\n--- and it is answerable afterwards ---")
cn = sqlite3.connect(fa.DB_PATH)
held = cn.execute("SELECT name, reason FROM held_results WHERE reason = 'flood-cut'").fetchall()
cn.close()
check("every excused player is written down with the reason",
      sorted(n for n, _ in held), sorted(L1 + L2))
h = fa.app.test_client()
with h.session_transaction() as s:
    pass
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET google_sub = 'sub:lone' WHERE norm_name = ?", (N("Lonea"),))
cn.commit()
cn.close()
with h.session_transaction() as s:
    s["google_sub"] = "sub:lone"
body = h.get("/api/my/held").get_data(as_text=True)
check("and the player is told why in words", "swarmed by a flood" in body, True)

print("\n--- the match itself still records who was there ---")
cn = sqlite3.connect(fa.DB_PATH)
row = cn.execute("SELECT id, flood FROM matches WHERE match_id = 'm2'").fetchone()
check("the cut is kept on the match", "flood_cut" in (row[1] or ""), True)
ps = cn.execute("SELECT name, won, delta FROM match_players WHERE match_row = ?",
                (row[0],)).fetchall()
cn.close()
check("with the winners rated", sorted(n for n, w, d in ps if w), sorted(WIN))
check("and nobody rated on the swarmed sides", [n for n, w, d in ps if not w], [])

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
