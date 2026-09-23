# -*- coding: utf-8 -*-
"""Cosmetics shop, featured sale, claimable achievements (owner-only preview)."""
import io
import json
import os
import re
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
TMP = tempfile.mkdtemp(prefix="cosm")
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


def q(sql, *args):
    cn = sqlite3.connect(fa.DB_PATH)
    r = cn.execute(sql, args).fetchall()
    cn.close()
    return r


def w(sql, *args):
    cn = sqlite3.connect(fa.DB_PATH)
    cn.execute(sql, args)
    cn.commit()
    cn.close()


def bal(nn):
    return q("SELECT COALESCE(gems,0) FROM players WHERE norm_name=?", nn)[0][0]


OWN, LON = fa.normalize_name("Owner One"), fa.normalize_name("Loner")
w("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan, peak_div) VALUES (?,?,?,?,?,?,?,?)",
  "Owner One", OWN, 1700, 12, 3, "sub:owner", "TST", "pulse")
w("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
  "Loner", LON, 1500, 3, 1, "sub:loner")
w("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", "TST", "sub:owner", "2026-09-01 00:00:00")
try:
    w("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", "sub:owner", "TST", "leader")
except sqlite3.Error as e:
    print("  clan_admins insert:", e, [r[1] for r in q("PRAGMA table_info(clan_admins)")])
cn = sqlite3.connect(fa.DB_PATH)
fa.gem_grant(cn.cursor(), "player", OWN, 60000, "backfill", "v1")
cn.commit()
cn.close()

app = fa.app.test_client()
CSS = io.open("templates/_cosmetics_css.html", encoding="utf-8").read()

print("\n--- the catalogue ---")
ids = [c[0] for c in fa.COSMETICS]
slots = dict(fa.COSMETIC_SLOTS)
check("at least 40 looks", len(ids) >= 40, True)
check("ids unique", len(set(ids)), len(ids))
check("every slot known; bought looks cost something, earned ones nothing", all(c[1] in slots and ((c[3] > 0) == (len(c) <= 5)) for c in fa.COSMETICS), True)
check("every slot has 5 or more", all(sum(1 for c in fa.COSMETICS if c[1] == s) >= 5 for s in slots), True)
missing = [i for i in ids if not i.startswith("t-") and ("cos-%s" % i) not in CSS]
check("every non-title look has a CSS rule", missing, [])
check("catalogue dicts carry the class", fa.COSMETIC_BY_ID["b-nebula"]["cls"], "cos-b-nebula")

print("\n--- who may see it ---")
stranger = fa.app.test_client()
check("stranger: shop 404", stranger.get("/shop").status_code, 404)
check("stranger: buy 404", stranger.post("/shop/buy", json={"item": "b-dark"}).status_code, 404)
check("stranger: achievements 404", stranger.get("/achievements").status_code, 404)
check("stranger: claim 404", stranger.post("/achievements/claim", json={"all": True}).status_code, 404)
plain = fa.app.test_client()
with plain.session_transaction() as s:
    s["google_sub"] = "sub:loner"
check("ordinary player: shop 404", plain.get("/shop").status_code, 404)
h = plain.get("/player/Owner%20One").get_data(as_text=True)
check("ordinary player's page carries no cosmetic CSS", "cos-b-dark" in h, False)

with app.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True

print("\n--- the shop page ---")
r = app.get("/shop")
check("owner: 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band + balance", ("Ships and looks" in h) and ('id="bal">60,000' in h), True)
nav = h.split('<nav class="subtabs" id="subtabs"')[1].split("</nav>")[0]
_clan = 1 if 'data-panel="clan"' in nav else 0
check("six sections as tabs (plus the clan tab for an officer)", nav.count("data-panel=") - _clan, 6)
check("a panel per section", h.count('<section class="panel" data-panel=') - _clan, 6)
check("every look has a tile", all(('data-item="%s"' % i) in h for i in ids), True)
check("featured strip with %d tiles" % fa.FEATURED_COUNT, ("Featured today" in h) and (h.split('class="featured"')[1].split("</section>")[0].count('<div class="ship') == fa.FEATURED_COUNT), True)
check("countdown wired", 'id="resetIn" data-secs=' in h, True)
check("name previews use my name", ('<span class="cosn cos-n-fire">Owner One</span>' in h), True)

print("\n--- featured: the same four for everyone, from the date ---")
a1, _ = fa.featured_today("2026-09-18")
a2, _ = fa.featured_today("2026-09-18")
b1, _ = fa.featured_today("2026-09-19")
check("deterministic per day", list(a1.keys()) == list(a2.keys()) and a1 == a2, True)
check("four on sale", len(a1), fa.FEATURED_COUNT)
check("a different day, a different set", set(a1) != set(b1), True)
check("discounts from the table, cheaper than list", all(v["off"] in fa.FEATURED_OFF and v["price"] < v["was"] for v in a1.values()), True)
check("priced to the nearest ten", all(v["price"] % 10 == 0 for v in a1.values()), True)
today_sale, _ = fa.featured_today()
check("resets within a day", 0 < fa.featured_resets_in() <= 86400, True)

