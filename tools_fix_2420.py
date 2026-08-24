"""Retro-apply the identity-only check-in rule to match 2420 (7.1.5).

Lobby #7707 'Achernirauris 258', 2026-08-24 05:32:37. Two checked-in
players were charged the loss through the old ship-binding placement
even though the roster rules never included them: neither was in
team_2's locked (peak top 8) roster - (L7) Tempest joined at 05:18:17,
13 minutes before the end, and (L7) Pyro's best score (815) sat far
below the locked eight. Under 7.1.5 a check-in is identity only, so
neither would be rated today. This removes their two rows; the board is
then made consistent by tools_rebuild_ratings.py --apply, which replays
the whole history under the live engine and takes its own backup first.

Dry-run by default; pass --apply to write.
"""
import sqlite3
import sys

DB = "/home/StarblastElo/mysite/players.db"
MROW = 2420
# norm_names of the two rows to remove - exactly the ship-bound,
# never-rostered pair. Nobody else on the match is touched.
TARGETS = ("Ł" + "7" + "ŦɆMⱣɆSŦ",
           "Ł" + "7" + "ⱣɎɌØ")
APPLY = "--apply" in sys.argv

conn = sqlite3.connect(DB)
c = conn.cursor()
meta = c.execute("SELECT match_id, sys_id, played_at FROM matches WHERE id = ?",
                 (MROW,)).fetchone()
if not meta:
    raise SystemExit("match row %s not found" % MROW)
print("match %s  lobby #%s  %s" % (meta[0], meta[1], meta[2]))

rows = c.execute("SELECT name, norm_name, team, won, ROUND(delta,2), score "
                 "FROM match_players WHERE match_row = ? AND norm_name IN (?,?)",
                 (MROW,) + TARGETS).fetchall()
if not rows:
    raise SystemExit("already corrected - neither row present on match %s" % MROW)
print("\nrows to remove (identity-only rule, never in the locked roster):")
for name, norm, team, won, delta, score in rows:
    print("   %-22s %-6s won=%s delta=%+8.2f score=%s" %
          (name[:22], team, won, delta, score))

if not APPLY:
    print("\nDRY RUN - would delete %d row(s). Re-run with --apply, then "
          "run tools_rebuild_ratings.py --apply to recompute the board." %
          len(rows))
    raise SystemExit(0)

c.execute("DELETE FROM match_players WHERE match_row = ? AND norm_name IN (?,?)",
          (MROW,) + TARGETS)
conn.commit()
print("\ndeleted %d row(s). Now run: python3 tools_rebuild_ratings.py --apply" %
      c.rowcount)
conn.close()
