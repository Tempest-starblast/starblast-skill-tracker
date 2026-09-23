# -*- coding: utf-8 -*-
"""The rebuilt clan pages and the flatter tab bar (9.31.0). Scratch database."""
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
TMP = tempfile.mkdtemp(prefix="clanpages")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
L, M, N, O = "sub:lead", "sub:member", "sub:nobody", "sub:other"

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
for t in ("players", "clans", "clan_admins", "clan_tag_styles", "clan_invites", "free_agents",
          "survival_players", "gem_ledger"):
    c.execute("DELETE FROM %s" % t)


def add_player(name, sub=None, clan=None, w=0, l=0, elo=1300):
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan) "
              "VALUES (?, ?, ?, ?, ?, ?, ?)", (name, fa.normalize_name(name), elo, w, l, sub, clan))


add_player("BOSS", L, None, 10, 2, 1600)
add_player("MEMBER", M, "TST", 4, 2, 1400)
add_player("NOBODY", N, None, 1, 1)
add_player("OTHER", O, "XYZ", 2, 2)
st, _ = fa.perform_clan_create(c, L, "TST", trusted=True)
check("TST created", st, 200)
c.execute("UPDATE players SET clan = 'TST' WHERE google_sub = ?", (L,))
c.execute("INSERT OR REPLACE INTO survival_players (norm_name, name, elo, rounds, wins, best_place) VALUES ('MEMBER', 'MEMBER', 1010, 3, 2, 1)")
cn.commit()
fa.tag_cache_reset()


def client(sub=None, preview=False):
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        if sub:
            s["google_sub"] = sub
        if preview:
            s["preview"] = True
    return cl


