# -*- coding: utf-8 -*-
"""The clan shop: looks, emblem, perks, slots - bought from the treasury by
officers, shown to viewers who may see the shop, never to anyone else."""
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
TMP = tempfile.mkdtemp(prefix="cshop")
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


def treasury(tag="TST"):
    return q("SELECT COALESCE(gems,0) FROM clans WHERE tag=?", tag)[0][0]


N = fa.normalize_name
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
for tag in ("TST", "OTH"):
    c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", (tag, "sub:owner" if tag == "TST" else "sub:o2", "2026-09-01 00:00:00"))
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", ("sub:owner", "TST", "leader"))
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", ("sub:c1", "TST", "coleader"))
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", ("sub:o2", "OTH", "leader"))
for name, sub, tag in (("Owner One", "sub:owner", "TST"), ("Co One", "sub:c1", "TST"), ("Alpha", "sub:a", "TST"),
                       ("Bravo", "sub:b", "TST"), ("Other Boss", "sub:o2", "OTH"), ("Loner", "sub:l", None)):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)",
              (name, N(name), 1500, 8, 4, sub, tag))
for i in range(6):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, clan) VALUES (?,?,?,?,?,?)", ("O%d" % i, "O%d" % i, 1800, 3, 3, "OTH"))
fa.gem_grant(c, "clan", "TST", 30000, "backfill", "v1")
cn.commit()
cn.close()


def client(sub, preview=True):
    cl = fa.app.test_client()
    if sub:
        with cl.session_transaction() as s:
            s["google_sub"] = sub
            if preview:
                s["preview"] = True
    return cl


owner, co, member, stranger, other = client("sub:owner"), client("sub:c1"), client("sub:a"), client(None), client("sub:o2")
CSS = io.open("templates/_cosmetics_css.html", encoding="utf-8").read()

print("\n--- the catalogue ---")
ids = [i[0] for i in fa.CLAN_ITEMS]
check("ids unique", len(set(ids)), len(ids))
check("looks reuse real CSS classes; tag looks have their own rules", all((("." + i[6]) in CSS) for i in fa.CLAN_ITEMS if i[1] == "look"), True)
check("a ship is an emblem at its own price", (fa.clan_item("cs-702")["kind"], fa.clan_item("cs-702")["price"] == next(x["price"] for x in fa.ship_catalog() if x["code"] == 702)), ("emblem", True))
check("nonsense is nothing", (fa.clan_item("cs-x"), fa.clan_item("nope")), (None, None))

print("\n--- who may spend ---")
check("stranger 404", stranger.post("/clan/shop/buy", json={"clan": "TST", "item": "cb-dark"}).status_code, 404)
check("a plain member may not", member.post("/clan/shop/buy", json={"clan": "TST", "item": "cb-dark"}).status_code, 403)
check("another clan's leader may not", other.post("/clan/shop/buy", json={"clan": "TST", "item": "cb-dark"}).status_code, 403)
check("unknown item 404", owner.post("/clan/shop/buy", json={"clan": "TST", "item": "cb-nope"}).status_code, 404)

print("\n--- looks ---")
t0 = treasury()
r = co.post("/clan/shop/buy", json={"clan": "TST", "item": "cb-nebula"}).get_json()
check("a co-leader buys a band background", (r["ok"], t0 - treasury()), (True, 6000))
check("ledger row on the clan", q("SELECT amount FROM gem_ledger WHERE owner_kind='clan' AND owner='TST' AND reason='purchase' AND ref='citem-cb-nebula'"), [(-6000,)])
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "cb-nebula"}).get_json()
check("buying it twice is refused", (r["ok"], "already has" in r["message"]), (False, True))
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "ct-diamond"}).get_json()
check("too dear for the treasury", (r["ok"], "treasury has" in r["message"], treasury()), (False, True, t0 - 6000))
check("bought is worn at once", json.loads(q("SELECT cosmetics FROM clans WHERE tag='TST'")[0][0]), {"banner": "cb-nebula"})
r = owner.post("/clan/shop/equip", json={"clan": "TST", "item": "cb-nebula"}).get_json()
check("putting it on again is harmless", (r["ok"], r["worn"]), (True, {"banner": "cb-nebula"}))
r = owner.post("/clan/shop/equip", json={"clan": "TST", "item": "cf-gold"}).get_json()
check("cannot wear what is not bought", (r["ok"], "does not have" in r["message"]), (False, True))
owner.post("/clan/shop/buy", json={"clan": "TST", "item": "ct-gold"})
owner.post("/clan/shop/equip", json={"clan": "TST", "item": "ct-gold"})
check("two slots on the row", json.loads(q("SELECT cosmetics FROM clans WHERE tag='TST'")[0][0]), {"banner": "cb-nebula", "tag": "ct-gold"})
fa._CLAN_COS_CACHE["ts"] = 0.0
h = owner.get("/clan/TST").get_data(as_text=True)
check("clan band wears the background and the tag look", ('class="chead cosb cos-b-nebula"' in h) and ('class="chtag cos-ct-gold"' in h), True)
h = owner.get("/player/Alpha").get_data(as_text=True)
check("a member's badge on their profile wears the tag look", 'class="badge cbadge cos-ct-gold"' in h, True)
h = owner.get("/shop").get_data(as_text=True)
check("Shop: the clan tab, the treasury and what is on", ('data-panel="clan"' in h) and ("gems" in h) and ("On now" in h), True)
h = stranger.get("/clan/TST").get_data(as_text=True)
check("a visitor sees a plain band", ("cos-b-nebula" in h) or ("cos-ct-gold" in h) or ("cbadge" in h), False)
h = stranger.get("/player/Alpha").get_data(as_text=True)
check("...and a plain badge", "cbadge" in h, False)
h = member.get("/shop").get_data(as_text=True)
check("a plain member has no clan tab in the Shop", 'data-panel="clan"' in h, False)
r = owner.post("/clan/shop/equip", json={"clan": "TST", "slot": "tag", "item": None}).get_json()
check("take the tag look off", (r["ok"], r["worn"]), (True, {"banner": "cb-nebula"}))

