# -*- coding: utf-8 -*-
"""9.35.0: fewer tabs, Survival folded away, home + header lined up."""
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
TMP = tempfile.mkdtemp(prefix="consol")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.OWNER_SUBS = set(fa.OWNER_SUBS) | {"sub:owner"}

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def bar_of(h):
    return h.split('<nav class="tabs" id="mainTabs">')[1].split('id="tabmore"')[0]


def menu_of(h):
    return h.split('id="tabmore"')[1].split("</nav>")[0]


c = sqlite3.connect(fa.DB_PATH)
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)",
          ("Owner One", fa.normalize_name("Owner One"), 1700, 9, 2, "sub:owner", "TST"))
c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
          ("Loner", fa.normalize_name("Loner"), 1500, 3, 1, "sub:loner"))
c.execute("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", ("TST", "sub:owner", "2026-09-01 00:00:00"))
c.commit()
c.close()

app = fa.app.test_client()

print("\n--- the bar, signed out ---")
h = app.get("/replays").get_data(as_text=True)
bar, menu = bar_of(h), menu_of(h)
check("no Survival tab", "/survival" in bar, False)
check("no Your clan tab", "/myclan" in bar, False)
check("the six public tabs", [x for x in ("/leaderboard", "/play", "/clans", "/social", "/replays", "/info") if x not in bar and not (x == "/leaderboard" and 'href="/"' in bar)], [])
check("Survival mode still on the Replays page", 'href="/replays?mode=survival"' in h, True)

print("\n--- Survival folded away ---")
r = app.get("/survival")
check("/survival -> the survival board", (r.status_code, r.headers.get("Location")), (302, "/?mode=survival"))
r = app.get("/survival/replay")
check("/survival/replay without a key -> survival replays", (r.status_code, r.headers.get("Location")), (302, "/replays?mode=survival"))
h = app.get("/?mode=survival").get_data(as_text=True)
check("the board's Survival mode answers and has no Players/Clans switch", ("Survival" in h) and ('class="lbtabs"' not in h), True)
h = app.get("/clans").get_data(as_text=True)
check("the clans list has no Players/Clans switch either", 'class="lbtabs"' in h, False)
check("no survival template left", os.path.exists("templates/survival.html") or os.path.exists("templates/_lbtabs.html"), False)

print("\n--- Your clan, one press away ---")
with app.session_transaction() as s:
    s["google_sub"] = "sub:owner"
h = app.get("/clans").get_data(as_text=True)
check("Clans band offers Your clan to a member", '<a class="phcta" href="/myclan">' in h, True)
check("Your clan in the menu", 'href="/myclan"' in menu_of(h), True)
check("not in the bar", 'href="/myclan"' in bar_of(h), False)
h = app.get("/myclan").get_data(as_text=True)
check("menu button lit on Your clan", 'aria-label="More"\n       class="on"' in h or 'aria-label="More"\n       class="on' in h, True)
with app.session_transaction() as s:
    s["google_sub"] = "sub:loner"
h = app.get("/clans").get_data(as_text=True)
check("no Your clan button for someone without a clan (gems off)", ('href="/myclan"' in h.split('class="pagehead"')[1].split("</div>\n</div>")[0]), False)

print("\n--- header column + home (owner preview) ---")
h = app.get("/replays").get_data(as_text=True)
check("header column stretches its rows", "#authIn{flex-direction:column;align-items:stretch" in h, True)
with app.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True
h = app.get("/").get_data(as_text=True)
check("home renders", ('class="profcard"' in h), True)
check("no Where to tiles", ("Where to" in h) or ('class="go"' in h), False)
check("emblem and name share a top line", "align-items:flex-start;padding:22px 24px" in h, True)
check("Achievements + Recent form kept", ("Achievements</h2>" in h) and ("Recent form</h2>" in h), True)
j = app.get("/me").get_json()
tops = [e.get("id") for e in j.get("nav", []) if e.get("top")]
ids = [e.get("id") for e in j.get("nav", [])]
check("Shop and Events are the bar tabs for the owner", tops, ["shopTab", "eventsTab"])
check("Achievements and Free agents are menu entries", ("achTab" in ids) and ("agentsTab" in ids), True)
h = app.get("/clans").get_data(as_text=True)
check("Clans band offers Free agents while gems are on", 'class="phcta ghost" href="/agents"' in h, True)

print("\n--- everything answers ---")
for p in ("/", "/leaderboard", "/play", "/clans", "/social", "/replays", "/info", "/changelog", "/account", "/myclan", "/agents", "/shop", "/achievements"):
    check("%s 200" % p, app.get(p).status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
