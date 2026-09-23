# -*- coding: utf-8 -*-
"""Batch A of the 23 Sep suggestions, each pinned.

  #2  the Odyssey: 150,000, on sale only to Mythos, handed to nobody,
      never on the featured strip
  #4  claiming an achievement animates the gems into the balance
  #5  search as you type, from the whole board
  #6  a worn hull is drawn in its own colour - the shop's
  #7b an event every eight hours: three a day at 00:00, 08:00, 16:00 UTC
  #7c the next event on the home page, read-only
  #10 five on the featured strip

Where a check reads a template's source it is because the behaviour is
in JavaScript the test cannot run; the check is that the wiring is still
there, not that the browser does the right thing with it."""
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
import ranks                                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="sugA")
fa.DB_PATH = os.path.join(TMP, "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
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


def src(rel):
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


cat = {i["code"]: i for i in fa.ship_catalog()}

print("\n--- #2 the Odyssey ---")
check("costs 150,000", fa.SHIP_SPECIAL_PRICE[701], 150000)
check("  and the catalogue agrees", cat[701]["price"], 150000)
check("on sale only to Mythos", fa.SHIP_BUY_LEVEL[701], ranks.MYTHOS_LEVEL)
check("  catalogue buy_level is Mythos", cat[701]["buy_level"], ranks.MYTHOS_LEVEL)
check("handed to no tier", 701 in fa.SHIP_RANK_UNLOCK, False)
check("  so it is not earn-only", cat[701]["earn_only_gate"], False)
check("  and still the mythic", cat[701]["mythic"], True)
check("still the dearest thing in the shop",
      cat[701]["price"], max(i["price"] for i in cat.values()))
seen_mythic = False
for d in range(90):
    day = time.strftime("%Y-%m-%d", time.gmtime(time.time() + d * 86400))
    out, _ = fa.featured_today(day)
    if ("ship", 701) in out:
        seen_mythic = True
check("never on the featured strip (90 days checked)", seen_mythic, False)
check("the shop says how to unlock it",
      "Finish a day at number one to unlock it" in src("templates/shop.html"), True)

print("\n--- #10 five featured ---")
check("FEATURED_COUNT is 5", fa.FEATURED_COUNT, 5)
out, _ = fa.featured_today("2026-09-23")
check("  and a day really has five", len(out), 5)
check("laid out five across when there is room",
      "repeat(5,1fr)" in src("templates/shop.html"), True)

print("\n--- #7b every eight hours ---")
check("EVENT_EVERY_H is 8", fa.EVENT_EVERY_H, 8)
check("three a day", len(fa.EVENT_HOURS), 3)
check("  at 00:00, 08:00 and 16:00 UTC - eight divides the day, nothing drifts",
      tuple(fa.EVENT_HOURS), (0, 8, 16))
slot = fa.event_slot(1790000000.0, 0)
check("a slot lands on one of those hours",
      int(slot[11:13]) in fa.EVENT_HOURS and slot.endswith(":00:00"), True)

print("\n--- #6 a hull in its own colour ---")
for code in (101, 202, 406, 603, 702):
    check("worn %s carries the shop's colour %s" % (code, cat[code]["color"]),
          fa.worn_emblem("X", {"X": code}, True)[1], cat[code]["color"])
check("the mythic keeps its crimson",
      fa.worn_emblem("X", {"X": 701}, True), (701, fa.MYTHIC_COLOR, True))
check("an unknown code falls back to grey rather than crashing",
      fa.ship_color(9999), "#8b949e")
check("the profile no longer claims the colour is the tier's",
      "The colour of the emblem is their tier" in src("templates/player.html"), False)

print("\n--- #5 search as you type ---")
idx = src("templates/index.html")
check("the box asks the server while typing", "/api/players/search?q=" in idx, True)
check("  debounced", "setTimeout" in idx.split("function suggest")[1].split("function esc")[0], True)
check("  results drop under the box", 'id="qdd"' in idx, True)
check("  a stale reply is ignored", "if(seq !== _qseq) return;" in idx, True)
check("  and Enter still searches the whole board", "Search all" in idx, True)
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("DELETE FROM players WHERE norm_name IN ('QUIXOTICPILOT','QUIXOTICMINER')")
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
          ("Quixotic Pilot", "QUIXOTICPILOT", 1300.0, 9, 3))
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
          ("Quixotic Miner", "QUIXOTICMINER", 1100.0, 2, 5))
