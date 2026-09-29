# -*- coding: utf-8 -*-
"""The release reset (9.79.0): test accounts gone, every gem back to zero for
players and clans, nothing bought or worn, the ledger kept aside - and every
stat intact, so earned achievements are waiting to be claimed."""
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="gemrel")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa._load_api_keys = lambda: {"k"}
HDR = {"X-API-Key": "k"}
N = fa.normalize_name
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def q(sql, *a):
    cn = sqlite3.connect(fa.DB_PATH)
    r = cn.execute(sql, a).fetchall()
    cn.close()
    return r


def w(sql, *a):
    cn = sqlite3.connect(fa.DB_PATH)
    cn.execute(sql, a)
    cn.commit()
    cn.close()


# ---- a preview economy, the way the live one looks -----------------------------
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("DELETE FROM gem_ledger")
# A real account that used an access key: a million test gems, a hull bought
# with them, worn, a look worn, a contract.
c.execute("DELETE FROM players WHERE norm_name IN (?, ?, ?)", (N("REALTESTER"), N("REALPLAYER"), N("SANDBOX")))
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, peak_div, display_ship, "
          "cosmetics, contract_clan, contract_until, contract_rate) "
          "VALUES ('REALTESTER', ?, 1650, 60, 20, 'sub:realtester', 'raider', 702, '{\"title\":\"t-rookie\"}', "
          "'RELC', '2027-01-01 00:00:00', 40)", (N("REALTESTER"),))
fa.gem_grant(c, "player", N("REALTESTER"), 1000000, "preview-credit", "key21")
fa.gem_grant(c, "player", N("REALTESTER"), -150000, "purchase", "ship-701")
fa.gem_grant(c, "player", N("REALTESTER"), 900, "match-win", "m1")
# An ordinary player with earned gems and a claimed achievement.
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) "
          "VALUES ('REALPLAYER', ?, 1300, 12, 9, 'sub:realplayer')", (N("REALPLAYER"),))
fa.gem_grant(c, "player", N("REALPLAYER"), 1200, "match-win", "m2")
fa.gem_grant(c, "player", N("REALPLAYER"), 100, "achievement", "wins-10")
# A sandbox with gems, a friend request, and a clan only it runs.
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) "
          "VALUES ('SANDBOX', ?, 1500, 0, 0, 'test:sandbox:21')", (N("SANDBOX"),))
fa.gem_grant(c, "player", N("SANDBOX"), 1000000, "sandbox", "s21")
c.execute("DELETE FROM clans WHERE tag IN ('TSTC', 'RELC')")
c.execute("INSERT INTO clans (tag, created_by, created_at) VALUES ('TSTC', 'test:sandbox:21', '2026-09-20')")
c.execute("DELETE FROM clan_admins WHERE clan IN ('TSTC', 'RELC')")
c.execute("INSERT INTO clan_admins (clan, google_sub, created_at) VALUES ('TSTC', 'test:sandbox:21', '2026-09-20')")
# A real clan with a treasury, a look, pay rates, a bought slot and a perk.
c.execute("INSERT INTO clans (tag, created_by, created_at, gems, cosmetics, member_rate, mod_rate, coleader_slots) "
          "VALUES ('RELC', 'sub:realplayer', '2026-09-01', 0, '{\"tag\":\"cos-ct-1\"}', 20, 30, 1)")
c.execute("INSERT INTO clan_admins (clan, google_sub, created_at) VALUES ('RELC', 'sub:realplayer', '2026-09-01')")
c.execute("UPDATE players SET clan = 'RELC' WHERE norm_name = ?", (N("REALPLAYER"),))
fa.gem_grant(c, "clan", "RELC", 9600, "member-win", "m2#realplayer")
c.execute("INSERT OR REPLACE INTO clan_perks (clan, perk, until) VALUES ('RELC', 'perk-spotlight', '2027-01-01')")
c.execute("INSERT INTO contract_escrow (clan, norm_name, total, paid, weeks, per_week, started_at, until) "
          "VALUES ('RELC', ?, 4000, 1000, 4, 1000, '2026-09-20', '2026-10-20')", (N("REALTESTER"),))
c.execute("INSERT OR REPLACE INTO free_agents (norm_name, name, price, note, listed_at) "
          "VALUES (?, 'REALPLAYER', 500, 'hire me', '2026-09-22')", (N("REALPLAYER"),))
c.execute("DELETE FROM preview_keys")
c.execute("INSERT INTO preview_keys (label, key_hash, created_at, created_by, expires_at, kind) "
          "VALUES ('live one', 'h', '2026-09-28', 'o', '2027-01-01', 'access')")
cn.commit()
cn.close()
stats_before = q("SELECT norm_name, elo, wins, losses, peak_div FROM players WHERE norm_name IN (?, ?) ORDER BY 1",
                 N("REALTESTER"), N("REALPLAYER"))
