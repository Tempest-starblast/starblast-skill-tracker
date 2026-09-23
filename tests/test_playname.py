# -*- coding: utf-8 -*-
"""A play name maps a result to its account without a check-in - and the two
ways that could be abused are closed. Runs against a scratch database."""
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
TMP = tempfile.mkdtemp(prefix="pntest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.init_db()
fa.app.config["TESTING"] = True
A, B, C, D, E = "sub:a", "sub:b", "sub:c", "sub:d", "sub:e"

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
for t in ("players", "name_bindings"):
    c.execute("DELETE FROM %s" % t)
rows = [
    # (name, norm, game_name, sub)
    ("FAFA", "FAFA", "AR FAFA", A),          # the case: a tagged play name
    ("AR FAFA", "ARFAFA", None, None),       # the orphan row that has been collecting his games
    ("TEKIT", "TEKIT", None, B),             # an account name somebody might covet
    ("SNEAK", "SNEAK", "TEKIT", C),          # ...and the account coveting it
    ("DEE", "DEE", "SHARED", D),             # two accounts, one play name
    ("EEE", "EEE", "SHARED", E),
]
for name, norm, game, sub in rows:
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, game_name, google_sub) "
              "VALUES (?, ?, 1000, 0, 0, ?, ?)", (name, norm, game, sub))
cn.commit()
fa._PLAY_CACHE["ts"] = 0.0


def who(name, sys_id=5):
    return fa.account_for_ingame_name(c, name, sys_id)


print("\n--- the case ---")
check("a set play name maps to the account, no check-in", who("AR FAFA"), "FAFA")
check("...even though an orphan row of that spelling exists", who("ar fafa"), "FAFA")
check("...and with no lobby id at all", who("AR FAFA", None), "FAFA")
check("the account's own name still maps to nothing new", who("FAFA"), None)

print("\n--- a check-in binding for THIS lobby outranks the play name ---")
c.execute("INSERT INTO name_bindings (sub, in_game_name, sys_id, ship_id, region, bound_at) "
          "VALUES (?, 'AR FAFA', 7, 3, 'america', '2026-09-17 00:00:00')", (B,))
cn.commit()
check("bound lobby -> the bound account", who("AR FAFA", 7), "TEKIT")
check("another lobby -> the play name's account", who("AR FAFA", 8), "FAFA")

print("\n--- the two abuses ---")
check("a play name that is somebody else's ACCOUNT name maps to nobody", who("TEKIT"), None)
check("a play name two accounts both claim maps to nobody", who("SHARED"), None)
check("a default game name never maps", who(sorted(fa.DEFAULT_GAME_NAMES)[0] if fa.DEFAULT_GAME_NAMES else "Hari Seldon"), None)
check("nothing maps to nothing", who("   "), None)

print("\n--- the map follows a change of play name at once ---")
st, payload = fa.perform_set_game_name(c, A, "NEWPLAY")
cn.commit()
check("set play name ok", st, 200)
check("the new name maps immediately", who("NEWPLAY"), "FAFA")
check("the old one no longer does", who("AR FAFA", 9), None)

print("\n--- the sandbox never claims anything ---")
c.execute("INSERT INTO players (name, norm_name, elo, game_name, google_sub) "
          "VALUES ('SANDBOX', 'SANDBOX', 1000, 'GHOSTNAME', ?)", (fa.SANDBOX_SUB,))
cn.commit()
fa._PLAY_CACHE["ts"] = 0.0
check("a sandbox play name maps to nobody", who("GHOSTNAME"), None)

print("\n--- the public wording says the new rule ---")
import info_text_en as en                                       # noqa: E402
body = dict(en.CARDS)["Checking in, and the green tick"]
check("Info no longer says an unchecked match only counts if you own the name",
      "only counts for you if you own that name" in body, False)
check("Info says a play-name match still counts", "still counts for you" in body, True)
h = fa.app.test_client().get("/play").get_data(as_text=True)
check("Play page no longer says 'only with the check-in'", "only with the check-in" in h, False)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
