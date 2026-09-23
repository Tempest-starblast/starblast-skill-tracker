# -*- coding: utf-8 -*-
"""Starting a clan: a key from the owner, gems, or the old approval - and a
new clan starts empty whichever way it was started (9.41.0)."""
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
TMP = tempfile.mkdtemp(prefix="clanstart")
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
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
          ("Owner One", N("Owner One"), 1700, 20, 5, "sub:owner"))
for nm, sb in (("Rich One", "sub:rich"), ("Poor One", "sub:poor"), ("Keyed One", "sub:key"),
               ("Approved One", "sub:appr")):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
              (nm, N(nm), 1400, 10, 10, sb))
# four unowned names already playing under [COV] - the roster a tag used to buy
for i in range(4):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
              ("[COV] Vet%d" % i, N("[COV] Vet%d" % i), 1800, 40, 10))
fa.gem_grant(c, "player", N("Rich One"), 60000, "backfill", "v1")
fa.gem_grant(c, "player", N("Poor One"), 900, "backfill", "v1")
c.execute("INSERT INTO clan_leader_requests(google_sub, handle, tag, note, created_at, status) "
          "VALUES (?,?,?,?,?,'approved')", ("sub:appr", "appr", "APR", "", "2026-09-01 00:00:00"))
cn.commit()
cn.close()


def client(sub, preview=False):
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        s["google_sub"] = sub
        if preview:
            s["preview"] = True
    return cl


def start(cl, tag, key=None):
    body = {"tag": tag}
    if key is not None:
        body["key"] = key
    r = cl.post("/clan/create", json=body)
    return r.status_code, r.get_json()


owner = client("sub:owner")

print("\n--- only the owner makes clan keys ---")
check("a stranger cannot open the page", fa.app.test_client().get("/dev/clankeys").status_code, 404)
check("a signed-in player cannot either", client("sub:rich").get("/dev/clankeys").status_code, 404)
check("nor make one", client("sub:rich").post("/dev/clankeys", data={"label": "x"}).status_code, 404)
check("the owner can", owner.get("/dev/clankeys").status_code, 200)


def new_key(label, uses=1, days=90):
    h = owner.post("/dev/clankeys", data={"label": label, "uses": str(uses),
                                          "days": str(days)}).get_data(as_text=True)
    assert '<code id="newkey">' in h, "no key shown"
    return h.split('<code id="newkey">')[1].split("</code>")[0].strip()


print("\n--- the key is shown once, stored as a hash ---")
k1 = new_key("tempest")
check("it looks like a clan key", k1.startswith(fa.CLAN_KEY_PREFIX + "-") and len(k1) > 24, True)
row = q("SELECT label, key_hash, uses, max_uses FROM clan_keys")[0]
check("labelled, one use, never holding the key itself", (row[0], k1 in row[1], row[2], row[3]),
      ("tempest", False, 0, 1))
h = owner.get("/dev/clankeys").get_data(as_text=True)
check("re-opening does not show it again", k1 in h, False)
check("it is listed as live", ("tempest" in h) and (">live<" in h), True)

