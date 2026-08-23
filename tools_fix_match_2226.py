#!/usr/bin/env python3
"""Correct lobby #1639 (match row 2226): the win went to the wrong team.

Evidence, from the tracker's own per-read log at 06:57-06:58 on 23 Aug:
  team_2  station DESTROYED (12/12 modules dead), 0 players   -> genuinely out
  team_1  station ALIVE (1 module dead), 15 players,  72,082  -> still playing
  team_3  station UNTOUCHED, 6,400 gems, 12 players, 86,837  -> still playing

Two teams alive at the end means the highest score wins, which is team_3.
The tracker instead declared team_1 "last team standing", because team_3 had
dipped to 2 players around the 20-minute mark and the quit-elimination flag
that set was never cleared when they refilled to 12 and won. That stickiness
is fixed in the tracker; this repairs the one result it spoiled.

    python3 tools_fix_match_2226.py            # show what would change
    python3 tools_fix_match_2226.py --apply    # swap the result, then rebuild

Applying only swaps the stored result for this match. Ratings are then put
right by re-running tools_rebuild_ratings.py --apply, which replays the whole
history under the live engine and takes its own backup.
"""
import sqlite3
import sys

DB = "/home/StarblastElo/mysite/players.db"
MROW = 2226
APPLY = "--apply" in sys.argv

conn = sqlite3.connect(DB)
c = conn.cursor()
rows = c.execute("SELECT name, team, won, delta FROM match_players "
                 "WHERE match_row = ? ORDER BY team, delta DESC", (MROW,)).fetchall()
if not rows:
    raise SystemExit("match row %s has no players - nothing to do" % MROW)
if not any(r[1] == 'win' for r in rows):
    raise SystemExit("no winning side recorded - refusing to guess")

print("BEFORE")
for name, team, won, delta in rows:
    print("   %-6s %-24s won=%s  %+8.2f" % (team, name[:24], won, delta or 0))

if any(r[1] == 'lose2' for r in rows) is False:
    raise SystemExit("no lose2 side - this is not the match this script was written for")

if not APPLY:
    print("\nWould swap: 'win' <-> 'lose2'  (team_1 becomes a loser, team_3 the winner).")
    print("'lose1' (team_2, whose station was destroyed) is unchanged.")
    print("\nDry run only. Re-run with --apply, then run tools_rebuild_ratings.py --apply.")
    conn.close()
    sys.exit(0)

c.execute("UPDATE match_players SET team = 'tmp' WHERE match_row = ? AND team = 'win'", (MROW,))
c.execute("UPDATE match_players SET team = 'win', won = 1 WHERE match_row = ? AND team = 'lose2'", (MROW,))
c.execute("UPDATE match_players SET team = 'lose2', won = 0 WHERE match_row = ? AND team = 'tmp'", (MROW,))
conn.commit()
print("\nAFTER")
for name, team, won, delta in c.execute(
        "SELECT name, team, won, delta FROM match_players WHERE match_row = ? "
        "ORDER BY team, delta DESC", (MROW,)):
    print("   %-6s %-24s won=%s" % (team, name[:24], won))
conn.close()
print("\nResult swapped. Now run:  python3 tools_rebuild_ratings.py --apply")
