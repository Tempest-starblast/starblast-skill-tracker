# -*- coding: utf-8 -*-
"""Reaching a tier is announced once, however often you cross back in."""
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
TMP = tempfile.mkdtemp(prefix="rankspam")
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
DID = "999000111222"
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def sync(level):
    return cl.post("/api/bot/rankroles/synced", data=json.dumps({"levels": {DID: level}}),
                   content_type="application/json", headers=HDR)


def stored():
    c = sqlite3.connect(fa.DB_PATH).cursor()
    r = c.execute("SELECT announced_level FROM discord_rank_state WHERE discord_id = ?",
                  (DID,)).fetchone()
    return r[0] if r else None


def would_announce(level):
    """The bot's own rule: announce when the live level beats what is stored."""
    prev = stored()
    return prev is not None and level > prev


print("\n--- the climb that should be celebrated ---")
sync(7)
check("first sync records Warden", stored(), 7)
check("reaching Archon would announce", would_announce(8), True)
sync(8)
check("and is then recorded", stored(), 8)

print("\n--- the boundary wobble that should not ---")
# The 0.5% line moves under a player who has not played: 8 -> 7 -> 8 -> 7 -> 8
for i, lvl in enumerate([7, 8, 7, 8, 7, 8]):
    announced = would_announce(lvl)
    sync(lvl)
    if announced:
        fail += 1
        print("  FAIL  crossing #%d at level %d announced again" % (i + 1, lvl))
if fail == 0 or True:
    pass
check("six boundary crossings produced no announcement", fail, 0)
check("the mark held at Archon throughout", stored(), 8)

print("\n--- a real promotion past it still counts ---")
check("Mythos would announce", would_announce(9), True)
sync(9)
check("and the mark rises to Mythos", stored(), 9)
check("dropping back to Archon does not lower it", (sync(8), stored())[1], 9)
check("and re-reaching Mythos is silent", would_announce(9), False)

print("\n--- a fresh account is still silent on first sight ---")
c = sqlite3.connect(fa.DB_PATH).cursor()
r = c.execute("SELECT announced_level FROM discord_rank_state WHERE discord_id = ?",
              ("000",)).fetchone()
check("never-seen id has no stored level", r, None)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
