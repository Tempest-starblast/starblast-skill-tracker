# -*- coding: utf-8 -*-
"""Whether a name has Protection on is only ever told to that name's owner.

Before this, the board drew a lock beside protected players and
GET /protection?name=<anyone> answered for any name with no sign-in - which
between them published the list of top players whose rating somebody else
playing under their name could still move."""
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
TMP = tempfile.mkdtemp(prefix="prot")
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


cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,strict_mode,clan) "
           "VALUES (?,?,?,?,?,?,?,?)",
           ("Topdog", N("Topdog"), 2400, 90, 10, "sub:top", 1, "L7"))
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,strict_mode,clan) "
           "VALUES (?,?,?,?,?,?,?,?)",
           ("Openguy", N("Openguy"), 2350, 88, 12, "sub:open", 0, "L7"))
cn.commit()
cn.close()

stranger = fa.app.test_client()
mine = fa.app.test_client()
with mine.session_transaction() as s:
    s["google_sub"] = "sub:top"

print("\n--- the lookup only answers for you ---")
d = stranger.get("/protection?name=Topdog").get_json()
check("a stranger is not told whether it is on", "enabled" in d, False)
check("and is told plainly that it is not theirs", d.get("owned"), False)
check("the name itself is still fine to confirm", d.get("name"), "Topdog")
d = stranger.get("/protection?name=Openguy").get_json()
check("nor for the one who has it OFF - which is the dangerous half",
      "enabled" in d, False)
d = mine.get("/protection?name=Topdog").get_json()
check("the owner is still told", (d.get("owned"), d.get("enabled")), (True, True))
check("a name nobody has is still a plain 404",
      stranger.get("/protection?name=Nobody At All").status_code, 404)

print("\n--- and nothing draws it any more ---")
for path in ("/", "/leaderboard"):
    h = stranger.get(path).get_data(as_text=True)
    check("no lock on %s" % path, "lockm" in h and "Protected - only matches" in h, False)
    check("   accounts still show their tick on %s" % path, "Has an account" in h, True)
h = stranger.get("/clan/L7").get_data(as_text=True)
check("no lock on a clan page", "Protected - only matches" in h, False)
check("and the legend no longer explains one", "means a protected rating" in h, False)

print("\n--- the payloads themselves carry nothing ---")
import json                                                     # noqa: E402
for path in ("/", "/clan/L7", "/player/Topdog"):
    h = stranger.get(path).get_data(as_text=True)
    check("%s says nothing about protection" % path,
          ('"protected"' in h) or ("protected: true" in h), False)

print("\n--- setting it is untouched ---")
r = mine.post("/protection", json={"name": "Topdog", "enabled": False})
check("the owner may still turn it off", r.status_code in (200, 400), True)
r = stranger.post("/protection", json={"name": "Topdog", "enabled": False})
check("a stranger still may not", r.status_code, 403)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
