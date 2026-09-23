# -*- coding: utf-8 -*-
"""Six objectives a day out of a measured catalogue: three easy, two medium,
one hard, rotating, claimed by hand, and paid once per day (9.48.0)."""
import collections
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="obj")
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


N = fa.normalize_name
O = fa.objectives
NOW = time.time()
TODAY = time.strftime("%Y-%m-%d", time.gmtime(NOW))

cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES ('AAA','sub:me','2026-09-01 00:00:00')")
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) "
          "VALUES (?,?,?,?,?,?,?)", ("Me", N("Me"), 1500, 30, 20, "sub:me", "AAA"))
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, clan) VALUES (?,?,?,?,?,?)",
          ("Mate", N("Mate"), 1400, 10, 10, "AAA"))
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
          ("Rival", N("Rival"), 1400, 10, 10))

mid = [0]


def match(at, region, rows):
    """rows = [(name, won, delta, score, ship, deaths, team)]"""
    mid[0] += 1
    c.execute("INSERT INTO matches(match_id, sys_id, played_at, region) VALUES (?,?,?,?)",
              ("o%d" % mid[0], mid[0], at, region))
    row = c.lastrowid
    for nm, won, delta, score, ship, deaths, team in rows:
        c.execute("INSERT INTO match_players(match_row, name, norm_name, won, delta, score, "
                  "ship, deaths, team) VALUES (?,?,?,?,?,?,?,?,?)",
                  (row, nm, N(nm), 1 if won else 0, delta, score, ship, deaths, team))


# a day: two wins on a tier 7 with a clanmate, then a loss, then a comeback win
match("%s 03:00:00" % TODAY, "europe",
      [("Me", 1, 22.0, 9000, 702, 0, "1"), ("Mate", 1, 12.0, 4000, 601, 2, "1"),
       ("Rival", 0, -12.0, 900, 404, 7, "2")])
match("%s 03:40:00" % TODAY, "europe",
      [("Me", 1, 18.0, 7000, 702, 1, "1"), ("Rival", 0, -11.0, 800, 404, 6, "2")])
match("%s 13:00:00" % TODAY, "america",
      [("Me", 0, -9.0, 6000, 605, 5, "2"), ("Rival", 1, 9.0, 3000, 404, 1, "1")])
match("%s 13:30:00" % TODAY, "america",
      [("Me", 1, 11.0, 5000, 605, 2, "1"), ("Rival", 0, -11.0, 700, 404, 8, "2")])
c.execute("INSERT INTO survival_round_players(round_key, norm_name, name, place, field, delta, "
          "ended_at) VALUES (?,?,?,?,?,?,?)",
          ("r1", N("Me"), "Me", 2, 22, 8.0, "%s 22:00:00" % TODAY))
cn.commit()
cn.close()

me = fa.app.test_client()
with me.session_transaction() as s:
    s["google_sub"] = "sub:me"
    s["preview"] = True


def facts():
    cn = sqlite3.connect(fa.DB_PATH)
    f = fa._obj_day_facts(cn.cursor(), N("Me"))
    cn.close()
    return f


print("\n--- the catalogue is only what the board has actually seen done ---")
check("hundreds of objectives", len(O.CATALOGUE) > 300, True)
check("every one carries a measured rate",
      all(o["rate"] is not None and o["rate"] > 0 for o in O.CATALOGUE), True)
check("none of the never-done ones got in",
      all(O.RATES.get(o["key"], 0) > 0 for o in O.CATALOGUE), True)
check("three bands", sorted(O.BY_BAND), ["easy", "hard", "medium"])
check("a rarer band pays more",
      max(o["gems"] for o in O.BY_BAND["easy"]) < min(o["gems"] for o in O.BY_BAND["hard"]), True)
check("nothing pays without being measured",
      all(o["gems"] == O.pay_for(o["rate"]) for o in O.CATALOGUE), True)

print("\n--- six a day, three easy, two medium, one hard ---")
a = fa.objectives_for()
check("the same six every time you ask",
      [o["key"] for o in a], [o["key"] for o in fa.objectives_for()])
check("six", len(a), 6)
check("the mix the owner asked for",
      dict(collections.Counter(o["band"] for o in a)), {"easy": 3, "medium": 2, "hard": 1})
