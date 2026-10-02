# -*- coding: utf-8 -*-
"""One account, one result per match (9.81.2): two in-game names that both
resolve to one account are rated once, not twice."""
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
TMP = tempfile.mkdtemp(prefix="onceper")
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


cn = sqlite3.connect(fa.DB_PATH)
for n in ("ONCEW1", "ONCEW2", "ONCEL1", "VULCANX"):
    cn.execute("DELETE FROM players WHERE norm_name = ?", (N(n),))
    cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?,?,1500,20,20)", (n, N(n)))
cn.commit()
cn.close()
# Both "SHIPNINE" and "VULCANX" resolve to the VULCANX account.
real = fa.account_for_ingame_name
fa.account_for_ingame_name = lambda c, nm, sys_id=None: "VULCANX" if nm == "SHIPNINE" else real(c, nm, sys_id)
names = ["ONCEW1", "ONCEW2", "ONCEL1", "VULCANX", "SHIPNINE"]
payload = {"match_id": "once-1", "sys_id": 1368, "region": "america",
           "winning_team": ["ONCEW1", "ONCEW2"], "losing_team_1": ["ONCEL1"],
           "losing_team_2": ["VULCANX", "SHIPNINE"],
           "scores": dict((n, 9000) for n in names), "peak_scores": dict((n, 9000) for n in names),
           "presence": dict((n, 1.0) for n in names), "watch_s": 2400, "tracked_reads": 700}
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload),
                              content_type="application/json", headers={"X-API-Key": "k"})
check("accepted", r.status_code in (200, 201), True)
c = sqlite3.connect(fa.DB_PATH)
rows = c.execute("SELECT COUNT(*) FROM match_players mp JOIN matches m ON m.id = mp.match_row "
                 "WHERE m.match_id = 'once-1' AND mp.norm_name = ?", (N("VULCANX"),)).fetchone()[0]
check("the account has one result row", rows, 1)
check("and one loss", c.execute("SELECT losses FROM players WHERE norm_name = ?", (N("VULCANX"),)).fetchone()[0], 21)
c.close()
print("\n%d passed, %d failed" % (ok, fail))
fa.account_for_ingame_name = real
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
