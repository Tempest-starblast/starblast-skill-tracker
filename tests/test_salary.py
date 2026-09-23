# -*- coding: utf-8 -*-
"""Joining bonuses and asks: paid once, from the treasury, only on the join,
and never more than the treasury has. Runs against a scratch database."""
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
TMP = tempfile.mkdtemp(prefix="saltest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.init_db()
fa.app.config["TESTING"] = True
fa.OWNER_SUBS = {"discord:owner-under-test"}
BOSS, MOD, NEW, NEW2 = "sub:boss", "sub:mod", "sub:new", "sub:new2"

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


def w(sql, args=()):
    """A write. q() reads and closes without committing - fine for SELECTs,
    silently rolled back for anything else, which is how a DELETE that
    looked done left a pending invite behind."""
    c = sqlite3.connect(fa.DB_PATH)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


def seed(treasury=5000):
    cn = sqlite3.connect(fa.DB_PATH)
    c = cn.cursor()
    for t in ("players", "gem_ledger", "clan_admins", "clan_invites"):
        c.execute("DELETE FROM %s" % t)
    c.execute("DELETE FROM clans WHERE tag = 'TST'")
    c.execute("INSERT INTO clans (tag, created_by, created_at, gems) VALUES ('TST','x','2026-01-01',0)")
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) "
              "VALUES ('BOSS','BOSS',1500,10,5,'TST',?,0)", (BOSS,))
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) "
              "VALUES ('MOD','MOD',1200,4,4,'TST',?,0)", (MOD,))
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems) "
              "VALUES ('NEWGUY','NEWGUY',1300,6,6,?,0)", (NEW,))
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems) "
              "VALUES ('NEWGUY2','NEWGUY2',1250,5,7,?,0)", (NEW2,))
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES ('TST',?,'2026-01-01','leader')", (BOSS,))
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES ('TST',?,'2026-01-01','moderator')", (MOD,))
    if treasury:
        fa.gem_grant(c, "clan", "TST", treasury, "backfill", "v1")
    cn.commit()
    cn.close()


def client(sub):
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        s["google_sub"] = sub
    return cl


def treasury():
    return q("SELECT COALESCE(gems,0) FROM clans WHERE tag='TST'")[0][0]


def gems(nn):
    return q("SELECT COALESCE(gems,0) FROM players WHERE norm_name=?", (nn,))[0][0]


def reconciled():
    a = q("SELECT COUNT(*) FROM clans cl WHERE COALESCE(cl.gems,0) != COALESCE((SELECT SUM(amount) FROM gem_ledger g WHERE g.owner_kind='clan' AND g.owner=cl.tag),0)")[0][0]
    b = q("SELECT COUNT(*) FROM players p WHERE COALESCE(p.gems,0) != COALESCE((SELECT SUM(amount) FROM gem_ledger g WHERE g.owner_kind='player' AND g.owner=p.norm_name),0)")[0][0]
    return a + b


print("\n--- an officer invites with a bonus ---")
seed(5000)
r = client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY", "gems": 1200})
check("the invite goes out", r.status_code, 200)
inv = q("SELECT id, gems, status FROM clan_invites WHERE name='NEWGUY' AND direction='invite'")
check("it carries the bonus", inv and inv[0][1] == 1200, True)
check("nothing has moved yet", (treasury(), gems("NEWGUY")), (5000, 0))
inv_id = inv[0][0]

print("\n--- accepting pays, once ---")
r = client(NEW).post("/clan/invite/respond", json={"id": inv_id, "accept": True})
check("accepted", r.status_code, 200)
check("they are in the clan", q("SELECT clan FROM players WHERE norm_name='NEWGUY'")[0][0], "TST")
check("the player got the bonus", gems("NEWGUY"), 1200)
check("the treasury paid it", treasury(), 3800)
check("the message says so", "1,200 gems" in r.get_json()["message"], True)
check("ledger: one salary row each side", q("SELECT COUNT(*) FROM gem_ledger WHERE reason='salary'")[0][0], 2)
r = client(NEW).post("/clan/invite/respond", json={"id": inv_id, "accept": True})
check("accepting again pays nothing more", (gems("NEWGUY"), treasury()), (1200, 3800))
check("balances reconcile with the ledger", reconciled(), 0)

print("\n--- a moderator cannot put treasury money on an invite ---")
r = client(MOD).post("/clan/add", json={"clan": "TST", "name": "NEWGUY2", "gems": 500})
check("refused", r.status_code, 403)
check("no invite made", q("SELECT COUNT(*) FROM clan_invites WHERE name='NEWGUY2'")[0][0], 0)
r = client(MOD).post("/clan/add", json={"clan": "TST", "name": "NEWGUY2"})
check("...but a plain invite from a moderator still works", r.status_code, 200)
w("DELETE FROM clan_invites WHERE name='NEWGUY2'")

print("\n--- a bonus the treasury cannot promise ---")
r = client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY2", "gems": 99999})
check("refused at invite time", r.status_code, 400)
check("the message gives the number", "3,800" in r.get_json()["message"], True)

