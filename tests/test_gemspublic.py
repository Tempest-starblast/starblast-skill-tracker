# -*- coding: utf-8 -*-
"""The released site (9.80.0): gems are on for everyone, the reset is closed,
and a player who starts at zero can claim what their record already earned."""
import io
import json
import os
import re
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
TMP = tempfile.mkdtemp(prefix="gemspub")
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


print("\n--- released ---")
check("GEMS_PUBLIC is on", fa.GEMS_PUBLIC, True)
check("the release reset is closed", fa.app.test_client().post(
    "/api/dev/gem-release", data="{}", content_type="application/json",
    headers={"X-API-Key": "k"}).status_code, 403)

# A player who starts at zero with a real record: 60 wins.
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM gem_ledger WHERE owner = ?", (N("PUBPLAYER"),))
cn.execute("DELETE FROM players WHERE norm_name = ?", (N("PUBPLAYER"),))
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems) "
           "VALUES ('PUBPLAYER', ?, 1400, 60, 30, 'sub:pub', 0)", (N("PUBPLAYER"),))
cn.commit()
cn.close()

print("\n--- a stranger ---")
st = fa.app.test_client()
check("sees the Shop", st.get("/shop").status_code, 200)
check("the front page is the board", 'id="qcard"' in st.get("/").get_data(as_text=True), True)

print("\n--- a signed-in player ---")
pl = fa.app.test_client()
with pl.session_transaction() as s:
    s["google_sub"] = "sub:pub"
home = pl.get("/").get_data(as_text=True)
check("their front page is their own page", 'class="idname"' in home and "PUBPLAYER" in home, True)
check("the board is one tab over", 'id="qcard"' in pl.get("/leaderboard").get_data(as_text=True), True)
me = pl.get("/me").get_json()
check("they start at zero", me.get("gems"), 0)
check("with Shop and Achievements in the menu",
      {n.get("id") for n in me.get("nav", [])} >= {"achTab", "shopTab"}, True)
check("the Achievements page opens", pl.get("/achievements").status_code, 200)

print("\n--- what their record earned is theirs to claim ---")
pay = {a["key"]: a["gems"] for a in fa.gem_achievement_catalog()}
r = pl.post("/achievements/claim", json={"key": "wins-50"}).get_json()
check("a 60-win record claims 'wins-50'", bool(r.get("ok")), True)
check("  and is paid", q("SELECT gems FROM players WHERE norm_name = ?", N("PUBPLAYER")), [(pay["wins-50"],)])
r = pl.post("/achievements/claim", json={"key": "wins-50"}).get_json()
check("  once", (r.get("ok"), q("SELECT gems FROM players WHERE norm_name = ?", N("PUBPLAYER"))),
      (False, [(pay["wins-50"],)]))
r = pl.post("/achievements/claim", json={"key": "wins-100"}).get_json()
check("  and not what it has not earned", bool(r.get("ok")), False)

print("\n--- the words ---")
h = st.get("/info").get_data(as_text=True)
check("the Info page explains gems, with the numbers in",
      ">Gems<" in h and "A rated win pays <b>%d</b>" % fa.GEM_WIN in h and not re.search(r"\[\[[A-Z]+\]\]", h), True)
h = st.get("/changelog").get_data(as_text=True)
check("the changelog says so", "Gems are here" in h and "Everyone starts at zero" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
