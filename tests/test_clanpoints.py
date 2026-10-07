# -*- coding: utf-8 -*-
"""Clan points, officer cuts, pay modes, rankings, application notes and removal
reasons (9.82.0). Runs against a scratch database."""
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="clanpts")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.GEMS_PUBLIC = True
fa._load_api_keys = lambda: {"k"}
BOSS, CO, MOD, M1, M2 = "sub:boss", "sub:co", "sub:mod", "sub:m1", "sub:m2"
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
    c = sqlite3.connect(fa.DB_PATH)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


def seed(treasury=0):
    cn = sqlite3.connect(fa.DB_PATH)
    c = cn.cursor()
    for t in ("players", "gem_ledger", "clan_admins", "clan_invites", "clan_points",
              "clan_removals", "survival_players", "survival_round_players", "discord_links"):
        c.execute("DELETE FROM %s" % t)
    c.execute("DELETE FROM clans")
    c.execute("INSERT INTO clans (tag, created_by, created_at, gems) VALUES ('TST','x','2026-01-01',0)")
    rows = [("BOSS", 1500, BOSS, "TST"), ("CO", 1400, CO, "TST"), ("MOD", 1200, MOD, "TST"),
            ("M1", 1300, M1, "TST"), ("M2", 1250, M2, "TST"), ("OUTSIDER", 1100, "sub:out", None)]
    for name, elo, sub, clan in rows:
        c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) "
                  "VALUES (?,?,?,5,5,?,?,0)", (name, name, elo, clan, sub))
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES ('TST',?,'2026-01-01','leader')", (BOSS,))
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES ('TST',?,'2026-01-01','coleader')", (CO,))
    c.execute("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES ('TST',?,'2026-01-01','moderator')", (MOD,))
    if treasury:
        fa.gem_grant(c, "clan", "TST", treasury, "backfill", "v1")
    cn.commit()
    cn.close()


def client(sub=None):
    cl = fa.app.test_client()
    if sub:
        with cl.session_transaction() as s:
            s["google_sub"] = sub
    return cl


def treasury():
    return q("SELECT COALESCE(gems,0) FROM clans WHERE tag='TST'")[0][0]


def gems(nn):
    return q("SELECT COALESCE(gems,0) FROM players WHERE norm_name=?", (nn,))[0][0]


def pts(nn, tag="TST"):
    return q("SELECT COALESCE(SUM(points),0) FROM clan_points WHERE clan=? AND norm_name=?", (tag, nn))[0][0]


def reconciled():
    a = q("SELECT COUNT(*) FROM clans cl WHERE COALESCE(cl.gems,0) != COALESCE((SELECT SUM(amount) FROM gem_ledger g WHERE g.owner_kind='clan' AND g.owner=cl.tag),0)")[0][0]
    b = q("SELECT COUNT(*) FROM players p WHERE COALESCE(p.gems,0) != COALESCE((SELECT SUM(amount) FROM gem_ledger g WHERE g.owner_kind='player' AND g.owner=p.norm_name),0)")[0][0]
    return a + b


def pay(nn, ref, kind=None, survival=False):
    cn = sqlite3.connect(fa.DB_PATH)
    try:
        got = fa.clan_pay_member_win(cn.cursor(), "TST", nn, ref, survival=survival, kind=kind)
        cn.commit()
        return got
    finally:
        cn.close()


def delta(fn):
    """(treasury, BOSS, CO, M1, MOD) change while fn runs."""
    before = (treasury(), gems("BOSS"), gems("CO"), gems("M1"), gems("MOD"))
    fn()
    after = (treasury(), gems("BOSS"), gems("CO"), gems("M1"), gems("MOD"))
    return tuple(a - b for a, b in zip(after, before))


