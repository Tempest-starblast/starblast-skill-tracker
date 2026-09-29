# -*- coding: utf-8 -*-
"""Looks on the leaderboard (9.81.0): every row wears its player's name style
and title and its clan's tag look, and hovering a name opens a player card in
the player's own banner, frame and effect."""
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
TMP = tempfile.mkdtemp(prefix="boardlooks")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

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


def first(slot, earned=False):
    for c in fa.COSMETICS:
        ci = fa.COSMETIC_BY_ID[c[0]]
        if ci["slot"] == slot and bool(ci["via"]) == earned:
            return ci
    raise LookupError(slot)


NAME, TITLE, BANNER, FRAME, FX = first("name"), first("title"), first("banner"), first("frame"), first("fx")
ETITLE = first("title", earned=True)
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players WHERE norm_name IN (?, ?, ?, ?)",
           (N("LOOKSGUY"), N("PLAINGUY"), N("EARNEDGUY"), N("NEWGUY")))
cn.execute("DELETE FROM clans WHERE tag = 'LKC'")
cn.execute("INSERT INTO clans (tag, created_by, created_at, cosmetics) VALUES ('LKC', 'x', '2026-09-01', ?)",
           (json.dumps({"tag": "ct-neon"}),))
worn = {"name": NAME["id"], "title": TITLE["id"], "banner": BANNER["id"], "frame": FRAME["id"], "fx": FX["id"]}
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, clan, cosmetics, bio, peak_rank) "
           "VALUES ('LOOKSGUY', ?, 3999, 40, 10, 'LKC', ?, ?, 3)",
           (N("LOOKSGUY"), json.dumps(worn), "Top pilot <script>alert(1)</script> since August"))
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES ('PLAINGUY', ?, 3998, 30, 10)",
           (N("PLAINGUY"),))
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses, cosmetics) VALUES ('EARNEDGUY', ?, 3997, 30, 10, ?)",
           (N("EARNEDGUY"), json.dumps({"title": ETITLE["id"]})))
cn.execute("INSERT INTO players (name, norm_name, elo, wins, losses) VALUES ('NEWGUY', ?, 3996, 1, 1)",
           (N("NEWGUY"),))
cn.commit()
cn.close()
fa._COS_CACHE["ts"] = 0
fa._CLAN_COS_CACHE["ts"] = 0
fa._BOARD_CACHE.clear()
cl = fa.app.test_client()
h = cl.get("/?region=all").get_data(as_text=True)


def row(name):
    m = re.search(r'<tr id="p-%s".*?</tr>' % re.escape(name), h, re.S)
    return m.group(0) if m else ""


print("\n--- every row wears its looks ---")
r = row("LOOKSGUY")
check("the row is there", bool(r), True)
check("the name in its name style", '<span class="cosn %s">' % NAME["cls"] in r, True)
check("the title after it", ('class="cost rcost"' in r) and (">%s<" % TITLE["name"] in r), True)
check("the clan badge in its tag look", 'class="badge cbadge cos-ct-neon"' in r, True)
check("the name opens the card", 'data-card="LOOKSGUY"' in r, True)
check("banners, frames and effects stay off the row", any(x in r for x in ("cosb", "cosf", "cosx")), False)
r = row("PLAINGUY")
check("a player with no looks: plain name, no title", ("cosn" in r, "rcost" in r), (False, False))
r = row("EARNEDGUY")
check("an earned title is marked earned", 'class="cost rcost earned"' in r, True)
check("the page carries the card and its script", 'id="pcard"' in h and "/card')" in h, True)

print("\n--- the card ---")
r = cl.get("/player/LOOKSGUY/card")
c = r.get_data(as_text=True)
check("it answers", (r.status_code, r.headers.get("Content-Type", "").startswith("text/html")), (200, True))
check("in the player's banner and frame", ("cosb %s" % BANNER["cls"] in c) and ("cosf %s" % FRAME["cls"] in c), True)
check("the effect on the emblem", "cosx %s" % FX["cls"] in c, True)
check("the name style and title", ('cosn %s' % NAME["cls"] in c) and (">%s<" % TITLE["name"] in c), True)
check("the clan in its tag look", 'class="badge cbadge cos-ct-neon"' in c, True)
# Best rank reads #1, not the #3 seeded: loading the board just recorded
# their new best, which is the site doing its job.
check("rank, record and best rank", ("<span>Rank</span><b>#1</b>" in c) and ("40&ndash;10" in c)
      and ("<span>Best rank</span><b>#1</b>" in c), True)
check("the bio, escaped", ("&lt;script&gt;" in c) and ("<script>alert" not in c), True)
check("and the way to the full profile", 'href="/player/LOOKSGUY"' in c, True)
c = cl.get("/player/NEWGUY/card").get_data(as_text=True)
check("a new player's card says the rating is settling", "rating still settling" in c, True)
check("an unknown name is 404", cl.get("/player/NOBODYHERE123/card").status_code, 404)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
