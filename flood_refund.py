# -*- coding: utf-8 -*-
"""Put back what the bot storms took.

Twenty rated matches were cut at a flood. The side that was ahead was paid,
which is right, but the sides the swarm landed on were charged for losing to
it. Under the rule as of 20 Sep 2026 they should have been excused, exactly
as a flipped match's losers are.

For every loser result in those matches: the elo comes back, the recorded
loss comes off, the match keeps the row with the change set to zero so the
record still shows who was there, and a held_results row says why - which is
what a cut match writes for itself from now on.

One exception, applied deliberately: a player sitting on the 500 floor was
never actually charged (the update clamps), so there is nothing to give
back. They are still excused the loss.

Run with DRY = True first. It writes nothing and prints exactly what it
would do.
"""
import json
import sqlite3
import time

DRY = True
DB = '/home/StarblastElo/mysite/players.db'
FLOOR = 500.0
LOG = '/home/StarblastElo/flood_refund_log.json'

cn = sqlite3.connect(DB, timeout=20)
c = cn.cursor()

cut = []
for mid, flood in c.execute("SELECT id, flood FROM matches "
                            "WHERE flood LIKE '%flood_cut%'").fetchall():
    try:
        f = json.loads(flood or '{}')
    except ValueError:
        continue
    if isinstance(f.get('flood_cut'), dict) and f['flood_cut']:
        cut.append(mid)
print('matches cut at a flood: %d' % len(cut))
assert cut, 'nothing to do'

qs = ','.join('?' * len(cut))
rows = c.execute(
    "SELECT mp.rowid, mp.match_row, mp.name, mp.norm_name, mp.delta, "
    "       m.match_id, m.sys_id, m.region, m.played_at, mp.score "
    "FROM match_players mp JOIN matches m ON m.id = mp.match_row "
    "WHERE mp.match_row IN (%s) AND mp.won = 0 AND mp.delta < 0" % qs, cut).fetchall()
print('results on the swarmed sides: %d' % len(rows))

plan, skipped_floor = [], []
for rid, mrow, name, nn, delta, match_id, sys_id, region, at, score in rows:
    pr = c.execute("SELECT elo, losses FROM players WHERE norm_name = ?", (nn,)).fetchone()
    if not pr:
        continue
    elo, losses = pr[0], pr[1] or 0
    give = -float(delta)
    if elo is not None and float(elo) <= FLOOR:
        skipped_floor.append((name, give))
        give = 0.0
    plan.append({"row": rid, "match_row": mrow, "match_id": match_id, "sys_id": sys_id,
                 "region": region, "played_at": at, "name": name, "norm": nn,
                 "was": float(delta), "refund": round(give, 2), "score": score})

total = round(sum(p["refund"] for p in plan), 2)
people = sorted({p["norm"] for p in plan})
print('players touched: %d' % len(people))
print('elo to give back: %.1f' % total)
if skipped_floor:
    print('on the 500 floor, so nothing was taken and nothing is given back:')
    for nm, amt in skipped_floor:
        print('   %-24s would have been %+.2f' % (nm[:24], amt))
print()
print('%-26s %9s %9s %9s' % ('player', 'refund', 'elo now', 'after'))
by = {}
for p in plan:
    by.setdefault(p["norm"], [p["name"], 0.0, 0])
    by[p["norm"]][1] += p["refund"]
    by[p["norm"]][2] += 1
for nn, (nm, amt, n) in sorted(by.items(), key=lambda kv: -kv[1][1])[:15]:
    e = c.execute("SELECT elo FROM players WHERE norm_name = ?", (nn,)).fetchone()[0]
    print('%-26s %9.1f %9.1f %9.1f' % (nm[:26], amt, e, e + amt))

if DRY:
    print('\nDRY RUN - nothing written.')
    cn.close()
    raise SystemExit(0)

stamp = time.strftime('%Y-%m-%d %H:%M:%S')
for p in plan:
    if p["refund"]:
        c.execute("UPDATE players SET elo = ROUND(elo + ?, 2) WHERE norm_name = ?",
                  (p["refund"], p["norm"]))
    c.execute("UPDATE players SET losses = MAX(0, losses - 1) WHERE norm_name = ?",
              (p["norm"],))
    c.execute("UPDATE match_players SET delta = 0 WHERE rowid = ?", (p["row"],))
    c.execute("INSERT INTO held_results (match_id, sys_id, region, name, norm_name, "
              "played_as, won, score, reason, played_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (p["match_id"], p["sys_id"], p["region"], p["name"], p["norm"],
               None, 0, p["score"], 'flood-cut', p["played_at"]))
cn.commit()
cn.close()
with open(LOG, 'w') as fh:
    json.dump({"at": stamp, "matches": cut, "total_elo": total,
               "results": plan, "floor_skipped": skipped_floor}, fh, indent=1)
print('\nWRITTEN. %d results corrected, %.1f elo returned. Log: %s' % (len(plan), total, LOG))
