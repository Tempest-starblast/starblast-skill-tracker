# -*- coding: utf-8 -*-
"""Social, Play and the clans list on the page pattern (9.33.0)."""
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
TMP = tempfile.mkdtemp(prefix="socplay")
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
for t in ("players", "clans", "clan_admins", "clan_tag_styles", "clan_invites"):
    c.execute("DELETE FROM %s" % t)
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan) VALUES ('ACE', 'ACE', 1444.5, 9, 3, 'sub:ace', 'TST')")
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan) VALUES ('MATE', 'MATE', 1300, 4, 4, 'sub:mate', 'TST')")
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('LEAD', 'LEAD', 1300, 1, 0, 'sub:lead')")
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub) VALUES ('SOLO', 'SOLO', 1200, 2, 2, 'sub:solo')")
st, _ = fa.perform_clan_create(c, "sub:lead", "TST", trusted=True)
cn.commit()
fa.tag_cache_reset()


def client(sub=None):
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        if sub:
            s["google_sub"] = sub
    return cl


print("\n--- Social ---")
r = client("sub:ace").get("/social")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band with counts", ('class="pagehead"' in h) and ("<span>Friends</span><b>" in h) and ("<span>Playing now</span>" in h), True)
check("tabs friends / requests / clan / privacy", all(('data-panel="%s"' % p) in h for p in ("friends", "requests", "clan", "privacy")), True)
for i in ("addq", "addbtn", "addsug", "msg", "hidep", "toast", "askdlg", "asktxt", "askyes", "askno"):
    check("control present: #%s" % i, ('id="%s"' % i) in h, True)
check("clanmates appear on the Clan tab", "TST clanmates" in h.split('<section class="panel" data-panel="clan"')[1].split("</section>")[0], True)
check("Your clan card on the Clan tab", "Your clan" in h.split('<section class="panel" data-panel="clan"')[1].split("</section>")[0], True)
check("privacy switch on its tab", 'id="hidep"' in h.split('<section class="panel" data-panel="privacy"')[1].split("</section>")[0], True)
check("the script is intact (join, befriend, presence, suggestions)", all(x in h for x in ("data-act", "/friends/request", "/friends/presence", "/api/players/search", "/api/social/live")), True)
h = client("sub:solo").get("/social").get_data(as_text=True)
check("no clan: the Clan tab offers to browse", "Browse clans" in h, True)
check("empty requests state", "Nobody is asking to be your friend" in h, True)
r = client(None).get("/social")
check("signed out: band and the sign-in line, no tabs", (r.status_code, "sign in with Discord" in r.get_data(as_text=True), '<nav class="subtabs"' in r.get_data(as_text=True)), (200, True, False))

print("\n--- Play ---")
r = client("sub:ace").get("/play")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band: the rule and the counts", ("Pick a match, press Play" in h) and ("<span>Live now</span>" in h) and ("<span>Tracked</span>" in h), True)
for i in ("youCard", "notSignedIn", "signedIn", "gameName", "acctName", "gnNote", "ckState", "claimRow", "claimName", "youMsg", "lobbyMsg", "rtabs"):
    check("control present: #%s" % i, ('id="%s"' % i) in h, True)
for fn in ("loadMe", "gameNameNote", "saveGameName", "cancelCheckIn", "markCheckedIn", "doClaim", "checkIn", "applyLobbyState", "showRegion"):
    check("handler present: %s" % fn, ("function %s(" % fn) in h, True)
check("region tabs still carry data-region", 'class="rtab on" data-region="' in h or 'class="rtab on"\n            data-region="' in h or 'data-region="america"' in h, True)
check("three steps", h.count('class="step"'), 3)
check("signed out still 200", client(None).get("/play").status_code, 200)

print("\n--- Clans list ---")
r = client(None).get("/clans")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band with the count", ('class="pagehead"' in h) and ("Every clan, ranked" in h), True)
check("directory comes before the request cards", h.index("Every clan") < h.index('id="requestCard"'), True)
for i in ("requestCard", "reqTag", "reqNote", "reqMsg", "stateCard", "stateText", "claimCard", "tagInput", "claimMsg", "signedOutCard", "moreCard", "tagReqList", "moreTag", "moreNote", "moreMsg", "codeCard", "codeInput", "codeMsg"):
    check("control present: #%s" % i, ('id="%s"' % i) in h, True)
check("TST is listed", "/clan/TST" in h, True)
_bar = h.split('<nav class="tabs" id="mainTabs">')[1].split('id="tabmore"')[0]
check("the Clans tab is the one lit on /clans", ('href="/clans"     class="on"' in _bar) and ('href="/"          class="on"' not in _bar), True)
check("changelog entry", "Social, Play and the clans list" in client(None).get("/changelog").get_data(as_text=True), True)
for p in ("/", "/account", "/myclan", "/clan/TST", "/info", "/replays"):
    check("%s 200" % p, client("sub:ace").get(p).status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