cn.commit()
cn.close()
fa._SEARCH_INDEX["rows"] = []
fa._SEARCH_INDEX["at"] = 0.0
with fa.app.test_client() as tc:
    r = tc.get("/api/players/search?q=quixotic").get_json()
names = [p["name"] for p in r["players"]]
check("the endpoint finds both from the whole board", set(names), {"Quixotic Pilot", "Quixotic Miner"})
check("  better player first", names[0], "Quixotic Pilot")
check("  with rating and games played",
      all("elo" in p and "played" in p for p in r["players"]), True)

print("\n--- #7c the next event on the home page ---")
pk = fa.event_peek(None)
check("event_peek says something", isinstance(pk, dict), True)
if pk:
    check("  a kind", pk["kind"] in fa.EVENT_KINDS, True)
    check("  a phase", pk["phase"] in ("later", "signup", "go", "join", "over"), True)
    check("  seconds until it starts", isinstance(pk["in_s"], int), True)
    check("  the quorum for that kind", pk["quorum"], fa.EVENT_QUORUM[pk["kind"]])
    check("  nobody signed up on a fresh database", pk["signed"], 0)
cn = sqlite3.connect(fa.DB_PATH)
before = cn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
fa.event_peek(None)
after = cn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
cn.close()
check("peeking never creates an event row", after, before)
was = fa.GEMS_PUBLIC
fa.GEMS_PUBLIC = True
with fa.app.test_client() as tc:
    h = tc.get("/").get_data(as_text=True)
check("the strip is on the home page when gems are public", 'id="evstrip"' in h, True)
check("  it names the kind", ("Team event" in h) or ("Survival event" in h), True)
check("  and links to the events page", 'href="/events"' in h, True)
fa.GEMS_PUBLIC = False
with fa.app.test_client() as tc:
    h = tc.get("/").get_data(as_text=True)
check("and not while the economy is unreleased", 'id="evstrip"' in h, False)
# And a signed-in player's own front page - which is what bare "/" becomes
# once gems are public - carries it too.
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players WHERE google_sub = 'test:home:1'")
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) "
           "VALUES (?,?,?,?,?,?)", ("Homebody", "HOMEBODY", 1050.0, 3, 2, "test:home:1"))
cn.commit()
cn.close()
fa.GEMS_PUBLIC = True
with fa.app.test_client() as tc:
    with tc.session_transaction() as sess:
        sess["google_sub"] = "test:home:1"
    h = tc.get("/").get_data(as_text=True)
check("a signed-in player's own home page carries it too",
      "Homebody" in h and 'id="evstrip"' in h, True)
check("  and that page is the home page, not the board", "<h2>Achievements</h2>" in h, True)
fa.GEMS_PUBLIC = was

print("\n--- #4 the claim animation ---")
ach = src("templates/achievements.html")
check("the page has the celebration", "function celebrate(" in ach, True)
check("  it flies to the balance chip", "getElementById('gchip')" in ach, True)
check("  the balance counts up", "requestAnimationFrame(step)" in ach, True)
check("  reduced motion is honoured", "prefers-reduced-motion" in ach, True)
check("  the reload waits for it", "setTimeout(function(){ location.reload(); }, wait)" in ach, True)
fsrc = src("flask_app.py")
claim = fsrc[fsrc.index("@app.route('/achievements/claim'"):][:4000]
check("the claim reply carries what was paid", '"gems": total' in claim, True)
check("  and the new balance", '"balance": balance' in claim, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
