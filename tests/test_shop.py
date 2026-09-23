# -*- coding: utf-8 -*-
"""The ship shop: what you own, what you can buy, what you can wear - and
that none of it shows to anyone but the owner while unreleased.

The money tests lean on gem_charge: a purchase must never overdraw, never
double-charge, and must leave the ledger and the balance in agreement.

Runs against a scratch database. Nothing here touches the live site.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="shoptest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.init_db()
fa.app.config["TESTING"] = True
OWNER, PLAYER = "discord:owner-under-test", "discord:plain-player"
fa.OWNER_SUBS = {OWNER}

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def conn():
    return sqlite3.connect(fa.DB_PATH)


def seed(gems=0, peak_div=None, peak_rank=None):
    cn = conn()
    cn.execute("DELETE FROM players")
    cn.execute("DELETE FROM gem_ledger")
    cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems, "
               "peak_div, peak_rank) VALUES ('OWNERGUY','OWNERGUY',1900,40,20,?,?,?,?)",
               (OWNER, gems, peak_div, peak_rank))
    cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems) "
               "VALUES ('PLAINGUY','PLAINGUY',1300,5,5,?,0)", (PLAYER,))
    if gems:
        cn.execute("INSERT INTO gem_ledger (owner_kind, owner, amount, reason, ref, at) "
                   "VALUES ('player','OWNERGUY',?,'backfill','v1','2026-09-17 00:00:00')", (gems,))
    cn.commit()
    cn.close()
    fa._SHIP_CACHE["ts"] = 0.0
    fa._BOARD_CACHE.clear()


def client(sub=None):
    cl = fa.app.test_client()
    if sub:
        with cl.session_transaction() as s:
            s["google_sub"] = sub
    return cl


def bal():
    cn = conn()
    r = cn.execute("SELECT gems FROM players WHERE norm_name='OWNERGUY'").fetchone()[0]
    cn.close()
    return r


def ledger():
    cn = conn()
    r = cn.execute("SELECT COALESCE(SUM(amount),0) FROM gem_ledger WHERE owner='OWNERGUY'").fetchone()[0]
    cn.close()
    return r


print("\n--- the catalogue ---")
cat = fa.ship_catalog()
codes = {i["code"] for i in cat}
check("every rendered ship is for sale", codes, set(fa.ship_shapes.ship_codes()))
check("34 hulls", len(cat), 34)
by = {i["code"]: i for i in cat}
check("the Odyssey is the mythic and the dearest thing in the shop",
      by[701]["mythic"] and by[701]["price"] == max(i["price"] for i in cat), True)
check("Aries costs more than the top rank pays", by[704]["price"] > fa.GEM_DIVISION_AWARD[8], True)
check("Bastion too", by[703]["price"] > fa.GEM_DIVISION_AWARD[8], True)
check("neither premium hull is mythic", by[703]["mythic"] or by[704]["mythic"], False)
check("level 7 unlocks the Marauder", by[603]["unlock_level"], 7)
# 9.68.0: the Odyssey is nobody's gift. Finishing a day at number one
# (Mythos) earns the RIGHT to buy it, at a price that makes it the goal.
check("the Odyssey is handed to no tier", by[701]["unlock_level"], None)
check("only Mythos may buy it", by[701]["buy_level"], fa.ranks.MYTHOS_LEVEL)
check("and it costs 150,000", by[701]["price"], 150000)
check("dearer by tier", [fa.SHIP_TIER_PRICE[t] for t in range(1, 8)]
      == sorted(fa.SHIP_TIER_PRICE[t] for t in range(1, 8)), True)

print("\n--- what a rank hands you ---")
seed(peak_div="advanced")
cn = conn()
own = fa.owned_ships(cn.cursor(), "OWNERGUY")
cn.close()
check("a rank hands out no hull at all (9.69.0)", any(v == "rank" for v in own.values()), False)
check("...so a Paladin peak owns nothing unbought", own, {})
check("...and never the Odyssey by rank", 701 in own, False)

print("\n--- the best player gets the mythic ---")
seed(peak_div="shadowx3", peak_rank=1)
cn = conn()
own = fa.owned_ships(cn.cursor(), "OWNERGUY")
cn.close()
check("peak rank #1 is NOT handed the Odyssey (9.68.0)", 701 in own, False)
check("nor any other hull (9.69.0)", sum(1 for v in own.values() if v == "rank"), 0)
seed(peak_div="shadowx3", peak_rank=2)
cn = conn()
check("peak rank #2 does not", 701 in fa.owned_ships(cn.cursor(), "OWNERGUY"), False)
cn.close()

print("\n--- buying ---")
# a Scout, so the tier-2 Trident is on sale to them: hulls are gated on
# the tier you have reached since 9.51.0
seed(gems=5000, peak_div="delta")
cl = client(OWNER)
TRIDENT = by[202]["price"]
r = cl.post("/shop/buy", json={"code": 202}).get_json()          # Trident, tier 2
check("a purchase lands", r.get("ok"), True)
check("balance debited", bal(), 5000 - TRIDENT)
check("ledger agrees", ledger(), 5000 - TRIDENT)
r = cl.post("/shop/buy", json={"code": 202}).get_json()
check("buying it again is refused", r.get("ok"), False)
check("...and costs nothing", bal(), 5000 - TRIDENT)
r = cl.post("/shop/buy", json={"code": 704}).get_json()          # Aries: dearer than the balance
check("too dear is refused", r.get("ok"), False)
check("...and costs nothing", bal(), 5000 - TRIDENT)
check("ledger still agrees", ledger(), 5000 - TRIDENT)
r = cl.post("/shop/buy", json={"code": 101}).get_json()          # Fly: tier 1, on sale to anyone
check("a tier's own hull is for sale now (9.69.0)", r.get("ok"), True)
r = cl.post("/shop/buy", json={"code": 999}).status_code
check("an unknown ship is 404", r, 404)

print("\n--- gem_charge never overdraws ---")
seed(gems=100)
cn = conn()
c = cn.cursor()
check("short by one is refused", fa.gem_charge(c, "OWNERGUY", 101, "purchase", "ship-x"), "short")
check("...and left no ledger row behind",
      c.execute("SELECT COUNT(*) FROM gem_ledger WHERE ref='ship-x'").fetchone()[0], 0)
check("exactly enough goes through", fa.gem_charge(c, "OWNERGUY", 100, "purchase", "ship-y"), "ok")
check("the same ref again is a duplicate", fa.gem_charge(c, "OWNERGUY", 100, "purchase", "ship-y"), "duplicate")
cn.commit()
check("balance is zero, not negative", bal(), 0)
cn.close()

print("\n--- wearing ---")
seed(gems=1000, peak_div="usniper")
cl = client(OWNER)
cl.post("/shop/buy", json={"code": 101})                          # nothing is handed out now
r = cl.post("/shop/equip", json={"code": 101}).get_json()
check("wearing a ship you bought", r.get("ok"), True)
cn = conn()
check("it is recorded", cn.execute("SELECT display_ship FROM players WHERE norm_name='OWNERGUY'").fetchone()[0], 101)
cn.close()
r = cl.post("/shop/equip", json={"code": 704}).get_json()
check("wearing a ship you do not own is refused", r.get("ok"), False)
r = cl.post("/shop/equip", json={"code": None}).get_json()
check("back to the rank's ship", r.get("ok"), True)
cn = conn()
check("it is cleared", cn.execute("SELECT display_ship FROM players WHERE norm_name='OWNERGUY'").fetchone()[0], None)
cn.close()

print("\n--- the worn ship is drawn only for a viewer who may see it ---")
seed(gems=1000, peak_div="usniper")
cl = client(OWNER)
cl.post("/shop/buy", json={"code": 101})                          # nothing is handed out now
cl.post("/shop/equip", json={"code": 101})
fa._SHIP_CACHE["ts"] = 0.0
m = fa.display_ship_map()
check("the map knows the choice", m.get("OWNERGUY"), 101)
check("allowed viewer: worn ship", fa.worn_emblem("OWNERGUY", m, True)[0], 101)
check("disallowed viewer: the division's own", fa.worn_emblem("OWNERGUY", m, False), (None, None, False))
check("the mythic carries its colour", fa.worn_emblem("X", {"X": 701}, True), (701, fa.MYTHIC_COLOR, True))
check("an ordinary ship carries its own colour, the shop's (9.68.0)",
      fa.worn_emblem("X", {"X": 202}, True), (202, fa.ship_color(202), False))
h = client().get("/leaderboard").get_data(as_text=True)
check("a stranger's board has no mythic class and no worn hull", "mythic" in h, False)

print("\n--- nobody but the owner ---")
check("signed out /shop is 404", client().get("/shop").status_code, 404)
check("a player's /shop is 404", client(PLAYER).get("/shop").status_code, 404)
check("a player cannot buy", client(PLAYER).post("/shop/buy", json={"code": 202}).status_code, 404)
check("a player cannot equip", client(PLAYER).post("/shop/equip", json={"code": 101}).status_code, 404)
r = client(OWNER).get("/shop")
check("the owner's /shop is 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("it lists the mythic", "Mythic" in h and "Odyssey" in h, True)
check("it lists Aries and Bastion", "Aries" in h and "Bastion" in h, True)
check("it says it is unreleased", "Not released" in h, True)
me = client(OWNER).get("/me").get_json()
check("the owner's menu has Shop", any(n.get("id") == "shopTab" for n in me.get("nav", [])), True)
me = client(PLAYER).get("/me").get_json()
check("a player's menu does not", any(n.get("id") == "shopTab" for n in me.get("nav", [])), False)

print()
print("--- a clan page renders for a stranger (the 9.23.0 regression) ---")
seed(gems=0, peak_div="usniper")
cn = conn()
cn.execute("INSERT OR IGNORE INTO clans (tag, created_by, created_at) VALUES ('TST','x','2026-01-01')")
cn.execute("UPDATE players SET clan = 'TST' WHERE norm_name = 'OWNERGUY'")
cn.commit(); cn.close()
fa._BOARD_CACHE.clear()
r = client().get("/clan/TST")
check("/clan/TST is 200 for a stranger", r.status_code, 200)
check("it lists the member", "OWNERGUY" in r.get_data(as_text=True), True)
r = client(OWNER).get("/clan/TST")
check("/clan/TST is 200 for the owner (worn-emblem path)", r.status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
