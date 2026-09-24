# -*- coding: utf-8 -*-
"""Everyone who plays is rated, and the ineligible count for no one (9.74.0).

The scorer no longer caps a side at eight; the site must rate a big roster
in full. And a player the site refuses to rate must not weigh on anyone
else's rating (owner: "they don't count for other people's elo"). That was
already true - team strength averages only players in elo_map, which is
built from the filtered lists - and this guards it."""
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

TMP = tempfile.mkdtemp(prefix="everyone")
fa.DB_PATH = os.path.join(TMP, "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)
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


def reset(elos):
    cn = sqlite3.connect(fa.DB_PATH)
    for n, e in elos.items():
        cn.execute("DELETE FROM players WHERE norm_name = ?", (n,))
        cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)",
                   (n, n, e, 20, 20))
    cn.commit()
    cn.close()


def play(match_id, sys_id, win, l1, l2, ambiguous=()):
    everyone = win + l1 + l2
    payload = {"match_id": match_id, "sys_id": sys_id, "region": "europe",
               "winning_team": win, "losing_team_1": l1, "losing_team_2": l2,
               "scores": dict((n, 9000) for n in everyone),
               "peak_scores": dict((n, 9000) for n in everyone),
               "presence": dict((n, 1.0) for n in everyone),
               "ambiguous": list(ambiguous), "watch_s": 2400, "tracked_reads": 730}
    with fa.app.test_client() as tc:
        r = tc.post("/api/game_end", data=json.dumps(payload),
                    content_type="application/json", headers=HDR)
    cn = sqlite3.connect(fa.DB_PATH)
    out = dict(cn.execute("SELECT mp.norm_name, mp.delta FROM match_players mp JOIN matches m "
                          "ON m.id = mp.match_row WHERE m.match_id = ?", (match_id,)).fetchall())
    cn.close()
    return r.status_code, out


print("\n--- a big roster is rated in full ---")
W = ["EVW%02d" % i for i in range(23)]
L1 = ["EVL%02d" % i for i in range(20)]
L2 = ["EVM%02d" % i for i in range(19)]
reset(dict((n, 1000.0) for n in W + L1 + L2))
code, got = play("every-big", 70001, W, L1, L2)
check("accepted", code in (200, 201), True)
check("all 23 winners rated", sum(1 for n in W if n in got), 23)
check("all 39 losers rated", sum(1 for n in L1 + L2 if n in got), 39)
check("winners gain", all(got[n] > 0 for n in W), True)
check("losers lose", all(got[n] < 0 for n in L1 + L2), True)

print("\n--- a loser the site refuses to rate weighs on nobody ---")
base = {"EVA": 1000.0, "EVB": 1000.0, "EVC": 1000.0, "EVD": 1000.0, "EVE": 1000.0,
        "EVSTRONG": 2600.0}
reset(base)
_, plain = play("every-plain", 70002, ["EVA", "EVB"], ["EVC", "EVD"], ["EVE"])
reset(base)
# The same match with a very strong player on losing side 1 whose name two
# ships flew at once - the site holds him ('duplicate-name'). If he still
# counted toward his side's strength, beating that side would pay more.
_, held = play("every-held", 70003, ["EVA", "EVB"], ["EVC", "EVD", "EVSTRONG"], ["EVE"],
               ambiguous=["EVSTRONG"])
check("the refused player is not rated", "EVSTRONG" in held, False)
for n in ("EVA", "EVB", "EVC", "EVD", "EVE"):
    check("  %s moves exactly as if he were not there (%+.2f)" % (n, plain.get(n, 0)),
          abs((held.get(n) or 0) - (plain.get(n) or 0)) < 0.01, True)

print("\n--- the words match ---")
en = io.open(os.path.join(ROOT, "info_text_en.py"), encoding="utf-8").read()
check("the Info page no longer says top eight", "top eight" in en, False)
check("it says everyone", "<b>everyone</b> who was in it for <b>ten minutes</b>" in en, True)
spec = io.open(os.path.join(ROOT, "RATING_SPEC.md"), encoding="utf-8").read()
check("the spec says no roster cap", "no roster cap" in spec.lower() or "**There is no roster cap**" in spec, True)
for lang in ("es", "fr", "de", "it", "ru", "vi", "zh", "fa"):
    m = __import__("info_text_" + lang)
    check("%s shows the English for the two changed cards" % lang,
          set(getattr(m, "STALE", ())) >= {2, 14}, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