print("\n--- the points, and the gems that follow them (default pay, as before) ---")
seed()
check("a team win: treasury 100, leader 50, co-leader 25", delta(lambda: pay("M1", "w1#M1")), (100, 50, 25, 0, 0))
check("and 10 points for the member", pts("M1"), 10)
check("the same result again pays nothing and adds no points", (delta(lambda: pay("M1", "w1#M1")), pts("M1")), ((0, 0, 0, 0, 0), 10))
check("a team 2nd place: half a win", delta(lambda: pay("M1", "w2#M1", kind="team-2nd")), (50, 25, 12, 0, 0))
check("5 more points", pts("M1"), 15)
check("a survival win: 200 / 100 / 50", delta(lambda: pay("M1", "s1#M1", kind="survival-win")), (200, 100, 50, 0, 0))
check("a survival top 3: half of that", delta(lambda: pay("M1", "s2#M1", kind="survival-top3")), (100, 50, 25, 0, 0))
check("30 + 15 more points", pts("M1"), 60)
check("the legacy call (survival=True) is a survival win", delta(lambda: pay("M1", "s3#M1", survival=True)), (200, 100, 50, 0, 0))
check("the values are the owner's", dict(fa.CLAN_POINTS), {"team-win": 10, "team-2nd": 5, "survival-win": 30, "survival-top3": 15})
check("balances reconcile", reconciled(), 0)

print("\n--- a member is paid by win (the original way), scaled by the result ---")
seed()
w("UPDATE clans SET member_rate = 20 WHERE tag='TST'")
check("team win pays the rate", delta(lambda: pay("M1", "a1#M1"))[3], 20)
check("2nd place pays half", delta(lambda: pay("M1", "a2#M1", kind="team-2nd"))[3], 10)
check("survival win pays double", delta(lambda: pay("M1", "a3#M1", kind="survival-win"))[3], 40)
check("survival top 3 pays the rate", delta(lambda: pay("M1", "a4#M1", kind="survival-top3"))[3], 20)
check("balances reconcile", reconciled(), 0)

print("\n--- a member is paid by the point ---")
seed()
w("UPDATE clans SET pay_mode='point', member_pp=3, mod_pp=1 WHERE tag='TST'")
check("team win: 10 points x 3", delta(lambda: pay("M1", "p1#M1"))[3], 30)
check("2nd place: 5 points x 3", delta(lambda: pay("M1", "p2#M1", kind="team-2nd"))[3], 15)
check("survival win: 30 points x 3 - survival pays members more", delta(lambda: pay("M1", "p3#M1", kind="survival-win"))[3], 90)
check("survival top 3: 15 points x 3", delta(lambda: pay("M1", "p4#M1", kind="survival-top3"))[3], 45)
check("a moderator is paid the moderator rate", delta(lambda: pay("MOD", "p5#MOD"))[4], 10)
check("officers get their cut and no member pay", delta(lambda: pay("BOSS", "p6#BOSS"))[1], 50 + 0)
w("UPDATE clans SET member_pp=10 WHERE tag='TST'")
check("never more than the result puts in: 300 capped at the 200 deposit",
      delta(lambda: pay("M1", "p7#M1", kind="survival-win"))[3], 200)
check("balances reconcile", reconciled(), 0)

print("\n--- a member is paid a percent of the deposit ---")
seed()
w("UPDATE clans SET pay_mode='percent', member_pct=40 WHERE tag='TST'")
check("team win: 40% of 100", delta(lambda: pay("M1", "c1#M1"))[3], 40)
check("survival win: 40% of 200", delta(lambda: pay("M1", "c2#M1", kind="survival-win"))[3], 80)
check("survival top 3: 40% of 100", delta(lambda: pay("M1", "c3#M1", kind="survival-top3"))[3], 40)
check("balances reconcile", reconciled(), 0)

