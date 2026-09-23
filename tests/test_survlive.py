# -*- coding: utf-8 -*-
"""Live survival: one lobby at a time, with its field, read like a replay."""
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
TMP = tempfile.mkdtemp(prefix="survlive")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
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


cl = fa.app.test_client()
fa._load_api_keys = lambda: {"testkey"}          # the tracker's side of the wire
KEY = {"X-API-Key": "testkey"}

def freshen():
    """The watcher stamps its rows in the server's local time and the feed's
    window is SQLite's UTC `now`. On the server both are UTC; on this machine
    they are hours apart, so re-stamp after each push and test the feed rather
    than the clock."""
    cn = sqlite3.connect(fa.DB_PATH)
    cn.execute("UPDATE live_lobbies SET updated_at = datetime('now')")
    cn.commit()
    cn.close()


print("\n--- the watcher pushes a round in progress ---")
r = cl.post("/api/survival/lobbies", headers=KEY, json={"lobbies": [
    {"id": 101, "name": "Rocky", "region": "america", "age": 1500, "players": 9,
     "watching": True, "names": ["Alfa", "Bravo", "Charlie", "elo bot"],
     "elim": True, "elim_age": 300, "field": 8,
     "out": [["Delta", 40], ["Echo", 220], ["Foxtrot", 150], ["homi is watching", 90]]},
    {"id": 102, "name": "Quiet", "region": "europe", "age": 200, "players": 3,
     "watching": False},
]})
check("the push is accepted", (r.status_code, r.get_json()["count"]), (200, 2))
freshen()

d = cl.get("/api/survival/live").get_json()
check("both lobbies come back", len(d["lobbies"]), 2)
one = [l for l in d["lobbies"] if l["id"] == 101][0]
two = [l for l in d["lobbies"] if l["id"] == 102][0]
check("the watched one is first", d["lobbies"][0]["id"], 101)
check("it knows it is in the elimination", (one["elim"], one["elim_age"]), (True, 300))
check("the living are named", one["alive"], ["Alfa", "Bravo", "Charlie"])
check("the eliminated come back newest-first with their times",
      [(e["name"], e["at"]) for e in one["out"]], [("Echo", 220), ("Foxtrot", 150), ("Delta", 40)])
check("the watchers themselves are not players",
      ("elo bot" in one["alive"]) or any("homi" in e["name"] for e in one["out"]), False)
check("the field counts everyone in it", one["field"], 8)
check("and how many are left", one["left"], 3)
check("an unwatched lobby has no roster and can be checked into",
      (two["alive"], two["out"], two["can_checkin"], two["elim"]), ([], [], True, False))
check("no check-in on the watched one", one["can_checkin"], False)

print("\n--- an older watcher, sending only names, still works ---")
cl.post("/api/survival/lobbies", headers=KEY, json={"lobbies": [
    {"id": 103, "name": "Plain", "region": "asia", "age": 60, "players": 2,
     "watching": True, "names": ["Golf", "Hotel"]}]})
freshen()
d = cl.get("/api/survival/live").get_json()
old = d["lobbies"][0]
check("only the one push is live now", (len(d["lobbies"]), old["id"]), (1, 103))
check("names show, no elimination claimed", (old["alive"], old["elim"], old["out"]),
      (["Golf", "Hotel"], False, []))
check("the field falls back to who is there", (old["field"], old["left"]), (2, 2))

print("\n--- the page ---")
h = cl.get("/live").get_data(as_text=True)
check("the survival tab picks one lobby at a time",
      ('id="rlSurvPick"' in h) and ('id="rlSurvOne"' in h), True)
check("the old all-at-once list is gone", 'id="rlSurvList"' in h, False)
check("it reads the new feed", "/api/survival/live" in h, True)
check("it draws the field like the replay does",
      ('sv-row' in h) and ('sv-bar' in h) and ('still in' in h), True)
check("it says what it is not - there is no radar for survival",
      "shares no positions" in h, True)
check("and points at the replay when it ends", "/replays?mode=survival" in h, True)

print("\n--- who checked in is still nobody's business ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO checkins (sub, player, sys_id, created_at) VALUES (?,?,?,datetime('now'))",
           ("sub:someone", "Zulu", 103))
cn.commit()
cn.close()
body = json.dumps(cl.get("/api/survival/live").get_json())
check("the feed never says who checked in",
      ("sub:someone" in body) or ("Zulu" in body), False)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