print("\n--- without a key, and without gems visible, nothing changed ---")
st, d = start(client("sub:rich"), "[NOPE]")
check("an unapproved player is still told to ask", (st, "approved to run a clan" in d["message"]), (403, True))
check("no clan was made", q("SELECT COUNT(*) FROM clans WHERE tag='NOPE'"), [(0,)])
check("and no gems were taken", fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Rich One")), 60000)

print("\n--- a key starts one, at once, with no approval ---")
st, d = start(client("sub:key"), "[COV]", k1)
check("it worked", (st, d["ok"], d["keyed"], d["paid"]), (200, True, True, 0))
check("the clan exists and they run it", (q("SELECT created_by FROM clans WHERE tag='COV'"),
                                          q("SELECT google_sub FROM clan_admins WHERE clan='COV'")),
      ([("sub:key",)], [("sub:key",)]))
check("the key is used up", q("SELECT uses, used_tag FROM clan_keys WHERE id=1"), [(1, "COV")])
check("and will not start a second clan", start(client("sub:key"), "[COV2]", k1)[1]["ok"], False)

print("\n--- a new clan starts EMPTY ---")
check("the four players wearing the tag did NOT join",
      q("SELECT COUNT(*) FROM players WHERE clan='COV' AND google_sub IS NULL"), [(0,)])
check("the message says so and counts them",
      ("starts empty" in d["message"], d["wearing_count"], "add them from Your clan" in d["message"]),
      (True, 4, True))
check("their names come back so the admin can see who", len(d["wearing"]), 4)
check("the admin's own name is on the roster",
      q("SELECT COUNT(*) FROM players WHERE clan='COV' AND google_sub='sub:key'"), [(1,)])

print("\n--- a bad key is refused, and says nothing about which keys exist ---")
st, d = start(client("sub:rich"), "[FAKE]", "sbclan-nonsense")
check("refused", (st, d["ok"], d.get("bad_key")), (400, False, True))
check("no clan", q("SELECT COUNT(*) FROM clans WHERE tag='FAKE'"), [(0,)])

print("\n--- paying, when the economy is visible to them ---")
rich = client("sub:rich", preview=True)
st, d = start(rich, "[VEGA]")
check("it worked and said what it cost", (st, d["ok"], d["paid"]), (200, True, fa.CLAN_START_COST))
check("the gems are gone, once",
      fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Rich One")),
      60000 - fa.CLAN_START_COST)
check("the ledger says what it was for",
      q("SELECT amount, reason FROM gem_ledger WHERE owner=? AND reason='clan-start'", N("Rich One")),
      [(-fa.CLAN_START_COST, "clan-start")])
check("this clan starts empty too", q("SELECT COUNT(*) FROM players WHERE clan='VEGA'"), [(1,)])

poor = client("sub:poor", preview=True)
st, d = start(poor, "[ORION]")
check("short of gems: refused, and told the price and the balance",
      (st, d["ok"], "{:,}".format(fa.CLAN_START_COST) in d["message"], "900" in d["message"]),
      (403, False, True, True))
check("nothing was taken",
      fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Poor One")), 900)
check("and no clan", q("SELECT COUNT(*) FROM clans WHERE tag='ORION'"), [(0,)])

print("\n--- money does not buy a second tag ---")
st, d = start(rich, "[VEGA2]")
check("a second one needs the owner, not more gems",
      (d["ok"], "own request" in d["message"]), (False, True))
check("nothing spent on the refusal",
      fa.gem_balance(sqlite3.connect(fa.DB_PATH).cursor(), "player", N("Rich One")),
      60000 - fa.CLAN_START_COST)

print("\n--- the old way still works, and still costs nothing ---")
st, d = start(client("sub:appr"), "[APR]")
check("an approved leader claims their tag", (st, d["ok"], d["paid"]), (200, True, 0))

print("\n--- revoking ---")
k2 = new_key("someone", uses=2)
check("a stranger cannot revoke", fa.app.test_client().post("/dev/clankeys/2/revoke").status_code, 404)
check("the owner can", owner.post("/dev/clankeys/2/revoke").status_code, 302)
check("the key stops working", start(client("sub:poor"), "[GONE]", k2)[1]["ok"], False)
h = owner.get("/dev/clankeys").get_data(as_text=True)
check("the page shows both states", (">revoked<" in h) and (">used up<" in h), True)

print("\n--- the page tells the visitor how to get in ---")
h = fa.app.test_client().get("/clans").get_data(as_text=True)
check("the key box is there for everyone", ('id="startKey"' in h) and ('id="startTag"' in h), True)
check("but the price is not, while the economy is hidden",
      ("{:,}".format(fa.CLAN_START_COST) in h) or ("gems" in h.lower()), False)
h = owner.get("/clans").get_data(as_text=True)
check("the owner sees the price", "{:,}".format(fa.CLAN_START_COST) in h, True)
check("and a confirm before spending", "cannot be undone" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
