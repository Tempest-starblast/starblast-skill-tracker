# -*- coding: utf-8 -*-
"""Access keys: the unreleased half of the site, on your own account, with
test gems - and the event announcement feed (9.50.0)."""
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
TMP = tempfile.mkdtemp(prefix="access")
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
fa._load_api_keys = lambda: {"testkey"}
KEY = {"X-API-Key": "testkey"}

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


def q(sql, *a):
    cn = sqlite3.connect(fa.DB_PATH)
    r = cn.execute(sql, a).fetchall()
    cn.close()
    return r


cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
          ("Owner One", N("Owner One"), 1700, 20, 5, "sub:owner"))
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
          ("Real Tester", N("Real Tester"), 1450, 30, 25, "sub:real"))
cn.commit()
cn.close()

owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"


def mint(label, kind):
    h = owner.post("/dev/keys", data={"label": label, "days": "14", "kind": kind}).get_data(as_text=True)
    assert '<code id="newkey">' in h, "no key shown"
    return h.split('<code id="newkey">')[1].split("</code>")[0].strip()


print("\n--- the owner can mint either kind ---")
sand = mint("sandbox one", "sandbox")
acc = mint("access one", "access")
check("both look like keys", all(k.startswith(fa.PREVIEW_KEY_PREFIX + "-") for k in (sand, acc)), True)
check("and are stored with their kind",
      sorted(r[0] for r in q("SELECT COALESCE(kind,'sandbox') FROM preview_keys")),
      ["access", "sandbox"])
h = owner.get("/dev/keys").get_data(as_text=True)
check("the page says which is which", ("as themselves" in h) and ("test account" in h), True)
cn = sqlite3.connect(fa.DB_PATH)
_kid, _plain = fa.preview_key_make(cn.cursor(), "odd one", 7, "sub:owner", "nonsense")
cn.commit()
cn.close()
check("a kind nobody has heard of falls back to a test account",
      q("SELECT COALESCE(kind,'sandbox') FROM preview_keys WHERE id = ?", _kid), [("sandbox",)])

print("\n--- a sandbox key still works exactly as it did ---")
t1 = fa.app.test_client()
r = t1.post("/dev/preview", data={"key": sand, "elo": 1500, "gems": 4000})
check("it lets them in", r.status_code, 302)
with t1.session_transaction() as s:
    check("on a test account of their own",
          (s.get("preview"), s.get("preview_kind"), str(s.get("google_sub")).startswith("test:sandbox")),
          (True, "sandbox", True))

print("\n--- an access key opens it on their OWN account ---")
t2 = fa.app.test_client()
r = t2.post("/dev/preview", data={"key": acc})
check("without being signed in it asks them to sign in first", r.status_code, 200)
check("and does not let them in", b"need_signin" in r.data or b"Sign in" in r.data, True)
with t2.session_transaction() as s:
    s["google_sub"] = "sub:real"
r = t2.post("/dev/preview", data={"key": acc})
check("signed in, it lets them in", r.status_code, 302)
with t2.session_transaction() as s:
    check("they are still themselves",
          (s.get("google_sub"), s.get("preview"), s.get("preview_kind")),
          ("sub:real", True, "access"))
check("their own record is untouched",
      q("SELECT elo, wins, losses FROM players WHERE google_sub='sub:real'"), [(1450, 30, 25)])
check("the shop opens for them", t2.get("/shop").status_code, 200)
check("so do the events", t2.get("/events").status_code, 200)

print("\n--- with test money to spend ---")
check("a million of it", fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Real Tester")),
      fa.PREVIEW_CREDIT)
check("in one labelled row",
      q("SELECT reason, amount FROM gem_ledger WHERE owner = ?", N("Real Tester")),
      [("preview-credit", fa.PREVIEW_CREDIT)])
r = t2.post("/shop/buy", json={"code": 202}).get_json()
check("they can actually buy something", r["ok"], True)
t2.post("/dev/preview", data={"key": acc})
check("redeeming again does not print a second million",
      fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Real Tester")),
      fa.PREVIEW_CREDIT - fa.SHIP_TIER_PRICE[2])

print("\n--- the banner tells them the truth ---")
h = t2.get("/").get_data(as_text=True)
check("early access, as yourself", "early access as yourself" in h, True)
check("and that what they buy is real", "buy, win and claim is real" in h, True)

print("\n--- hiding it again leaves their account alone ---")
t2.post("/dev/restore")
with t2.session_transaction() as s:
    check("still signed in as themselves, just without the preview",
          (s.get("google_sub"), s.get("preview")), ("sub:real", None))
check("their player row is still there",
      q("SELECT COUNT(*) FROM players WHERE google_sub='sub:real'"), [(1,)])
check("and the shop is shut again", t2.get("/shop").status_code, 404)

print("\n--- revoking an access key touches nothing of theirs ---")
kid = q("SELECT id FROM preview_keys WHERE COALESCE(kind,'sandbox')='access'")[0][0]
owner.post("/dev/keys/%d/revoke" % kid)
check("the key is dead", q("SELECT revoked_at IS NOT NULL FROM preview_keys WHERE id=?", kid), [(1,)])
check("their account survived",
      q("SELECT elo, wins FROM players WHERE google_sub='sub:real'"), [(1450, 30)])
check("the key no longer opens the door",
      fa.app.test_client().post("/dev/preview", data={"key": acc}).status_code, 404)

print("\n--- test money stays out of the real economy figures ---")
cn = sqlite3.connect(fa.DB_PATH)
e = fa.economy_snapshot(cn.cursor())
cn.close()
check("it is not counted as made", e["made"], 0)
check("nor the spending of it - a tester is left out of the figures entirely",
      e["burned"], 0)

print("\n--- the announcement feed ---")
r = fa.app.test_client().get("/api/bot/events/undelivered")
check("needs the key", r.status_code, 401)
ev = owner.post("/dev/events/now", json={"kind": "survival"}).get_json()
fa.app.test_client().post("/api/events/set", headers=KEY, json={
    "event_id": ev["event_id"], "sid": 9100, "addr": "1.2.3.4:9100",
    "link": "https://starblast.io/#9100@1.2.3.4:9100"})
d = fa.app.test_client().get("/api/bot/events/undelivered", headers=KEY).get_json()
live = [x for x in d["events"] if x["what"] == "live"]
check("it offers the lobby to announce", len(live), 1)
check("with the link and the mode",
      ("9100" in live[0]["link"], live[0]["kind"]), (True, "survival"))
fa.app.test_client().post("/api/bot/events/delivered", headers=KEY,
                          json={"done": [{"id": ev["event_id"], "what": "live"}]})
d = fa.app.test_client().get("/api/bot/events/undelivered", headers=KEY).get_json()
check("once posted it is never offered again",
      [x for x in d["events"] if x["what"] == "live" and x["id"] == ev["event_id"]], [])

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
