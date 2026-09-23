# -*- coding: utf-8 -*-
"""Achievements hand out looks; earned titles are not for sale; more of both."""
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
TMP = tempfile.mkdtemp(prefix="rew")
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


OWN = fa.normalize_name("Owner One")
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)",
          ("Owner One", OWN, 1700, 120, 30, "sub:owner", "TST"))
c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", ("TST", "sub:owner", "2026-09-01 00:00:00"))
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", ("sub:owner", "TST", "leader"))
# rated matches in three regions with scores and deaths
for i, region in enumerate(("america", "europe", "asia", "america", "europe")):
    c.execute("INSERT INTO matches(match_id, sys_id, played_at, lobby_name, region) VALUES (?,?,?,?,?)",
              ("m%d" % i, 100 + i, "2026-09-1%d 10:00:00" % i, "Alpha", region))
    mid = c.lastrowid
    c.execute("INSERT INTO match_players(match_row, name, norm_name, won, delta, score, deaths) VALUES (?,?,?,?,?,?,?)",
              (mid, "Owner One", OWN, 1, 1.0, 30000 if i else 120000, 30))
# friends, days with a win, lifetime gems
for i in range(6):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)", ("F%d" % i, "F%d" % i, 1400, 1, 1))
    c.execute("INSERT INTO friends(a, b, requester, state, asked_at, acted_at) VALUES (?,?,?,?,?,?)",
              (min(OWN, "F%d" % i), max(OWN, "F%d" % i), OWN, "accepted", "2026-09-01", "2026-09-01"))
for d in range(8):
    fa.gem_grant(c, "player", OWN, fa.GEM_DAILY_FIRST_WIN, "daily-win", "2026-09-0%d" % (d + 1))
fa.gem_grant(c, "player", OWN, 150000, "backfill", "v1")
cn.commit()
cn.close()

app = fa.app.test_client()
with app.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True
CSS = io.open("templates/_cosmetics_css.html", encoding="utf-8").read()

print("\n--- the catalogue, expanded ---")
cat = fa.gem_achievement_catalog()
keys = {a["key"] for a in cat}
titles = [c for c in fa.COSMETICS if c[1] == "title"]
earned = [c for c in fa.COSMETICS if len(c) > 5]
check("55 or more achievements", len(cat) >= 55, True)
check("groups incl. Combat and Social", all(g in {a["group"] for a in cat} for g in ("Combat", "Social", "Wealth")), True)
check("35 or more titles", len(titles) >= 35, True)
check("20 or more looks only an achievement gives", len(earned) >= 20, True)
check("every earned look names a real achievement", [c[0] for c in earned if c[5] not in keys], [])
check("earned looks cost nothing; bought ones cost something", all((c[3] == 0) == (len(c) > 5) for c in fa.COSMETICS), True)
check("every unlock in ACH_UNLOCKS is a real look for that key", all(fa.COSMETIC_BY_ID[i]["via"] == k for k, ids in fa.ACH_UNLOCKS.items() for i in ids), True)
check("every earned look is handed out by its achievement", all(c[0] in fa.ACH_UNLOCKS.get(c[5], ()) for c in earned), True)
check("Millionaire and Billionaire", (fa.COSMETIC_BY_ID["t-millionaire"]["price"], fa.COSMETIC_BY_ID["t-billionaire"]["price"]), (1000000, 1000000000))
check("new looks have CSS", all(("cos-%s" % i) in CSS for i in ("b-immortal", "f-diamond", "x-crown")), True)
sale, _ = fa.featured_today("2026-09-20")
check("sale never holds an earned look or a 500k+ title", all(v["was"] < fa.FEATURED_MAX_PRICE and not (v["kind"] == "cos" and fa.COSMETIC_BY_ID[v["key"]]["via"]) for v in sale.values()), True)

