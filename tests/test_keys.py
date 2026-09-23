# -*- coding: utf-8 -*-
"""Tester keys: one per person, isolated test accounts, revocable (9.40.0)."""
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
TMP = tempfile.mkdtemp(prefix="keys")
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
cn.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
           ("Owner One", N("Owner One"), 1700, 20, 5, "sub:owner"))
cn.execute("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
           ("Real Player", N("Real Player"), 1600, 30, 10))
cn.commit()
cn.close()

owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"


def new_key(label, days=14):
    r = owner.post("/dev/keys", data={"label": label, "days": str(days)})
    h = r.get_data(as_text=True)
    assert '<code id="newkey">' in h, "no key shown"
    return h.split('<code id="newkey">')[1].split("</code>")[0].strip()


print("\n--- only the owner makes keys ---")
for cl, who in ((fa.app.test_client(), "a stranger"), ):
    check("%s cannot open the page" % who, cl.get("/dev/keys").status_code, 404)
    check("%s cannot make a key" % who, cl.post("/dev/keys", data={"label": "x"}).status_code, 404)
check("the owner can", owner.get("/dev/keys").status_code, 200)

print("\n--- a key is shown once and stored only as a hash ---")
k1 = new_key("niwu")
check("it looks like a key", k1.startswith(fa.PREVIEW_KEY_PREFIX + "-") and len(k1) > 24, True)
rows = q("SELECT label, key_hash, uses, revoked_at FROM preview_keys")
check("one row, labelled, never holding the key itself", (len(rows), rows[0][0], k1 in rows[0][1], rows[0][2], rows[0][3]), (1, "niwu", False, 0, None))
h = owner.get("/dev/keys").get_data(as_text=True)
check("re-opening the page does not show it again", k1 in h, False)
check("but it lists the key as live", ("niwu" in h) and (">live<" in h), True)

print("\n--- a tester gets in, and gets their own account ---")
t1 = fa.app.test_client()
check("the door is a form", t1.get("/dev/preview").status_code, 200)
check("a wrong key is a 404, which does not confirm anything exists",
      t1.post("/dev/preview", data={"key": "sbgem-nonsense"}).status_code, 404)
r = t1.post("/dev/preview", data={"key": k1, "elo": 1500, "gems": 25000})
check("the right key lets them in", r.status_code, 302)
with t1.session_transaction() as s:
    check("their session is a preview on their own key", (s.get("preview"), s.get("preview_key"), s.get("google_sub")), (True, 1, "test:sandbox:1"))
check("the key counts the use", q("SELECT uses FROM preview_keys WHERE id=1"), [(1,)])
check("they can see the shop", t1.get("/shop").status_code, 200)
check("and the achievements", t1.get("/achievements").status_code, 200)
h = t1.get("/shop").get_data(as_text=True)
check("with the gems they asked for", "25,000" in h, True)
check("the page tells them it is a test account", ("trying the preview on a test account of your own" in t1.get("/").get_data(as_text=True)) and ("Leave the preview" in t1.get("/").get_data(as_text=True)), True)

k2 = new_key("fafa")
t2 = fa.app.test_client()
t2.post("/dev/preview", data={"key": k2, "elo": 1200, "gems": 900})
with t2.session_transaction() as s:
    check("the second tester is a different account", s.get("google_sub"), "test:sandbox:2")
check("two test accounts exist at once", len(q("SELECT name FROM players WHERE google_sub LIKE 'test:sandbox%'")), 2)
h = t1.get("/shop").get_data(as_text=True)
check("the first tester still has their own gems", "25,000" in h, True)
h = t2.get("/shop").get_data(as_text=True)
check("and the second has theirs", "900" in h, True)

print("\n--- test accounts stay off the real board ---")
h = fa.app.test_client().get("/leaderboard").get_data(as_text=True)
board = h.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in h else h
check("no test account on the leaderboard", "SANDBOX" in board.upper(), False)
check("the real player is", "Real Player" in board, True)

print("\n--- revoking takes it back at once ---")
r = owner.post("/dev/keys/1/revoke")
check("the owner revokes it", r.status_code, 302)
check("a stranger cannot revoke", fa.app.test_client().post("/dev/keys/2/revoke").status_code, 404)
check("the row is marked revoked", q("SELECT revoked_at IS NOT NULL FROM preview_keys WHERE id=1"), [(1,)])
check("their test account is cleaned up", q("SELECT COUNT(*) FROM players WHERE google_sub='test:sandbox:1'"), [(0,)])
check("the shop shuts for them", t1.get("/shop").status_code, 404)
check("the other tester is untouched", t2.get("/shop").status_code, 200)
check("the revoked key no longer opens the door", t1.post("/dev/preview", data={"key": k1}).status_code, 404)

print("\n--- expiry ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE preview_keys SET expires_at = '2020-01-01 00:00:00' WHERE id = 2")
cn.commit()
cn.close()
fa._PREVIEW_OK_CACHE.clear()
check("an expired key stops working mid-session", t2.get("/shop").status_code, 404)
check("and will not let anyone back in", fa.app.test_client().post("/dev/preview", data={"key": k2}).status_code, 404)
h = owner.get("/dev/keys").get_data(as_text=True)
check("the page shows both states", (">revoked<" in h) and (">expired<" in h), True)

print("\n--- leaving ---")
k3 = new_key("someone", days=7)
t3 = fa.app.test_client()
t3.post("/dev/preview", data={"key": k3, "gems": 5000})
check("in", t3.get("/shop").status_code, 200)
t3.post("/dev/restore")
check("out, and the preview is gone", t3.get("/shop").status_code, 404)
check("their test account went with them", q("SELECT COUNT(*) FROM players WHERE google_sub='test:sandbox:3'"), [(0,)])
check("the owner's own account was never touched", q("SELECT COUNT(*) FROM players WHERE google_sub='sub:owner'"), [(1,)])

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