print("\n--- the officers' cuts: lower them and the difference goes to the treasury ---")
seed()
w("UPDATE clans SET leader_cut=20, coleader_cut=5 WHERE tag='TST'")
d = delta(lambda: pay("M1", "k1#M1"))
check("team win: treasury 100+30+20, leader 20, co-leader 5", d, (150, 20, 5, 0, 0))
check("no gems made or lost: 175 either way", d[0] + d[1] + d[2], 175)
d = delta(lambda: pay("M1", "k2#M1", kind="survival-win"))
check("survival win: cuts double, savings too", d, (300, 40, 10, 0, 0))
check("still 350 in total", d[0] + d[1] + d[2], 350)
w("UPDATE clans SET leader_cut=0, coleader_cut=0, pay_mode='point', member_pp=10 WHERE tag='TST'")
check("savings raise the cap: survival win pays the full 300", delta(lambda: pay("M1", "k3#M1", kind="survival-win"))[3], 300)
w("UPDATE clans SET leader_cut=999, coleader_cut=999, pay_mode='win', member_pp=0 WHERE tag='TST'")
check("a cut cannot be raised above the standard", delta(lambda: pay("M1", "k4#M1")), (100, 50, 25, 0, 0))
check("balances reconcile", reconciled(), 0)

print("\n--- the leader sets all of that on the pay page ---")
seed(1000)
r = client(MOD).post("/clan/pay", json={"clan": "TST", "mode": "point"})
check("a moderator cannot", r.status_code, 403)
r = client(BOSS).post("/clan/pay", json={"clan": "TST", "mode": "weekly"})
check("an unknown mode is refused", r.status_code, 400)
r = client(BOSS).post("/clan/pay", json={"clan": "TST", "mode": "point", "member_pp": 99, "mod_pp": 2,
                                          "leader_cut": 30, "coleader_cut": 99, "member_rate": 7})
j = r.get_json()
check("saved", (r.status_code, j["mode"]), (200, "point"))
check("pay per point is capped", j["member_pp"], fa.CLAN_PP_MAX)
check("a cut cannot go above the standard", (j["leader_cut"], j["coleader_cut"]), (30, fa.GEM_COLEADER_WIN))
check("the settings read back", fa.clan_pay_settings(sqlite3.connect(fa.DB_PATH).cursor(), "TST")["mode"], "point")
r = client(BOSS).post("/clan/pay", json={"clan": "TST", "member_pct": 25})
j = r.get_json()
check("a partial save keeps the rest", (j["mode"], j["member_pp"], j["leader_cut"], j["member_pct"]), ("point", fa.CLAN_PP_MAX, 30, 25))

print("\n--- second place in a three-team match ---")
A = [("W1", 1, 5.0), ("B1", 0, -5.0), ("B2", 0, -5.0), ("C1", 0, -5.0)]
T = {"B1": "lose1", "B2": "lose1", "C1": "lose2"}
check("the better-scoring losing team is second",
      fa._second_place_team(A, T, {"B1": 1000, "B2": 500, "C1": 2000}), {"C1"})
check("or the other one", fa._second_place_team(A, T, {"B1": 3000, "B2": 500, "C1": 2000}), {"B1", "B2"})
check("a tie names nobody", fa._second_place_team(A, T, {"B1": 1000, "B2": 1000, "C1": 2000}), set())
check("a two-team match has no second place",
      fa._second_place_team([("W1", 1, 5.0), ("B1", 0, -5.0)], {"B1": "lose1"}, {"B1": 9}), set())
check("a losing team with nobody rated cannot be judged",
      fa._second_place_team([("W1", 1, 5.0), ("B1", 0, -5.0)], {"B1": "lose1", "X": "lose2"}, {"B1": 9, "X": 99}), set())

print("\n--- the match award hands second place its points and gems ---")
seed()
w("UPDATE players SET clan = NULL WHERE norm_name = 'M2'")
w("UPDATE players SET clan = 'TST' WHERE norm_name = 'M2'")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) VALUES ('M3','M3',1000,0,0,'TST',NULL,0)")
cn.commit()
applied = [("M1", 1, 10.0), ("M2", 0, -10.0), ("M3", 0, -10.0), ("OUTSIDER", 0, -10.0)]
before = treasury()
fa.award_match_gems(cn.cursor(), applied, "matchA", second={"M2"})
cn.commit()
cn.close()
check("the winner got 10", pts("M1"), 10)
check("second place got 5", pts("M2"), 5)
check("the other loser got none", pts("M3"), 0)
check("a player with no clan earns the clan nothing", q("SELECT COUNT(*) FROM clan_points WHERE norm_name='OUTSIDER'")[0][0], 0)
check("the treasury took a win's 100 and a 2nd's 50", treasury() - before, 150)
cn = sqlite3.connect(fa.DB_PATH)
fa.award_match_gems(cn.cursor(), applied, "matchA", second={"M2"})
cn.commit()
cn.close()
check("a repeat of the same match changes nothing", (pts("M1"), pts("M2"), treasury() - before), (10, 5, 150))