check("each keyed by the day", all(o["ref"].startswith(fa.obj_day_key()) for o in a), True)
check("another day, another set",
      [o["key"] for o in fa.objectives_for(NOW + 86400)] == [o["key"] for o in a], False)

print("\n--- it rotates: everything comes round before anything repeats ---")
seen = []
for d in range(30):
    seen.extend(o["key"] for o in fa.objectives_for(NOW + d * 86400))
easy_days = len(O.BY_BAND["easy"]) // 3
check("no easy one repeats until the whole easy band has been used",
      len(set(k for k in seen[:easy_days * 6] if O.BY_KEY[k]["band"] == "easy")),
      easy_days * 3)
check("the hard one is different every day",
      len(set(k for k in seen if O.BY_KEY[k]["band"] == "hard")), 30)

print("\n--- what today's play counts for ---")
f = facts()
check("matches and wins", (f["played"], f["wins"]), (4, 3))
check("score, best and the score in a loss", (f["score"], f["best"], f["lossscore"]),
      (27000, 9000, 6000))
check("rating gained", int(f["elo"]), 42)
check("a win straight after a loss", f["comeback"], 1)
check("the longest run of wins", f["streak"], 2)
check("ships and tiers flown", (len(f["ships"]), len(f["tiers"])), (2, 2))
check("by hull", (f["shipwin"].get(702), f["shipplay"].get(605)), (2, 2))
check("a win worth 20+ in that hull", f["shipbig"].get(702), 1)
check("5,000 in a match in that hull", f["shipscore"].get(702), 2)
check("by tier", (f["tierwin"].get(7), f["tierplay"].get(6)), (2, 2))
check("tier 6 or better, counted as 'or better'", f["tierplus"].get(6), 3)
check("wins without dying, and with two or fewer", (f["clean"].get(0), f["clean"].get(2)), (1, 3))
check("wins worth 15+ and 20+", (f["big"].get(15), f["big"].get(20)), (2, 1))
check("where they were played", (f["region"].get("europe"), f["regionwin"].get("america")), (2, 1))
check("what time of day", (f["hour"].get("0"), f["hour"].get("12")), (2, 2))
check("alongside a clanmate", f["mate_wins"], 1)
check("survival: a round, in the top half of a field of 22",
      (f["surv_rounds"], f["surv_half"], f["surv_place"].get(3), f["surv_bigtop"].get(20)),
      (1, 1, 1, 1))

print("\n--- claiming ---")
cn = sqlite3.connect(fa.DB_PATH)
st = fa.obj_status(cn.cursor(), N("Me"))
cn.close()
check("six with progress on them", len(st), 6)
check("nothing pays itself",
      fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Me")), 0)
ready = [o for o in st if o["ready"]]
if ready:
    first = ready[0]
    r = me.post("/objectives/claim", json={"key": first["key"]}).get_json()
    check("claiming one pays exactly what it says", (r["ok"], r["gems"]), (True, first["gems"]))
    check("twice pays nothing", me.post("/objectives/claim", json={"key": first["key"]}).get_json()["ok"], False)
    check("the ledger keys it to today",
          sqlite3.connect(fa.DB_PATH).execute(
              "SELECT reason, ref FROM gem_ledger WHERE owner = ?", (N("Me"),)).fetchall(),
          [("objective", first["ref"])])
else:
    check("at least one of today's six was in reach", False, True)
check("an objective that is not today's is refused",
      me.post("/objectives/claim", json={"key": "wins:-:99"}).get_json()["ok"], False)

print("\n--- the page ---")
h = me.get("/achievements").get_data(as_text=True)
check("today's six are on it", ('data-okey=' in h) and ("Today" in h), True)
check("each says its band and how often it happens", "% of days" in h, True)
check("the clock counts down to midnight", 'class="clock" data-until=' in h, True)
check("and it says how many there are in all", str(len(O.CATALOGUE)) in h, True)
check("no weekly set any more", "This week" in h, False)

print("\n--- shut while the economy is unreleased ---")
check("a stranger cannot claim",
      fa.app.test_client().post("/objectives/claim", json={"all": True}).status_code, 404)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