print("\n--- buying looks ---")
not_on_sale = next(i for i in ids if ("cos", i) not in today_sale and i.startswith("b-"))
price = fa.COSMETIC_BY_ID[not_on_sale]["price"]
b0 = bal(OWN)
r = app.post("/shop/buy", json={"item": not_on_sale}).get_json()
check("bought at list price", (r["ok"], b0 - bal(OWN), r.get("paid")), (True, price, price))
check("ledger row", q("SELECT amount FROM gem_ledger WHERE owner=? AND reason='purchase' AND ref=?", OWN, "cos-" + not_on_sale), [(-price,)])
r = app.post("/shop/buy", json={"item": not_on_sale}).get_json()
check("buying it again is refused", (r["ok"], "already" in r["message"].lower()), (False, True))
cos_sale = next((k for k in today_sale if k[0] == "cos"), None)
if cos_sale:
    b0 = bal(OWN)
    r = app.post("/shop/buy", json={"item": cos_sale[1]}).get_json()
    check("a featured look costs today's price", (r["ok"], b0 - bal(OWN)), (True, today_sale[cos_sale]["price"]))
else:
    ship_sale = next(k for k in today_sale if k[0] == "ship")
    b0 = bal(OWN)
    r = app.post("/shop/buy", json={"code": ship_sale[1]}).get_json()
    check("a featured ship costs today's price", (r["ok"], b0 - bal(OWN)), (True, today_sale[ship_sale]["price"]))
check("unknown item 404", app.post("/shop/buy", json={"item": "b-nope"}).status_code, 404)
loner = fa.app.test_client()
with loner.session_transaction() as s:
    s["google_sub"] = "sub:loner"
    s["preview"] = True
r = loner.post("/shop/buy", json={"item": "t-overlord"}).get_json()
check("no gems, no title", (r["ok"], "not enough" in r["message"].lower(), bal(LON)), (False, True, 0))

print("\n--- wearing looks ---")
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
for i in ("n-fire", "t-ace", "x-pulse", "f-neon"):
    fa.gem_charge(c, OWN, fa.COSMETIC_BY_ID[i]["price"], "purchase", "cos-" + i)
cn.commit()
cn.close()
r = app.post("/shop/equip", json={"item": not_on_sale}).get_json()
check("wear a banner", (r["ok"], r["worn"].get("banner")), (True, not_on_sale))
r = app.post("/shop/equip", json={"item": "n-fire"}).get_json()
check("and a name style, keeping the banner", (r["ok"], r["worn"].get("banner"), r["worn"].get("name")), (True, not_on_sale, "n-fire"))
for i in ("t-ace", "x-pulse", "f-neon"):
    app.post("/shop/equip", json={"item": i})
worn = json.loads(q("SELECT cosmetics FROM players WHERE norm_name=?", OWN)[0][0])
check("five slots on the row", sorted(worn), ["banner", "frame", "fx", "name", "title"])
r = app.post("/shop/equip", json={"item": "n-rainbow"}).get_json()
check("cannot wear what you do not own", (r["ok"], "do not have" in r["message"]), (False, True))
r = app.post("/shop/equip", json={"slot": "fx", "item": None}).get_json()
check("take one off", (r["ok"], "fx" in r["worn"], r["worn"].get("name")), (True, False, "n-fire"))
check("bad slot 400", app.post("/shop/equip", json={"slot": "hat", "item": None}).status_code, 400)
r = app.post("/shop/equip", json={"code": None}).get_json()
check("ship path still works", r["ok"], True)

print("\n--- where it shows ---")
fa._COS_CACHE["ts"] = 0.0
h = app.get("/").get_data(as_text=True)
check("home: banner + frame on the card", ('cosb cos-%s' % not_on_sale in h) and ("cosf cos-f-neon" in h), True)
check("home: name style + title", ('<span class="cosn cos-n-fire">Owner One</span>' in h) and ('<span class="cost">Ace</span>' in h), True)
h = app.get("/account").get_data(as_text=True)
check("account band: banner + name + title", ("cos-%s" % not_on_sale in h) and ("cosn cos-n-fire" in h) and (">Ace</span>" in h), True)
h = app.get("/player/Owner%20One").get_data(as_text=True)
check("own profile: banner + name", ("cos-%s" % not_on_sale in h) and ("cosn cos-n-fire" in h), True)
h = stranger.get("/player/Owner%20One").get_data(as_text=True)
check("a stranger sees none of it", ("cos-" in h) or ("cosn" in h) or ('class="cost"' in h), False)
h = plain.get("/player/Owner%20One").get_data(as_text=True)
check("nor an ordinary player", ("cos-" in h) or ('class="cost"' in h), False)
h = app.get("/shop").get_data(as_text=True)
check("shop marks what is worn", h.count("&#10003; Wearing") >= 4, True)

