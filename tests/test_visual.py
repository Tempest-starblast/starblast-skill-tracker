# -*- coding: utf-8 -*-
"""9.37.0: every page opens with the band; phone overflow fixes present."""
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
TMP = tempfile.mkdtemp(prefix="visual")
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


cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)",
           ("Owner One", fa.normalize_name("Owner One"), 1700, 12, 3, "sub:owner", "TST"))
for i in range(12):
    cn.execute("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)", ("P%02d" % i, "P%02d" % i, 1400 + i * 20, 5 + i, 5))
cn.execute("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", ("TST", "sub:owner", "2026-09-01 00:00:00"))
cn.execute("INSERT INTO survival_results(key, ended_at, region, lobby, winner, elim_field_size, data) VALUES (?,?,?,?,?,?,?)",
           ("500|2026-09-12 10:00:00", "2026-09-12 10:00:00", "europe", "500", "P01", 6,
            '{"winner":"P01","fighters":[{"name":"P01"},{"name":"P02"}],"elim_field_size":6,"ended_at":"2026-09-12 10:00:00","region":"europe","lobby":"500","duration_s":600}'))
cn.commit()
cn.close()

app = fa.app.test_client()
owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True

print("\n--- the band on every page ---")
BAND = 'class="pagehead'
pages = {"/": "Every player, ranked", "/?mode=survival": "Last ship standing, ranked", "/compare": "Two players, side by side",
         "/live": "Live matches", "/customgames": "Played for fun, kept on record", "/reports": "Tell us what went wrong",
         "/merge": "Fold an old name into your account", "/replays": "Every match, replayable", "/info": "in short",
         "/changelog": "Every change, newest first", "/clans": "Every clan, ranked", "/play": "Pick a match, press Play",
         "/social": "Friends, clanmates, who is on", "/account": "Sign in"}
for path, text in pages.items():
    r = app.get(path)
    h = r.get_data(as_text=True)
    check("%s: 200 + band + heading" % path, (r.status_code, BAND in h, text in h), (200, True, True))
h = app.get("/").get_data(as_text=True)
check("board: mode switch is a tab row under the band", ('<nav class="subtabs" role="tablist"' in h) and ('class="modebar"' not in h), True)
check("board: ticker lives inside the band", h.find('class="btick"') < h.find('<nav class="subtabs"') if 'class="btick"' in h else True, True)
check("board: no old title left", 'class="ptitle"' in h, False)
r = owner.get("/survival/replay?key=500%7C2026-09-12%2010%3A00%3A00")
h = r.get_data(as_text=True)
check("survival replay: 200 + band with the lobby + back link in the eyebrow", (r.status_code, 'class="pagehead rhead"' in h, '<p class="pheye"><a class="rback"' in h), (200, True, True))
h = owner.get("/agents").get_data(as_text=True)
check("agents (owner): band with the listed count", (BAND in h) and ("Players for hire" in h) and ("<span>Listed</span>" in h) and ('class="ptitle"' not in h), True)
for path in ("/compare", "/live", "/customgames", "/reports", "/merge", "/replays"):
    check("%s: no old title" % path, 'class="ptitle"' in app.get(path).get_data(as_text=True), False)

print("\n--- phone overflow + rows ---")
h = io.open("templates/clans.html", encoding="utf-8").read()
check("clans table wrapped for sideways scroll", '<div class="tablewrap">\n  <table class="board">' in h, True)
h = app.get("/").get_data(as_text=True)
check("board hero stacks on a phone, pods may shrink", (".hero{flex-direction:column}" in h) and (".pod{min-width:0}" in h), True)
check("mini player above the phone tab bar", "bottom:74px" in h, True)
check("info button rule shared", ".pheye .infobtn{" in h, True)
h = app.get("/replays").get_data(as_text=True)
check("replay text filters flex into one row", ".rpfilters input[type=text]{flex:1 1 150px" in h, True)
h = owner.get("/account").get_data(as_text=True)
check("name rows are centred flex rows", (".phname{" in h) and ("align-items:center;gap:6px 8px" in h), True)
h = app.get("/changelog").get_data(as_text=True)
check("changelog entry", "One header everywhere" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
