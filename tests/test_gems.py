# -*- coding: utf-8 -*-
"""The gem economy: does it pay the right people once, and only once.

The thing most worth testing is not that a win pays 100 - it is that a match
reported twice, an achievement re-checked on every result, and a backfill run
again all pay nothing the second time. That property is the whole reason the
ledger has a unique index, so most of this file leans on it.

Runs against a scratch database. Nothing here touches the live site.
"""
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

TMP = tempfile.mkdtemp(prefix="gemtest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.init_db()
fa.app.config["TESTING"] = True
OWNER = "discord:owner-under-test"
fa.OWNER_SUBS = {OWNER}

ok = fail = 0
_open = None


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def conn():
    c = sqlite3.connect(fa.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def seed():
    global _open
    try:
        _open.close()
    except Exception:
        pass
    cn = conn()
    c = cn.cursor()
    for t in ("players", "gem_ledger", "clan_admins"):
        c.execute("DELETE FROM %s" % t)
    c.execute("DELETE FROM clans WHERE tag = 'TST'")
    c.execute("INSERT OR IGNORE INTO clans (tag, created_by, created_at, gems) "
              "VALUES ('TST', 'x', '2026-01-01', 0)")
    c.execute("UPDATE clans SET gems = 0 WHERE tag = 'TST'")
    # a leader, a member, and an unaffiliated player
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) "
              "VALUES ('BOSS','BOSS',1500,0,0,'TST','sub:boss',0)")
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, gems) "
              "VALUES ('MEMBER','MEMBER',1200,0,0,'TST',0)")
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, gems) "
              "VALUES ('LONER','LONER',1100,0,0,0)")
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) "
              "VALUES ('TST','sub:boss','2026-01-01','leader')")
    # a co-leader (paid) and a moderator (not paid), both with player rows
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) "
              "VALUES ('COLEAD','COLEAD',1400,0,0,'TST','sub:colead',0)")
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) "
              "VALUES ('MOD','MOD',1100,0,0,'TST','sub:mod',0)")
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) "
              "VALUES ('TST','sub:colead','2026-01-01','coleader')")
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) "
              "VALUES ('TST','sub:mod','2026-01-01','moderator')")
    cn.commit()
    _open = cn
    return cn


def bal(cn, who):
    r = cn.execute("SELECT COALESCE(gems,0) FROM players WHERE norm_name = ?", (who,)).fetchone()
    return r[0] if r else None


def clanbal(cn, tag):
    return cn.execute("SELECT COALESCE(gems,0) FROM clans WHERE tag = ?", (tag,)).fetchone()[0]


def ledger_sum(cn, kind, owner):
    r = cn.execute("SELECT COALESCE(SUM(amount),0) FROM gem_ledger "
                   "WHERE owner_kind = ? AND owner = ?", (kind, owner)).fetchone()
    return r[0]


print("\n--- a win pays the player, the clan and the leader ---")
cn = seed()
c = cn.cursor()
c.execute("UPDATE players SET wins = 1 WHERE norm_name = 'MEMBER'")
fa.award_match_gems(c, [("MEMBER", 1, 12.3)], "m1")
cn.commit()
W, D = fa.GEM_WIN, fa.GEM_DAILY_FIRST_WIN
first = [a for a in fa.GEM_WIN_MILESTONES if a[0] == "first-win"][0][4]
check("member gets win + daily (the first-win achievement waits to be claimed)", bal(cn, "MEMBER"), W + D)
check("clan treasury gets its cut", clanbal(cn, "TST"), fa.GEM_CLAN_WIN)
check("leader gets their cut", bal(cn, "BOSS"), fa.GEM_LEADER_WIN)
check("co-leader gets half the leader's cut", bal(cn, "COLEAD"), fa.GEM_COLEADER_WIN)
check("a moderator is not paid on it", bal(cn, "MOD"), 0)
check("the treasury's cut is the owner's 100 (18 Sep)", fa.GEM_CLAN_WIN, 100)
check("each officer's cut is the owner's 50 (18 Sep)", fa.GEM_LEADER_WIN, 50)
check("balance equals the ledger", bal(cn, "MEMBER"), ledger_sum(cn, "player", "MEMBER"))

print("\n--- the same match again pays nobody ---")
before = (bal(cn, "MEMBER"), clanbal(cn, "TST"), bal(cn, "BOSS"))
fa.award_match_gems(c, [("MEMBER", 1, 12.3)], "m1")
cn.commit()
check("player unchanged", bal(cn, "MEMBER"), before[0])
check("clan unchanged", clanbal(cn, "TST"), before[1])
check("leader unchanged", bal(cn, "BOSS"), before[2])
check("co-leader unchanged", bal(cn, "COLEAD"), fa.GEM_COLEADER_WIN)

