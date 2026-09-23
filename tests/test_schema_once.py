# -*- coding: utf-8 -*-
"""The live feed is indexed, pruned, and its schema declared once.

Three things made the site slow, in descending order of blame:

1. rawlive kept every lobby it had ever seen - 4,453 rows over 29 days,
   11 MB - and had no index on `updated`. Every reader of the live feed
   asks for rows newer than 40-120 seconds, so each one scanned all of it
   to return six rows: 1.2 seconds, measured, three runs in a row. In
   rollback-journal mode that read lock blocks the raw-observer ingest
   arriving 1.4 times a second, so the queue backed up until pages doing
   no work at all took eight seconds.

2. rawlive_hist is pruned on every ingest by `updated`, and the only
   index was (sys_id, updated), which that query cannot use.

3. live_db() and replay_db() re-declared their whole schema on every
   call - 23 ms an ingest, ~11,000 calls an hour. Not the cause, but not
   free either.

(An earlier version of this file asserted that CREATE INDEX IF NOT EXISTS
blocks on an existing index. It does not; the probe that "proved" it was
naming an index that had never been created. The statement is merely
wasted work, which is reason enough to hoist it but not the bug.)

This test fails if any of the three comes back."""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import flask_app as fa                                          # noqa: E402

TMP = tempfile.mkdtemp(prefix="schema1")
fa.DB_PATH = os.path.join(TMP, "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


print("\n--- live_db() declares its schema once ---")
fa._LIVE_SCHEMA_READY = False
cn = fa.live_db()
check("first call builds the schema", fa._LIVE_SCHEMA_READY, True)
tables = set(r[0] for r in cn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"))
for t in ("live", "live_prev", "model", "shadow_model", "rawlive",
          "rawlive_hist", "asteroids"):
    check("  table %s exists" % t, t in tables, True)
idx = set(r[0] for r in cn.execute(
    "SELECT name FROM sqlite_master WHERE type='index'"))
check("  the prune index exists", "idx_rawlive_hist_updated" in idx, True)
cn.close()

# A later call must return without waiting on anything, whatever another
# connection is doing to the file.
holder = sqlite3.connect(fa.LIVE_DB_PATH, timeout=30)
holder.execute("BEGIN IMMEDIATE")
holder.execute("INSERT INTO rawlive (sys_id, updated, payload) VALUES (1, 1, '{}')")
t0 = time.perf_counter()
try:
    cn2 = fa.live_db()
    cn2.close()
    blocked = False
except sqlite3.OperationalError:
    blocked = True
elapsed = time.perf_counter() - t0
holder.execute("ROLLBACK")
holder.close()
check("a later live_db() does not wait on the write lock", blocked, False)
check("  and returns promptly (< 1 s)", elapsed < 1.0, True)

print("\n--- nothing reads the live feed with a table scan ---")
cn = fa.live_db()


def plan(sql, args=(0,)):
    return " ".join(str(r) for r in cn.execute("EXPLAIN QUERY PLAN " + sql, args))


# The live readers, verbatim from flask_app: rawlive_matches,
# asteroids_needed, people_playing, friends_playing.
p = plan("SELECT payload FROM rawlive WHERE updated > ?")
check("the live-feed read is a seek, not a scan", "SCAN rawlive" in p, False)
check("  and it uses the updated index", "idx_rawlive_updated" in p, True)
p = plan("SELECT sys_id, updated FROM rawlive WHERE updated > ? "
         "ORDER BY updated DESC")
check("the /live listing is indexed too", "SCAN rawlive" in p, False)
p = plan("DELETE FROM rawlive_hist WHERE updated < ?")
check("the ingest's hist prune is indexed", "idx_rawlive_hist_updated" in p, True)
p = plan("DELETE FROM rawlive WHERE updated < ?")
check("the rawlive prune is indexed", "idx_rawlive_updated" in p, True)
cn.close()

print("\n--- and rawlive is actually pruned ---")
check("a keep window exists", fa._RAWLIVE_KEEP_S, 86400)
check("  far longer than the 120 s anything reads",
      fa._RAWLIVE_KEEP_S > 120, True)
check("the prune runs on a timer, not every ingest",
      fa._RAWLIVE_PRUNE_EVERY >= 60.0, True)
check("the ingest is what prunes it",
      "DELETE FROM rawlive WHERE updated < ?"
      in io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read(),
      True)

cn = fa.live_db()
now = time.time()
cn.execute("DELETE FROM rawlive")
for i in range(40):                                # one lobby per hour back
    cn.execute("INSERT INTO rawlive (sys_id, updated, payload) VALUES (?,?,?)",
               (i, now - (i * 3600), '{"x":1}'))
cn.commit()
before = cn.execute("SELECT COUNT(*) FROM rawlive").fetchone()[0]
cn.execute("DELETE FROM rawlive WHERE updated < ?", (now - fa._RAWLIVE_KEEP_S,))
after = cn.execute("SELECT COUNT(*) FROM rawlive").fetchone()[0]
cn.commit()
check("40 lobbies spanning 40 hours went in", before, 40)
# Hours 0 through 24 inclusive are within a day of now: 25 rows.
check("  and only the last day survives", after, 25)
cn.close()

print("\n--- replay_db() declares its schema once too ---")
fa._TSR_MIGRATED = False
fa._REPLAY_INDEXES_READY = False
rc = fa.replay_db()
check("first call migrates", fa._TSR_MIGRATED, True)
check("  and builds the listing indexes", fa._REPLAY_INDEXES_READY, True)
rc.close()
holder = sqlite3.connect(fa.REPLAY_DB_PATH, timeout=30)
holder.execute("BEGIN IMMEDIATE")
holder.execute("INSERT INTO trueskill_replay (match_key) VALUES ('x')")
try:
    rc2 = fa.replay_db()
    rc2.close()
    blocked = False
except sqlite3.OperationalError:
    blocked = True
holder.execute("ROLLBACK")
holder.close()
check("a later replay_db() does not wait on the write lock", blocked, False)

print("\n--- and the source keeps the guards ---")
src = io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read()
check("live_db checks _LIVE_SCHEMA_READY", "if _LIVE_SCHEMA_READY:" in src, True)
check("_ensure_replay_indexes checks its flag",
      "if _REPLAY_INDEXES_READY:" in src, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
