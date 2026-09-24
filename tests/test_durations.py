# -*- coding: utf-8 -*-
"""Match lengths come from the watch the scorer measured (9.73.0).

The Replays list showed Achernaluli #8848 as 417 minutes; it ran 136. It
was computing tracked_reads * 10 - the retired browser tracker's cadence -
while the raw observer reads every ~3.3 s. The replay page did the same,
and used the inflated figure to call full recordings partial.

A match here is written the way the scorer writes one: 2,503 reads and a
watch of 8,189 s shared out as played_s. Every surface must say ~136 min."""
import io
import os
import re
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

import flask_app as fa                                          # noqa: E402

TMP = tempfile.mkdtemp(prefix="dur")
fa.DB_PATH = os.path.join(TMP, "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.replay_db().close()          # the Replays list reads this schema
fa.app.config["TESTING"] = True
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


READS, WATCH = 2503, 8189                   # Achernaluli #8848, 23 Sep
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO matches (match_id, sys_id, region, played_at, lobby_name, tracked_reads, watch_s) "
          "VALUES (?,?,?,datetime('now'),?,?,?)", ("dur-test-8848", 998848, "europe", "Achernaluli", READS, WATCH))
mid = c.lastrowid
for i, share in enumerate((0.88, 0.842, 0.404)):          # nobody there start to finish
    c.execute("INSERT INTO match_players (match_row, name, norm_name, won, delta, score, played_s) "
              "VALUES (?,?,?,?,?,?,?)", (mid, "DURP%d" % i, "DURP%d" % i, 1, 10.0, 5000,
                                         int(round(WATCH * share))))
c.execute("INSERT INTO matches (match_id, sys_id, region, played_at, lobby_name, tracked_reads) "
          "VALUES (?,?,?,datetime('now','-1 minute'),?,?)", ("dur-test-old", 998849, "europe", "Oldmatch", 1000))
old = c.lastrowid
c.execute("INSERT INTO match_players (match_row, name, norm_name, won, delta, score) "
          "VALUES (?,?,?,?,?,?)", (old, "DUROLD", "DUROLD", 1, 10.0, 5000))
# The Replays list only shows matches that have a replay stored.
for row in (mid, old):
    c.execute("INSERT INTO match_replays (match_row, data, created_at) VALUES (?,?,datetime('now'))",
              (row, None))
cn.commit()

print("\n--- the helper ---")
check("a scored match is its measured watch", fa.match_watch_seconds(c, mid, READS), WATCH)
check("  about 136 minutes", round(fa.match_watch_seconds(c, mid, READS) / 60.0), 136)
check("  even though no rated player was there for all of it (9.73.0 said 120)",
      round(fa.match_watch_seconds(c, mid, READS) / 60.0) != 120, True)
check("a match from before watch_s was kept falls back to reads x RAW_READ_SECONDS",
      fa.match_watch_seconds(c, old, 1000), int(1000 * fa.RAW_READ_SECONDS))
check("never reads x 10", fa.match_watch_seconds(c, mid, READS) != READS * 10, True)
cn.close()

print("\n--- the Replays list ---")
with fa.app.test_client() as tc:
    h = tc.get("/replays").get_data(as_text=True)
row = h[h.find("Achernaluli"):][:1500]
m = re.search(r"(\d+) min", row)
check("the list shows the match", bool(m), True)
check("  at 136 min, not 417", int(m.group(1)) if m else None, 136)
row2 = h[h.find("Oldmatch"):][:1500]
m2 = re.search(r"(\d+) min", row2)
check("an old match uses the fallback cadence",
      int(m2.group(1)) if m2 else None, int(round(1000 * fa.RAW_READ_SECONDS / 60.0)))

print("\n--- the replay page ---")
# Most matches have the radar replay but no frozen score snapshot, so the
# page's own match is written without a match_replays row.
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO matches (match_id, sys_id, region, played_at, lobby_name, tracked_reads, watch_s) "
          "VALUES (?,?,?,datetime('now','-2 minutes'),?,?,?)", ("dur-test-page", 998850, "europe", "Pagematch", READS, WATCH))
page = c.lastrowid
c.execute("INSERT INTO match_players (match_row, name, norm_name, won, delta, score, played_s) "
          "VALUES (?,?,?,?,?,?,?)", (page, "DURPG", "DURPG", 1, 10.0, 5000, WATCH))
cn.commit()
cn.close()
with fa.app.test_client() as tc:
    d = tc.get("/api/replay/%d" % page).get_json(silent=True) or {}
check("tracked_seconds is the measured watch", d.get("tracked_seconds"), WATCH)
check("  so a full recording is not called partial (it was %d s)" % (READS * 10),
      d.get("tracked_seconds") != READS * 10, True)

print("\n--- game_end keeps the watch the scorer sends ---")
import json                                                     # noqa: E402
fa._load_api_keys = lambda: {"test-key"}
payload = {"match_id": "dur-test-ge", "sys_id": 998851, "region": "europe",
           "winning_team": ["GEA", "GEB"], "losing_team_1": ["GEC", "GED"], "losing_team_2": [],
           "scores": {"GEA": 9000, "GEB": 8000, "GEC": 7000, "GED": 6000},
           "presence": {"GEA": 0.9, "GEB": 0.9, "GEC": 0.9, "GED": 0.9},
           "watch_s": WATCH, "tracked_reads": READS}
with fa.app.test_client() as tc:
    tc.post("/api/game_end", data=json.dumps(payload), content_type="application/json",
            headers={"X-API-Key": "test-key"})
cn = sqlite3.connect(fa.DB_PATH)
got = cn.execute("SELECT watch_s FROM matches WHERE match_id = 'dur-test-ge'").fetchone()
cn.close()
check("the stored watch is the scorer's", got[0] if got else None, WATCH)

print("\n--- nothing multiplies reads by ten any more ---")
src = io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read()
check("no 'tracked_reads, 0) * 10'", "tracked_reads, 0) * 10" in src, False)
check("no 'm_treads or 0) * 10'", "m_treads or 0) * 10" in src, False)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
