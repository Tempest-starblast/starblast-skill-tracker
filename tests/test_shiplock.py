# -*- coding: utf-8 -*-
"""An early-access tester buys at the tier they earned, not the one they pick."""
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="shiplock")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402
import ranks                                                    # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.GEMS_PUBLIC = True
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


# DOM has genuinely reached Raider (level 3) and has plenty of test money.
# A crowd above him matters: on a board he tops, being number one IS Mythos
# by design, which hands him every hull and hides the thing being tested.
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players")
for i in range(40):
    cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses) VALUES (?,?,?,?,?)",
               ("RIVAL%02d" % i, N("RIVAL%02d" % i), 2600 - i * 10, 60, 20))
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,peak_div,"
           "peak_rank,gems) VALUES ('DOM',?,1500,40,20,'sub:dom','pulse',18,999999)",
           (N("DOM"),))
cn.commit()
cn.close()
c = sqlite3.connect(fa.DB_PATH).cursor()
check("DOM's earned tier is Raider (3)", fa.gem_peak_level(c, N("DOM")), 3)

def as_access(level=None, kind="access", sub="sub:dom"):
    """A FRESH client each time. Dom's session is an ACCESS key - himself, on
    his real account - optionally with a tier picked in the bar. Sharing one
    client across scenarios let one section's session leak into the next."""
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        s["google_sub"] = sub
        s["preview"] = True
        s["preview_kind"] = kind
        if level:
            s["preview_level"] = level
    return cl


def buy(cl, code):
    r = cl.post("/shop/buy", data=json.dumps({"kind": "ship", "code": code}),
                content_type="application/json")
    return r.get_json() or {}



ODYSSEY, WARDEN_HULL, RAIDER_HULL = 701, 603, 302

print("\n--- the lens is gone from an access session ---")
cl = as_access(level=ranks.TOP_CLIMBABLE)
r = cl.post("/dev/level", data=json.dumps({"level": 8}), content_type="application/json")
check("/dev/level refuses an access session", r.status_code, 403)
h = cl.get("/").get_data(as_text=True)
check("the bar shows no tier picker", 'id="devTier"' in h, False)
check("but the bar itself is still there", "early access as yourself" in h, True)

print("\n--- and a stale picked tier no longer counts ---")
# a preview_level cookie left over from before the fix
with fa.app.test_request_context("/"):
    fa.session["preview"] = True
    fa.session["preview_kind"] = "access"
    fa.session["preview_level"] = ranks.TOP_CLIMBABLE
    fa.session["google_sub"] = "sub:dom"
    check("preview_level_for ignores it", fa.preview_level_for(N("DOM")), 0)

print("\n--- so the hulls above his tier are refused ---")
cl = as_access(level=ranks.TOP_CLIMBABLE)
j = buy(cl, ODYSSEY)
check("the Odyssey is refused", j.get("ok"), False)
check("and says why", "Climb" in (j.get("message") or ""), True)
j = buy(cl, WARDEN_HULL)
check("a tier-6 hull is refused too", j.get("ok"), False)

print("\n--- what he HAS earned still sells ---")
cl = as_access(level=ranks.TOP_CLIMBABLE)
j = buy(cl, RAIDER_HULL)
check("a tier-3 hull sells to a Raider", j.get("ok"), True)

print("\n--- the shop draws the locks ---")
cl = as_access(level=ranks.TOP_CLIMBABLE)
resp = cl.get("/shop")
h = resp.get_data(as_text=True)
check("locked tiles carry the locked class", 'class="ship locked"' in h, True)
check("and a padlock", "&#128274;" in h or "\U0001f512" in h, True)
check("the Odyssey is not offered for sale", "Locked &middot;" in h, True)

print("\n--- a sandbox tester is untouched: nothing there is real ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub,gems) "
           "VALUES ('SANDBOX',?,1500,30,10,'test:sandbox:1',999999)", (N("SANDBOX"),))
cn.commit()
cn.close()
with fa.app.test_request_context("/"):
    fa.session["preview"] = True
    fa.session["preview_kind"] = "sandbox"
    fa.session["preview_level"] = ranks.TOP_CLIMBABLE
    fa.session["google_sub"] = "test:sandbox:1"
    check("the sandbox lens still works", fa.preview_level_for(N("SANDBOX")),
          ranks.TOP_CLIMBABLE)
sb = as_access(level=ranks.TOP_CLIMBABLE, kind="sandbox", sub="test:sandbox:1")
r = sb.post("/dev/level", data=json.dumps({"level": 5}), content_type="application/json")
check("and the sandbox may still pick a tier", r.status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
