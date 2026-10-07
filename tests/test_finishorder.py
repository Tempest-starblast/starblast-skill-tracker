# -*- coding: utf-8 -*-
"""Finishing order from station telemetry (finish_order.py)."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import finish_order as fo                                       # noqa: E402

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def st(dead):
    """A station entry; dead=None is a read with no station data."""
    return None if dead is None else {"lvl": 0, "gems": 0, "dead": dead, "weak": 0, "n": 12, "mods": []}


def mk(timeline, step=3.0, length=300):
    """timeline: {team: [(from_second, dead)]} - the dead count a team reads from
    that second on (default 0). Returns reads every `step` seconds."""
    reads = []
    t = 0.0
    while t <= length:
        sh = []
        for team in range(3):
            d = 0
            for frm, val in sorted(timeline.get(team, [])):
                if t >= frm:
                    d = val
            sh.append(st(d))
        reads.append({"ts": 1000.0 + t, "sh": sh})
        t += step
    return reads


print("\n--- a clean three-team finish ---")
r = fo.finish_order(mk({1: [(100, 12)], 2: [(200, 12)]}), 0, [1, 2])
check("winner first, the team that lasted longer second", r["places"], {0: 1, 2: 2, 1: 3})
check("on the strength of when each went out", (r["basis"], r["out_s"][0]), ("elimination", None))
check("elimination moments are seconds into the match (reads come every 3 s)",
      (100 <= r["out_s"][1] < 103, 200 <= r["out_s"][2] < 203), (True, True))
r = fo.finish_order(mk({1: [(200, 12)], 2: [(100, 12)]}), 0, [1, 2])
check("and the other way round", r["places"], {0: 1, 1: 2, 2: 3})
r = fo.finish_order(mk({1: [(100, 12)], 2: [(200, 12)]}), 1, [0, 2])
check("any team can be the winner", r["places"][1], 1)

print("\n--- when the order cannot be told, none is claimed ---")
r = fo.finish_order(mk({1: [(100, 12)], 2: [(102, 12)]}), 0, [1, 2])
check("two stations going down within a couple of reads", (r["basis"], r["places"]), ("unknown", {0: 1}))
r = fo.finish_order(mk({0: [(296, 12)], 1: [(280, 12)], 2: [(292, 12)]}), 0, [1, 2])
check("all three reading dead at the end is the end-of-match blur, not an order", (r["basis"], r["places"]), ("unknown", {0: 1}))
r = fo.finish_order(mk({1: [(280, 12)], 2: [(292, 12)]}), 0, [1, 2])
check("with the winner still standing, a close finish between the losers is real", (r["basis"], r["places"]), ("elimination", {0: 1, 2: 2, 1: 3}))
r = fo.finish_order(mk({1: [(290, 12)], 2: [(292, 12)]}), 0, [1, 2])
check("but not when they fell within a couple of reads of each other", (r["basis"], r["places"]), ("unknown", {0: 1}))
r = fo.finish_order(mk({1: [(100, 12)], 2: [(292, 12)]}), 0, [1, 2])
check("one early and one at the very end is still an order", (r["basis"], r["places"]), ("elimination", {0: 1, 2: 2, 1: 3}))
r = fo.finish_order(mk({}), 0, [1, 2])
check("neither going down", (r["basis"], r["places"]), ("unknown", {0: 1}))
r = fo.finish_order(mk({1: [(100, 12)]}), 0, [1, 2])
check("one standing to the end beats one that fell", (r["basis"], r["places"]), ("elimination", {0: 1, 2: 2, 1: 3}))

print("\n--- glitches do not count ---")
tl = {1: [(50, 12), (53, 0), (150, 12)], 2: [(200, 12)]}
r = fo.finish_order(mk(tl), 0, [1, 2])
check("a station that read dead for one moment and came back went out at its last fall", r["out_s"][1], 150.0)
reads = mk({1: [(100, 12)], 2: [(200, 12)]})
for rd in reads:
    if 150 <= rd["ts"] - 1000 <= 190:
        rd["sh"][1] = None
        rd["sh"][2] = None
check("reads with no station data are skipped, not counted", fo.finish_order(reads, 0, [1, 2])["places"], {0: 1, 2: 2, 1: 3})
reads = mk({1: [(100, 12)]})
for rd in reads[-12:]:
    rd["sh"][2] = None
check("a team with no reading at the end is judged by its last reading", fo.team_out_times(reads)[2], None)

print("\n--- two teams, and bad input ---")
r = fo.finish_order(mk({1: [(100, 12)]}), 0, [1])
check("a two-team match: the other side is second", (r["basis"], r["places"]), ("two-team", {0: 1, 1: 2}))
check("no reads at all", fo.finish_order([], 0, [1, 2])["basis"], "unknown")
check("reads with no station field", fo.finish_order([{"ts": 1.0}, {"ts": 2.0}], 0, [1, 2])["basis"], "unknown")
check("junk does not raise", fo.finish_order([None, 5, {"sh": "x"}], 0, [1, 2])["places"], {0: 1})
check("the winner's own end-of-match reading is irrelevant",
      fo.finish_order(mk({0: [(290, 12)], 1: [(100, 12)], 2: [(200, 12)]}), 0, [1, 2])["places"], {0: 1, 2: 2, 1: 3})

print("\n%d passed, %d failed" % (ok, fail))
sys.exit(1 if fail else 0)
