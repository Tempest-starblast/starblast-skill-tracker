# -*- coding: utf-8 -*-
"""Alpha Orionis Wars (9.78.0): its own rating, the board's rules with the
bars doubled, only players already on the board, never the main board."""
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
TMP = tempfile.mkdtemp(prefix="aow")
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


def post(path, payload):
    return fa.app.test_client().post(path, data=json.dumps(payload),
                                     content_type="application/json", headers=HDR)


def board_players(names, elo=1000.0, wins=1, losses=1):
    cn = sqlite3.connect(fa.DB_PATH)
    for n in names:
        cn.execute("DELETE FROM players WHERE norm_name = ?", (N(n),))
        cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
                   (n, N(n), elo, wins, losses))
    cn.commit()
    cn.close()


def aow_payload(mid, teams, winner, peaks=None, presence=None, **extra):
    names = [n for t in teams for n in t]
    p = {"match_id": mid, "sys_id": 9898, "region": "america", "teams": teams, "winner": winner,
         "peak_scores": peaks or dict((n, 9000) for n in names),
         "presence": presence or dict((n, 1.0) for n in names),
         "watch_s": 3600, "tracked_reads": 1100, "match_key": "raw_9898_america_2",
         "team_counts": [len(t) + 60 for t in teams]}
    p.update(extra)
    return p


print("\n--- tables ---")
tabs = {r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table'")}
check("the four AOW tables exist",
      {"aow_ratings", "aow_matches", "aow_match_players", "aow_announce"} <= tabs, True)
check("the bars are the board's, doubled",
      (fa.AOW_MIN_WIN_PEAK, fa.AOW_MIN_LOSE_PEAK, fa.AOW_MIN_PRESENCE_MIN, fa.AOW_MIN_MATCH_MIN),
      (2 * fa.MIN_RATED_PEAK, 2 * fa.MIN_LOCK_SCORE, 20, 20))

print("\n--- same elo rules: a three-team AOW match moves exactly as the board does ---")
W, L1, L2 = ["SAMEW1", "SAMEW2", "SAMEW3"], ["SAMEA1", "SAMEA2"], ["SAMEB1", "SAMEB2", "SAMEB3"]
board_players(W + L1 + L2)
presence = dict((n, 1.0) for n in W + L1 + L2)
presence["SAMEW3"] = 0.3                       # a late winner: the half stake
main = {"match_id": "same-main", "sys_id": 7001, "region": "america",
        "winning_team": W, "losing_team_1": L1, "losing_team_2": L2,
        "scores": dict((n, 9000) for n in W + L1 + L2),
        "peak_scores": dict((n, 9000) for n in W + L1 + L2),
        "presence": presence, "half_elo": ["SAMEW3"], "watch_s": 3000, "tracked_reads": 900}
check("main board match accepted", post("/api/game_end", main).status_code in (200, 201), True)
main_d = dict(q("SELECT mp.norm_name, mp.delta FROM match_players mp JOIN matches m "
                "ON m.id = mp.match_row WHERE m.match_id = 'same-main'"))
r = post("/api/aow_end", aow_payload("same-aow", [W, L1, L2], 0, presence=presence,
                                     half_elo=["SAMEW3"]))
check("AOW match accepted", (r.status_code, (r.get_json() or {}).get("rated")), (200, 8))
aow_d = dict(q("SELECT ap.norm_name, ap.delta FROM aow_match_players ap JOIN aow_matches am "
               "ON am.id = ap.match_row WHERE am.match_id = 'same-aow'"))
for n in W + L1 + L2:
    check("  %s: AOW %+.2f = board %+.2f" % (n, aow_d.get(N(n), 0), main_d.get(N(n), 0)),
          abs(aow_d.get(N(n), 99) - main_d.get(N(n), -99)) < 0.02, True)

print("\n--- the main board is never touched by AOW ---")
before = q("SELECT norm_name, elo, wins, losses FROM players WHERE norm_name IN (?,?,?)",
           N("SAMEW1"), N("SAMEA1"), N("SAMEB1"))
post("/api/aow_end", aow_payload("untouched-aow", [W, L1, L2], 1))
check("board ratings and records unchanged",
      q("SELECT norm_name, elo, wins, losses FROM players WHERE norm_name IN (?,?,?)",
        N("SAMEW1"), N("SAMEA1"), N("SAMEB1")), before)
check("no board match row made", q("SELECT COUNT(*) FROM matches WHERE match_id LIKE '%aow%'")[0][0], 0)

print("\n--- only players already on the board, and the doubled bars ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players WHERE norm_name IN (?,?)", (N("AOWONLY"), N("NOGAMES")))
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES ('NOGAMES', ?, 1000, 0, 0)",
           (N("NOGAMES"),))
