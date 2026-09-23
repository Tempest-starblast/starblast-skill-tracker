# -*- coding: utf-8 -*-
"""A rename carries the player's friendships with it.

Every other table keyed by norm_name rides along in RENAME_KEYED_TABLES.
friends could not, because it keys a pair across two columns, so it was
left out of both and quietly orphaned. The 18 Sep rule that strips a clan
tag off an account name the moment it joins a clan renames people
routinely, so on the live database sixteen names in the friends table
belonged to nobody - one of them in twenty rows. Darkstalker reported it
as the site deleting his friend list.

Pairs are stored sorted, so remapping one side can re-sort the row, land
it on a row that already exists, or make somebody their own friend. All
three are checked here."""
import io
import os
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

import flask_app as fa                                          # noqa: E402

TMP = tempfile.mkdtemp(prefix="frnd")
fa.DB_PATH = os.path.join(TMP, "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)
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
c.execute("DELETE FROM friends")


def put(x, y, state, requester=None, asked="2026-09-17 00:00:00", acted=None):
    a, b = fa.friend_pair(x, y)
    c.execute("INSERT OR REPLACE INTO friends (a, b, requester, state, asked_at, acted_at) "
              "VALUES (?,?,?,?,?,?)", (a, b, requester or a, state, asked, acted))


def pairs():
    return {(a, b): st for a, b, st in c.execute("SELECT a, b, state FROM friends")}


print("\n--- the plain case: a friendship follows the rename ---")
put("L7ALICE", "BOB", "accepted", acted="2026-09-17 00:05:00")
n = fa.move_friendships(c, "L7ALICE", "ALICE")
check("one row moved", n, 1)
p = pairs()
check("the old name is gone", any("L7ALICE" in k for k in p), False)
check("the new pair is there", fa.friend_pair("ALICE", "BOB") in p, True)
check("  and it is still accepted", p[fa.friend_pair("ALICE", "BOB")], "accepted")

print("\n--- the pair re-sorts when the new name sorts differently ---")
c.execute("DELETE FROM friends")
put("AAA", "ZZBOB", "accepted")        # stored as (AAA, ZZBOB)
fa.move_friendships(c, "AAA", "ZZZ")   # now sorts after ZZBOB
row = c.execute("SELECT a, b FROM friends").fetchone()
check("stored sorted, whichever side changed", row, ("ZZBOB", "ZZZ"))

print("\n--- a duplicate: they re-friended under the new name ---")
c.execute("DELETE FROM friends")
put("L7ALICE", "BOB", "accepted", acted="2026-09-17 00:05:00")
put("ALICE", "BOB", "pending", requester="ALICE", asked="2026-09-23 12:43:00")
check("two rows before", len(pairs()), 2)
fa.move_friendships(c, "L7ALICE", "ALICE")
p = pairs()
check("one row after", len(p), 1)
check("and the real friendship wins over the new request",
      p[fa.friend_pair("ALICE", "BOB")], "accepted")

print("\n--- the other way round: pending old, accepted new ---")
c.execute("DELETE FROM friends")
put("L7ALICE", "BOB", "pending")
put("ALICE", "BOB", "accepted", acted="2026-09-23 12:43:00")
fa.move_friendships(c, "L7ALICE", "ALICE")
p = pairs()
check("still one row", len(p), 1)
check("still accepted", p[fa.friend_pair("ALICE", "BOB")], "accepted")

print("\n--- nobody becomes their own friend ---")
c.execute("DELETE FROM friends")
put("L7ALICE", "ALICE", "accepted")
fa.move_friendships(c, "L7ALICE", "ALICE")
check("the self-pair is dropped", len(pairs()), 0)

print("\n--- a requester is carried too ---")
c.execute("DELETE FROM friends")
put("L7ALICE", "BOB", "pending", requester="L7ALICE")
fa.move_friendships(c, "L7ALICE", "ALICE")
check("the request is now from the new name",
      c.execute("SELECT requester FROM friends").fetchone()[0], "ALICE")

print("\n--- and the whole rename path does it ---")
c.execute("DELETE FROM friends")
c.execute("DELETE FROM players WHERE name IN ('(L7)Carol', 'Carol')")
c.execute("INSERT INTO players (name, norm_name, elo) VALUES (?,?,1000)",
          ("(L7)Carol", fa.normalize_name("(L7)Carol")))
put(fa.normalize_name("(L7)Carol"), "BOB", "accepted")
fa.rekey_identity(c, "(L7)Carol", "Carol")
p = pairs()
check("rekey_identity moved the friendship",
      fa.friend_pair(fa.normalize_name("Carol"), "BOB") in p, True)
check("  and nothing was left behind",
      any(fa.normalize_name("(L7)Carol") in k for k in p), False)

print("\n--- the source keeps the wiring ---")
src = io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read()
check("rekey_identity calls it", "move_friendships(c, old_key, new_key)" in src, True)
check("friends is still NOT in the blanket list",
      "\"friends\"," in src.split("RENAME_KEYED_TABLES = (")[1].split(")")[0], False)

cn.close()
print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
