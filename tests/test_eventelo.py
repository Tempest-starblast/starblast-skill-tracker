# -*- coding: utf-8 -*-
"""A hosted event's match moves rating 1.5x, both ways (9.70.0).

The same match is scored twice from the same starting ratings: once in an
ordinary lobby, once in a lobby that is a live event. Every delta in the
second must be 1.5x the first, winners and losers alike, and the two
matches must net the same share of nothing - the multiplier is applied
after the balancing, so it cannot create or destroy rating."""
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

import flask_app as fa                                          # noqa: E402

TMP = tempfile.mkdtemp(prefix="evelo")
fa.DB_PATH = os.path.join(TMP, "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)   # the full schema
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa._load_api_keys = lambda: {"test-key"}
HDR = {"X-API-Key": "test-key"}
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


WIN = ["EVA", "EVB", "EVC"]
LOSE = ["EVD", "EVE", "EVF"]
START = {"EVA": 1100.0, "EVB": 1000.0, "EVC": 950.0,
         "EVD": 1050.0, "EVE": 1000.0, "EVF": 900.0}


def reset():
    """Everyone back to the same starting line, with a history so nobody
    is provisional and the experience multiplier is the same for all."""
    cn = sqlite3.connect(fa.DB_PATH)
    c = cn.cursor()
    for n, e in START.items():
        c.execute("DELETE FROM players WHERE norm_name = ?", (n,))
        c.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
                  (n, n, e, 20, 20))
    cn.commit()
    cn.close()


def play(match_id, sys_id):
    payload = {
        "match_id": match_id, "sys_id": sys_id, "region": "america",
        "winning_team": WIN, "losing_team_1": LOSE, "losing_team_2": [],
        "scores": dict([(n, 12000) for n in WIN] + [(n, 8000) for n in LOSE]),
        "presence": dict((n, 1.0) for n in WIN + LOSE),
        "watch_s": 2400, "tracked_reads": 700,
    }
    cl = fa.app.test_client()
    r = cl.post("/api/game_end", data=json.dumps(payload),
                content_type="application/json", headers=HDR)
    check("game_end for %s accepted" % match_id, r.status_code in (200, 201), True)
    cn = sqlite3.connect(fa.DB_PATH)
    out = dict(cn.execute(
        "SELECT mp.norm_name, mp.delta FROM match_players mp JOIN matches m ON m.id = mp.match_row "
        "WHERE m.match_id = ?", (match_id,)).fetchall())
    cn.close()
    return out


print("\n--- the constant ---")
check("EVENT_K_MULT is 1.5", fa.EVENT_K_MULT, 1.5)

print("\n--- an ordinary match ---")
reset()
plain = play("evelo-plain", 4242)
check("six players rated", len(plain), 6)

print("\n--- the same match, as a hosted event ---")
reset()
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO events (kind, start_at, state, sid) VALUES (?,?,?,?)",
           ("team", "2026-09-23 16:00:00", "live", 5151))
cn.commit()
c = cn.cursor()
check("the lobby is recognised as an event", bool(fa.event_live_row(c, 5151)), True)
check("  and the ordinary one is not", fa.event_live_row(c, 4242), None)
cn.close()
event = play("evelo-event", 5151)
check("six players rated", len(event), 6)

print("\n--- every delta is 1.5x, both ways ---")
for n in WIN + LOSE:
    a, b = plain.get(n) or 0.0, event.get(n) or 0.0
    check("%s: %+.2f -> %+.2f" % (n, a, b), abs(b - a * 1.5) < 0.05, True)
check("winners still gain", all((event.get(n) or 0) > 0 for n in WIN), True)
check("losers still lose", all((event.get(n) or 0) < 0 for n in LOSE), True)

print("\n--- and the books still close ---")
net_plain = sum(plain.values())
net_event = sum(event.values())
check("the event nets 1.5x what the ordinary match nets (i.e. still ~nothing)",
      abs(net_event - net_plain * 1.5) < 0.1, True)
moved = sum(abs(v) for v in event.values())
check("  relative drift stays inside the multiplier bound",
      abs(net_event) / moved < 0.35 if moved else True, True)

print("\n--- and the event page says so ---")
h = io.open(os.path.join(ROOT, "templates/events.html"), encoding="utf-8").read()
check("the events page states the multiplier", "1.5&times;" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
