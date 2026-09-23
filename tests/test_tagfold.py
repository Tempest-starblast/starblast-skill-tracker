# -*- coding: utf-8 -*-
"""A clan member who restyles their name still counts for their account -
and two members who read alike still count for neither."""
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
TMP = tempfile.mkdtemp(prefix="tagfold")
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


TEMP = "\u0166\u0247m\u1d7d\u0247s\u0167"                    # Ŧɇmᵽɇsŧ
DOM = "\u0110\u00d8M\u0197\u0141\u0197\u023b\ua740"          # ĐØMƗŁƗȻꝀ
NOOB = "\u20a6\u00d8\u00d8\u0e3f\u20a5\u20b3\u20b4\u20ae\u0246\u2c64"
L7 = "\u01417"                                               # Ł7

cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM clans")
cn.execute("DELETE FROM clan_tag_styles")
cn.execute("INSERT INTO clans(tag, display_tag, created_by, created_at) VALUES ('L7', ?, 'x', datetime('now'))", (L7,))
cn.execute("INSERT INTO clan_tag_styles(clan, shown, created_by, created_at) VALUES ('L7', ?, 'x', ?)",
           (L7, fa._stamp()))
for nm, sub in ((TEMP, "sub:t"), (DOM, "sub:d"), (NOOB, "sub:n"), ("PALADIN", "sub:p")):
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,clan) "
               "VALUES (?,?,?,?,?,?,'L7')", (nm, N(nm), 1500, 20, 10, sub))
cn.commit()
cn.close()
fa.tag_cache_reset()
c = sqlite3.connect(fa.DB_PATH).cursor()

print("\n--- the name as written still wins, unchanged ---")
check("the styled name resolves as it always did",
      fa.clan_member_for_tagged_name(c, "(%s)%s" % (L7, TEMP)), TEMP)
check("a member whose name is already plain, too",
      fa.clan_member_for_tagged_name(c, "(%s)PALADIN" % L7), "PALADIN")

print("\n--- and a restyled member is found now ---")
check("(L7)TEMPEST reaches the account written in stroked letters",
      fa.clan_member_for_tagged_name(c, "(%s)TEMPEST" % L7), TEMP)
check("(L7) DOMILICK too",
      fa.clan_member_for_tagged_name(c, "(%s) DOMILICK" % L7), DOM)
check("and NOOBMASTER, which is spelt in currency signs",
      fa.clan_member_for_tagged_name(c, "(%s)NOOBMASTER" % L7), NOOB)

print("\n--- the gates that stop it guessing ---")
check("no tag, no attribution - the tag is the evidence",
      fa.clan_member_for_tagged_name(c, "TEMPEST"), None)
check("a name nobody in the clan has is still nobody",
      fa.clan_member_for_tagged_name(c, "(%s)STRANGER" % L7), None)
check("another clan's tag does not reach into this one",
      fa.clan_member_for_tagged_name(c, "(ZZ)TEMPEST"), None)

print("\n--- two members who read alike identify neither ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,clan) "
           "VALUES ('TEMPEST', ?, 1500, 5, 5, 'sub:plain', 'L7')", (N("TEMPEST"),))
cn.commit()
cn.close()
fa.tag_cache_reset()
c = sqlite3.connect(fa.DB_PATH).cursor()
check("the plain one still matches itself exactly",
      fa.clan_member_for_tagged_name(c, "(%s)TEMPEST" % L7), "TEMPEST")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE players SET name='Tempest ', norm_name=? WHERE google_sub='sub:plain'",
           (N("Tempest2"),))
cn.commit()
cn.close()
fa.tag_cache_reset()
c = sqlite3.connect(fa.DB_PATH).cursor()
got = fa.clan_member_for_tagged_name(c, "(%s)TEMPEST" % L7)
check("with two members reading TEMPEST, it refuses rather than guesses",
      got in (None, "Tempest "), True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
