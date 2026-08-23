#!/usr/bin/env python3
"""Rebuild every rating from match history under the 7.0.0 engine.

Replays all recorded matches in order, applying the three-team
expectation, the shrinkage team rating, provisional K bands and
per-match conservation - the same code the live site now uses.

    python3 ~/rebuild_ratings.py           # dry run, reports only
    python3 ~/rebuild_ratings.py --apply   # writes (backs up first)

Respects account wipes: a player who wiped on claiming only replays
matches after their wipe. Held and skipped results were never rated and
stay that way. Match records themselves are untouched apart from each
row's delta, which is rewritten to what the corrected engine produced.
"""
import shutil
import sqlite3
import sys
import time

DB = "/home/StarblastElo/mysite/players.db"
APPLY = "--apply" in sys.argv

STARTING_ELO = 1000
ELO_K = 200.0
ELO_SCALE = 2000.0
FLOOR = 500.0
PROVISIONAL_GAMES, ESTABLISHED_GAMES = 5, 20
PROVISIONAL_K_MULT, ESTABLISHED_K_MULT = 1.4, 0.8
TEAM_PRIOR_WEIGHT = 3.0


def team_rating(keys, elos):
    known = [elos[k] for k in keys if k in elos]
    if not known:
        return float(STARTING_ELO)
    return ((sum(known) + TEAM_PRIOR_WEIGHT * STARTING_ELO)
            / (len(known) + TEAM_PRIOR_WEIGHT))


def win_expectation(own, rivals):
    total = 1.0
    for r in rivals:
        total += 10 ** ((r - own) / ELO_SCALE)
    return 1.0 / total


def k_factor(games):
    if games < PROVISIONAL_GAMES:
        return ELO_K * PROVISIONAL_K_MULT
    if games < ESTABLISHED_GAMES:
        return ELO_K
    return ELO_K * ESTABLISHED_K_MULT


conn = sqlite3.connect(DB)
c = conn.cursor()

wiped = {}
try:
    for norm, wb in c.execute(
            "SELECT norm_name, wiped_before FROM players "
            "WHERE wiped_before IS NOT NULL AND wiped_before != ''"):
        wiped[norm] = wb
except sqlite3.OperationalError:
    pass
print("%d wiped account(s) will only replay matches after their wipe" % len(wiped))

matches = c.execute("SELECT id, played_at FROM matches ORDER BY id").fetchall()
rows = c.execute("SELECT match_row, norm_name, name, won, COALESCE(half,0), team "
                 "FROM match_players ORDER BY match_row").fetchall()
by_match = {}
for mrow, norm, name, won, half, team in rows:
    by_match.setdefault(mrow, []).append((norm, name, won, half, team))
print("%d matches, %d rated results" % (len(matches), len(rows)))

elos, games, wins, losses = {}, {}, {}, {}
new_deltas = []
pool_before = pool_after = 0.0
skipped_wiped = 0

