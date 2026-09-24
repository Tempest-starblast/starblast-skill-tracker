# -*- coding: utf-8 -*-
"""A result set aside because two ships flew one name is written down -
for an account, and only for an account."""
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
TMP = tempfile.mkdtemp(prefix="ambiglog")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
# game_end is key-gated; the test supplies one rather than weakening the gate.
fa._load_api_keys = lambda: {"test-key"}
HDR = {"X-API-Key": "test-key"}
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


WIN = ["WINNER%d" % i for i in range(8)]
LOSE = ["LOSER%d" % i for i in range(8)]
# DODGER owns an account; DRIFTER is an unregistered stranger. Both are
# ambiguous in this match, on the losing side.
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM held_results")
for nm in WIN + LOSE:
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES (?,?,1500,10,10)",
               (nm, N(nm)))
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub) "
           "VALUES ('DODGER',?,1600,30,10,'sub:dodger')", (N("DODGER"),))
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) "
           "VALUES ('DRIFTER',?,1500,5,5)", (N("DRIFTER"),))
cn.commit()
cn.close()

losers = LOSE + ["DODGER", "DRIFTER"]
payload = {
    "match_id": "test-ambig-1",
    "sys_id": 4242,
    "region": "america",
    "winning_team": WIN,
    "losing_team_1": losers,
    "losing_team_2": [],
    "scores": dict([(n, 9000) for n in WIN] + [(n, 7000) for n in losers]),
    "presence": dict((n, 1.0) for n in WIN + losers),
    "watch_s": 2400,
    "tracked_reads": 700,
    # the scorer's verdict: both of these names were on two ships at once
    "ambiguous": ["DODGER", "DRIFTER"],
}
cl = fa.app.test_client()
r = cl.post("/api/game_end", data=json.dumps(payload),
            content_type="application/json", headers=HDR)
if r.status_code not in (200, 201):
    print("  (body: %s)" % r.get_data(as_text=True)[:200])
print("\n--- the post landed ---")
check("game_end accepted the match", r.status_code in (200, 201), True)

c = sqlite3.connect(fa.DB_PATH).cursor()
rows = c.execute("SELECT name, norm_name, won, reason FROM held_results "
                 "WHERE reason = 'duplicate-name'").fetchall()
names = {r[0] for r in rows}

print("\n--- what got written down ---")
check("the account's set-aside result is on record", "DODGER" in names, True)
check("the stranger sharing a nickname is not", "DRIFTER" in names, False)
check("exactly one row, not one per read", len(rows), 1)
if rows:
    check("filed as a loss, which is what it was", rows[0][2], 0)
    check("with the reason attached", rows[0][3], "duplicate-name")

print("\n--- and nothing was rated ---")
elo = c.execute("SELECT elo, wins, losses FROM players WHERE norm_name = ?",
                (N("DODGER"),)).fetchone()
check("DODGER's rating is untouched", round(elo[0], 1), 1600.0)
check("and no loss was added", (elo[1], elo[2]), (30, 10))
w = c.execute("SELECT elo FROM players WHERE norm_name = ?", (N("WINNER0"),)).fetchone()
check("the real winners still got rated", w[0] > 1500, True)

print("\n--- the player is told why, in words ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET google_sub = 'sub:dodger' WHERE norm_name = ?", (N("DODGER"),))
cn.commit()
cn.close()
with cl.session_transaction() as sess:
    sess['user'] = 'sub:dodger'
    sess['google_sub'] = 'sub:dodger'
h = cl.get("/api/my/held")
body = h.get_data(as_text=True)
check("the held endpoint answers", h.status_code, 200)
check("and explains it in words, not just the reason code",
      "there is no telling which of the two earned it" in body, True)   # wording since 9.76.0
check("the generic fallback is NOT what they get",
      "set aside for review" in body, False)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
