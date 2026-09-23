# -*- coding: utf-8 -*-
"""An archived replay is a record, not a recording: smaller, unplayable,
and still true about who played and how it finished."""
import io
import json
import os
import shutil
import sys
import tempfile
import warnings
import zlib

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="arch")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


# A replay shaped like a real one: 12s frames over 70 minutes, plus the
# three playback streams.
N = 350
frames = []
for i in range(N):
    t = round(i * 12.0, 1)
    frames.append([t, [["ALPHA", 100 * i, 0, 302], ["BETA", 90 * i, 1, 201]]])
doc = {
    "f": frames,
    "rd": [[[0, i % 100, i % 80]] * 12 for i in range(N)],
    "st": [[[3, 500, [255] * 12]] * 3 for i in range(N)],
    "wp": [[0.3, 0.4, 0.3] for _ in range(N)],
    "nm": {"9001": "ALPHA", "9002": "BETA"},
    "hues": [0, 120, 240], "seed": 4242, "gt0": 1.0, "mt0": 2.0,
    "stlay": [{"id": "d1"}], "bs": [1, 2, 3],
}
before = len(zlib.compress(json.dumps(doc).encode()))

small = fa.archive_replay_doc(doc)
after = len(zlib.compress(json.dumps(small).encode()))

print("\n--- what survives ---")
check("the score frames are kept", "f" in small, True)
check("the radar is gone", "rd" in small, False)
check("the station stream is gone", "st" in small, False)
check("the win probability is gone", "wp" in small, False)
check("it is flagged archived", small.get("archived"), 1)
check("who was who is kept", small.get("nm"), doc["nm"])
check("the lobby colours are kept", small.get("hues"), doc["hues"])

print("\n--- the record is still true ---")
check("the first frame is exact", small["f"][0], frames[0])
check("the last frame is exact", small["f"][-1], frames[-1])
check("so the closing scores are exact",
      small["f"][-1][1][0][1], frames[-1][1][0][1])
check("frames thinned to about one a minute",
      12 <= len(small["f"]) <= 75, True)
gaps = [small["f"][i + 1][0] - small["f"][i][0] for i in range(len(small["f"]) - 2)]
check("and no gap is shorter than a minute", all(g >= 60 for g in gaps), True)

print("\n--- and it is much smaller ---")
pct = 100.0 * after / before
print("      %d bytes -> %d bytes (%.0f%% of the original)" % (before, after, pct))
check("under a quarter of the size", pct < 25, True)

print("\n--- it survives odd input ---")
check("a bare frame list still archives",
      isinstance(fa.archive_replay_doc(frames), dict), True)
check("an empty document archives to nothing",
      fa.archive_replay_doc({"f": []}), None)
check("garbage archives to nothing", fa.archive_replay_doc({}), None)

print("\n--- the prune only touches what is old, and only once ---")
conn = fa.replay_db()
cols = [r[1] for r in conn.execute("PRAGMA table_info(trueskill_replay)")]
check("the archived column exists", "archived" in cols, True)
blob = zlib.compress(json.dumps(doc).encode())
conn.execute("INSERT INTO trueskill_replay(match_key, sys_id, at, region, first_ts, data) "
             "VALUES ('old:1', 1, datetime('now','-40 days'), 'america', 1.0, ?)", (blob,))
conn.execute("INSERT INTO trueskill_replay(match_key, sys_id, at, region, first_ts, data) "
             "VALUES ('new:1', 2, datetime('now','-2 days'), 'america', 1.0, ?)", (blob,))
conn.commit()
n = fa.prune_replays(conn, force=True)
check("one row archived", n, 1)
row = conn.execute("SELECT archived, LENGTH(data) FROM trueskill_replay "
                   "WHERE match_key='old:1'").fetchone()
check("the old one is flagged", row[0], 1)
check("and shrank", row[1] < len(blob), True)
row = conn.execute("SELECT archived, LENGTH(data) FROM trueskill_replay "
                   "WHERE match_key='new:1'").fetchone()
check("the recent one is untouched", (row[0] or 0, row[1]), (0, len(blob)))
check("running again does nothing", fa.prune_replays(conn, force=True), 0)
conn.close()

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
