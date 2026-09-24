# -*- coding: utf-8 -*-
"""Replays, Survival, Info and Changelog on the page pattern (9.34.0)."""
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
TMP = tempfile.mkdtemp(prefix="pages2")
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


app = fa.app.test_client()

print("\n--- Replays ---")
r = app.get("/replays")
check("team 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band + counts", ("Every match, replayable" in h) and ("<span>Matches</span>" in h) and ("<span>Page</span>" in h or "<span>Seite</span>" in h), True)
check("mode tabs in the shared look, team on", ('<nav class="subtabs"' in h) and ('href="/replays" class="on"' in h), True)
check("filters kept", all(x in h for x in ('name="date"', 'name="sys"', 'name="q"', 'name="mode"')), True)
r = app.get("/replays?mode=survival")
check("survival 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("survival band + rounds count", ("Every survival round, replayed" in h) and ("<span>Rounds</span>" in h), True)
check("survival tab on", 'href="/replays?mode=survival" class="on"' in h, True)
check("no server-name filter in survival mode", 'name="q"' in h, False)
check("tabs are plain links, not panels (the shared script ignores them)", "data-panel" in h.split('<nav class="subtabs"')[1].split("</nav>")[0], False)

print("\n--- Survival (folded into the board and Replays) ---")
r = app.get("/survival")
check("old page sends you to the survival board", (r.status_code, r.headers.get("Location", "")), (302, "/?mode=survival"))
r = app.get("/survival/replay?key=nope")
check("a bad replay key lands on the survival replays", (r.status_code, r.headers.get("Location", "")), (302, "/replays?mode=survival"))

print("\n--- Info ---")
r = app.get("/info")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band with the search inside it", ('class="pagehead"' in h) and ('id="iq"' in h.split('class="pagehead"')[1].split("</div>\n</div>")[0] if 'class="pagehead"' in h else False), True)
check("clear button + no-match line kept", ('id="iclear"' in h) and ('id="inomatch"' in h), True)
import info_i18n                                                # noqa: E402
n = len(info_i18n.page("en")["cards"])
check("every card rendered (%d)" % n, h.count('<div class="card">'), n)
check("card count named in the band", ("%d short cards" % n) in h, True)
check("deep link script kept", "URLSearchParams(location.search).get('q')" in h, True)
r = app.get("/info?lang=de")
check("German 200 with the German clans card", (r.status_code, "Dein Kontoname bist nur du" in r.get_data(as_text=True)), (200, True))

print("\n--- the board search suggestions sit above the board ---")
import re as _re                                                # noqa: E402
h = app.get("/").get_data(as_text=True)
m = _re.search(r"#qcard\{[^}]*z-index:(\d+)", h)
check("the search card has a z-index above the table (9.75.2)", bool(m) and int(m.group(1)) > 0, True)
check("  and below the period menu", bool(m) and int(m.group(1)) < 40, True)
check("  the suggestion box is inside that card", h.find('id="qdd"') > h.find('id="qcard"') > 0, True)

print("\n--- Changelog ---")
r = app.get("/changelog")
check("200", r.status_code, 200)
h = r.get_data(as_text=True)
check("band with the version", ("Every change, newest first" in h) and (("v" + fa.APP_VERSION) in h), True)
check("release cards + NEW script kept", ('class="card rel"' in h) and ("sbClogSeen" in h) and ('class="dayhead"' in h), True)
check("entry for this step", "Replays, Survival, Info and the changelog" in h, True)

print("\n--- everything else still answers ---")
for p in ("/", "/play", "/social", "/clans", "/account", "/myclan"):
    check("%s 200" % p, app.get(p).status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
