# -*- coding: utf-8 -*-
"""The preview key: sees everything the owner sees, can do nothing the owner
can do, and leaves nothing behind. Runs against a scratch database."""
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
TMP = tempfile.mkdtemp(prefix="prevtest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.init_db()
fa.app.config["TESTING"] = True
OWNER = "discord:owner-under-test"
fa.OWNER_SUBS = {OWNER}
KEY = "a-very-long-preview-key-for-tests-only-0123456789"

cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM gem_ledger")
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) "
           "VALUES ('REALGUY','REALGUY',1300,5,5,'sub:real')")
cn.commit()
cn.close()

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def q(sql, args=()):
    c = sqlite3.connect(fa.DB_PATH)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


print("\n--- no key file: the route does not exist ---")
fa.PREVIEW_KEY = None
cl = fa.app.test_client()
check("GET is 404", cl.get("/dev/preview").status_code, 404)
check("POST is 404", cl.post("/dev/preview", json={"key": "anything"}).status_code, 404)

print("\n--- with a key ---")
fa.PREVIEW_KEY = KEY
cl = fa.app.test_client()
check("GET is the form", cl.get("/dev/preview").status_code, 200)
check("the form never puts the key in a URL", 'method="post"' in cl.get("/dev/preview").get_data(as_text=True), True)
check("a wrong key is 404, not 403 - nothing to confirm", cl.post("/dev/preview", json={"key": "wrong"}).status_code, 404)
check("an empty key is 404", cl.post("/dev/preview", json={}).status_code, 404)
check("no sandbox row was made by the failures", q("SELECT COUNT(*) FROM players WHERE google_sub=?", (fa.SANDBOX_SUB,))[0][0], 0)

r = cl.post("/dev/preview", json={"key": KEY, "elo": 1750, "gems": 12345})
check("the right key enters", r.status_code, 200)
with cl.session_transaction() as s:
    check("the session is the sandbox", s.get("google_sub"), fa.SANDBOX_SUB)
    check("it is marked preview", bool(s.get("preview")), True)
    check("it is NOT an owner stash", s.get("dev_real_owner"), None)
row = q("SELECT elo, gems FROM players WHERE google_sub=?", (fa.SANDBOX_SUB,))
check("sandbox row exists with the rating", row and abs(row[0][0] - 1750) < 0.01, True)
check("and the gems asked for, through the ledger", row and row[0][1] == 12345, True)
check("ledger row is reason 'sandbox'", q("SELECT COUNT(*) FROM gem_ledger WHERE reason='sandbox'")[0][0], 1)

print("\n--- it sees the unreleased surfaces ---")
h = cl.get("/").get_data(as_text=True)
check("/ is the home", "Recent form" in h and "Achievements" in h, True)
check("the balance shows", "12,345" in h, True)
check("/shop is 200", cl.get("/shop").status_code, 200)
check("/achievements is 200", cl.get("/achievements").status_code, 200)
me = cl.get("/me").get_json()
check("/me carries gems", me.get("gems"), 12345)
check("/me has Shop and Achievements", {n.get("id") for n in me.get("nav", [])} >= {"achTab", "shopTab"}, True)
check("the banner shows it is a test account",
      "trying the preview on a test account of your own" in h, True)

print("\n--- but it is not an owner ---")
check("is_owner is false in /me", me.get("is_owner"), False)
check("no Owner section in the menu", any(n.get("id") == "ownerSec" for n in me.get("nav", [])), False)
check("/dev/actas is refused", cl.post("/dev/actas", json={"mode": "new"}).status_code, 403)
_m = cl.get("/dev/merges")
check("/dev/merges is refused (bounced to /, or denied)",
      _m.status_code in (403, 404) or (_m.status_code == 302 and _m.headers.get("Location", "").endswith("/")), True)
check("...and shows no merge requests", "merge_requests" in _m.get_data(as_text=True) or "Approve" in _m.get_data(as_text=True), False)

print("\n--- it can use the shop like a player ---")
r = cl.post("/shop/buy", json={"code": 202}).get_json()
check("a purchase lands", r.get("ok"), True)
check("balance debited", q("SELECT gems FROM players WHERE google_sub=?", (fa.SANDBOX_SUB,))[0][0],
      12345 - fa.SHIP_TIER_PRICE[2])

print("\n--- and leaves nothing behind ---")
cl.post("/dev/restore")
check("sandbox row gone", q("SELECT COUNT(*) FROM players WHERE google_sub=?", (fa.SANDBOX_SUB,))[0][0], 0)
check("its ledger rows gone too", q("SELECT COUNT(*) FROM gem_ledger WHERE reason IN ('sandbox','purchase')")[0][0], 0)
with cl.session_transaction() as s:
    check("signed out", s.get("google_sub"), None)
    check("preview flag gone", s.get("preview"), None)
check("/shop is 404 again", cl.get("/shop").status_code, 404)
check("the real player was never touched", q("SELECT COUNT(*) FROM players WHERE norm_name='REALGUY'")[0][0], 1)

print("\n--- the owner's own switch still works, and clears a preview flag ---")
cl = fa.app.test_client()
with cl.session_transaction() as s:
    s["google_sub"] = OWNER
    s["preview"] = True                       # a stale flag from an earlier life
cl.post("/dev/actas", json={"mode": "account", "elo": 1400})
with cl.session_transaction() as s:
    check("owner stash set", s.get("dev_real_owner"), OWNER)
    check("preview flag cleared by the owner's switch", s.get("preview"), None)
cl.post("/dev/restore")
with cl.session_transaction() as s:
    check("owner restored", s.get("google_sub"), OWNER)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