print("\n--- achievements: unlocked by deeds, paid on claim ---")
cn = sqlite3.connect(fa.DB_PATH)
st = {a["key"]: a for a in fa.ach_status(cn.cursor(), OWN)}
cn.close()
cat = fa.gem_achievement_catalog()
check("35 or more achievements", len(cat) >= 35, True)
check("every group present", [g for g in fa.ACH_GROUPS if not any(a["group"] == g for a in cat)], [])
check("12 wins: first-win + wins-10 unlocked, wins-50 at 12/50", (st["first-win"]["unlocked"], st["wins-10"]["unlocked"], st["wins-50"]["unlocked"], st["wins-50"]["have"], st["wins-50"]["need"]), (True, True, False, 12, 50))
check("in a clan, and running it", (st["clan-member"]["unlocked"], st["clan-officer"]["unlocked"]), (True, True))
check("dressed up after the purchases", st["cos-first"]["unlocked"], True)
cn = sqlite3.connect(fa.DB_PATH)
_lvl = fa.gem_peak_level(cn.cursor(), OWN)
cn.close()
check("rank achievements unlocked up to the recorded peak (level %d) and none above" % _lvl, sum(1 for k in st if k.startswith("div-") and st[k]["unlocked"]), _lvl)
check("nothing paid on its own", q("SELECT COUNT(*) FROM gem_ledger WHERE owner=? AND reason='achievement'", OWN)[0][0], 0)
h = app.get("/achievements").get_data(as_text=True)
ready_n = sum(1 for a in st.values() if a["ready"])
check("page: a Claim button per ready achievement + Claim all", (h.count('class="claim" data-claim="'), 'id="claimAll"' in h), (ready_n, True))
check("page: progress on a locked one", "12 / 50" in h, True)
h = app.get("/").get_data(as_text=True)
check("home: claim link with the count", ("Claim %d achievement" % ready_n) in h, True)
r = app.post("/achievements/claim", json={"key": "wins-50"}).get_json()
check("claim a locked one: refused with progress", (r["ok"], "12 of 50" in r["message"]), (False, True))
b0 = bal(OWN)
r = app.post("/achievements/claim", json={"key": "wins-10"}).get_json()
check("claim wins-10: +250", (r["ok"], bal(OWN) - b0, r["gems"]), (True, 250, 250))
r = app.post("/achievements/claim", json={"key": "wins-10"}).get_json()
check("claim it again: nothing", (r["ok"], bal(OWN) - b0), (False, 250))
check("unknown key 404", app.post("/achievements/claim", json={"key": "nope"}).status_code, 404)
b0 = bal(OWN)
r = app.post("/achievements/claim", json={"all": True}).get_json()
cn = sqlite3.connect(fa.DB_PATH)
st2 = fa.ach_status(cn.cursor(), OWN)
cn.close()
# Claiming hands over looks, and the looks finish "Collector", so one press
# pays the rest AND what the payout itself just unlocked - nothing left over.
check("claim all pays the rest and the cascade, leaving nothing",
      (r["ok"], len(r["claimed"]) >= ready_n - 1, "Collector" in r["claimed"],
       bal(OWN) - b0 == r["gems"], sum(1 for a in st2 if a["ready"])),
      (True, True, True, True, 0))
r = app.post("/achievements/claim", json={"all": True}).get_json()
check("claim all again: nothing to claim", r["ok"], False)
h = app.get("/").get_data(as_text=True)
check("home: no claim link once collected", "Claim " in h.split('class="gemcard"')[1].split("</div>")[0], False)

print("\n--- hangar achievements ---")
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
for code in fa._tier_codes(2):
    fa.gem_grant(c, "player", OWN, -1, "purchase", "ship-%d" % code)
cn.commit()
st = {a["key"]: a for a in fa.ach_status(c, OWN)}
cn.close()
check("every tier-2 hull -> Tier 2 complete ready", (st["tier-2"]["ready"], st["tier-3"]["unlocked"]), (True, False))
check("first hull counted", st["hull-first"]["unlocked"], True)

print("\n--- match results no longer pay achievements ---")
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("UPDATE players SET wins = 100 WHERE norm_name = ?", (LON,))
fa.award_match_gems(c, [("Loner", 1, 1.0)], "m-1")
cn.commit()
check("a win pays the win, not the milestone", q("SELECT COUNT(*) FROM gem_ledger WHERE owner=? AND reason='achievement'", LON)[0][0], 0)
check("but the milestone is ready to claim", any(a["key"] == "wins-100" and a["ready"] for a in fa.ach_status(c, LON)), True)
cn.close()

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
