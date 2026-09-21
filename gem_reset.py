# -*- coding: utf-8 -*-
"""Open the economy from scratch.

The economy has been running quietly since 17 September: 18,377 players are
carrying balances they have never been able to see or spend, from a
backfill of their match history, from matches played since, and - for one
tester - from a million gems of test money.

None of that is how it should start. This empties the ledger so every
balance is zero on day one.

Achievements are deliberately NOT sealed (owner's call, 21 Sep 2026). They
are worked out from a career - total wins, highest tier, ships flown - so
emptying the ledger makes them claimable again, and a player who has been
on the board a year can claim what that year earned them. Starting at zero
and being paid for your history are not in conflict: the zero is the
balance, the history is the achievements.

What goes with it, necessarily: anything bought with money that is being
taken back. A purchase row is also the record of OWNING the thing, so the
hulls and looks bought during the preview un-own themselves, and anything
worn that is no longer owned is taken off. A tier's own ship is untouched -
that is not owned by a ledger row, it is owned by having reached the tier.

Run it with no arguments first. It writes nothing and prints every figure.
`--apply` takes a backup and then does it.
"""
import json
import shutil
import sqlite3
import sys
import time

APPLY = "--apply" in sys.argv
DB = '/home/StarblastElo/mysite/players.db'
LOG = '/home/StarblastElo/gem_reset_log.json'

sys.path.insert(0, '/home/StarblastElo/mysite')
import flask_app as fa                                          # noqa: E402

cn = sqlite3.connect(DB, timeout=30)
c = cn.cursor()


def one(sql, *a):
    r = c.execute(sql, a).fetchone()
    return r[0] if r else 0


print("=== what the ledger holds now ===")
rows = c.execute("SELECT reason, COUNT(*), SUM(amount) FROM gem_ledger "
                 "GROUP BY reason ORDER BY 2 DESC").fetchall()
for reason, n, amt in rows:
    print("   %-20s %6d rows  %+d" % (reason, n, amt or 0))
holders = one("SELECT COUNT(*) FROM players WHERE COALESCE(gems, 0) > 0")
held = one("SELECT SUM(gems) FROM players WHERE COALESCE(gems, 0) > 0")
clans_held = one("SELECT COALESCE(SUM(gems), 0) FROM clans")
print("   %d players holding %s; clan treasuries hold %s"
      % (holders, format(held, ","), format(clans_held, ",")))

print()
print("=== what stops being owned ===")
bought_ships = one("SELECT COUNT(*) FROM gem_ledger WHERE reason = 'purchase' "
                   "AND ref LIKE 'ship-%'")
bought_cos = one("SELECT COUNT(*) FROM gem_ledger WHERE reason IN ('purchase','unlock') "
                 "AND ref LIKE 'cos-%'")
worn_cos = one("SELECT COUNT(*) FROM players WHERE cosmetics IS NOT NULL AND cosmetics != ''")
print("   %d bought hulls, %d looks (bought or unlocked), %d players wearing something"
      % (bought_ships, bought_cos, worn_cos))

# A worn hull that the tier itself grants stays; one that was bought does not.
keep_ship, drop_ship = [], []
for nn, code in c.execute("SELECT norm_name, display_ship FROM players "
                          "WHERE display_ship IS NOT NULL"):
    need = fa.SHIP_RANK_UNLOCK.get(code)
    lvl = fa.gem_peak_level(c, nn)
    (keep_ship if (need and lvl >= need) else drop_ship).append(nn)
print("   worn hulls: %d granted by a tier and kept, %d bought and taken off"
      % (len(keep_ship), len(drop_ship)))

print()
print("=== what day one looks like ===")
claimable, who = 0, []
for (nn,) in c.execute("SELECT norm_name FROM players WHERE google_sub IS NOT NULL "
                       "AND COALESCE(wins,0) + COALESCE(losses,0) >= 5"):
    try:
        facts = fa._ach_facts(c, nn)
    except Exception:
        continue
    owed = 0
    for a in fa.gem_achievement_catalog():
        have, need = fa._ach_need(a["key"], facts)
        if have >= max(1, int(need)):
            owed += a["gems"]
    if owed:
        claimable += owed
        who.append((owed, nn))
who.sort(reverse=True)
print("   every balance starts at 0")
print("   %d accounts have a history to claim, worth %s between them"
      % (len(who), format(claimable, ",")))
for owed, nn in who[:10]:
    print("      %-24s %s" % (nn[:24], format(owed, ",")))

if not APPLY:
    print()
    print("DRY RUN - nothing written. Re-run with --apply to do it.")
    cn.close()
    raise SystemExit(0)

stamp = time.strftime('%Y%m%d-%H%M%S')
backup = '/home/StarblastElo/players.db.bak-pre-gemreset-' + stamp
cn.close()
shutil.copy(DB, backup)
print()
print("backed up to " + backup)

cn = sqlite3.connect(DB, timeout=30)
c = cn.cursor()
before = {"rows": one("SELECT COUNT(*) FROM gem_ledger"),
          "players": holders, "held": held, "clans": clans_held}
c.execute("DELETE FROM gem_ledger")
c.execute("UPDATE players SET gems = 0 WHERE COALESCE(gems, 0) != 0")
c.execute("UPDATE clans SET gems = 0 WHERE COALESCE(gems, 0) != 0")
# Nothing is owned, so nothing bought can still be worn.
c.execute("UPDATE players SET cosmetics = NULL "
          "WHERE cosmetics IS NOT NULL AND cosmetics != ''")
if drop_ship:
    for s in range(0, len(drop_ship), 400):
        chunk = drop_ship[s:s + 400]
        c.execute("UPDATE players SET display_ship = NULL WHERE norm_name IN (%s)"
                  % ",".join("?" * len(chunk)), chunk)
cn.commit()

after = {"rows": one("SELECT COUNT(*) FROM gem_ledger"),
         "players": one("SELECT COUNT(*) FROM players WHERE COALESCE(gems, 0) > 0"),
         "held": one("SELECT COALESCE(SUM(gems), 0) FROM players"),
         "clans": one("SELECT COALESCE(SUM(gems), 0) FROM clans")}
cn.close()
with open(LOG, 'w') as fh:
    json.dump({"at": time.strftime('%Y-%m-%d %H:%M:%S'), "backup": backup,
               "before": before, "after": after,
               "claimable_on_day_one": claimable,
               "hulls_taken_off": len(drop_ship)}, fh, indent=1)
print("DONE. ledger %d -> %d rows, %s gems -> %s, treasuries %s -> %s"
      % (before["rows"], after["rows"], format(before["held"], ","),
         format(after["held"], ","), format(before["clans"], ","),
         format(after["clans"], ",")))
print("log: " + LOG)
print()
print("Now: rm ~/mysite/boardcache/* and touch the wsgi file, or the pages")
print("will keep serving the balances they cached.")
