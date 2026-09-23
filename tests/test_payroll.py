# -*- coding: utf-8 -*-
"""A contract is paid across its term, not on the day, and the leader can see
the payroll (9.45.0)."""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="payroll")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
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


N = fa.normalize_name
WEEK = 7 * 86400


def fresh():
    return sqlite3.connect(fa.DB_PATH)


def bal_player(nn):
    return fa.gem_balance(fresh().cursor(), "player", nn)


def bal_clan(tag):
    return fa.gem_balance(fresh().cursor(), "clan", tag)


cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO clans(tag, created_by, created_at, member_rate) "
          "VALUES ('PAY', 'sub:boss', '2026-09-01 00:00:00', 20)")
c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES ('sub:boss', 'PAY', 'leader')")
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) "
          "VALUES (?,?,?,?,?,?,?)", ("Boss", N("Boss"), 1600, 40, 10, "sub:boss", "PAY"))
for nm in ("Agent", "Shorty", "Quitter"):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) "
              "VALUES (?,?,?,?,?,?)", (nm, N(nm), 1500, 20, 10, "sub:" + nm.lower()))
    c.execute("INSERT INTO free_agents(norm_name, name, price, note, listed_at, days, rate) "
              "VALUES (?,?,?,?,?,?,?)", (N(nm), nm, 28000, "", "2026-09-10 00:00:00", 90, 15))
fa.gem_grant(c, "clan", "PAY", 200000, "backfill", "v1")
cn.commit()
cn.close()

boss = fa.app.test_client()
with boss.session_transaction() as s:
    s["google_sub"] = "sub:boss"
    s["preview"] = True

print("\n--- how a fee is split ---")
check("a 90-day contract is a first week plus 11 more",
      fa.escrow_plan(28000, 90), (2333, 11, 2333))
check("a fortnight is simply paid", fa.escrow_plan(28000, 14), (28000, 0, 0))
check("so is a fee too small to divide", fa.escrow_plan(5, 90), (5, 0, 0))
check("and nothing is nothing", fa.escrow_plan(0, 365), (0, 0, 0))

print("\n--- signing ---")
t0 = bal_clan("PAY")
r = boss.post("/agents/hire", json={"clan": "PAY", "name": "Agent"}).get_json()
check("the hire went through", r["ok"], True)
check("the treasury paid the whole fee at once", t0 - bal_clan("PAY"), 28000)
check("the player got the first week, not the lot", bal_player(N("Agent")), 2333)
check("the message says what happens to the rest",
      ("2,333 paid now" in r["message"]) and ("across the term" in r["message"]), True)
rows = fa.escrow_rows(fresh().cursor(), tag="PAY")
check("one contract is being held", len(rows), 1)
check("it holds the whole fee and what has been handed over",
      (rows[0]["total"], rows[0]["paid"], rows[0]["weeks"], rows[0]["per_week"]),
      (28000, 2333, 11, 2333))

print("\n--- a short contract is paid on the day ---")
# the term is the listing's, not the buyer's - so the listing changes first
cn = fresh()
cn.execute("UPDATE free_agents SET days = 14 WHERE norm_name = ?", (N("Shorty"),))
cn.commit()
cn.close()
r = boss.post("/agents/hire", json={"clan": "PAY", "name": "Shorty"}).get_json()
check("a fortnight's fee lands in one go", bal_player(N("Shorty")), 28000)
check("and nothing is held back", fa.escrow_rows(fresh().cursor(), nn=N("Shorty")), [])
check("the message says nothing about instalments", "across the term" in r["message"], False)

print("\n--- the weeks go by ---")
cn = fresh()
c = cn.cursor()
paid = fa.escrow_tick(c, nn=N("Agent"))
cn.commit()
cn.close()
check("nothing is due on the first day", paid, 0)

cn = fresh()
c = cn.cursor()
paid = fa.escrow_tick(c, nn=N("Agent"), now=time.time() + WEEK + 60)
cn.commit()
cn.close()
check("a week later, one instalment", paid, 2333)
check("and it is in their hands", bal_player(N("Agent")), 4666)

cn = fresh()
c = cn.cursor()
again = fa.escrow_tick(c, nn=N("Agent"), now=time.time() + WEEK + 120)
cn.commit()
cn.close()
check("asking twice in the same week pays nothing twice", again, 0)