print("\n--- the emblem ---")
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "cs-201"}).get_json()
check("buy the Delta-Fighter for the clan",
      (r["ok"], q("SELECT amount FROM gem_ledger WHERE owner='TST' AND ref='citem-cs-201'")),
      (True, [(-fa.clan_item("cs-201")["price"],)]))
check("worn on purchase", json.loads(q("SELECT cosmetics FROM clans WHERE tag='TST'")[0][0]).get("emblem"), "cs-201")
fa._CLAN_COS_CACHE["ts"] = 0.0
h = owner.get("/clan/TST").get_data(as_text=True)
check("band shows the emblem beside the tag", 'class="chemb"' in h, True)

print("\n--- perks ---")
cn = sqlite3.connect(fa.DB_PATH)
fa.gem_grant(cn.cursor(), "clan", "TST", 40000, "backfill", "v1b")
cn.commit()
cn.close()
t0 = treasury()
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-recruit"}).get_json()
check("Recruiting for a week", (r["ok"], "runs until" in r["message"], t0 - treasury()), (True, True, 1500))
until1 = q("SELECT until FROM clan_perks WHERE clan='TST' AND perk='perk-recruit'")[0][0]
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-recruit"}).get_json()
until2 = q("SELECT until FROM clan_perks WHERE clan='TST' AND perk='perk-recruit'")[0][0]
check("buying again extends it by a week, from the end", (r["ok"], until2 > until1, until2[:10] > until1[:10]), (True, True, True))
owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-spotlight"})
fa._CLAN_COS_CACHE["ts"] = 0.0
h = owner.get("/clan/TST").get_data(as_text=True)
check("band: the Recruiting pill, and no boast about paying", (">Recruiting</span>" in h) and (">Spotlight</span>" not in h), True)
h = owner.get("/clans").get_data(as_text=True)
rows = h.split("<tbody>")[1].split("</tbody>")[0]
first = rows.split("<tr")[1]
check("clans page: the ranking is untouched, with a Featured clan banner above it", ("Featured clan" in h) and ('class="featc' in h) and ("Spotlight" not in h.split("<tbody>")[1]), True)
h = stranger.get("/clans").get_data(as_text=True)
rows = h.split("<tbody>")[1].split("</tbody>")[0]
check("a visitor sees the true order and no pills", ("/clan/OTH" in rows.split("<tr")[1]) and ("Spotlight" not in rows), True)

print("\n--- lobby host ---")
check("co-leader cannot host before the perk", co.get("/api/customgame/status").get_json()["can_host"], False)
owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-host"})
check("co-leader can host with it", co.get("/api/customgame/status").get_json()["can_host"], True)
check("a plain member still cannot", member.get("/api/customgame/status").get_json()["can_host"], False)
check("nor the same co-leader without the preview (gems off)", client("sub:c1", preview=False).get("/api/customgame/status").get_json()["can_host"], False)
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE clan_perks SET until = '2020-01-01 00:00:00' WHERE perk = 'perk-host'")
cn.commit()
cn.close()
check("expired: no longer a host", co.get("/api/customgame/status").get_json()["can_host"], False)

print("\n--- co-leader slots ---")
r = owner.post("/clan/role", json={"clan": "TST", "name": "Alpha", "role": "coleader"}).get_json()
check("second co-leader fits under the cap of %d" % fa.CLAN_COLEADER_MAX, r["ok"], True)
r = owner.post("/clan/role", json={"clan": "TST", "name": "Bravo", "role": "coleader"}).get_json()
check("a third does not", r["ok"], False)
cn = sqlite3.connect(fa.DB_PATH)
fa.gem_grant(cn.cursor(), "clan", "TST", 50000, "backfill", "v2")
cn.commit()
cn.close()
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-coleader"}).get_json()
check("buy a slot: cap is now %d" % (fa.CLAN_COLEADER_MAX + 1), (r["ok"], ("may have %d now" % (fa.CLAN_COLEADER_MAX + 1)) in r["message"]), (True, True))
r = owner.post("/clan/role", json={"clan": "TST", "name": "Bravo", "role": "coleader"}).get_json()
check("now the third fits", r["ok"], True)
owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-coleader"})
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-coleader"}).get_json()
check("no more than %d extra slots" % fa.CLAN_COLEADER_SLOTS_MAX, (r["ok"], "every extra" in r["message"], q("SELECT coleader_slots FROM clans WHERE tag='TST'")), (False, True, [(2,)]))

print("\n--- the treasury never overdraws ---")
check("balance is the ledger", treasury(), q("SELECT COALESCE(SUM(amount),0) FROM gem_ledger WHERE owner_kind='clan' AND owner='TST'")[0][0])
check("and never negative", treasury() >= 0, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
