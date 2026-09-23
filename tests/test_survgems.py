# -*- coding: utf-8 -*-
"""The 18 Sep rates, survival-win gems, and survival wins on clan stats."""
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
TMP = tempfile.mkdtemp(prefix="survgems")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
L, M, S = "sub:boss", "sub:member", "sub:solo"

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
for t in ("players", "clans", "clan_admins", "clan_tag_styles", "clan_invites", "gem_ledger",
          "survival_players", "survival_round_players", "free_agents"):
    c.execute("DELETE FROM %s" % t)


def add_player(name, sub=None, clan=None, w=0, l=0):
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan, gems) "
              "VALUES (?, ?, 1300, ?, ?, ?, ?, 0)", (name, fa.normalize_name(name), w, l, sub, clan))


add_player("BOSS", L)
add_player("MEMBER", M, "TST", 4, 2)
add_player("SOLO", S, None, 1, 1)
st, _ = fa.perform_clan_create(c, L, "TST", trusted=True)
check("TST created", st, 200)
c.execute("UPDATE players SET clan = 'TST' WHERE google_sub = ?", (L,))
cn.commit()
fa.tag_cache_reset()


def bal(nn):
    return c.execute("SELECT COALESCE(gems,0) FROM players WHERE norm_name = ?", (nn,)).fetchone()[0]


def clanbal(tag):
    return c.execute("SELECT COALESCE(gems,0) FROM clans WHERE tag = ?", (tag,)).fetchone()[0]


print("\n--- the rates ---")
check("treasury per member team win is 100", fa.GEM_CLAN_WIN, 100)
check("each officer per member team win is 50", fa.GEM_LEADER_WIN, 50)
check("survival win pays the winner 200", fa.GEM_SURVIVAL_WIN, 200)
check("...the treasury 200", fa.GEM_SURVIVAL_CLAN_WIN, 200)
check("...each officer 100", fa.GEM_SURVIVAL_LEADER_WIN, 100)

print("\n--- a member's team win at the new rates ---")
fa.award_match_gems(c, [("MEMBER", 1, 9.0)], "m1")
cn.commit()
check("treasury +100", clanbal("TST"), 100)
check("leader +50", bal("BOSS"), 50)

print("\n--- a survival win ---")
got = fa.award_survival_gems(c, "MEMBER", "r1")
cn.commit()
check("winner paid 200", got, 200)
check("treasury +200 on top", clanbal("TST"), 300)
check("leader +100 on top", bal("BOSS"), 150)
before = (bal("MEMBER"), clanbal("TST"), bal("BOSS"))
fa.award_survival_gems(c, "MEMBER", "r1")
cn.commit()
check("the same round again pays nobody", (bal("MEMBER"), clanbal("TST"), bal("BOSS")), before)
fa.award_survival_gems(c, "MEMBER", "r2")
cn.commit()
check("another round pays again", (clanbal("TST"), bal("BOSS")), (500, 250))
got = fa.award_survival_gems(c, "SOLO", "r3")
cn.commit()
check("a clan-less winner gets the 200 and nobody else moves", (got, bal("SOLO"), clanbal("TST")), (200, 200, 500))
got = fa.award_survival_gems(c, "GHOSTNAME", "r4")
cn.commit()
check("a winner with no row on the site earns nothing", (got, c.execute("SELECT COUNT(*) FROM gem_ledger WHERE ref = 'r4'").fetchone()[0]), (0, 0))
check("ledger reasons are the survival ones", set(r[0] for r in c.execute("SELECT DISTINCT reason FROM gem_ledger WHERE ref LIKE 'r%'")), {"survival-win", "survival-member-win"})
check("balance equals the ledger for the leader", bal("BOSS"), c.execute("SELECT SUM(amount) FROM gem_ledger WHERE owner_kind='player' AND owner='BOSS'").fetchone()[0])

print("\n--- a round is rated under the ACCOUNT, and paid once ---")
STY = "S" + chr(0x1105) + "F" + chr(0x336)
c.execute("DELETE FROM gem_ledger")
c.execute("UPDATE players SET gems = 0")
c.execute("UPDATE clans SET gems = 0")
c.execute("DELETE FROM survival_players")
c.execute("DELETE FROM survival_round_players")
add_player("BHU", "sub:bhu", "TST", 2, 1)
cn.commit()
fa.tag_cache_reset()
fa._PLAY_CACHE["ts"] = 0.0


def round_data(order, sid=77):
    return {"reached_elimination": True, "sid": sid, "leave_order": [[nm] for nm in order]}


n = fa.apply_survival_round(c, "77|2026-09-18 10:00:00", "2026-09-18 10:00:00",
                            round_data(["TST BHU", "SOLO", "GUESTA", "GUESTB"]))
cn.commit()
check("field of four rated", n, 4)
check("the win flown as 'TST BHU' landed on BHU's row", c.execute("SELECT rounds, wins FROM survival_players WHERE norm_name='BHU'").fetchone(), (1, 1))
check("...no row of the tagged spelling", c.execute("SELECT COUNT(*) FROM survival_players WHERE norm_name=?", (fa.normalize_name("TST BHU"),)).fetchone()[0], 0)
check("...the name as flown is kept", c.execute("SELECT name FROM survival_round_players WHERE norm_name='BHU'").fetchone()[0], "TST BHU")
check("winner paid 200, clan 200, leader 100", (bal("BHU"), clanbal("TST"), bal("BOSS")), (200, 200, 100))
n2 = fa.apply_survival_round(c, "77|2026-09-18 10:00:00", "2026-09-18 10:00:00",
                             round_data(["TST BHU", "SOLO", "GUESTA", "GUESTB"]))