print("\n--- survival: the win and the top three ---")
seed()
cn = sqlite3.connect(fa.DB_PATH)
for i in range(1, 8):
    cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, google_sub, gems) VALUES (?,?,1000,0,0,?,NULL,0)",
               ("P%d" % i, "P%d" % i, "TST" if i <= 3 else None))
cn.commit()
data = {"reached_elimination": True, "leave_order": ["P%d" % i for i in range(1, 8)]}
n = fa.apply_survival_round(cn.cursor(), "round1", "2026-10-07 12:00:00", data, set())
cn.commit()
check("a seven-player round was rated", n, 7)
check("first place: 30", pts("P1"), 30)
check("second and third: 15 each", (pts("P2"), pts("P3")), (15, 15))
check("fourth and below, and non-members: none", q("SELECT COUNT(*) FROM clan_points WHERE norm_name IN ('P4','P5','P6','P7')")[0][0], 0)
small = {"reached_elimination": True, "leave_order": ["P1", "P2", "P3", "P4", "P5"]}
fa.apply_survival_round(cn.cursor(), "round2", "2026-10-07 13:00:00", small, set())
cn.commit()
check("a field of five has no top three (the win still counts)", (pts("P1"), pts("P2"), pts("P3")), (60, 15, 15))
cn.close()
check("balances reconcile", reconciled(), 0)

print("\n--- ranking the clans ---")
seed()
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO clans (tag, created_by, created_at, gems) VALUES ('ALP','x','2026-01-01',0)")
for nm, elo in (("A1", 2000), ("A2", 2000)):
    cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, gems) VALUES (?,?,?,5,5,'ALP',0)", (nm, nm, elo))
now = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
old = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() - 20 * 86400))
for clan, nn, kind, p, at, ref in (("TST", "M1", "team-win", 10, now, "r1"), ("TST", "M2", "survival-win", 30, now, "r2"),
                                    ("ALP", "A1", "team-win", 10, now, "r3"), ("ALP", "A2", "survival-win", 30, old, "r4"),
                                    ("ALP", "A2", "survival-win", 30, old, "r5")):
    cn.execute("INSERT INTO clan_points (clan, norm_name, name, kind, points, ref, at) VALUES (?,?,?,?,?,?,?)",
               (clan, nn, nn, kind, p, ref, at))
cn.commit()
cn.close()


def order(html):
    seen = []
    for tag in ("TST", "ALP"):
        i = html.find('href="/clan/%s"' % tag)
        if i >= 0:
            seen.append((i, tag))
    return [t for _, t in sorted(seen)]


h = client().get("/clans").get_data(as_text=True)
check("by default, by points all time: ALP has 70, TST 40", order(h), ["ALP", "TST"])
check("the page says how points are earned", "a survival top 3 15" in h, True)
h = client().get("/clans?by=points&period=week").get_data(as_text=True)
check("this week: old points do not count, TST leads 40 to 10", order(h), ["TST", "ALP"])
h = client().get("/clans?by=skill").get_data(as_text=True)
check("by skill: ALP (2000 avg) still first, and a different title", (order(h), "Ranked by the average skill" in h), (["ALP", "TST"], True))
w("DELETE FROM clan_points")
h = client().get("/clans").get_data(as_text=True)
check("with no points anywhere the table is not empty", "<tbody>" in h and 'href="/clan/ALP"' in h, True)
check("clan totals", (fa.clan_points_totals(sqlite3.connect(fa.DB_PATH).cursor()), fa.clan_points_rank(sqlite3.connect(fa.DB_PATH).cursor(), "TST")), ({}, (None, 0)))