print("\n--- new facts drive new achievements ---")
cn = sqlite3.connect(fa.DB_PATH)
st = {a["key"]: a for a in fa.ach_status(cn.cursor(), OWN)}
cn.close()
check("games 150 -> Committed done, Lifer 150/500", (st["games-100"]["unlocked"], st["games-500"]["have"], st["games-500"]["need"]), (True, 150, 500))
check("best score 120k -> Big/Huge/High score all done", all(st[k]["unlocked"] for k in ("score-25k", "score-50k", "score-60k")), True)
check("total 240k -> A million 240,000/1,000,000", (st["total-1m"]["have"], st["total-1m"]["unlocked"]), (240000, False))
check("deaths 150 -> Respawner done, Phoenix 150/500", (st["deaths-100"]["unlocked"], st["deaths-500"]["have"]), (True, 150))
check("three regions -> Globetrotter", st["regions-3"]["unlocked"], True)
check("8 days with a win -> week yes, month 8/30", (st["days-7"]["unlocked"], st["days-30"]["have"]), (True, 8))
check("6 friends -> Friendly yes, Popular 6/20", (st["friends-5"]["unlocked"], st["friends-20"]["have"]), (True, 6))
check("earned 152k -> Well paid yes, Self-made no", (st["earned-100k"]["unlocked"], st["earned-500k"]["unlocked"]), (True, False))
check("120 wins -> Veteran ready with its title listed", (st["wins-100"]["ready"], [u["id"] for u in st["wins-100"]["unlock_items"]]), (True, ["t-centurion"]))
check("the officer title waits on the Officer achievement", [u["id"] for u in st["clan-officer"]["unlock_items"]], ["t-commander"])

print("\n--- earned looks are not for sale ---")
r = app.post("/shop/buy", json={"item": "t-centurion"}).get_json()
check("cannot buy Centurion", (r["ok"], "not for sale" in r["message"]), (False, True))
r = app.post("/shop/equip", json={"item": "t-centurion"}).get_json()
check("cannot wear it before earning it", r["ok"], False)
h = app.get("/shop").get_data(as_text=True)
tile = h.split('data-item="t-centurion"')[1].split("</div>")[0]
check("shop tile says which achievement earns it", ("Earned:" in tile) and ("Veteran" in tile) and (">Earn it<" in tile), True)
tile = h.split('data-item="t-billionaire"')[1].split("</div>")[0]
check("Billionaire priced at a billion", "1,000,000,000" in tile, True)
h = app.get("/achievements").get_data(as_text=True)
check("achievements page lists the title an achievement gives", ('<span class="cost earned">Centurion</span>' in h) and ("effect <b>Crown</b>" in h) and ("banner <b>Immortal</b>" in h), True)

print("\n--- claiming hands the look over ---")
b0 = q("SELECT COALESCE(gems,0) FROM players WHERE norm_name=?", OWN)[0][0]
r = app.post("/achievements/claim", json={"key": "wins-100"}).get_json()
check("Veteran claimed: gems + Centurion", (r["ok"], r.get("unlocked"), "Unlocked: Centurion" in r["message"]), (True, ["Centurion"], True))
check("gems moved, and the unlock row is worth nothing", (q("SELECT COALESCE(gems,0) FROM players WHERE norm_name=?", OWN)[0][0] - b0, q("SELECT amount FROM gem_ledger WHERE owner=? AND reason='unlock' AND ref='cos-t-centurion'", OWN)), (2500, [(0,)]))
r = app.post("/shop/equip", json={"item": "t-centurion"}).get_json()
check("now it can be worn", (r["ok"], r["worn"].get("title")), (True, "t-centurion"))
fa._COS_CACHE["ts"] = 0.0
h = app.get("/").get_data(as_text=True)
check("home shows the earned chip in cyan", '<span class="cost earned">Centurion</span>' in h, True)
h = app.get("/player/Owner%20One").get_data(as_text=True)
check("profile too", 'class="cost earned">Centurion</span>' in h, True)
r = app.post("/achievements/claim", json={"key": "wins-100"}).get_json()
check("claiming again does nothing", r["ok"], False)
r = app.post("/achievements/claim", json={"all": True}).get_json()
check("claim all pays the rest and hands over every look due", (r["ok"], "t-commander" in fa.owned_cosmetics(sqlite3.connect(fa.DB_PATH).cursor(), OWN), "t-globetrotter" in fa.owned_cosmetics(sqlite3.connect(fa.DB_PATH).cursor(), OWN)), (True, True, True))
cn = sqlite3.connect(fa.DB_PATH)
st = {a["key"]: a for a in fa.ach_status(cn.cursor(), OWN)}
cn.close()
check("Dressed up still means BOUGHT (unlocks do not count)", st["cos-first"]["unlocked"], False)
check("Everything counts only what the shop sells", st["cos-all"]["need"], sum(1 for c in fa.COSMETICS if len(c) <= 5))

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
