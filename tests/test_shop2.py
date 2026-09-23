# -*- coding: utf-8 -*-
"""9.38.1: one shop (the clan tab lives on /shop), bought looks go on at once,
the profile shows gems spent and the clan role, never a balance."""
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
TMP = tempfile.mkdtemp(prefix="shop2")
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


N = fa.normalize_name
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", ("TST", "sub:owner", "2026-09-01 00:00:00"))
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", ("sub:owner", "TST", "leader"))
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", ("sub:m1", "TST", "moderator"))
for name, sub, tag in (("Owner One", "sub:owner", "TST"), ("Mod One", "sub:m1", "TST"), ("Alpha", "sub:a", "TST"), ("Loner", "sub:l", None)):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)", (name, N(name), 1500, 8, 4, sub, tag))
fa.gem_grant(c, "clan", "TST", 30000, "backfill", "v1")
fa.gem_grant(c, "player", N("Alpha"), 9000, "backfill", "v1")
fa.gem_charge(c, N("Alpha"), 2500, "purchase", "cos-n-fire")
fa.gem_charge(c, N("Alpha"), 800, "purchase", "cos-t-ace")
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


owner, mod, alpha, stranger = client("sub:owner"), client("sub:m1"), client("sub:a"), client(None)

print("\n--- one shop ---")
h = owner.get("/shop").get_data(as_text=True)
check("the leader's Shop has a clan tab", ('data-panel="clan"' in h) and ('data-citem="cb-nebula"' in h) and ('data-citem="perk-host"' in h) and ('data-citem="cs-702"' in h), True)
check("it names the clan and its treasury", ("TST clan" in h) and ("<b>30,000</b> gems" in h), True)
check("copy says header, not band", ("band" in h.lower().split('data-panel="clan"')[1][:3000]), False)
h = alpha.get("/shop").get_data(as_text=True)
check("a plain member's Shop has no clan tab", 'data-panel="clan"' in h, False)
h = mod.get("/shop").get_data(as_text=True)
check("nor a moderator's", 'data-panel="clan"' in h, False)
h = owner.get("/myclan").get_data(as_text=True)
check("Your clan has no shop tab any more, and points at the Shop", ('data-panel="shop"' in h, 'href="/shop#clan"' in h), (False, True))

print("\n--- bought is worn ---")
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "cs-201"}).get_json()
check("buying the emblem puts it on", (r["ok"], "on now" in r["message"], json.loads(q("SELECT cosmetics FROM clans WHERE tag='TST'")[0][0]).get("emblem")), (True, True, "cs-201"))
fa._CLAN_COS_CACHE["ts"] = 0.0
h = owner.get("/clan/TST").get_data(as_text=True)
check("...and the clan page shows it at once", 'class="chemb"' in h, True)
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "ct-neon"}).get_json()
check("a tag look too", (r["ok"], json.loads(q("SELECT cosmetics FROM clans WHERE tag='TST'")[0][0]).get("tag")), (True, "ct-neon"))
h = owner.get("/shop").get_data(as_text=True)
tile = h.split('data-citem="ct-neon"')[1].split("</div>")[0]
check("the tile says it is on", "On now" in tile, True)
r = owner.post("/clan/shop/buy", json={"clan": "TST", "item": "perk-recruit"}).get_json()
check("a perk still just runs", (r["ok"], "runs until" in r["message"]), (True, True))

print("\n--- tiles line up ---")
check("shop tiles anchor price + button at the bottom", ('<span class="buy">' in h) and (".ship .buy{margin-top:auto" in h) and (".ship .why{" in h and "flex:1}" in h), True)
h = owner.get("/achievements").get_data(as_text=True)
check("the unlock plus is a chip-height box", ('<span class="plus">+</span>' in h) and (".ach .unl .plus,.ach .unl .ulook{display:inline-flex;align-items:center;height:20px" in h), True)

print("\n--- the profile ---")
h = owner.get("/player/Alpha").get_data(as_text=True)
stats = h.split('class="pbox-stats"')[1].split("</div>\n  </div>")[0]
check("owner sees gems spent (3,300), never a balance", ("Gems spent" in stats) and ("3,300" in stats) and ("5,700" not in h), True)
check("clan stat with the role", ("TST" in stats) and ("Member" in stats), True)
h = owner.get("/player/Owner%20One").get_data(as_text=True)
check("leader's profile says Leader", "&middot; Leader" in h, True)
h = owner.get("/player/Mod%20One").get_data(as_text=True)
check("moderator's says Moderator", "&middot; Moderator" in h, True)
h = stranger.get("/player/Alpha").get_data(as_text=True)
check("a visitor sees the clan but no gem figure", ("Gems spent" in h, ">TST</a>" in h), (False, True))
h = stranger.get("/player/Loner").get_data(as_text=True)
check("no clan: a dash", "&mdash;" in h.split("Clan</div>")[1][:120], True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
