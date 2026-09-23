# -*- coding: utf-8 -*-
"""The achievement ladders stay honest (9.72.0).

Measured 23 Sep 2026, 44 days after the wipe: nobody had reached 500 wins,
1,000 games, 50 survival wins or ten million points, and Immortal (1,000
wins - seven months away at the best pace anyone has shown) paid 10,000:
ten gems a win, less than one hard daily objective pays for an afternoon.
Institution (500 wins) paid less than Fixture (250). The owner asked for
the whole thing scaled from the data.

These pin the SHAPE, so the next person who edits one number by feel finds
out at once: within a ladder, each rung pays more than the last, and the
pay per unit never falls as the rungs get rarer. The specific figures live
beside the constants with the measurement that set them."""
import io
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import flask_app as fa                                          # noqa: E402
import objectives as O                                          # noqa: E402

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


gems = {a["key"]: a["gems"] for a in fa.gem_achievement_catalog()}
need = {k: n for (k, _nm, _d, n, _amt) in fa.GEM_WIN_MILESTONES}
for (k, _g, _nm, _d, _gems, _icon, fn) in fa._ACH_EXTRA:
    try:
        need[k] = fn({"wins": 0, "games": 0, "days": 0, "hours": 0, "regions": 0, "surv": 0,
                      "best": 0, "total": 0, "deaths": 0, "bought": 0, "ships": set(),
                      "cos": set(), "bought_cos": 0, "worn": 0, "spent": 0, "earned": 0,
                      "friends": 0, "clan": False, "officer": False, "peak": 0})[1]
    except Exception:                                  # noqa: BLE001
        pass

LADDERS = {
    "wins": ["first-win", "wins-10", "wins-50", "wins-100", "wins-250", "wins-500", "wins-1000"],
    "games": ["games-100", "games-500", "games-1000"],
    "days": ["days-7", "days-30", "days-100"],
    "hours": ["hours-10", "hours-50", "hours-100", "hours-500"],
    "survival": ["surv-1", "surv-10", "surv-50", "surv-100"],
    "score": ["score-25k", "score-50k", "score-60k"],
    "total": ["total-1m", "total-10m"],
    "deaths": ["deaths-100", "deaths-500"],
}

print("\n--- every ladder climbs, and pays more per unit as it gets rarer ---")
for name, keys in LADDERS.items():
    pays = [gems[k] for k in keys]
    check("%s: each rung pays more than the last %s" % (name, pays),
          all(b > a for a, b in zip(pays, pays[1:])), True)
    per = [gems[k] / float(need[k]) for k in keys[1:]]      # the first rung is a gift
    check("  and the pay per unit never falls after the first rung %s"
          % [round(x, 1) for x in per],
          all(b >= a - 1e-9 for a, b in zip(per, per[1:])), True)

print("\n--- the ones nobody has reached pay like rare things ---")
hard_day = max(hi for _n, _f, _lo, hi in O.BANDS)       # the most a daily objective pays
for k in ("wins-500", "wins-1000", "games-1000", "surv-50", "surv-100", "total-10m",
          "hours-500", "days-100"):
    check("%s pays at least four hard days' objectives (%d)" % (k, 4 * hard_day),
          gems[k] >= 4 * hard_day, True)
check("Immortal is worth at least ten Veterans", gems["wins-1000"] >= 10 * gems["wins-100"], True)
check("Institution pays more than Fixture (it did not)", gems["wins-500"] > gems["wins-250"], True)
check("Immortal is most of an Odyssey, not all of it",
      fa.SHIP_SPECIAL_PRICE[701] // 2 <= gems["wins-1000"] < fa.SHIP_SPECIAL_PRICE[701], True)

print("\n--- divisions ---")
d = fa.GEM_DIVISION_AWARD
check("each division pays more than the one below",
      all(d[l + 1] > d[l] for l in range(1, 9)), True)
check("Mythos pays a sixth of the Odyssey", d[9], fa.SHIP_SPECIAL_PRICE[701] // 6)
check("  and more than any climbable tier", d[9] > d[8], True)

print("\n--- the tier-7 hulls ---")
cat = {i["code"]: i for i in fa.ship_catalog()}
check("Shadow X-3 is the tier price", cat[702]["price"], fa.SHIP_TIER_PRICE[7])
check("Bastion costs more than the Shadow X-3", cat[703]["price"] > cat[702]["price"], True)
check("Aries costs more than the Bastion", cat[704]["price"] > cat[703]["price"], True)
check("the Odyssey is far above all three", cat[701]["price"] >= 5 * cat[704]["price"], True)
check("Aries still costs more than the top climbable rank pays", cat[704]["price"] > d[8], True)
check("a heavy week (~1,500) does not buy a Bastion", cat[703]["price"] > 1500 * 4, True)

print("\n--- the numbers carry their measurement ---")
src = io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read()
check("GEM_WIN_MILESTONES says when and what it was measured against",
      "Measured 23 Sep 2026" in src[src.index("GEM_WIN_MILESTONES = [") - 600:src.index("GEM_WIN_MILESTONES = [")], True)
check("the long milestones say nobody has reached them",
      "Nobody has reached Institution, Immortal" in src, True)
check("the premium hulls say what a heavy week earns",
      "A heavy week of play earns about 1,500" in src, True)

print("\n%d passed, %d failed" % (ok, fail))
sys.exit(1 if fail else 0)
