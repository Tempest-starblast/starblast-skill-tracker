# -*- coding: utf-8 -*-
"""The owner's economy page: what was made, what was burned, by whom, on what."""
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
TMP = tempfile.mkdtemp(prefix="econ")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.OWNER_SUBS = set(fa.OWNER_SUBS) | {"sub:owner"}

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
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
          ("Owner One", N("Owner One"), 1700, 20, 5, "sub:owner"))
for nm in ("Spender", "Saver"):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
              (nm, N(nm), 1500, 10, 10))
c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES ('RICHCLAN', 'sub:owner', '2026-09-01 00:00:00')")

fa.gem_grant(c, "player", N("Saver"), 40000, "backfill", "v1")
fa.gem_grant(c, "player", N("Spender"), 30000, "backfill", "v1")
for i in range(6):
    fa.gem_grant(c, "player", N("Spender"), fa.GEM_WIN, "win", "m%d" % i)
fa.gem_grant(c, "player", N("Spender"), fa.GEM_DAILY_FIRST_WIN, "daily-win", "2026-09-19")
fa.gem_grant(c, "clan", "RICHCLAN", 9000, "clan-deposit", "w1")
fa.gem_charge(c, N("Spender"), 25000, "purchase", "cos-t-millionaire")
fa.gem_charge(c, N("Spender"), 3000, "purchase", "ship-403")
# a test account must never show up in any of it
fa.gem_grant(c, "player", "test:sandbox:1", 99999999, "sandbox", "v1")
cn.commit()
cn.close()

owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"

print("\n--- owner only ---")
check("a stranger gets a 404", fa.app.test_client().get("/dev/economy").status_code, 404)
signed = fa.app.test_client()
with signed.session_transaction() as s:
    s["google_sub"] = "sub:someone"
check("a signed-in player too", signed.get("/dev/economy").status_code, 404)
check("the owner can read it", owner.get("/dev/economy").status_code, 200)

print("\n--- the numbers ---")
cn = sqlite3.connect(fa.DB_PATH)
e = fa.economy_snapshot(cn.cursor())
cn.close()
made = 40000 + 30000 + 6 * fa.GEM_WIN + fa.GEM_DAILY_FIRST_WIN + 9000
burned = 25000 + 3000
check("everything made", e["made"], made)
check("everything burned", e["burned"], burned)
check("held now is what is left", e["held"], made - burned)
check("split between players and clans", (e["held_players"], e["held_clans"]),
      (made - burned - 9000, 9000))
check("the test account is nowhere in it", e["held"] < 99999999, True)
check("a row per day, two weeks of them", len(e["days"]), 14)
check("today carries today's numbers",
      (e["days"][-1]["made"], e["days"][-1]["burned"]), (made, burned))
reasons = {r["reason"]: r for r in e["reasons"]}
check("wins are named in plain words", reasons["win"]["label"], "Team win")
check("and counted", (reasons["win"]["made"], reasons["win"]["n"]), (6 * fa.GEM_WIN, 6))
check("sandbox is not a reason here", "sandbox" in reasons, False)
check("spending is against the thing bought",
      [(b["name"], b["gems"]) for b in e["bought"]],
      [("Millionaire", 25000), ("Ship 403", 3000)])
check("the biggest balance is the saver", e["holders"][0], {"who": N("Saver"), "gems": 40000})
check("the biggest spender is the spender", e["spenders"][0], {"who": N("Spender"), "gems": 28000})
check("the treasury is listed", e["clans"], [{"who": "RICHCLAN", "gems": 9000}])

print("\n--- the page says it ---")
h = owner.get("/dev/economy").get_data(as_text=True)
check("held, made and burned in the band",
      ("{:,}".format(made - burned) in h) and ("{:,}".format(made) in h), True)
check("the day bars are drawn", ("ebars" in h) and ('class="made"' in h), True)
check("the rates are on the page", ("Team win" in h) and (str(fa.GEM_WIN) in h), True)
check("what was bought is named", "Millionaire" in h, True)
check("and the starting-a-clan sink", "Starting a clan" in h, True)
check("no test account leaked in", "sandbox:1" in h, False)

print("\n--- an empty economy does not crash the page ---")
TMP2 = tempfile.mkdtemp(prefix="econ2")
shutil.copy("players.db", os.path.join(TMP2, "players.db"))
fa.DB_PATH = os.path.join(TMP2, "players.db")
fa.init_db()
fa.OWNER_SUBS = set(fa.OWNER_SUBS) | {"sub:owner"}
blank = fa.app.test_client()
with blank.session_transaction() as s:
    s["google_sub"] = "sub:owner"
r = blank.get("/dev/economy")
check("it renders with nothing in the ledger", r.status_code, 200)
check("and says so", "Nothing has been bought yet." in r.get_data(as_text=True), True)
shutil.rmtree(TMP2, ignore_errors=True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
