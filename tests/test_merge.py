# -*- coding: utf-8 -*-
"""A name merge must never destroy the record it is folding (9.39.0)."""
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
TMP = tempfile.mkdtemp(prefix="merge")
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


N = fa.normalize_name
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()


def add_player(name, sub=None, wins=0, losses=0, elo=1000.0):
    c.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
              (name, N(name), elo, wins, losses, sub))


def add_match(mid, name, won, delta):
    c.execute("INSERT INTO matches(match_id, sys_id, played_at) VALUES (?,?,?)", ("x%d" % mid, mid, "2026-09-1%d 10:00:00" % (mid % 9)))
    row = c.lastrowid
    c.execute("INSERT INTO match_players(match_row, name, norm_name, won, delta) VALUES (?,?,?,?,?)",
              (row, name, N(name), 1 if won else 0, delta))
    return row


# the exact shape that cost a live record: OLD holds the account, NEW does not exist
add_player("Old Name", "sub:victim", 2, 1, 1180.0)
for i, (won, d) in enumerate(((1, 100.0), (1, 90.0), (0, -10.0))):
    add_match(100 + i, "Old Name", won, d)
# an ordinary pair, both rows real, the account on the source
add_player("Alias", "sub:two", 1, 0, 1050.0)
add_player("Main", None, 1, 1, 1010.0)
add_match(200, "Alias", 1, 50.0)
add_match(201, "Main", 1, 40.0)
add_match(202, "Main", 0, -30.0)
c.execute("INSERT INTO survival_players(norm_name, name, elo, rounds, wins) VALUES (?,?,?,?,?)", (N("Alias"), "Alias", 1100, 4, 2))
fa.gem_grant(c, "player", N("Alias"), 500, "backfill", "v1")
# two different accounts
add_player("Mine", "sub:a", 1, 0, 1100.0)
add_player("Yours", "sub:b", 1, 0, 1100.0)
cn.commit()
cn.close()


def fresh():
    return sqlite3.connect(fa.DB_PATH)


print("\n--- it refuses instead of destroying ---")
cn = fresh()
c = cn.cursor()
r = fa.perform_name_merge(c, N("Old Name"), N("Never Existed"))
cn.commit()
cn.close()
check("merging into a name with no row is refused", (r["ok"], "no record to merge into" in r["error"]), (False, True))
cn = fresh()
row = cn.execute("SELECT name, google_sub, wins, losses FROM players WHERE norm_name=?", (N("Old Name"),)).fetchone()
orphans = cn.execute("SELECT COUNT(*) FROM match_players mp LEFT JOIN players p ON p.norm_name=mp.norm_name WHERE p.norm_name IS NULL").fetchone()[0]
cn.close()
check("the record and the account are untouched", (row[0], row[1], row[2], row[3]), ("Old Name", "sub:victim", 2, 1))
check("no result was orphaned", orphans, 0)

cn = fresh()
c = cn.cursor()
r = fa.perform_name_merge(c, N("Nobody At All"), N("Main"))
cn.close()
check("merging FROM a name with no row is refused too", (r["ok"], "Nothing on the board" in r["error"]), (False, True))

cn = fresh()
c = cn.cursor()
r = fa.perform_name_merge(c, N("Mine"), N("Yours"))
cn.close()
check("a merge across two accounts is refused", (r["ok"], "different accounts" in r["error"]), (False, True))

print("\n--- a real merge carries everything ---")
cn = fresh()
c = cn.cursor()
r = fa.perform_name_merge(c, N("Alias"), N("Main"))
cn.commit()
cn.close()
check("it ran and moved the match", (r["ok"], r["matches_moved"]), (True, 1))
cn = fresh()
main = cn.execute("SELECT name, google_sub, wins, losses, elo FROM players WHERE norm_name=?", (N("Main"),)).fetchone()
gone = cn.execute("SELECT COUNT(*) FROM players WHERE norm_name=?", (N("Alias"),)).fetchone()[0]
surv = cn.execute("SELECT norm_name, rounds, wins FROM survival_players WHERE norm_name IN (?,?)", (N("Main"), N("Alias"))).fetchall()
gems = cn.execute("SELECT owner, amount FROM gem_ledger WHERE reason='backfill'").fetchall()
mp = cn.execute("SELECT COUNT(*) FROM match_players WHERE norm_name=?", (N("Main"),)).fetchone()[0]
orphans = cn.execute("SELECT COUNT(*) FROM match_players mp LEFT JOIN players p ON p.norm_name=mp.norm_name WHERE p.norm_name IS NULL").fetchone()[0]
cn.close()
check("the three results are all Main's now", mp, 3)
check("record recomputed from the deltas", (main[2], main[3], main[4]), (2, 1, 1060.0))
check("the account came with the record", main[1], "sub:two")
check("the old row is gone and nothing is orphaned", (gone, orphans), (0, 0))
check("the survival record came too", surv, [(N("Main"), 4, 2)])
check("so did the gems", gems, [(N("Main"), 500)])

print("\n--- the owner's approve button ---")
cn = fresh()
c = cn.cursor()
c.execute("INSERT INTO merge_requests(google_sub, from_name, from_norm, to_name, to_norm, reason, status, created_at) "
          "VALUES (?,?,?,?,?,?,?,?)", ("sub:victim", "Old Name", N("Old Name"), "Never Existed", N("Never Existed"), "please", "pending", "2026-09-18 00:00:00"))
rid = c.lastrowid
cn.commit()
cn.close()
fa.OWNER_SUBS = set(fa.OWNER_SUBS) | {"sub:owner"}
owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"
r = owner.post("/dev/merges/%d" % rid, data={"action": "approve"})
check("the owner may decide", r.status_code in (200, 302), True)
cn = fresh()
req = cn.execute("SELECT status, decided_note FROM merge_requests WHERE id=?", (rid,)).fetchone()
still = cn.execute("SELECT COUNT(*) FROM players WHERE norm_name=?", (N("Old Name"),)).fetchone()[0]
cn.close()
check("approving an impossible merge leaves it pending with the reason", (req[0], "no record to merge into" in (req[1] or "")), ("pending", True))
check("and the record survives", still, 1)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