print("\n--- ranking the members of a clan ---")
w("INSERT INTO clan_points (clan, norm_name, name, kind, points, ref, at) VALUES ('TST','M2','M2','survival-win',30,'q1',?)", (now,))
w("INSERT INTO clan_points (clan, norm_name, name, kind, points, ref, at) VALUES ('TST','M1','M1','team-win',10,'q2',?)", (now,))
w("INSERT INTO clan_points (clan, norm_name, name, kind, points, ref, at) VALUES ('TST','MOD','MOD','team-win',10,'q3',?)", (now,))
w("INSERT INTO clan_points (clan, norm_name, name, kind, points, ref, at) VALUES ('TST','GONE','GONE','team-win',20,'q4',?)", (now,))
h = client().get("/clan/TST").get_data(as_text=True)
body = h.split("<tbody>")[1]                       # the roster, not the "Run by" line above it
pos = {n: body.find('href="/player/%s"' % n) for n in ("M1", "M2", "MOD", "BOSS")}
check("members are listed by points: M2 (30) before M1 and MOD (10) before BOSS (0)",
      pos["M2"] < pos["M1"] < pos["BOSS"] and pos["M2"] < pos["MOD"] < pos["BOSS"], True)
check("the clan total counts a member who left too (30+10+10+20)", "<b class=\"blue\">70</b>" in h, True)
check("the page shows the points column", ">Points<" in h, True)
check("a member's points are in the roster", "<b>30</b>" in h, True)

print("\n--- an application carries a note ---")
seed()
fa.bio_blocked = (lambda real: lambda t: True if "BADWORD" in str(t).upper() else real(t))(fa.bio_blocked)
w("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES ('TST','sub:out','2026-01-01','moderator')") if False else None
r = client("sub:out").post("/clan/apply", json={"clan": "TST", "name": "OUTSIDER", "note": "  Main on weekends,   love team mode  "})
check("applied", r.status_code, 200)
check("the reply mentions the note", "note went with it" in r.get_json()["message"], True)
row = q("SELECT note, gems FROM clan_invites WHERE name='OUTSIDER' AND direction='application'")[0]
check("the note is tidied and saved, with no gem ask", row, ("Main on weekends, love team mode", 0))
cn = sqlite3.connect(fa.DB_PATH)
apps = fa.clan_applications(cn.cursor(), "TST")
cn.close()
check("the leader's list carries it", apps[0]["note"], "Main on weekends, love team mode")
fa.bot_authorised = lambda: True
r = client().get("/api/bot/clan/applications/undelivered")
check("and so does the bot's feed", r.get_json()["applications"][0]["note"], "Main on weekends, love team mode")
h = client(BOSS).get("/myclan").get_data(as_text=True)
check("the leader sees the note on the requests tab", "Main on weekends, love team mode" in h, True)
w("DELETE FROM clan_invites")
r = client("sub:out").post("/clan/apply", json={"clan": "TST", "name": "OUTSIDER", "note": "x" * 501})
check("a note over 500 characters is refused", (r.status_code, "501" in r.get_json()["message"]), (400, True))
r = client("sub:out").post("/clan/apply", json={"clan": "TST", "name": "OUTSIDER", "note": "this has a badword in it"})
check("a blocked word is refused", r.status_code, 400)
r = client("sub:out").post("/clan/apply", json={"clan": "TST", "name": "OUTSIDER"})
check("no note is fine", r.status_code, 200)
check("an application with no note shows as such", "No note." in client(BOSS).get("/myclan").get_data(as_text=True), True)

print("\n--- applying from Discord, with a note ---")
seed()
w("INSERT INTO discord_links (account_sub, discord_id, username, linked_at) VALUES ('sub:out', 'd-out', 'out', '2026-01-01')")
r = client().post("/api/bot/clan/apply", json={"discord_id": "d-out", "clan": "TST", "note": "Found you on Discord"})
j = r.get_json()
check("the Discord command works (it had no route before)", (r.status_code, j["ok"]), (200, True))
check("with the name on the account and the note", q("SELECT name, note FROM clan_invites WHERE direction='application'"), [("OUTSIDER", "Found you on Discord")])
r = client().post("/api/bot/clan/apply", json={"discord_id": "d-out", "clan": "TST"})
j = r.get_json()
check("a second application is refused in plain words, not a bare error", (r.status_code, j["ok"], "pending" in j["message"]), (200, False, True))
r = client().post("/api/bot/clan/apply", json={"discord_id": "d-nobody", "clan": "TST"})
check("someone with no linked account is told how", (r.status_code, r.get_json()["ok"]), (200, False))
fa.bot_authorised = lambda: False
check("and the bot must be authorised", client().post("/api/bot/clan/apply", json={"discord_id": "d-out", "clan": "TST"}).status_code, 401)
fa.bot_authorised = lambda: True