for mrow, played_at in matches:
    entries = by_match.get(mrow)
    if not entries:
        continue
    live = []
    for norm, name, won, half, team in entries:
        wb = wiped.get(norm)
        if wb and (played_at or "") <= wb:
            skipped_wiped += 1
            continue
        live.append((norm, name, won, half, team))
    if not live:
        continue
    for norm, name, won, half, team in live:
        elos.setdefault(norm, float(STARTING_ELO))
        games.setdefault(norm, 0)
        wins.setdefault(norm, 0)
        losses.setdefault(norm, 0)

    winners = [e for e in live if e[2]]
    l1 = [e for e in live if not e[2] and (e[4] or "lose1") == "lose1"]
    l2 = [e for e in live if not e[2] and e[4] == "lose2"]
    if not winners:
        continue

    r_w = team_rating([e[0] for e in winners], elos)
    r_1 = team_rating([e[0] for e in l1], elos) if l1 else None
    r_2 = team_rating([e[0] for e in l2], elos) if l2 else None
    rivals_w = [r for r in (r_1, r_2) if r is not None]
    # A win with every opponent excused still has to be worth something;
    # measure it against an average side rather than against nobody.
    if not rivals_w:
        rivals_w = [float(STARTING_ELO)]

    pend = []
    for norm, name, won, half, team in winners:
        eff = (elos[norm] + r_w) / 2
        raw = ELO_K * (1 - win_expectation(eff, rivals_w))
        if half:
            raw *= 0.5
        pend.append((norm, 1, raw, k_factor(games[norm]) / ELO_K))
    for group, mine, other in ((l1, r_1, r_2), (l2, r_2, r_1)):
        for norm, name, won, half, team in group:
            eff = (elos[norm] + (mine if mine is not None else STARTING_ELO)) / 2
            rivals = [r_w] + ([other] if other is not None else [])
            raw = ELO_K * win_expectation(eff, rivals)
            if half:
                raw *= 0.5
            pend.append((norm, 0, raw, k_factor(games[norm]) / ELO_K))

    tg = sum(r for _, w, r, _m in pend if w)
    tl = sum(r for _, w, r, _m in pend if not w)
    fg = fl = 1.0
    if tg > 0 and tl > 0:
        if tg > tl:
            fg = tl / tg
        else:
            fl = tg / tl

    for norm, won, raw, mult in pend:
        if won:
            d = raw * fg * mult
            elos[norm] = round(elos[norm] + d, 2)
            wins[norm] += 1
        else:
            d = -raw * fl * mult
            elos[norm] = round(max(FLOOR, elos[norm] + d), 2)
            losses[norm] += 1
        games[norm] += 1
        new_deltas.append((round(d, 2), mrow, norm))

old = dict(c.execute("SELECT norm_name, elo FROM players "
                     "WHERE norm_name IS NOT NULL").fetchall())
moved = [(n, float(old.get(n, STARTING_ELO)), e) for n, e in elos.items()]
moved.sort(key=lambda t: t[2] - t[1])

print("\n=== REBUILD SUMMARY (%s) ===" % ("APPLYING" if APPLY else "dry run"))
print("players rebuilt      : %d" % len(elos))
print("results replayed     : %d  (%d skipped by wipes)" % (len(new_deltas), skipped_wiped))
print("pool before          : %+.0f vs a %d start" % (
    sum(float(v) for v in old.values()) - STARTING_ELO * len(old), STARTING_ELO))
print("pool after           : %+.0f" % (sum(elos.values()) - STARTING_ELO * len(elos)))
print("average before/after : %.1f -> %.1f" % (
    sum(float(v) for v in old.values()) / max(1, len(old)),
    sum(elos.values()) / max(1, len(elos))))
print("at the 500 floor     : %d -> %d" % (
    sum(1 for v in old.values() if float(v) <= 500.5),
    sum(1 for v in elos.values() if v <= 500.5)))
print("\nbiggest drops:")
for n, o, e in moved[:5]:
    print("   %-22s %8.1f -> %8.1f  (%+.1f)" % (n[:22], o, e, e - o))
print("biggest rises:")
for n, o, e in moved[-5:][::-1]:
    print("   %-22s %8.1f -> %8.1f  (%+.1f)" % (n[:22], o, e, e - o))

top_old = sorted(old.items(), key=lambda kv: -float(kv[1]))[:10]
print("\ntop 10 now vs after:")
for n, v in top_old:
    print("   %-22s %8.1f -> %8.1f" % (n[:22], float(v), elos.get(n, float(STARTING_ELO))))

if not APPLY:
    print("\nDry run only - nothing written. Re-run with --apply to commit.")
    conn.close()
    sys.exit(0)

backup = DB + ".bak-pre-v7-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy(DB, backup)
print("\nbackup written: %s" % backup)
c.execute("UPDATE players SET elo = ?, wins = 0, losses = 0 "
          "WHERE norm_name IN (SELECT DISTINCT norm_name FROM match_players)",
          (STARTING_ELO,))
for norm, e in elos.items():
    c.execute("UPDATE players SET elo = ?, wins = ?, losses = ? WHERE norm_name = ?",
              (e, wins.get(norm, 0), losses.get(norm, 0), norm))
c.executemany("UPDATE match_players SET delta = ? WHERE match_row = ? AND norm_name = ?",
              new_deltas)
conn.commit()
conn.close()
print("done - %d ratings and %d match rows rewritten." % (len(elos), len(new_deltas)))