cn.commit()
cn.close()
board_players(["BARW1", "BARW2", "BARL1", "BARL2", "PROT"])
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET strict_mode = 1 WHERE norm_name = ?", (N("PROT"),))
cn.commit()
cn.close()
peaks = {"BARW1": 9000, "BARW2": 3999, "BARL1": 150, "BARL2": 900, "AOWONLY": 9000,
         "NOGAMES": 9000, "PROT": 9000}
r = post("/api/aow_end", aow_payload("bars-aow", [["BARW1", "BARW2", "AOWONLY", "NOGAMES", "PROT"],
                                                  ["BARL1", "BARL2"]], 0, peaks=peaks))
rated = {x[0] for x in q("SELECT ap.norm_name FROM aow_match_players ap JOIN aow_matches am "
                         "ON am.id = ap.match_row WHERE am.match_id = 'bars-aow'")}
held = json.loads(q("SELECT held FROM aow_matches WHERE match_id = 'bars-aow'")[0][0])
check("a winner at 9,000 is rated", N("BARW1") in rated, True)
check("a winner at 3,999 is not - the bar is 4,000", (N("BARW2") in rated, held.get("BARW2")), (False, "low-score"))
check("a loser at 150 is not - the bar is 200", (N("BARL1") in rated, held.get("BARL1")), (False, "low-score"))
check("a loser at 900 is rated", N("BARL2") in rated, True)
check("a name with no board row is not rated", (N("AOWONLY") in rated, held.get("AOWONLY")), (False, "aow-only"))
check("a board row with no games is not rated", (N("NOGAMES") in rated, held.get("NOGAMES")), (False, "aow-only"))
check("a protected account with no check-in is not rated", held.get("PROT"), "protected")
check("the AOW-only name got no AOW rating", q("SELECT COUNT(*) FROM aow_ratings WHERE norm_name = ?", N("AOWONLY"))[0][0], 0)

print("\n--- the unrated weigh on nobody: an AOW-only teammate changes nothing ---")
board_players(["WGHW", "WGHL"])
c1 = post("/api/aow_end", aow_payload("wgh-1", [["WGHW"], ["WGHL"]], 0)).get_json()
d1 = dict(q("SELECT ap.norm_name, ap.delta FROM aow_match_players ap JOIN aow_matches am "
            "ON am.id = ap.match_row WHERE am.match_id = 'wgh-1'"))
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM aow_ratings WHERE norm_name IN (?,?)", (N("WGHW"), N("WGHL")))
cn.commit()
cn.close()
post("/api/aow_end", aow_payload("wgh-2", [["WGHW", "STRANGER1", "STRANGER2"], ["WGHL"]], 0))
d2 = dict(q("SELECT ap.norm_name, ap.delta FROM aow_match_players ap JOIN aow_matches am "
            "ON am.id = ap.match_row WHERE am.match_id = 'wgh-2'"))
check("same deltas with or without AOW-only teammates", d1 == d2, True)

print("\n--- five teams: every side rated, the books close ---")
teams = [["FIVE%d%d" % (t, i) for i in range(4)] for t in range(5)]
board_players([n for tm in teams for n in tm])
r = post("/api/aow_end", aow_payload("five-aow", teams, 3))
rows = q("SELECT ap.team, ap.won, ap.delta FROM aow_match_players ap JOIN aow_matches am "
         "ON am.id = ap.match_row WHERE am.match_id = 'five-aow'")
check("all 20 rated", len(rows), 20)
check("winners gain", all(d > 0 for t, w, d in rows if w), True)
check("losers lose", all(d < 0 for t, w, d in rows if not w), True)
check("winners are team 4", {t for t, w, d in rows if w}, {3})
check("the books close (gains = losses)", abs(sum(d for _, _, d in rows)) < 0.1, True)

print("\n--- one result, once ---")
snap = q("SELECT norm_name, elo, wins, losses FROM aow_ratings ORDER BY norm_name")
r = post("/api/aow_end", aow_payload("five-aow", teams, 3))
check("a repeat is 'already recorded'", (r.get_json() or {}).get("status"), "already recorded")
check("and moves nothing", q("SELECT norm_name, elo, wins, losses FROM aow_ratings ORDER BY norm_name"), snap)
check("a bad payload is refused", post("/api/aow_end", {"match_id": "x", "teams": [["A"]], "winner": 3}).status_code, 400)
check("no key, no entry", fa.app.test_client().post("/api/aow_end", json={}).status_code, 401)

