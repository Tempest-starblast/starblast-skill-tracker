# -*- coding: utf-8 -*-
"""The clan pay model: officer cuts, the co-leader cap, per-win member pay
out of the deposit, contract rates - and a treasury that cannot go negative."""
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
TMP = tempfile.mkdtemp(prefix="cpay")
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


def bal(nn):
    return q("SELECT COALESCE(gems,0) FROM players WHERE norm_name=?", nn)[0][0]


def treasury():
    return q("SELECT COALESCE(gems,0) FROM clans WHERE tag='TST'")[0][0]


N = fa.normalize_name
people = [("Owner One", "sub:owner", "leader"), ("Co One", "sub:c1", "coleader"), ("Co Two", "sub:c2", "coleader"),
          ("Mod One", "sub:m1", "moderator"), ("Alpha", "sub:a", None), ("Bravo", "sub:b", None), ("Zed", "sub:z", None)]
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", ("TST", "sub:owner", "2026-09-01 00:00:00"))
for name, sub, role in people:
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)",
              (name, N(name), 1500, 5, 5, sub, None if name == "Zed" else "TST"))
    if role:
        c.execute("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", (sub, "TST", role))
cn.commit()
cn.close()
W, D = fa.GEM_WIN, fa.GEM_DAILY_FIRST_WIN

print("\n--- the split on a member win, no rates set ---")
cn = sqlite3.connect(fa.DB_PATH)
fa.award_match_gems(cn.cursor(), [("Alpha", 1, 1.0)], "m1")
cn.commit()
cn.close()
check("winner: win + daily, nothing from the clan yet", bal(N("Alpha")), W + D)
check("treasury +100", treasury(), fa.GEM_CLAN_WIN)
check("leader +50", bal(N("Owner One")), fa.GEM_LEADER_WIN)
check("each co-leader +25", (bal(N("Co One")), bal(N("Co Two"))), (fa.GEM_COLEADER_WIN, fa.GEM_COLEADER_WIN))
check("moderator gets no cut", bal(N("Mod One")), 0)

print("\n--- the leader sets rates ---")
leader = fa.app.test_client()
with leader.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True
co = fa.app.test_client()
with co.session_transaction() as s:
    s["google_sub"] = "sub:c1"
    s["preview"] = True
check("stranger: 404", fa.app.test_client().post("/clan/pay", json={"clan": "TST", "member_rate": 30}).status_code, 404)
check("co-leader may not set pay", co.post("/clan/pay", json={"clan": "TST", "member_rate": 30}).status_code, 403)
r = leader.post("/clan/pay", json={"clan": "TST", "member_rate": 30, "mod_rate": 60}).get_json()
check("leader sets members +30, moderators +60", (r["ok"], q("SELECT member_rate, mod_rate FROM clans WHERE tag='TST'")), (True, [(30, 60)]))
r = leader.post("/clan/pay", json={"clan": "TST", "member_rate": 999, "mod_rate": -5}).get_json()
check("rates clamp to 0..%d" % fa.CLAN_RATE_MAX, (r["member_rate"], r["mod_rate"]), (fa.CLAN_RATE_MAX, 0))
leader.post("/clan/pay", json={"clan": "TST", "member_rate": 30, "mod_rate": 60})

print("\n--- pay comes out of the win's own deposit ---")
t0, a0, m0, l0, c0 = treasury(), bal(N("Alpha")), bal(N("Mod One")), bal(N("Owner One")), bal(N("Co One"))
cn = sqlite3.connect(fa.DB_PATH)
fa.award_match_gems(cn.cursor(), [("Alpha", 1, 1.0), ("Mod One", 1, 1.0), ("Owner One", 1, 1.0), ("Co One", 1, 1.0)], "m2")
cn.commit()
cn.close()
check("member: win + 30 from the clan", bal(N("Alpha")) - a0, W + 30)
check("moderator: win + daily + 60", bal(N("Mod One")) - m0, W + D + 60)
check("leader: own win + daily + 4 x 50 cut, no member pay", bal(N("Owner One")) - l0, W + D + 4 * fa.GEM_LEADER_WIN)
check("co-leader: own win + daily + 4 x 25, no member pay", bal(N("Co One")) - c0, W + D + 4 * fa.GEM_COLEADER_WIN)
check("treasury: 4 deposits minus 30 and 60", treasury() - t0, 4 * fa.GEM_CLAN_WIN - 30 - 60)
check("ledger: clan-pay rows for the two, keyed on the match", q("SELECT owner, amount FROM gem_ledger WHERE reason='clan-pay' AND ref LIKE 'm2#%' ORDER BY owner"), [(N("Alpha"), 30), (N("Mod One"), 60)])

print("\n--- the treasury can never go negative ---")
leader.post("/clan/pay", json={"clan": "TST", "member_rate": 100, "mod_rate": 100})
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE clans SET gems = 0 WHERE tag = 'TST'")
cn.execute("DELETE FROM gem_ledger WHERE owner_kind='clan'")
cn.commit()
fa.award_match_gems(cn.cursor(), [("Bravo", 1, 1.0)], "m3")
cn.commit()
cn.close()
check("rate 100 on an empty treasury: the win pays the member and the clan ends where it started", (treasury(), q("SELECT amount FROM gem_ledger WHERE reason='clan-pay' AND ref='m3#%s'" % N("Bravo"))), (0, [(100,)]))
leader.post("/clan/pay", json={"clan": "TST", "member_rate": 30, "mod_rate": 60})

