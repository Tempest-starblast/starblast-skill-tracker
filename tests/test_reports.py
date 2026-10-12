# -*- coding: utf-8 -*-
"""Match reports, merge requests on Discord, and the play name in force while a
match was played (9.83.0). Runs against a scratch database."""
import io
import json
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
TMP = tempfile.mkdtemp(prefix="reports")
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
fa.bot_authorised = lambda: True
fa.OWNER_SUBS = {"sub:owner"}
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


def client(sub=None):
    cl = fa.app.test_client()
    if sub:
        with cl.session_transaction() as s:
            s["google_sub"] = sub
    return cl


def stamp(ago_s=0):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() - ago_s))


for t in ("players", "matches", "match_players", "match_reports", "merge_requests", "discord_links", "play_name_log"):
    w("DELETE FROM %s" % t)
w("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('VICTIM', 'VICTIM', 1300, 10, 10, 'sub:victim')")
w("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('OTHER', 'OTHER', 1500, 5, 5, 'sub:other')")
w("INSERT INTO discord_links (account_sub, discord_id, username, linked_at) VALUES ('sub:victim', 'd-victim', 'v', '2026-01-01')")
for mid, ago, won, delta in ((1, 3600, 0, -40.0), (2, 7200, 1, 30.0), (3, 10 * 86400, 0, -25.0), (4, 5000, 0, -12.5)):
    w("INSERT INTO matches (id, match_id, sys_id, played_at, region, lobby_name) VALUES (?, ?, 100, ?, 'america', 'Test Lobby')",
      (mid, "m-%d" % mid, stamp(ago)))
    w("INSERT INTO match_players (match_row, name, norm_name, won, delta, half) VALUES (?, 'VICTIM', 'VICTIM', ?, ?, 0)",
      (mid, won, delta))

print("\n--- reporting a loss ---")
r = client().post("/match/report", json={"match_row": 1, "reason": "impostor"})
check("signed out: refused", r.status_code, 401)
r = client("sub:victim").post("/match/report", json={"match_row": 1, "reason": "made-up"})
check("an unknown reason is refused", r.status_code, 400)
r = client("sub:victim").post("/match/report", json={"match_row": 2, "reason": "impostor"})
check("a win cannot be reported", r.status_code, 400)
r = client("sub:victim").post("/match/report", json={"match_row": 3, "reason": "impostor"})
check("a loss older than the window cannot", (r.status_code, "7 days" in r.get_json()["message"]), (400, True))
r = client("sub:other").post("/match/report", json={"match_row": 1, "reason": "impostor"})
check("someone else's match cannot", r.status_code, 404)
r = client("sub:victim").post("/match/report", json={"match_row": 1, "reason": "impostor", "note": "x" * 501})
check("a note over 500 characters is refused", r.status_code, 400)
r = client("sub:victim").post("/match/report", json={"match_row": 1, "reason": "impostor", "note": "I was asleep, someone copied my name"})
check("a real report is taken", (r.status_code, "40.0" in r.get_json()["message"]), (200, True))
r = client("sub:victim").post("/match/report", json={"match_row": 1, "reason": "impostor"})
check("once per match", r.status_code, 400)
h = client("sub:victim").get("/account").get_data(as_text=True)
check("the account page shows it as reported, and offers Report on the other loss",
      ("Reported" in h, "openReport(4" in h, "openReport(1" in h, "openReport(3" in h), (True, True, False, False))

print("\n--- the owner sees it on Discord ---")
got = client().get("/api/bot/matchreports/undelivered").get_json()["reports"]
check("the bot is handed the report with what to decide on",
      (len(got), got[0]["name"], got[0]["reason_label"], got[0]["delta"], "replay/1" in got[0]["replay"]),
      (1, "VICTIM", "Someone else was flying my name", -40.0, True))
client().post("/api/bot/matchreports/delivered", json={"ids": [got[0]["id"]]})
check("and only once", client().get("/api/bot/matchreports/undelivered").get_json()["reports"], [])

print("\n--- approving gives the loss back ---")
rid = got[0]["id"]
r = client().post("/api/bot/matchreports/decide", json={"id": rid, "decision": "approved", "decided_by": "tempest"}).get_json()
check("approved", (r["ok"], r["status"], r["refund"]), (True, "approved", 40.0))
check("rating back and the loss off the record", q("SELECT elo, losses FROM players WHERE norm_name='VICTIM'"), [(1340.0, 9)])
check("the match row keeps what it was", q("SELECT delta, refunded FROM match_players WHERE match_row=1"), [(0.0, -40.0)])
r = client().post("/api/bot/matchreports/decide", json={"id": rid, "decision": "approved"}).get_json()
check("deciding twice changes nothing", (r["ok"], q("SELECT elo FROM players WHERE norm_name='VICTIM'")[0][0]), (False, 1340.0))
out = client().get("/api/bot/matchreports/outcomes").get_json()["outcomes"]
check("the player is told, on their Discord", (len(out), out[0]["status"], out[0]["discord_id"]), (1, "approved", "d-victim"))
client().post("/api/bot/matchreports/told", json={"ids": [rid]})
check("once", client().get("/api/bot/matchreports/outcomes").get_json()["outcomes"], [])
h = client("sub:victim").get("/account").get_data(as_text=True)
check("the account page shows the refund", "Refunded +40.0" in h, True)