print("\n--- removing a member with a reason ---")
seed()
w("INSERT INTO discord_links (account_sub, discord_id, username, linked_at) VALUES (?, 'd-m2', 'm2', '2026-01-01')", (M2,))
r = client(BOSS).post("/clan/remove", json={"name": "M2", "reason": "nonsense"})
check("an unknown reason is refused", r.status_code, 400)
r = client(BOSS).post("/clan/remove", json={"name": "M2", "reason": "names", "message": "x" * 301})
check("a message over 300 characters is refused", r.status_code, 400)
check("nothing happened yet", q("SELECT clan FROM players WHERE norm_name='M2'")[0][0], "TST")
r = client(BOSS).post("/clan/remove", json={"name": "M2", "reason": "names",
                                             "message": "Your name is too close to another member's."})
check("removed", r.status_code, 200)
check("and told why", "told why" in r.get_json()["message"], True)
check("off the roster", q("SELECT clan FROM players WHERE norm_name='M2'")[0][0], None)
rem = q("SELECT clan, name, removed_by_name, reason, message, seen, notified FROM clan_removals")
check("the clan logged it", rem, [("TST", "M2", "BOSS", "names", "Your name is too close to another member's.", 0, 0)])
h = client(M2).get("/account").get_data(as_text=True)
check("the removed player sees who, which clan and why on their account page",
      all(x in h for x in ("BOSS", "TST", "Conflicting names", "too close to another member")), True)
check("an outsider sees no such notice", "Conflicting names" in client("sub:out").get("/account").get_data(as_text=True), False)
r = client("sub:out").post("/clan/notice/seen", json={"id": 1})
check("only the player can dismiss it", (r.status_code, q("SELECT seen FROM clan_removals")[0][0]), (404, 0))
r = client(BOSS).get("/myclan")
check("the leader's page keeps the log", all(x in r.get_data(as_text=True) for x in ("Removed from the clan", "Conflicting names", "too close")), True)
r = client().get("/api/bot/clan/removals/undelivered")
got = r.get_json()["removals"]
check("the bot is told, with the Discord id", (len(got), got[0]["discord_id"], got[0]["reason_label"]), (1, "d-m2", "Conflicting names"))
client().post("/api/bot/clan/removals/delivered", json={"ids": [got[0]["id"]]})
check("and only once", client().get("/api/bot/clan/removals/undelivered").get_json()["removals"], [])
r = client(M2).post("/clan/notice/seen", json={"id": got[0]["id"]})
check("the player dismisses it", (r.status_code, q("SELECT seen FROM clan_removals")[0][0]), (200, 1))
check("and it is gone from their page", "Conflicting names" in client(M2).get("/account").get_data(as_text=True), False)
check("the log stays", len(q("SELECT * FROM clan_removals")), 1)

print("\n--- a removal with no reason is still logged; a hand-fix by the site is not ---")
r = client(BOSS).post("/clan/remove", json={"name": "M1"})
check("removed without a reason", r.status_code, 200)
check("logged with none", q("SELECT reason, message FROM clan_removals WHERE name='M1'"), [("", "")])
check("the player is not told 'why' when there is nothing to say", "told why" in r.get_json()["message"], False)
r = client().post("/clan/remove", json={"name": "MOD"}, headers={"X-API-Key": "k"})
check("the site's own key removes quietly", (r.status_code, q("SELECT COUNT(*) FROM clan_removals WHERE name='MOD'")[0][0]), (200, 0))

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