print("\n--- survival pays double, capped at the deposit ---")
t0, a0, l0, c0 = treasury(), bal(N("Alpha")), bal(N("Owner One")), bal(N("Co Two"))
cn = sqlite3.connect(fa.DB_PATH)
fa.award_survival_gems(cn.cursor(), N("Alpha"), "r1")
cn.commit()
cn.close()
check("winner: 200 + 60", bal(N("Alpha")) - a0, fa.GEM_SURVIVAL_WIN + 60)
check("leader +100, co-leader +50", (bal(N("Owner One")) - l0, bal(N("Co Two")) - c0), (fa.GEM_SURVIVAL_LEADER_WIN, fa.GEM_SURVIVAL_COLEADER_WIN))
check("treasury +200 -60", treasury() - t0, fa.GEM_SURVIVAL_CLAN_WIN - 60)

print("\n--- a contract rate overrides the clan's rate while it runs ---")
zed = fa.app.test_client()
with zed.session_transaction() as s:
    s["google_sub"] = "sub:z"
    s["preview"] = True
cn = sqlite3.connect(fa.DB_PATH)
fa.gem_grant(cn.cursor(), "clan", "TST", 5000, "backfill", "v1")
cn.commit()
cn.close()
r = zed.post("/agents/list", json={"price": 500, "note": "", "days": 30, "rate": 80}).get_json()
check("listing names a per-win rate", (r["ok"], r["rate"], "+80 a win" in r["message"]), (True, 80, True))
h = leader.get("/agents").get_data(as_text=True)
check("tile shows it", "<b>+80</b> a win" in h, True)
r = leader.post("/agents/hire", json={"name": "Zed", "clan": "TST"}).get_json()
check("hired at +80 a win", (r["ok"], r["rate"], "+80 a win" in r["message"], q("SELECT contract_rate FROM players WHERE norm_name=?", N("Zed"))), (True, 80, True, [(80,)]))
z0 = bal(N("Zed"))
cn = sqlite3.connect(fa.DB_PATH)
fa.award_match_gems(cn.cursor(), [("Zed", 1, 1.0)], "m4")
cn.commit()
cn.close()
check("Zed's win pays 80, not the clan's 30", bal(N("Zed")) - z0, W + D + 80)
h = zed.get("/account").get_data(as_text=True)
check("account band says so", "at +80 a win" in h, True)
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET contract_until = '2020-01-01 00:00:00' WHERE norm_name = ?", (N("Zed"),))
cn.commit()
z0 = bal(N("Zed"))
fa.award_match_gems(cn.cursor(), [("Zed", 1, 1.0)], "m5")
cn.commit()
cn.close()
check("after the term: the clan's own rate", bal(N("Zed")) - z0, W + 30)

print("\n--- the co-leader cap ---")
r = leader.post("/clan/role", json={"clan": "TST", "name": "Alpha", "role": "coleader"}).get_json()
check("a third co-leader is refused", (r["ok"], "most a clan may have is %d" % fa.CLAN_COLEADER_MAX in r["message"]), (False, True))
leader.post("/clan/role", json={"clan": "TST", "name": "Co Two", "role": ""})
r = leader.post("/clan/role", json={"clan": "TST", "name": "Alpha", "role": "coleader"}).get_json()
check("after removing one, the slot is free", r["ok"], True)
check("a moderator role is still unlimited", leader.post("/clan/role", json={"clan": "TST", "name": "Bravo", "role": "moderator"}).get_json()["ok"], True)

print("\n--- the pages ---")
h = leader.get("/myclan").get_data(as_text=True)
check("Your clan: the Pay card with the rates", ('id="payCard"' in h) and ('id="payMember"' in h) and ('value="30"' in h) and ('value="60"' in h), True)
check("Your clan: what left the treasury this week", "Left the treasury this week" in h, True)
check("roster shows per-win pay", "<b>+30</b>Per win" in h, True)
h = leader.get("/clan/TST").get_data(as_text=True)
check("clan band shows member pay", "<span>Member pay</span><b class=\"gold\">+30" in h, True)
h = fa.app.test_client().get("/clan/TST").get_data(as_text=True)
check("a visitor sees none of it", ("Member pay" in h) or ("Per win" in h), False)
h = co.get("/myclan").get_data(as_text=True)
# 9.45.0: a co-leader hires from the treasury, so they see the payroll -
# but the rates are still the leader's alone.
check("a co-leader sees the payroll", 'data-panel="pay"' in h, True)
check("...but cannot change what the clan pays", 'id="payMember"' in h, False)
h = leader.get("/changelog").get_data(as_text=True)
check("changelog: only the cap is public", ("at most two co-leaders" in h) and ("per win" not in h.split("9.38.0")[1].split("9.37.0")[0]), True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