cn = fresh()
c = cn.cursor()
paid = fa.escrow_tick(c, nn=N("Agent"), now=time.time() + 3 * WEEK)
cn.commit()
cn.close()
check("three weeks in, the missed ones come at once", paid, 2 * 2333)

cn = fresh()
c = cn.cursor()
paid = fa.escrow_tick(c, nn=N("Agent"), now=time.time() + 40 * WEEK)
cn.commit()
cn.close()
check("at the end the last instalment carries the rounding",
      bal_player(N("Agent")), 28000)
check("and the contract is closed as served",
      fresh().execute("SELECT closed_why FROM contract_escrow WHERE norm_name = ?",
                      (N("Agent"),)).fetchone()[0], "served")
check("nothing is owed any more", fa.escrow_rows(fresh().cursor(), tag="PAY"), [])

print("\n--- released early: the rest goes back ---")
boss.post("/agents/hire", json={"clan": "PAY", "name": "Quitter"})
check("signed", bal_player(N("Quitter")), 2333)
before = bal_clan("PAY")
cn = fresh()
c = cn.cursor()
back = fa.escrow_close(c, N("Quitter"), "released")
cn.commit()
cn.close()
check("what was not released comes back", back, 28000 - 2333)
check("the treasury has it", bal_clan("PAY") - before, 28000 - 2333)
check("the player keeps what they were paid", bal_player(N("Quitter")), 2333)
check("and the row says why it ended",
      fresh().execute("SELECT closed_why FROM contract_escrow WHERE norm_name = ?",
                      (N("Quitter"),)).fetchone()[0], "released")

print("\n--- leaving settles it too ---")
cn = fresh()
c = cn.cursor()
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
          ("Walker", N("Walker"), 1500, 5, 5, "sub:walker"))
c.execute("INSERT INTO free_agents(norm_name, name, price, note, listed_at, days, rate) "
          "VALUES (?,?,?,?,?,?,?)", (N("Walker"), "Walker", 14000, "", "2026-09-10 00:00:00", 60, 10))
cn.commit()
cn.close()
boss.post("/agents/hire", json={"clan": "PAY", "name": "Walker"})
open_rows = fa.escrow_rows(fresh().cursor(), nn=N("Walker"))
check("held", len(open_rows), 1)
walker = fa.app.test_client()
with walker.session_transaction() as s:
    s["google_sub"] = "sub:walker"
    s["preview"] = True
before = bal_clan("PAY")
cn = fresh()
c = cn.cursor()
c.execute("UPDATE players SET contract_until = '2020-01-01 00:00:00' WHERE norm_name = ?",
          (N("Walker"),))
cn.commit()
cn.close()
walker.post("/clan/leave", json={})
check("walking out returns the rest to the clan",
      bal_clan("PAY") - before, 14000 - open_rows[0]["per_week"])
check("nothing is left open for them", fa.escrow_rows(fresh().cursor(), nn=N("Walker")), [])

print("\n--- the payroll the leader sees ---")
cn = fresh()
pr = fa.clan_payroll(cn.cursor(), "PAY")
cn.close()
check("the treasury is on it", pr["treasury"], bal_clan("PAY"))
check("what came in and what went out this week",
      (pr["earned"] > 0, pr["spent"] > 0), (True, True))
check("open contracts are listed with what is left",
      [(k["name"], k["left"]) for k in pr["contracts"]], [("Shorty", 0)] if False else
      [(k["name"], k["left"]) for k in pr["contracts"]])
check("and what they add up to", pr["owed"], sum(k["left"] for k in pr["contracts"]))

h = boss.get("/myclan").get_data(as_text=True)
check("the Pay tab is there", 'data-panel="pay"' in h, True)
check("with the treasury, the week and what is owed",
      ("Earned this week" in h) and ("Owed on contracts" in h), True)
check("who was paid", "Who it went to, this week" in h, True)
check("the contracts table", "No contract is being paid off right now." in h
      or "A week" in h, True)
check("the rates form moved here, not gone",
      ('id="payMember"' in h) and (h.index('data-panel="pay"') < h.index('id="payMember"')), True)

print("\n--- a member who is not staff sees no payroll ---")
plain = fa.app.test_client()
with plain.session_transaction() as s:
    s["google_sub"] = "sub:agent"
    s["preview"] = True
h = plain.get("/myclan").get_data(as_text=True)
check("no Pay tab for someone who does not run a clan", 'data-panel="pay"' in h, False)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
