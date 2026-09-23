# -*- coding: utf-8 -*-
"""9.38.2 + 9.39.1: the phone tab bar reaches every tab, achievement cards
line up, a bought look shows at once, and Spotlight is a banner that never
touches the ranking."""
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
TMP = tempfile.mkdtemp(prefix="align")
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
for tag, sub in (("WEAK", "sub:owner"), ("STRONG", "sub:o2")):
    c.execute("INSERT INTO clans(tag, created_by, created_at, bio, region) VALUES (?,?,?,?,?)",
              (tag, sub, "2026-09-01 00:00:00", "We play most evenings.", "america"))
    c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", (sub, tag, "leader"))
for i in range(4):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, clan) VALUES (?,?,?,?,?,?)", ("W%d" % i, "W%d" % i, 1200, 5, 5, "WEAK"))
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, clan) VALUES (?,?,?,?,?,?)", ("S%d" % i, "S%d" % i, 2200, 25, 5, "STRONG"))
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)",
          ("Owner One", N("Owner One"), 1500, 120, 20, "sub:owner", "WEAK"))
fa.gem_grant(c, "clan", "WEAK", 40000, "backfill", "v1")
cn.commit()
cn.close()

owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True

print("\n--- the phone tab bar reaches everything ---")
h = owner.get("/").get_data(as_text=True)
css = h.split("<style>")[1].split("</style>")[0] if "<style>" in h else h
check("the strip scrolls sideways on a phone", ".tabs{overflow-x:auto;overflow-y:hidden" in css, True)
check("the menu button is pinned at its right end", ".tabmore{position:sticky;right:0" in css, True)
check("the flyout is fixed, so the strip cannot clip it", (".tabmenu{position:fixed" in css) and ("bottom:calc(62px + env(safe-area-inset-bottom))" in css), True)
check("desktop still lets the flyout escape the bar", ".tabs{overflow:visible}" in css, True)

print("\n--- achievement cards ---")
h = owner.get("/achievements").get_data(as_text=True)
check("cards stretch to one height in a row", ".ach{display:flex;gap:12px;align-items:stretch" in h, True)
check("the body fills the card", ".ach .body{min-width:0;flex:1;display:flex;flex-direction:column}" in h, True)
check("the foot is pushed to the bottom, so Claim buttons share a line", (".achfoot{margin-top:auto" in h) and ('<span class="achfoot">' in h), True)
check("the pay line wraps inside the card", ".ach .pay{display:flex;flex-wrap:wrap" in h, True)

print("\n--- Spotlight is a banner, and never touches the ranking ---")
fa.clan_cos_map()                      # warm the cache with no perks, like a worker would
h = owner.get("/clans").get_data(as_text=True)
first = h.split("<tbody>")[1].split("</tbody>")[0].split("<tr")[1]
check("before buying, the stronger clan leads", "/clan/STRONG" in first, True)
r = owner.post("/clan/shop/buy", json={"clan": "WEAK", "item": "perk-spotlight"}).get_json()
check("bought", r["ok"], True)
fa._CLAN_COS_CACHE["ts"] = fa.time.time()      # pretend another worker holds a stale cache
h = owner.get("/clans").get_data(as_text=True)
rows = h.split("<tbody>")[1].split("</tbody>")[0].split("<tr")
check("the table order is untouched - the stronger clan still leads", "/clan/STRONG" in rows[1], True)
check("the clan that paid stays where it ranks", "/clan/WEAK" in rows[2], True)
check("no badge in the table saying a clan paid", "Spotlight" in h.split("<tbody>")[1], False)
check("a Featured clan banner instead, despite the stale cache",
      ('class="featc' in h) and ("Featured clan" in h) and ('href="/clan/WEAK"' in h.split('class="featc')[1]), True)
check("the banner carries the clan's numbers", ("<b>5</b> members" in h) and ("average skill" in h), True)
h = owner.get("/leaderboard").get_data(as_text=True)
check("and one on the leaderboard", ('class="featc' in h) and ("Featured clan" in h), True)
stranger = fa.app.test_client()
h = stranger.get("/clans").get_data(as_text=True)
rows = h.split("<tbody>")[1].split("</tbody>")[0].split("<tr")
check("a visitor sees the true order and no banner", ("/clan/STRONG" in rows[1]) and ("featc" not in h) and ("Featured clan" not in h), True)
check("nor on their leaderboard", "featc" in stranger.get("/leaderboard").get_data(as_text=True), False)
check("Recruiting is still a label on the row", 'perk-recruit' in io.open("templates/clans.html", encoding="utf-8").read(), True)

print("\n--- both clan pages read their looks live too ---")
r = owner.post("/clan/shop/buy", json={"clan": "WEAK", "item": "ct-neon"}).get_json()
fa._CLAN_COS_CACHE["ts"] = fa.time.time()
h = owner.get("/clan/WEAK").get_data(as_text=True)
check("the tag look shows at once on the clan page", (r["ok"], 'class="chtag cos-ct-neon"' in h), (True, True))
check("the clan's own band no longer brags that it paid", "Spotlight" in h, False)
h = owner.get("/myclan").get_data(as_text=True)
check("and on Your clan", "cos-ct-neon" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
