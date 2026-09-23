# -*- coding: utf-8 -*-
"""The rebuilt account page (9.32.0): band, tabs, every control kept."""
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
TMP = tempfile.mkdtemp(prefix="acct")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True

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
for t in ("players", "clans", "clan_admins", "clan_tag_styles", "clan_invites", "match_players"):
    c.execute("DELETE FROM %s" % t)
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan) VALUES ('ACE', 'ACE', 1444.5, 9, 3, 'sub:ace', 'TST')")
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('LEAD', 'LEAD', 1300, 1, 0, 'sub:lead')")
st, _ = fa.perform_clan_create(c, "sub:lead", "TST", trusted=True)
cn.commit()
fa.tag_cache_reset()


def client(sub=None):
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        if sub:
            s["google_sub"] = sub
    return cl


print("\n--- an account with a name ---")
r = client("sub:ace").get("/account")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band: name with the clan badge", ('class="phname"' in h) and ('class="badge"' in h) and (">ACE<" in h), True)
check("band: rank and the numbers", ("<b>#" in h) and ('class="blue big">1444.5' in h) and (">9-3</b>" in h) and (">75%</b>" in h), True)
check("tabs: overview / names / protection / settings, overview default",
      all(('data-panel="%s"' % p) in h for p in ("overview", "names", "protection", "settings")) and 'data-default="overview"' in h, True)
check("no owner tab for a player", 'data-panel="owner"' in h, False)
for i in ("accName", "nameMsg", "tagBox", "tagWhich", "tagBareBtn", "takenBox", "takenWhich", "takenSame", "claimNote",
          "anywayBtn", "claimMsg", "claimCard", "pendingClaims", "claimList", "withdrawMsg", "protCard", "prot",
          "protConfirm", "protWhy", "protMsg", "inboxCard", "missedList", "inviteList", "updateList", "inboxMsg",
          "heldCard", "heldList", "forgotCard", "forgotName", "forgotMsg", "accBio", "accBioCount", "accBioMsg",
          "currentName", "signedIn", "tabInbox"):
    check("control present: #%s" % i, ('id="%s"' % i) in h, True)
for fn in ("saveName", "showTag", "saveBare", "showTaken", "loadClaims", "withdrawClaim", "doClaim", "loadProt",
           "setProt", "applyProt", "loadInbox", "decideMissed", "answerInvite", "forgotClaim", "pickTagStyle", "loadMe"):
    check("handler present: %s" % fn, ("function %s(" % fn) in h, True)
check("the shared sub-tab script is on the page", "window.sbShowPanel" in h, True)
check("no matches yet: the Overview says so with a Play button", ("No rated matches yet" in h) and ('class="phcta go" href="/play"' in h), True)
check("Discord lives on Settings", "Discord" in h.split('<section class="panel" data-panel="settings"')[1].split("</section>")[0], True)
check("Your account is no longer a bar tab", 'class="metab' in h, False)

print("\n--- no name yet ---")
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('X-TEMP', 'XTEMP', 1000, 0, 0, 'sub:new')")
c.execute("DELETE FROM players WHERE google_sub = 'sub:new'")
cn.commit()
h = client("sub:new").get("/account").get_data(as_text=True)
check("band says no name yet and points at Names", ("No name yet" in h) and ('href="#names"' in h), True)
check("Names is the default tab", 'data-default="names"' in h, True)
check("no numbers block", 'class="phnums"' in h, False)
check("no bio card without a name", 'id="accBio"' in h, False)

print("\n--- signed out / owner ---")
r = client(None).get("/account")
check("signed out: 200, asked to sign in, no tabs", (r.status_code, "Sign in at the top" in r.get_data(as_text=True), '<nav class="subtabs"' in r.get_data(as_text=True)), (200, True, False))
fa.OWNER_SUBS = set(fa.OWNER_SUBS) | {"sub:owner"}
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('OWNER', 'OWNER', 2000, 30, 1, 'sub:owner')")
cn.commit()
h = client("sub:owner").get("/account").get_data(as_text=True)
check("owner gets the Owner tab and the sandbox buttons", ('data-panel="owner"' in h) and ("Test as a new player" in h) and ("Test as this player" in h), True)

print("\n--- the old suites' expectations still hold on the new page ---")
h = client("sub:ace").get("/account").get_data(as_text=True)
check("tagBox for the tag prompt", 'id="tagBox"' in h, True)
r = client("sub:ace").get("/changelog")
check("changelog entry", "Your account rebuilt" in r.get_data(as_text=True), True)
for p in ("/", "/myclan", "/clan/TST", "/social", "/play"):
    check("%s 200" % p, client("sub:ace").get(p).status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
