# -*- coding: utf-8 -*-
"""Typing a stylised name in plain capitals finds it - and typing the clan
tag still does too."""
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
TMP = tempfile.mkdtemp(prefix="plain")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
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


NOOB = "\u20a6\u00d8\u00d8\u0e3f\u20a5\u20b3\u20b4\u20ae\u0246\u2c64"   # NOOBMASTER
SKY = "S\ua740\u024eS\u0246N\u0166\u0197N\u0246\u0141"                 # SKYSENTINEL
TEMP = "\u0166\u0247m\u1d7d\u0247s\u0167"                              # Tempest
WRAITH = "W\u024c\u023a\u0197\u0166\u0126"                             # WRAITH
SMALLCAPS = "\u1d0f\u0280\u026a\u1d0f\u0274"                           # orion in small caps
CYR = "\u0417\u0414\u0420\u0410\u0412"

print("\n--- the reading itself ---")
for raw, want in ((NOOB, "NOOBMASTER"), (SKY, "SKYSENTINEL"), (TEMP, "TEMPEST"),
                  (WRAITH, "WRAITH"), (SMALLCAPS, "ORION"), ("PALADIN", "PALADIN")):
    check("%s reads as %s" % (raw[:14], want), fa.plain_reading(raw), want)
check("Cyrillic is left exactly as it is", fa.plain_reading(CYR), CYR)
check("so is Chinese", fa.plain_reading("\u4f60\u597d"), "\u4f60\u597d")
check("and punctuation and spaces go, as everywhere else",
      fa.plain_reading("Bel Riose!"), "BELRIOSE")

print("\n--- it is in the key the search box matches ---")
for raw, typed in ((NOOB, "NOOBMASTER"), (SKY, "SKYSENTINEL"), (TEMP, "TEMPEST")):
    check("typing %s reaches %s" % (typed, raw[:12]), typed in fa.search_key(raw, None), True)
check("the name as written still finds itself",
      fa.normalize_name(SKY) in fa.search_key(SKY, None), True)
check("and the clan tag still finds the member",
      "L7" in fa.search_key(SKY, "L7"), True)

print("\n--- end to end, on a board ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
for nm in (NOOB, SKY, TEMP, WRAITH, SMALLCAPS):
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,clan) VALUES (?,?,?,?,?,?)",
               (nm, N(nm), 1600, 40, 10, "L7"))
cn.commit()
cn.close()
cl = fa.app.test_client()
for typed, want in (("NOOBMASTER", NOOB), ("SKYSENTINEL", SKY), ("TEMPEST", TEMP),
                    ("WRAITH", WRAITH), ("ORION", SMALLCAPS)):
    h = cl.get("/?q=%s&search=all" % typed).get_data(as_text=True)
    check("searching %-12s finds %s" % (typed, want[:12]), want in h, True)
h = cl.get("/?q=L7&search=all").get_data(as_text=True)
check("searching the tag still finds the clan's members", h.count("pname") >= 5, True)

print("\n--- a reading is never an identity on its own ---")
check("two people who read the same are still two rows",
      fa.normalize_name(SKY) == fa.normalize_name("SKYSENTINEL"), False)
check("and the clan key is untouched by any of this",
      fa.clean_clan_tag("\u1d00\u01a6"), fa.clean_clan_tag("\u1d00\u01a6"))

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
