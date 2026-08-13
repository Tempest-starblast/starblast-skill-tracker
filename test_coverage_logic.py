# -*- coding: utf-8 -*-
"""Drives the real patched counter block, lifted verbatim out of
auto_observer.py, through a scripted sequence of sweeps.

The point is to prove the two rates say different things: a lobby that
never became eligible must not be counted as a miss, and one that WAS
eligible and went unwatched must be.
"""
import re
import textwrap

src = open('auto_observer.py', encoding='utf-8').read()

# Lift the counter block exactly as it will run in production.
start = src.index('                if nodes:\n                    live_ids =')
end = src.index('                coverage = f"', start)
block = textwrap.dedent(src[start:end])
block = block[block.index('if nodes:'):]
print('--- block under test (%d lines) ---' % len(block.strip().splitlines()))
print(block.strip())
print('--- end block ---\n')

ns = {
    'seen_lobbies': {}, 'ended_total': 0, 'ended_watched': 0,
    'ended_eligible': 0, 'ended_eligible_watched': 0,
}
code = compile(block, '<counter-block>', 'exec')


def sweep(lobbies, eligible, watching):
    """lobbies: list of ids present; eligible: ids meeting the rule;
    watching: ids a worker is attached to."""
    ns['nodes'] = [1]
    ns['na_team_lobbies'] = [{'id': i} for i in lobbies]
    ns['eligible_lobbies'] = [{'id': i} for i in eligible]
    ns['active_futures'] = {i: None for i in watching}
    exec(code, ns)


# A: young lobby, never eligible, dies at 5 min      -> not a real miss
# B: becomes eligible, watched, ends                 -> watched
# C: becomes eligible, NEVER watched, ends           -> a real miss
# D: eligible + watched, then ages out, then ends    -> sticky eligibility
sweep(['A', 'B', 'C', 'D'], [],              [])
sweep(['A', 'B', 'C', 'D'], ['B', 'C', 'D'], ['B', 'D'])
sweep(['B', 'C', 'D'],      ['B', 'C', 'D'], ['B', 'D'])   # A ended young
sweep(['C', 'D'],           ['C', 'D'],      ['D'])        # B ended, watched
sweep(['D'],                [],              ['D'])        # C ended unwatched; D aged out
sweep([],                   [],              [])           # D ended, was watched

got = {k: ns[k] for k in
       ('ended_total', 'ended_watched', 'ended_eligible', 'ended_eligible_watched')}
want = {'ended_total': 4, 'ended_watched': 2,
        'ended_eligible': 3, 'ended_eligible_watched': 2}

for k in want:
    ok = got[k] == want[k]
    print('%-26s got %-3s want %-3s  %s' % (k, got[k], want[k], 'PASS' if ok else 'FAIL'))

raw = round(100 * got['ended_watched'] / got['ended_total'])
watch = round(100 * got['ended_eligible_watched'] / got['ended_eligible'])
print()
print('raw rate       : %d/%d = %d%%   <- includes A, which was never watchable'
      % (got['ended_watched'], got['ended_total'], raw))
print('watchable rate : %d/%d = %d%%   <- C is the only genuine miss'
      % (got['ended_eligible_watched'], got['ended_eligible'], watch))

assert got == want, 'counter semantics wrong: %r' % got
assert raw < watch, 'the raw rate should be the pessimistic one'
print('\nALL COUNTER CHECKS PASSED')

# ---------------------------------------------------------------- stagger
# Same spacing as the old inline sleep, without blocking the loop.
WORKER_SPAWN_STAGGER = 12
SWEEP = 12
now = 0.0
last_spawn_at = 0.0
spawns = []
waiting = 5
for _ in range(60):                      # 60 sweeps = 720 simulated seconds
    may_spawn = (now - last_spawn_at) >= WORKER_SPAWN_STAGGER
    if may_spawn and waiting > 0:
        spawns.append(now)
        last_spawn_at = now
        waiting -= 1
    now += SWEEP                          # loop NEVER sleeps extra

gaps = [b - a for a, b in zip(spawns, spawns[1:])]
print('\nspawn times   :', spawns)
print('gaps          :', gaps)
print('min gap       : %ss (stagger is %ss)' % (min(gaps), WORKER_SPAWN_STAGGER))
assert all(g >= WORKER_SPAWN_STAGGER for g in gaps), 'stagger violated'
assert len(spawns) == 5, 'not every waiting lobby got a worker'
# 5 workers placed in 5 sweeps = 60s, exactly as the old code took - but the
# old code spent 48s of that blocked inside the sweep.
assert spawns[-1] - spawns[0] == 48
print('STAGGER PRESERVED, LOOP NEVER BLOCKED')