print("\n--- denying changes nothing but the report ---")
client("sub:victim").post("/match/report", json={"match_row": 4, "reason": "bots"})
rid2 = q("SELECT id FROM match_reports WHERE match_row=4")[0][0]
before = q("SELECT elo, losses FROM players WHERE norm_name='VICTIM'")
r = client("sub:owner").post("/dev/reports/%d" % rid2, data={"action": "deny", "note": "the match was fair"})
check("the owner can decide on the site too", r.status_code in (302, 303), True)
check("denied, rating untouched", (q("SELECT status FROM match_reports WHERE id=?", (rid2,))[0][0],
                                   q("SELECT elo, losses FROM players WHERE norm_name='VICTIM'") == before), ("denied", True))
check("only the owner sees the review page", (client("sub:victim").get("/dev/reports").status_code,
                                             client("sub:owner").get("/dev/reports").status_code), (302, 200))

print("\n--- merge requests reach the owner on Discord ---")
w("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES ('ALTNAME', 'ALTNAME', 1180, 1, 0)")
w("INSERT INTO match_players (match_row, name, norm_name, won, delta, half) VALUES (2, 'ALTNAME', 'ALTNAME', 1, 180.0, 0)")
w("INSERT INTO merge_requests (google_sub, from_name, from_norm, to_name, to_norm, reason, status, created_at) "
  "VALUES ('sub:victim', 'ALTNAME', 'ALTNAME', 'VICTIM', 'VICTIM', 'my second name', 'pending', ?)", (stamp(),))
got = client().get("/api/bot/merges/undelivered").get_json()["merges"]
check("the bot is handed the request with both records",
      (len(got), got[0]["from_name"], got[0]["to_name"], got[0]["from_rec"], got[0]["requester"]),
      (1, "ALTNAME", "VICTIM", [1, 0, 1180.0], "VICTIM"))
client().post("/api/bot/merges/delivered", json={"ids": [got[0]["id"]]})
check("shown once", client().get("/api/bot/merges/undelivered").get_json()["merges"], [])
r = client().post("/api/bot/merges/decide", json={"id": got[0]["id"], "decision": "approved", "decided_by": "tempest"}).get_json()
check("approving on Discord merges, exactly as the page does", (r["ok"], r["status"], r["discord_id"]), (True, "approved", "d-victim"))
check("the name's row is gone into the account", q("SELECT COUNT(*) FROM players WHERE norm_name='ALTNAME'")[0][0], 0)
r = client().post("/api/bot/merges/decide", json={"id": got[0]["id"], "decision": "denied"}).get_json()
check("a decided request cannot be decided again", r["ok"], False)

print("\n--- the play name in force while the match was played ---")
for t in ("matches", "match_players", "play_name_log"):
    w("DELETE FROM %s" % t)
w("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, game_name) VALUES ('FAFAMAIN', 'FAFAMAIN', 1500, 10, 2, 'sub:fafa', 'NAMEB')")
for nm in ("FAFAMAIN", "NAMEA", "NAMEB", "X1", "X2", "Y1", "Y2"):
    if not q("SELECT 1 FROM players WHERE norm_name=?", (nm,)):
        w("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?, ?, 1200, 5, 5)", (nm, nm))
# FAFA had NAMEA as his play name for the match, then switched to NAMEB before its result arrived.
w("INSERT INTO play_name_log (sub, name, at) VALUES ('sub:fafa', 'NAMEA', ?)", (stamp(4000),))
w("INSERT INTO play_name_log (sub, name, at) VALUES ('sub:fafa', 'NAMEB', ?)", (stamp(60),))
fa._PLAY_CACHE["ts"] = 0
c = sqlite3.connect(fa.DB_PATH)
check("now: NAMEA is nobody's play name", fa.account_for_ingame_name(c.cursor(), "NAMEA"), None)
check("but during the match it was FAFA's", fa.account_for_ingame_name(c.cursor(), "NAMEA", None, (stamp(2500), stamp(120))), "FAFAMAIN")
check("a window from before he took it finds nobody", fa.account_for_ingame_name(c.cursor(), "NAMEA", None, (stamp(9000), stamp(8000))), None)
c.close()
names = ["NAMEA", "X1", "X2", "Y1", "Y2", "OTHER"]
payload = {"match_id": "pn-1", "sys_id": 777, "region": "america",
           "winning_team": ["NAMEA", "X1"], "losing_team_1": ["X2", "Y1"], "losing_team_2": ["Y2", "OTHER"],
           "scores": dict((n, 9000) for n in names), "peak_scores": dict((n, 9000) for n in names),
           "presence": dict((n, 1.0) for n in names), "watch_s": 2400, "tracked_reads": 700,
           "ended_at": stamp(120)}
r = fa.app.test_client().post("/api/game_end", data=json.dumps(payload), content_type="application/json",
                              headers={"X-API-Key": "k"})
check("the match posts", r.status_code in (200, 201), True)
check("FAFA's win lands on his account, not on the bare name",
      (q("SELECT COUNT(*) FROM match_players WHERE norm_name='FAFAMAIN'")[0][0],
       q("SELECT COUNT(*) FROM match_players WHERE norm_name='NAMEA'")[0][0]), (1, 0))
check("and it remembers the name he flew", q("SELECT played_as FROM match_players WHERE norm_name='FAFAMAIN'"), [("NAMEA",)])

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