cn.commit()
check("the same round again is a no-op", (n2, bal("BHU")), (0, 200))
c.execute("DELETE FROM survival_players")
c.execute("DELETE FROM survival_round_players")
cn.commit()
fa.apply_survival_round(c, "77|2026-09-18 10:00:00", "2026-09-18 10:00:00",
                        round_data(["TST BHU", "SOLO", "GUESTA", "GUESTB"]))
cn.commit()
check("a rebuild re-rates but pays nobody twice", (c.execute("SELECT wins FROM survival_players WHERE norm_name='BHU'").fetchone()[0], bal("BHU"), clanbal("TST")), (1, 200, 200))

print("\n--- two names that are one account rate neither; protection needs the check-in ---")
n = fa.apply_survival_round(c, "77|2026-09-18 11:00:00", "2026-09-18 11:00:00",
                            round_data(["BHU", "TST BHU", "GUESTA", "GUESTB"]))
cn.commit()
check("field still counts", n, 4)
check("neither BHU spelling got a row for that round", c.execute("SELECT COUNT(*) FROM survival_round_players WHERE round_key LIKE '%11:00:00' AND norm_name='BHU'").fetchone()[0], 0)
check("...and no second payment", bal("BHU"), 200)
c.execute("UPDATE players SET strict_mode = 1 WHERE norm_name = 'BHU'")
cn.commit()
fa.apply_survival_round(c, "77|2026-09-18 12:00:00", "2026-09-18 12:00:00",
                        round_data(["TST BHU", "SOLO", "GUESTA", "GUESTB"]))
cn.commit()
check("protected, reached through the tag, no check-in: not rated", c.execute("SELECT COUNT(*) FROM survival_round_players WHERE round_key LIKE '%12:00:00' AND norm_name='BHU'").fetchone()[0], 0)
c.execute("INSERT INTO checkins (player, sys_id, created_at, sub) VALUES ('BHU', 77, '2026-09-18 12:30:00', 'sub:bhu')")
cn.commit()
fa.apply_survival_round(c, "77|2026-09-18 13:00:00", "2026-09-18 13:00:00",
                        round_data(["TST BHU", "SOLO", "GUESTA", "GUESTB"]))
cn.commit()
check("...with a check-in for the lobby it is", c.execute("SELECT COUNT(*) FROM survival_round_players WHERE round_key LIKE '%13:00:00' AND norm_name='BHU'").fetchone()[0], 1)
c.execute("UPDATE players SET strict_mode = 0 WHERE norm_name = 'BHU'")
cn.commit()

print("\n--- gem_grant leaves no ledger row for an owner with no row ---")
got = fa.gem_grant(c, "player", "NOSUCHROW", 100, "win", "zz1")
cn.commit()
check("nothing granted", got, 0)
check("no stranded ledger row", c.execute("SELECT COUNT(*) FROM gem_ledger WHERE owner='NOSUCHROW'").fetchone()[0], 0)
got = fa.gem_grant(c, "clan", "NOCLAN", 100, "member-win", "zz2")
cn.commit()
check("same for a clan that does not exist", (got, c.execute("SELECT COUNT(*) FROM gem_ledger WHERE owner='NOCLAN'").fetchone()[0]), (0, 0))

print("\n--- survival wins on the clan stats ---")
c.execute("INSERT OR REPLACE INTO survival_players (norm_name, name, elo, rounds, wins, best_place) VALUES ('MEMBER', 'MEMBER', 1040, 7, 3, 1)")
c.execute("INSERT OR REPLACE INTO survival_players (norm_name, name, elo, rounds, wins, best_place) VALUES ('BOSS', 'BOSS', 1010, 2, 1, 1)")
c.execute("INSERT OR REPLACE INTO survival_players (norm_name, name, elo, rounds, wins, best_place) VALUES ('SOLO', 'SOLO', 1010, 2, 2, 1)")
cn.commit()
app = fa.app.test_client()
r = app.get("/clan/TST")
check("clan page 200", r.status_code, 200)
h = r.get_data(as_text=True)
expect = c.execute("SELECT COALESCE(SUM(s.wins),0) FROM survival_players s JOIN players p ON p.norm_name = s.norm_name WHERE p.clan = 'TST'").fetchone()[0]
check("survival wins in the header band = members' wins added", ('<span>Survival</span><b>%d</b>' % expect in h), True)
check("no treasury for a visitor", "Treasury" in h, False)
r = app.get("/clans")
check("clans list 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("clans list has the Survival column with the same number", (">Survival<" in h) and ('<td class="mid">%d</td>' % expect in h), True)
r = app.get("/info")
check("info mentions survival wins on the clan page", "its survival wins" in r.get_data(as_text=True), True)
r = app.get("/changelog")
check("changelog entry", "survival wins" in r.get_data(as_text=True).lower(), True)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
