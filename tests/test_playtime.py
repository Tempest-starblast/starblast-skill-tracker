# -*- coding: utf-8 -*-
"""Rated playtime: stored from the watch, added up honestly, shown once."""
import io
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
TMP = tempfile.mkdtemp(prefix="playtime")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
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


print("\n--- the column exists on a board that predates it ---")
cn = sqlite3.connect(fa.DB_PATH)
cols = [r[1] for r in cn.execute("PRAGMA table_info(match_players)")]
check("match_players has played_s", "played_s" in cols, True)

print("\n--- how long it reads ---")
for secs, want in ((0, "-"), (None, "-"), (30, "under a minute"), (2700, "45m"),
                   (3600, "1h"), (45000, "12h 30m")):
    check("%s reads as %s" % (secs, want), fa.pretty_hours(secs), want)

print("\n--- adding it up ---")
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM matches")
cn.execute("DELETE FROM match_players")
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES ('GRINDER',?,1700,60,20)",
           (N("GRINDER"),))
rows = [
    # (days ago, seconds, voided)
    (1, 3600, 0),
    (3, 1800, 0),
    (20, 7200, 0),          # outside the fortnight
    (2, 9999, 1),           # voided - counts for nothing
    (2, None, 0),           # an old result, never timed
]
for i, (ago, secs, void) in enumerate(rows):
    cn.execute("INSERT INTO matches(match_id, sys_id, played_at, voided) "
               "VALUES (?, 1, datetime('now', ?), ?)",
               ("m%d" % i, "-%d days" % ago, void))
    mr = cn.execute("SELECT id FROM matches WHERE match_id = ?", ("m%d" % i,)).fetchone()[0]
    cn.execute("INSERT INTO match_players(match_row,name,norm_name,won,delta,played_s) "
               "VALUES (?,'GRINDER',?,1,10,?)", (mr, N("GRINDER"), secs))
cn.commit()
cn.close()
c = sqlite3.connect(fa.DB_PATH).cursor()
check("all time is 1h + 30m + 2h, and nothing else",
      fa.played_seconds(c, N("GRINDER")), 3600 + 1800 + 7200)
check("the fortnight drops the 20-day-old match",
      fa.played_seconds(c, N("GRINDER"), days=14), 3600 + 1800)
check("a voided match is worth no time at all",
      fa.played_seconds(c, N("GRINDER")) == 3600 + 1800 + 7200 + 9999, False)
check("somebody with no rated matches has no playtime",
      fa.played_seconds(c, N("NOBODY")), 0)

print("\n--- it reaches the profile, and only when there is some ---")
h = fa.app.test_client().get("/player/GRINDER").get_data(as_text=True)
check("the career total is on the card", "3h 30m" in h, True)
check("so is the fortnight, labelled", "1h 30m / 2w" in h, True)
check("and the stat is called Playtime", "Playtime" in h, True)
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES ('FRESH',?,1500,1,1)",
           (N("FRESH"),))
cn.commit()
cn.close()
h2 = fa.app.test_client().get("/player/FRESH").get_data(as_text=True)
check("a player with no timed matches is shown no playtime stat",
      "Playtime" in h2, False)

print("\n--- and the hours pay ---")
c = sqlite3.connect(fa.DB_PATH).cursor()
keys = [a["key"] for a in fa.gem_achievement_catalog()]
for k in ("hours-10", "hours-50", "hours-100", "hours-500"):
    check("%s is in the catalogue" % k, k in keys, True)
st = {a["key"]: a for a in fa.ach_status(c, N("GRINDER"))}
check("3.5 hours is 3 of the 10 needed", (st["hours-10"]["have"], st["hours-10"]["need"]), (3, 10))
check("and not unlocked", st["hours-10"]["unlocked"], False)
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE match_players SET played_s = 40000 WHERE norm_name = ? AND played_s IS NOT NULL",
           (N("GRINDER"),))
cn.commit()
cn.close()
c = sqlite3.connect(fa.DB_PATH).cursor()
st = {a["key"]: a for a in fa.ach_status(c, N("GRINDER"))}
check("33 hours unlocks the ten-hour one", st["hours-10"]["unlocked"], True)
check("but not the fifty-hour one", st["hours-50"]["unlocked"], False)
check("the hours milestones sit with the other milestones",
      st["hours-100"]["group"], "Milestones")

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