print("\n--- a second, different match pays again (but the daily does not) ---")
c.execute("UPDATE players SET wins = 2 WHERE norm_name = 'MEMBER'")
fa.award_match_gems(c, [("MEMBER", 1, 5.0)], "m2")
cn.commit()
check("only the win, no second daily bonus", bal(cn, "MEMBER"), before[0] + W)

print("\n--- a loss pays the consolation and nothing else ---")
fa.award_match_gems(c, [("LONER", 0, -9.0)], "m3")
cn.commit()
check("loser paid", bal(cn, "LONER"), fa.GEM_LOSS)
check("no clan pay-out for a loss", clanbal(cn, "TST"), fa.GEM_CLAN_WIN * 2)

print("\n--- a clan with two winners in one match is paid for each ---")
cn2 = seed()
c2 = cn2.cursor()
c2.execute("UPDATE players SET wins = 1 WHERE norm_name IN ('MEMBER','BOSS')")
fa.award_match_gems(c2, [("MEMBER", 1, 1.0), ("BOSS", 1, 1.0)], "m9")
cn2.commit()
check("clan paid twice over", clanbal(cn2, "TST"), fa.GEM_CLAN_WIN * 2)
check("leader collects on both, plus their own win",
      bal(cn2, "BOSS"), W + D + fa.GEM_LEADER_WIN * 2)

print("\n--- win milestones ---")
cn = seed()
c = cn.cursor()
c.execute("UPDATE players SET wins = 50 WHERE norm_name = 'LONER'")
cn.commit()
b0 = bal(cn, "LONER")
st = {a["key"]: a for a in fa.ach_status(c, "LONER")}
check("50 wins unlocks first-win, 10 and 50", [k for k in ("first-win", "wins-10", "wins-50") if st[k]["unlocked"]],
      ["first-win", "wins-10", "wins-50"])
check("and not the ones above it", any(st[k]["unlocked"] for k in ("wins-100", "wins-250")), False)
check("unlocked is not paid - it waits to be claimed", (bal(cn, "LONER") - b0, all(st[k]["ready"] for k in ("first-win", "wins-10", "wins-50"))), (0, True))

print("\n--- rank achievements pay for every division passed through ---")
cn = seed()
c = cn.cursor()
c.execute("UPDATE players SET peak_div = 'advanced' WHERE norm_name = 'LONER'")
cn.commit()
lvl = fa.ranks.RANK_BY_KEY["advanced"]["level"]
st = [a for a in fa.ach_status(c, "LONER") if a["group"] == "Tiers"]
check("six tiers up to Vanguard ready to claim", sum(1 for a in st if a["ready"]), 6)
want = sum(fa.GEM_DIVISION_AWARD[l] for l in range(1, lvl + 1))
check("worth the sum of the ladder below it", sum(a["gems"] for a in st if a["ready"]), want)
check("peak level read from the row", fa.gem_peak_level(c, "LONER"), lvl)

print("\n--- spending is just a negative row ---")
cn = seed()
c = cn.cursor()
fa.gem_grant(c, "player", "LONER", 5000, "backfill", "v1")
cn.commit()
check("granted", bal(cn, "LONER"), 5000)
check("a second backfill is refused", fa.gem_grant(c, "player", "LONER", 5000, "backfill", "v1"), 0)
fa.gem_grant(c, "player", "LONER", -1200, "purchase", "tint-rose")
cn.commit()
check("charged", bal(cn, "LONER"), 3800)
check("buying the same thing twice is refused",
      fa.gem_grant(c, "player", "LONER", -1200, "purchase", "tint-rose"), 0)
check("balance still equals the ledger", bal(cn, "LONER"), ledger_sum(cn, "player", "LONER"))

print("\n--- nobody but the owner can see any of it ---")
check("the flag is off", fa.GEMS_PUBLIC, False)
cl = fa.app.test_client()
check("signed out -> 404", cl.get("/achievements").status_code, 404)
cl = fa.app.test_client()
with cl.session_transaction() as sess:
    sess["google_sub"] = "sub:boss"
check("an ordinary player -> 404", cl.get("/achievements").status_code, 404)
cl = fa.app.test_client()
with cl.session_transaction() as sess:
    sess["google_sub"] = OWNER
r = cl.get("/achievements")
check("the owner -> 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("it says it is not released", "Not released" in h, True)
check("it lists the top division", "Shadow X-3" in h, True)
check("it lists a milestone", "First blood" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
