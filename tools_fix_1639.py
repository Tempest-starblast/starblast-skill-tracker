#!/usr/bin/env python3
"""Award lobby #1639 (match row 2226) to the team that actually won it.

The tracker recorded the wrong winner. A side that had collapsed to two
players was marked eliminated and never un-marked; it refilled to twelve,
killed both other teams, and the win fell by default to a team that had
itself been destroyed after the tracker's last readable frame.

Under the resurgence rule this match becomes:
  * the team that came back and won  -> credited the win
  * both teams it finished off       -> excused, no loss, no rating change
                                        (they had already spent themselves
                                        on each other; a resurrection is
                                        not something they could answer)

    python3 tools_fix_1639.py           # show what would change
    python3 tools_fix_1639.py --apply   # apply, then rebuild ratings

Applying rewrites this match's stored result and files the excused
players under held_results so they can see why. Ratings are then put
right by tools_rebuild_ratings.py --apply, which replays the whole
history under the live engine and takes its own backup first.
"""
import sqlite3
import sys
import time

DB = "/home/StarblastElo/mysite/players.db"
MROW = 2226
APPLY = "--apply" in sys.argv

conn = sqlite3.connect(DB)
c = conn.cursor()
meta = c.execute("SELECT match_id, sys_id, region, played_at FROM matches "
                 "WHERE id = ?", (MROW,)).fetchone()
if not meta:
    raise SystemExit("match row %s not found" % MROW)
match_id, sys_id, region, played_at = meta

rows = c.execute("SELECT name, norm_name, team, won, delta, score, played_as "
                 "FROM match_players WHERE match_row = ? ORDER BY team, delta DESC",
                 (MROW,)).fetchall()
if not rows:
    raise SystemExit("already corrected - no rated rows left on match %s" % MROW)
winners_now = [r for r in rows if r[2] == 'win']
purple = [r for r in rows if r[2] == 'lose2']
green = [r for r in rows if r[2] == 'lose1']
if not purple:
    raise SystemExit("no 'lose2' side on this match - refusing to guess")

print("lobby #%s  %s" % (sys_id, played_at))
print("\nCURRENT")
for label, group in (("recorded winner", winners_now), ("excused", green),
                     ("actual winner", purple)):
    print("  %s:" % label)
    for name, _n, team, won, delta, _s, _p in group:
        print("     %-26s %-6s won=%s %+8.2f" % (name[:26], team, won, delta or 0))

if not APPLY:
    print("\nWOULD DO")
    print("  %d player(s) on the resurgent team -> credited the win" % len(purple))
    print("  %d player(s) on the other two teams -> excused, rating untouched"
          % (len(winners_now) + len(green)))
    print("\nDry run only. Re-run with --apply, then tools_rebuild_ratings.py --apply.")
    conn.close()
    sys.exit(0)

now = time.strftime('%Y-%m-%d %H:%M:%S')
for name, norm, team, won, delta, score, played_as in winners_now + green:
    c.execute("INSERT INTO held_results (match_id, sys_id, region, name, norm_name, "
              "played_as, won, score, reason, played_at) VALUES (?,?,?,?,?,?,0,?,?,?)",
              (match_id, sys_id, region, name, norm, played_as or name, score,
               'resurgence', played_at))
c.execute("DELETE FROM match_players WHERE match_row = ? AND team IN ('win','lose1')",
          (MROW,))
c.execute("UPDATE match_players SET team = 'win', won = 1 WHERE match_row = ?", (MROW,))
conn.commit()
print("\nAPPLIED")
for name, team, won in c.execute("SELECT name, team, won FROM match_players "
                                 "WHERE match_row = ?", (MROW,)):
    print("   %-26s %-6s won=%s" % (name[:26], team, won))
print("   %d excused result(s) filed under held_results" % (len(winners_now) + len(green)))
conn.close()
print("\nNow run:  python3 tools_rebuild_ratings.py --apply")
