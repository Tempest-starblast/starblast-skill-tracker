# -*- coding: utf-8 -*-
"""A result waits for its replay, and reports the length it really ran."""
import io
import json
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
TMP = tempfile.mkdtemp(prefix="replaylink")
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
cl = fa.app.test_client()
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def utc(delta=0):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() + delta))


# The replays database the endpoint attaches.
rc = sqlite3.connect(fa.REPLAY_DB_PATH)
rc.execute("CREATE TABLE IF NOT EXISTS trueskill_replay (match_key TEXT PRIMARY KEY, "
           "sys_id INTEGER, at TEXT, region TEXT, first_ts REAL, data BLOB, name TEXT, "
           "players INTEGER, dur_s REAL, no_result INTEGER, reason TEXT)")
rc.commit()
rc.close()

cn = sqlite3.connect(fa.DB_PATH)
for t in ("matches", "match_players", "players"):
    cn.execute("DELETE FROM %s" % t)
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES ('A','A',1500,5,5)")
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES ('B','B',1500,5,5)")


def add_match(match_id, sysid, played_at, reads, played_s):
    # watch_s as game_end stores it since 9.73.1 - the scorer's own measure.
    cn.execute("INSERT INTO matches(match_id, sys_id, played_at, lobby_name, "
               "tracked_reads, region, announced, watch_s) VALUES (?,?,?,?,?,?,0,?)",
               (match_id, sysid, played_at, "Lobby %s" % sysid, reads, 'america', played_s))
    row = cn.execute("SELECT id FROM matches WHERE match_id = ?", (match_id,)).fetchone()[0]
    for nm, won, d in (("A", 1, 20.0), ("B", 0, -20.0)):
        cn.execute("INSERT INTO match_players(match_row,name,norm_name,won,delta,played_s) "
                   "VALUES (?,?,?,?,?,?)", (row, nm, nm, won, d, played_s))
    return row


# 1: just ended, no replay yet - the case that lost its link.
fresh = add_match("m-fresh", 91, utc(-30), 1307, 4200)
# 2: ended a while ago, still no replay - must not be held for ever.
old = add_match("m-old", 92, utc(-3600), 600, 1900)
# 3: just ended AND the replay is already stored.
withrep = add_match("m-rep", 93, utc(-30), 800, 2560)
cn.commit()
cn.close()

rc = sqlite3.connect(fa.REPLAY_DB_PATH)
rc.execute("INSERT INTO trueskill_replay(match_key, sys_id, at, region, first_ts, data) "
           "VALUES ('93:america:2:1', 93, ?, 'america', 1.0, x'00')", (utc(-30),))
rc.commit()
rc.close()


def feed():
    r = cl.get("/api/bot/matches/undelivered", headers=HDR)
    return {m["match_id"]: m for m in (r.get_json() or {}).get("matches") or []}


print("\n--- a match whose replay has not landed yet waits ---")
got = feed()
check("the fresh one is held back", "m-fresh" in got, False)
check("the one with a replay goes straight out", "m-rep" in got, True)
check("and it carries the link",
      (got.get("m-rep") or {}).get("replay_url", "").endswith("/replay/%d" % withrep), True)

print("\n--- but nothing is held for ever ---")
check("an older match with no replay is announced anyway", "m-old" in got, True)
check("with no link, honestly", (got.get("m-old") or {}).get("replay_url"), None)

print("\n--- and the replay arriving releases it ---")
rc = sqlite3.connect(fa.REPLAY_DB_PATH)
rc.execute("INSERT INTO trueskill_replay(match_key, sys_id, at, region, first_ts, data) "
           "VALUES ('91:america:2:1', 91, ?, 'america', 1.0, x'00')", (utc(-30),))
rc.commit()
rc.close()
got = feed()
check("the held match is offered now", "m-fresh" in got, True)
check("with its link", (got.get("m-fresh") or {}).get("replay_url", "").endswith(
    "/replay/%d" % fresh), True)

print("\n--- the length is the watch, not reads x 10 ---")
check("4200s of watch reads as 70 min", got["m-fresh"]["tracked_minutes"], 70)
check("not the 218 it used to claim",
      got["m-fresh"]["tracked_minutes"] == int(round(1307 * 10 / 60.0)), False)
check("2560s reads as 43 min", got["m-rep"]["tracked_minutes"], 43)

print("\n--- a row with no played_s falls back to the real cadence ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE match_players SET played_s = NULL WHERE match_row = ?", (old,))
cn.execute("UPDATE matches SET watch_s = NULL WHERE id = ?", (old,))    # from before 9.73.1
cn.commit()
cn.close()
got = feed()
check("600 reads at the measured cadence reads as %d min" % round(600 * fa.RAW_READ_SECONDS / 60.0),
      got["m-old"]["tracked_minutes"], int(round(600 * fa.RAW_READ_SECONDS / 60.0)))

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