print("\n--- the pages ---")
cl = fa.app.test_client()
h = cl.get("/aow").get_data(as_text=True)
check("/aow renders", cl.get("/aow").status_code, 200)
check("  with the AOW board", "SAMEW1" in h and "AOW board" in h, True)
check("  the results, by team, with the replay", "Team 4" in h and "/replay/r/raw_9898_america_2" in h, True)
check("  the doubled bars, stated", "4,000" in h and "20 minutes" in h, True)
check("  and why some were not rated", "no record on the board yet" in h, True)
h = cl.get("/player/SAMEW1").get_data(as_text=True)
check("a rated player's profile shows the AOW card", 'id="aowCard"' in h, True)
board_players(["NEVERAOW"])
check("an unrated player's does not", 'id="aowCard"' in cl.get("/player/NEVERAOW").get_data(as_text=True), False)

print("\n--- the banner and the live status ---")
real_start = fa.AOW_SESSION_START
fa._aow_fetch_players = lambda: 187
fa.AOW_SESSION_START = int(time.time()) + 20 * 3600
h = cl.get("/").get_data(as_text=True)
check("20 h before: the strip is on the board", 'id="aowstrip"' in h and 'data-phase="soon"' in h, True)
check("  with the theme glow", 'class="aowglow"' in h, True)
check("  but not on the AOW page itself", 'id="aowstrip"' in cl.get("/aow").get_data(as_text=True), False)
fa.AOW_SESSION_START = int(time.time()) - 1800
fa._AOW_STATUS["at"] = 0
d = cl.get("/api/aow/status").get_json()
check("half an hour in: live, with the headcount", (d["phase"], d["players"]), ("live", 187))
fa.AOW_SESSION_START = int(time.time()) + 10 * 86400
check("ten days out: no strip", 'id="aowstrip"' in cl.get("/").get_data(as_text=True), False)
fa.AOW_SESSION_START = int(time.time()) - 3 * 3600
fa._AOW_STATUS["at"] = 0
fa._aow_fetch_players = lambda: 2
check("hours in and nearly empty: over", cl.get("/api/aow/status").get_json()["phase"], "over")

print("\n--- Discord: two reminders and each result, compact, no pings ---")
bot = fa.app.test_client()
fa.AOW_SESSION_START = int(time.time()) + 3000
posts = bot.get("/api/bot/aow/undelivered", headers=HDR).get_json()["posts"]
kinds = [p["kind"] for p in posts]
check("50 minutes out: the hour reminder is due", "reminder-hour" in kinds, True)
check("  the ten-minute one is not", "reminder-ten" in kinds, False)
check("  every result is waiting (six recorded; the repeat was refused)",
      sum(1 for k in kinds if k.startswith("result-")), 6)
res = [p for p in posts if p["kind"].startswith("result-")]
check("  result posts fit in one Discord message", all(len(p["text"]) <= 1900 for p in res), True)
check("  and carry the AOW board link", all("/aow>" in p["text"] for p in res), True)
bot.post("/api/bot/aow/delivered", json={"kinds": kinds}, headers=HDR)
check("delivered ones are not offered again", bot.get("/api/bot/aow/undelivered", headers=HDR).get_json()["posts"], [])
fa.AOW_SESSION_START = int(time.time()) + 300
kinds = [p["kind"] for p in bot.get("/api/bot/aow/undelivered", headers=HDR).get_json()["posts"]]
check("five minutes out: the ten-minute reminder", kinds, ["reminder-ten"])

print("\n--- a 200-player result stays one message, names made safe ---")
big = [["BIG%03d" % i for i in range(100)], ["BIG%03d" % i for i in range(100, 200)]]
board_players([n for t in big for n in t] + ["@everyone*"])
big[0][0] = "@everyone*"
post("/api/aow_end", aow_payload("big-aow", big, 0))
txt = [p for p in bot.get("/api/bot/aow/undelivered", headers=HDR).get_json()["posts"]
       if p["kind"].startswith("result-")][0]["text"]
check("200 rated, one message", ("200 players rated" in txt, len(txt) <= 1900), (True, True))
check("no live @everyone in it", "@everyone" in txt, False)

fa.AOW_SESSION_START = real_start
print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
