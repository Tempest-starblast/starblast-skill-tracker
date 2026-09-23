# -*- coding: utf-8 -*-
"""The preview front door: the owner gets the home, everyone else gets the
site exactly as it was - with no trace that a home exists.

"No trace" is the property most worth testing, so a stranger's and an
ordinary player's pages are searched for every string the preview adds.
"""
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
TMP = tempfile.mkdtemp(prefix="hometest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa.init_db()
fa.app.config["TESTING"] = True
OWNER, PLAYER = "discord:owner-under-test", "discord:plain-player"
fa.OWNER_SUBS = {OWNER}

cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
cn.execute("DELETE FROM gem_ledger")
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems) "
           "VALUES ('OWNERGUY','OWNERGUY',1900,40,20,?,0)", (OWNER,))
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, gems) "
           "VALUES ('PLAINGUY','PLAINGUY',1300,5,5,?,0)", (PLAYER,))
cn.commit()
c = cn.cursor()
fa.gem_grant(c, "player", "OWNERGUY", 4321, "backfill", "v1")
fa.gem_grant(c, "player", "OWNERGUY", 250, "achievement", "wins-10")
cn.commit()
cn.close()
# In a two-player scratch board the owner is rank 1, so the peak recorder will
# hand over every division. Run it here, synchronously, and read the balance it
# leaves - the pages must show THAT number, whatever it is.
fa._BOARD_CACHE.clear()
_b = fa.board_bundle('team', 'all', fa.ALL_REGIONS)
fa._record_peaks(_b.get("entries") or [])
cn = sqlite3.connect(fa.DB_PATH)
EXPECTED = cn.execute("SELECT COALESCE(gems,0) FROM players WHERE norm_name='OWNERGUY'").fetchone()[0]
cn.close()
print("owner balance after the recorder:", EXPECTED)

ok = fail = 0
TRACES = ("gchip", "achTab", "/achievements", ">Home<", "Not released")


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def client(sub=None):
    cl = fa.app.test_client()
    if sub:
        with cl.session_transaction() as s:
            s["google_sub"] = sub
    return cl


def page(cl, path):
    r = cl.get(path)
    return r.status_code, r.get_data(as_text=True)


print("\n--- a stranger sees the board, with no trace of any of it ---")
code, h = page(client(), "/")
check("/ is 200", code, 200)
check("it is the leaderboard", "Leaderboard" in h and "Recent form" not in h, True)
for t in TRACES:
    check("no %r anywhere in the page" % t, t in h, False)
me = client().get("/me").get_json()
check("/me carries no gems", me.get("gems"), None)

print("\n--- an ordinary signed-in player: same board, same silence ---")
cl = client(PLAYER)
code, h = page(cl, "/")
check("/ is the board", code == 200 and "Recent form" not in h, True)
for t in TRACES:
    check("no %r for a signed-in player" % t, t in h, False)
me = cl.get("/me").get_json()
check("/me carries no gems for them", me.get("gems"), None)
check("/me has no Achievements entry", any(n.get("id") == "achTab" for n in me.get("nav", [])), False)
check("/achievements is 404 for them", cl.get("/achievements").status_code, 404)

print("\n--- the owner gets the home ---")
cl = client(OWNER)
code, h = page(cl, "/")
check("/ is 200", code, 200)
check("it is the home, not the board", "Recent form" in h and "Achievements" in h, True)
check("it says it is unreleased", "Not released" in h, True)
check("it shows the name", "OWNERGUY" in h, True)
check("it shows the balance", "{:,}".format(EXPECTED) in h, True)
check("it shows the earned milestones", "First blood" in h and "Getting somewhere" in h, True)
check("it names the next one", "Next:" in h, True)
check("the tab strip has Home and Leaderboard", ">Home<" in h and 'href="/leaderboard"' in h, True)
check("the gem chip is in the header", 'id="gchip"' in h, True)

print("\n--- the board is still reachable, exactly where its own links point ---")
code, h = page(cl, "/?region=europe")
check("/?region=... is the board", code == 200 and "Recent form" not in h, True)
code, h = page(cl, "/leaderboard")
check("/leaderboard is the board", code == 200 and "Recent form" not in h, True)

print("\n--- /me for the owner ---")
me = cl.get("/me").get_json()
check("carries the balance", me.get("gems"), EXPECTED)
check("adds Achievements to the menu", any(n.get("id") == "achTab" for n in me.get("nav", [])), True)

print("\n--- an owner with NO player row still gets the board, not an error ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players WHERE google_sub = ?", (OWNER,))
cn.commit()
cn.close()
code, h = page(client(OWNER), "/")
check("/ is 200 and the board", code == 200 and "Recent form" not in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
