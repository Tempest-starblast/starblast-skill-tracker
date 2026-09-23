# -*- coding: utf-8 -*-
"""Batch B of the 23 Sep suggestions, each pinned.

  #1  reaching a tier puts its hull on sale to you and pays half the price
      on claim; nothing is handed out any more
  #9  a Wardrobe on the account page: what you own, what you wear, and
      wear / take off in place, through the same /shop/equip as the shop
  and the two hardening fixes from the tester-key report: a real error
  page, and a preview door whose bookkeeping cannot fail it."""
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

import flask_app as fa                                          # noqa: E402
import ranks                                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="sugB")
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


SUB = "test:sugb:1"
NAME, NN = "Wardrobe Tester", "WARDROBETESTER"


def seed(peak_div, gems):
    cn = sqlite3.connect(fa.DB_PATH)
    c = cn.cursor()
    c.execute("DELETE FROM players WHERE norm_name = ?", (NN,))
    c.execute("DELETE FROM gem_ledger WHERE owner = ?", (NN,))
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, peak_div) "
              "VALUES (?,?,?,?,?,?,?)", (NAME, NN, 1200.0, 30, 20, SUB, peak_div))
    if gems:
        fa.gem_grant(c, "player", NN, gems, "sandbox", "sugb")
    cn.commit()
    cn.close()


def client():
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        s["google_sub"] = SUB
    return cl


cat = {i["code"]: i for i in fa.ship_catalog()}
level_of_tier = {}
for r in ranks.RANKS:
    t = r["ship"] // 100
    level_of_tier[t] = min(level_of_tier.get(t, 99), r["level"])

print("\n--- #1 nothing is handed out ---")
seed(peak_div="shadowx3", gems=0)                 # Archon: every climbable tier reached
cn = sqlite3.connect(fa.DB_PATH)
own = fa.owned_ships(cn.cursor(), NN)
cn.close()
check("an Archon who has bought nothing owns nothing", own, {})
check("no hull is earn-only any more",
      any(i["earn_only_gate"] for i in cat.values()), False)
for code, lvl in sorted(fa.SHIP_RANK_UNLOCK.items()):
    check("tier hull %s goes on sale at its own tier (level %d)" % (code, lvl),
          cat[code]["buy_level"], lvl)
    check("  priced by its tier", cat[code]["price"], fa.SHIP_TIER_PRICE[code // 100])

print("\n--- #1 and what a tier pays on claim ---")
for lvl in range(1, 7):
    tier = ranks.RANK_BY_LEVEL[lvl]["ship"] // 100
    check("level %d pays half its hull (%d)" % (lvl, fa.SHIP_TIER_PRICE[tier] // 2),
          fa.GEM_DIVISION_AWARD[lvl], fa.SHIP_TIER_PRICE[tier] // 2)
# Warden's hull is a tier-6 hull like Paladin's; a literal half would pay
# both 2,000. Warden is lifted so a higher rank never pays the same.
check("Warden pays more than Paladin", fa.GEM_DIVISION_AWARD[7] > fa.GEM_DIVISION_AWARD[6], True)
check("  and at least half its hull", fa.GEM_DIVISION_AWARD[7] >= fa.SHIP_TIER_PRICE[6] // 2, True)
check("Archon kept at 4,000", fa.GEM_DIVISION_AWARD[8], 4000)
check("Mythos pays a sixth of the Odyssey (9.72.0)", fa.GEM_DIVISION_AWARD[9], 25000)
check("each tier pays more than the one below",
      [fa.GEM_DIVISION_AWARD[l] for l in range(1, 10)]
      == sorted(fa.GEM_DIVISION_AWARD[l] for l in range(1, 10)), True)
myth = next(a for a in fa.gem_achievement_catalog() if a["key"] == "div-mythos")
check("the Mythos achievement promises the RIGHT to buy, not the hull",
      "right to buy the Odyssey" in myth["desc"] and "with the Odyssey" not in myth["desc"], True)

print("\n--- #1 buying your tier's hull ---")
was = fa.GEMS_PUBLIC
fa.GEMS_PUBLIC = True
seed(peak_div="delta", gems=5000)                 # Scout: tiers 1 and 2 reached
cl = client()
r = cl.post("/shop/buy", json={"code": 201}).get_json()
check("a Scout may buy the Scout's own hull", r.get("ok"), True)
r = cl.post("/shop/buy", json={"code": 101}).get_json()
check("  and the Drifter's", r.get("ok"), True)
r = cl.post("/shop/buy", json={"code": 301}).get_json()
check("  but not the Raider's, one tier up", r.get("ok"), False)
check("  told to climb, not to earn", "Climb to" in (r.get("message") or ""), True)
cn = sqlite3.connect(fa.DB_PATH)
own = fa.owned_ships(cn.cursor(), NN)
cn.close()
check("both purchases are owned, as bought", own, {201: "bought", 101: "bought"})

print("\n--- #9 the Wardrobe ---")
h = cl.get("/account").get_data(as_text=True)
check("the account page has a Wardrobe tab", 'data-panel="wardrobe"' in h, True)
check("  listing the bought hulls", cat[201]["name"] in h and 'data-code="201"' in h, True)
check("  with nothing worn yet", "Wearing &middot; take off" in h, False)
check("  and every look slot named",
      all(label in h for _s, label in fa.COSMETIC_SLOTS), True)
r = cl.post("/shop/equip", json={"code": 201}).get_json()
check("wearing from the wardrobe goes through /shop/equip", r.get("ok"), True)
h = cl.get("/account").get_data(as_text=True)
check("  and the page now says so", "Wearing &middot; take off" in h, True)
first_cos = next(c for c in fa.COSMETICS if c[1] == "banner")
r = cl.post("/shop/buy", json={"item": first_cos[0]}).get_json()
check("a look can be bought", r.get("ok"), True)
h = cl.get("/account").get_data(as_text=True)
check("  and appears in its slot", 'data-item="%s"' % first_cos[0] in h, True)
r = cl.post("/shop/equip", json={"item": first_cos[0]}).get_json()
check("  and worn", r.get("ok"), True)
h = cl.get("/account").get_data(as_text=True)
check("  the wardrobe marks it", h.count("Wearing &middot; take off"), 2)
r = cl.post("/shop/equip", json={"slot": "banner", "item": None}).get_json()
check("  and taken off again", r.get("ok"), True)
fa.GEMS_PUBLIC = False
h = cl.get("/account").get_data(as_text=True)
check("no Wardrobe while the economy is unreleased", 'data-panel="wardrobe"' in h, False)
fa.GEMS_PUBLIC = was

print("\n--- a real error page ---")
body, code = fa.error_500(Exception("boom"))
check("a broken page answers 500", code, 500)
check("  with words, not a blank", "Something broke on our side" in body, True)
check("  and a way back", 'href="/"' in body, True)
check("  registered with the app", 500 in fa.app.error_handler_spec[None], True)

print("\n--- the preview door's bookkeeping cannot fail the door ---")
s = src("flask_app.py")
check("the use-count is written by one helper",
      s.count("_preview_key_used(c, kid)") - s.count("def _preview_key_used(c, kid)"), 2)
helper = s[s.index("def _preview_key_used"):][:600]
check("  which swallows a locked database", "except sqlite3.OperationalError" in helper, True)
check("  and the raw UPDATE is nowhere else in the door",
      "UPDATE preview_keys SET uses" in s[s.index("def dev_preview"):][:6000], False)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