print("\n--- a bonus the treasury could promise but cannot pay by acceptance time ---")
r = client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY2", "gems": 3000})
check("invite made", r.status_code, 200)
inv2 = q("SELECT id FROM clan_invites WHERE name='NEWGUY2' AND status='pending'")[0][0]
cn = sqlite3.connect(fa.DB_PATH)
fa.gem_clan_charge(cn.cursor(), "TST", 3500, "test-drain", "x")      # treasury -> 300
cn.commit(); cn.close()
r = client(NEW2).post("/clan/invite/respond", json={"id": inv2, "accept": True})
check("acceptance refused", r.status_code, 400)
check("they did not join", q("SELECT clan FROM players WHERE norm_name='NEWGUY2'")[0][0], None)
check("the invite is still open", q("SELECT status FROM clan_invites WHERE id=?", (inv2,))[0][0], "pending")
check("nothing moved", (gems("NEWGUY2"), treasury()), (0, 300))
check("no stray salary rows", q("SELECT COUNT(*) FROM gem_ledger WHERE reason='salary' AND ref=?", ("invite-%d" % inv2,))[0][0], 0)
check("balances reconcile", reconciled(), 0)

print("\n--- an application with an ask ---")
seed(2000)
r = client(NEW2).post("/clan/apply", json={"clan": "TST", "name": "NEWGUY2", "gems": 500})
check("applied", r.status_code, 200)
check("the reply confirms the ask", "500 gems" in r.get_json()["message"], True)
app = q("SELECT id, gems FROM clan_invites WHERE name='NEWGUY2' AND direction='application'")
check("the ask is on the row", app and app[0][1] == 500, True)
app_id = app[0][0]
cn = sqlite3.connect(fa.DB_PATH)
apps = fa.clan_applications(cn.cursor(), "TST")
cn.close()
check("the officer's list shows the ask", apps and apps[0].get("gems"), 500)
r = client(BOSS).post("/clan/application/respond", json={"id": app_id, "accept": True})
j = r.get_json()
check("accepted", r.status_code == 200 and j.get("accepted"), True)
check("the applicant got the ask", gems("NEWGUY2"), 500)
check("the treasury paid it", treasury(), 1500)
check("the message says so", "500 gems" in j["message"], True)
check("balances reconcile", reconciled(), 0)

print("\n--- an ask the treasury cannot cover ---")
seed(400)
r = client(NEW2).post("/clan/apply", json={"clan": "TST", "name": "NEWGUY2", "gems": 900})
app_id = q("SELECT id FROM clan_invites WHERE name='NEWGUY2' AND direction='application'")[0][0]
r = client(BOSS).post("/clan/application/respond", json={"id": app_id, "accept": True})
check("acceptance refused", r.status_code, 400)
check("both numbers are in the message", "900" in r.get_json()["message"] and "400" in r.get_json()["message"], True)
check("still pending", q("SELECT status FROM clan_invites WHERE id=?", (app_id,))[0][0], "pending")
check("they did not join", q("SELECT clan FROM players WHERE norm_name='NEWGUY2'")[0][0], None)
check("nothing moved", (gems("NEWGUY2"), treasury()), (0, 400))
r = client(BOSS).post("/clan/application/respond", json={"id": app_id, "accept": False})
check("declining works and pays nothing", (r.status_code, treasury()), (200, 400))
check("declined", q("SELECT status FROM clan_invites WHERE id=?", (app_id,))[0][0], "declined")

print("\n--- the default is zero, and zero changes nothing ---")
seed(1000)
r = client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY"})
inv_id = q("SELECT id FROM clan_invites WHERE name='NEWGUY'")[0][0]
check("no bonus on the row", q("SELECT COALESCE(gems,0) FROM clan_invites WHERE id=?", (inv_id,))[0][0], 0)
r = client(NEW).post("/clan/invite/respond", json={"id": inv_id, "accept": True})
check("joined", q("SELECT clan FROM players WHERE norm_name='NEWGUY'")[0][0], "TST")
check("no ledger rows at all", q("SELECT COUNT(*) FROM gem_ledger WHERE reason='salary'")[0][0], 0)
check("treasury untouched", treasury(), 1000)
r = client(NEW2).post("/clan/apply", json={"clan": "TST", "name": "NEWGUY2"})
check("an application without an ask reads as before", "asked" in r.get_json()["message"], False)

print("\n--- a negative or silly amount is treated as zero ---")
seed(1000)
r = client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY", "gems": -50})
check("negative -> 0", q("SELECT COALESCE(gems,0) FROM clan_invites WHERE name='NEWGUY'")[0][0], 0)
w("DELETE FROM clan_invites")
r = client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY", "gems": "lots"})
check("garbage -> 0", q("SELECT COALESCE(gems,0) FROM clan_invites WHERE name='NEWGUY'")[0][0], 0)

print("\n--- the inbox tells the invitee about the bonus ---")
seed(3000)
client(BOSS).post("/clan/add", json={"clan": "TST", "name": "NEWGUY", "gems": 750})
cn = sqlite3.connect(fa.DB_PATH)
notes = fa.notice_invites(cn.cursor(), NEW)
cn.close()
check("notice carries the bonus", notes and notes[0].get("gems"), 750)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