print("\n--- a plain member finally gets their clan on /myclan ---")
r = client(M).get("/myclan")
check("member: 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("member sees the header band with the tag", ('class="chtag">TST' in h), True)
check("...run by the leader", "Run by" in h and ">BOSS<" in h, True)
check("...and the numbers (2 members, 14-4 record, 2 survival wins)", (">2</b>" in h) and (">14-4</b>" in h) and ("<span>Survival</span><b>2</b>" in h), True)
_nav = h.split('<nav class="subtabs"')[1].split('</nav>')[0]
check("member has the Members and You tabs only", (_nav.count('data-panel="'), h.count('<section class="panel" data-panel="')), (2, 2))
check("...no management panels", ('data-panel="requests"' in h) or ('id="linkUrl"' in h) or ('id="confirmTag"' in h), False)
check("member can leave", 'onclick="leaveClan()"' in h, True)
check("member's own row is marked", 'class="mcrow me"' in h, True)
check("not the 'you run no clan' page", "You do not run a clan" in h, False)

print("\n--- the leader gets every tab, every control keeps its id ---")
r = client(L).get("/myclan")
check("leader: 200", r.status_code, 200)
h = r.get_data(as_text=True)
for p in ("members", "requests", "invite", "appearance", "roles", "settings", "you"):
    check("tab + panel: %s" % p, h.count('data-panel="%s"' % p), 2)
for i in ("linkUrl", "memberName", "regionSel", "rn_player", "rc_player", "themeRow", "styleList",
          "styleNew", "clanBio", "transferSel", "confirmTag", "rankHelp", "appMsg", "invitedMsg",
          "memberMsg", "roleMsg", "linkMsg", "regionMsg", "profileMsg", "styleMsg", "transferMsg",
          "deleteMsg", "youMsg"):
    check("control present: #%s" % i, ('id="%s"' % i) in h, True)
for fn in ("copyLink", "newLink", "revokeLink", "decideApp", "cancelInvite", "addMember", "removeMember",
           "pickRank", "askRemove", "setRole", "saveRegion", "deleteClan", "saveRoleNames", "styleAdd",
           "styleAct", "saveProfile", "transferClan", "leaveClan", "roleHelp", "pickColor", "pickTheme"):
    check("handler present: %s" % fn, ("function %s(" % fn) in h, True)
check("Your clan is in the menu, not the bar", ('href="/myclan"' in h.split('id="tabmore"')[1]) and ('href="/myclan"' not in h.split('<nav class="tabs" id="mainTabs">')[1].split('id="tabmore"')[0]), True)
c.execute("INSERT INTO clan_invites (clan, name, created_at, status, direction) VALUES ('TST', 'NOBODY', '2026-09-18', 'pending', 'application')")
cn.commit()
h = client(L).get("/myclan").get_data(as_text=True)
check("a waiting request shows as a count on the Requests tab", 'Requests<span class="n hot">1</span>' in h, True)

print("\n--- nobody / signed out ---")
r = client(N).get("/myclan")
check("clan-less: 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("...told plainly, with the places to go", ("You are not in a clan" in h) and ('href="/clans"' in h) and ('href="/social"' in h), True)
check("...no free-agent trace outside the preview", "/agents" in h, False)
h = client(N, preview=True).get("/myclan").get_data(as_text=True)
check("...free agents offered inside the preview", 'href="/agents"' in h, True)
r = client(None).get("/myclan")
check("signed out: 200 and asked to sign in", (r.status_code, "Sign in at the top" in r.get_data(as_text=True)), (200, True))

print("\n--- the public clan page ---")
r = client(None).get("/clan/TST")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("header band", ('class="chtag">TST' in h) and ("Run by" in h), True)
check("membership card with the one button", ('id="enroll"' in h) and ('id="applyBtn"' in h) and ('id="joinText"' in h), True)
check("roster rows carry the name and role", ('data-name="MEMBER"' in h) and ('class="rolechip"' in h), True)
check("no treasury for a visitor", "Treasury" in h, False)
h = client(L, preview=True).get("/clan/TST").get_data(as_text=True)
check("treasury in the band for the owner preview", '<span>Treasury</span><b class="gold">' in h, True)
check("unknown clan is 404", client(None).get("/clan/NOPE").status_code, 404)

print("\n--- the tab bar ---")
h = client(None).get("/").get_data(as_text=True)
for href, label in (("/clans", "Clans"), ("/info", "Info"), ("/social", "Social"), ("/replays", "Replays"), ("/play", "Play")):
    check("bar has %s" % label, ('href="%s"' % href) in h.split('id="tabmore"')[0], True)
bar = h.split('<nav class="tabs" id="mainTabs">')[1].split('id="tabmore"')[0]
check("Your clan is NOT in the bar for a visitor", "/myclan" in bar, False)
check("Your account left the bar (chip + menu carry it)", 'class="metab' in h, False)
menu = h.split('class="tabmenu"')[1].split("</div>\n  </div>")[0]
check("menu keeps the long tail", all(x in menu for x in ("/live", "/compare", "/customgames", "/reports", "/merge", "/changelog", "/account")), True)
check("menu no longer duplicates Info or Survival", ("/info" in menu) or ("/survival" in menu), False)
check("server tabs land in the bar (JS)", "function sbTabAdd(" in h and "else if(n.top) sbTabAdd(" in h, True)
j = client(L, preview=True).get("/me").get_json()
# The bar is for the two things with something happening in them: what you
# can spend on, and what is on in the next few hours.
check("/me marks Shop and Events as bar tabs",
      [e.get("id") for e in j["nav"] if e.get("top")], ["shopTab", "eventsTab"])
h = client(M).get("/").get_data(as_text=True)
bar = h.split('<nav class="tabs" id="mainTabs">')[1].split('id="tabmore"')[0]
check("Your clan is NOT in the bar for a member (menu + band instead)", 'href="/myclan"' in bar, False)

print("\n--- everything else still answers ---")
for p in ("/", "/clans", "/social", "/info", "/replays", "/account", "/changelog"):
    check("%s 200" % p, client(M).get(p).status_code, 200)
check("changelog carries the entry", "Clan pages rebuilt" in client(None).get("/changelog").get_data(as_text=True), True)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
