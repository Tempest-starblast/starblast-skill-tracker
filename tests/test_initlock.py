# -*- coding: utf-8 -*-
"""The site must load when players.db is locked at start-up (9.81.3).

7 Oct 2026: init_db() raised 'database is locked' at import, the app never
loaded, and the in-app lock self-heal never got to run - 35 hours down."""
import io
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
TMP = tempfile.mkdtemp(prefix="initlock")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


real = fa.init_db
calls = []


def locked():
    calls.append(1)
    raise sqlite3.OperationalError("database is locked")


fa.init_db = locked
fa._DB_READY[0] = False
try:
    r = fa.ensure_db_ready(2, pause=0)
    check("a locked start-up does not raise", r, False)
except sqlite3.OperationalError:
    check("a locked start-up does not raise", "raised", False)
check("it tried the number of times asked", len(calls), 2)
check("and is not marked ready", fa._DB_READY[0], False)

# A request retries the schema check, but not on every request.
calls.clear()
fa._DB_INIT_TRY[0] = fa.time.time()
fa.app.config["TESTING"] = True
fa.app.test_client().get("/robots.txt")
check("a request inside the retry window does not retry", len(calls), 0)
fa._DB_INIT_TRY[0] = fa.time.time() - fa.DB_INIT_RETRY_S - 1
fa.app.test_client().get("/robots.txt")
check("a request after the window retries once", len(calls), 1)

# When the lock clears, the next retry goes through and sticks.
fa.init_db = real
fa._DB_INIT_TRY[0] = 0
fa.app.test_client().get("/robots.txt")
check("the lock clears and the app is marked ready", fa._DB_READY[0], True)

# Anything that is not a lock is still a real error.
fa._DB_READY[0] = False


def broken():
    raise sqlite3.OperationalError("no such table: nope")


fa.init_db = broken
try:
    fa.ensure_db_ready(1, pause=0)
    check("a non-lock error still raises", "silent", "raised")
except sqlite3.OperationalError:
    check("a non-lock error still raises", "raised", "raised")
fa.init_db = real
fa._DB_READY[0] = True

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