tc = fa.app.test_client()


def call(body):
    return tc.post("/api/dev/gem-release", data=json.dumps(body), content_type="application/json", headers=HDR)


print("\n--- guarded ---")
check("no key, no reset", tc.post("/api/dev/gem-release", json={}).status_code, 401)

print("\n--- a dry run reports it all and changes nothing ---")
r = call({})
d = r.get_json()
check("dry run answers", (r.status_code, d.get("applied")), (200, False))
check("  names the test account", d.get("test_accounts"), ["SANDBOX"])
check("  and the clan only it ran", d.get("test_clans_removed"), ["TSTC"])
# Counted after the test accounts go: the tester's 850,900 and the player's 1,300 at least.
check("  counts the gems out there", d["gems_before"]["players"] >= 852200, True)
check("  but nothing moved", q("SELECT gems FROM players WHERE norm_name = ?", N("REALTESTER")), [(850900,)])
check("  no archive left behind", q("SELECT COUNT(*) FROM sqlite_master WHERE name = 'gem_ledger_prerelease'"), [(0,)])
check("  the sandbox is still there", q("SELECT COUNT(*) FROM players WHERE google_sub LIKE 'test:sandbox%'"), [(1,)])
check("a wrong confirm is a dry run too", call({"apply": True, "confirm": "yes"}).get_json().get("applied"), False)

print("\n--- applied ---")
r = call({"apply": True, "confirm": fa.GEM_RELEASE_CONFIRM})
d = r.get_json()
check("applied", (r.status_code, d.get("applied")), (200, True))
check("every test account gone", q("SELECT COUNT(*) FROM players WHERE google_sub LIKE 'test:sandbox%'"), [(0,)])
check("  and the clan only it ran", q("SELECT COUNT(*) FROM clans WHERE tag = 'TSTC'"), [(0,)])
check("  but the real clan stays", q("SELECT COUNT(*) FROM clans WHERE tag = 'RELC'"), [(1,)])
check("every player at 0", q("SELECT COUNT(*) FROM players WHERE COALESCE(gems, 0) != 0"), [(0,)])
check("every clan at 0", q("SELECT COUNT(*) FROM clans WHERE COALESCE(gems, 0) != 0"), [(0,)])
check("the ledger is empty", q("SELECT COUNT(*) FROM gem_ledger"), [(0,)])
# Six rows: the test account's own went with it before the archive was taken.
check("  and its history kept aside", q("SELECT COUNT(*) FROM gem_ledger_prerelease")[0][0] >= 6, True)
check("nothing worn: hull, looks", q("SELECT display_ship, cosmetics FROM players WHERE norm_name = ?", N("REALTESTER")),
      [(None, None)])
check("no contract", q("SELECT contract_clan, contract_until, contract_rate FROM players WHERE norm_name = ?",
                       N("REALTESTER")), [(None, None, 0)])
check("clan looks, pay rates and bought slots cleared",
      q("SELECT cosmetics, member_rate, mod_rate, coleader_slots FROM clans WHERE tag = 'RELC'"), [(None, 0, 0, 0)])
check("perks, escrow and listings cleared",
      [q("SELECT COUNT(*) FROM %s" % t)[0][0] for t in ("clan_perks", "contract_escrow", "free_agents")], [0, 0, 0])
check("tester keys revoked", q("SELECT COUNT(*) FROM preview_keys WHERE revoked_at IS NULL"), [(0,)])

print("\n--- the stats are all still there ---")
check("ratings, records and peaks untouched",
      q("SELECT norm_name, elo, wins, losses, peak_div FROM players WHERE norm_name IN (?, ?) ORDER BY 1",
        N("REALTESTER"), N("REALPLAYER")), stats_before)
cn = sqlite3.connect(fa.DB_PATH)
st = {a["key"]: a for a in fa.ach_status(cn.cursor(), N("REALTESTER"))}
st2 = {a["key"]: a for a in fa.ach_status(cn.cursor(), N("REALPLAYER"))}
cn.close()
check("a win milestone they reached is claimable again", (st["wins-50"]["unlocked"], st["wins-50"]["ready"]), (True, True))
check("one claimed before is claimable again", (st2["wins-10"]["unlocked"], st2["wins-10"]["ready"]), (True, True))
check("the hull bought with test gems is not theirs any more", 701 in fa.owned_ships(sqlite3.connect(fa.DB_PATH).cursor(), N("REALTESTER")), False)

print("\n--- once, and never after release ---")
check("a second run is refused", call({"apply": True, "confirm": fa.GEM_RELEASE_CONFIRM}).status_code, 409)
fa.GEMS_PUBLIC = True
check("closed once gems are public", call({}).status_code, 403)
fa.GEMS_PUBLIC = False

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
