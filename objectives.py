# -*- coding: utf-8 -*-
"""The objective catalogue: every one the site can set, and how often each is
actually done.

Two halves that must stay in step. GRID is the rule for what an objective can
be - a fact, a threshold, and the words for it - and it is generated rather
than written out, because there are six hundred of them. RATES is what the
live board says about each one: the share of players WITH AN ACCOUNT who,
having played at all that day (or that week), already met it. Rates are
measured by scripts/measure_objectives.py against the real database, never
estimated; an objective with no measured rate is not offered.

Difficulty and pay come from the rate and nothing else, so an objective that
a third of the board does every week can never pay more than one that three
per cent manage.
"""

import ship_shapes

# ---------------------------------------------------------------- the grid
# (kind, metric, arg, need). kind is "d" for a day or "w" for a week; arg is
# whatever the metric needs beside the count - a tier, a hull, a region, a
# death cap, a rating floor - and need is how many.
REGIONS = (("america", "North America"), ("europe", "Europe"), ("asia", "Asia"))
DEATH_CAPS = (0, 1, 2, 3)
RATING_FLOORS = (10, 15, 20, 25, 30)

_DAY_COUNTS = (1, 2, 3, 4, 5, 6, 8, 10)
_WEEK_COUNTS = (2, 3, 5, 8, 10, 15, 20, 30, 40)
_DAY_SCORE = (2000, 5000, 10000, 15000, 20000, 30000, 40000, 60000)
_WEEK_SCORE = (10000, 20000, 40000, 60000, 80000, 120000, 200000, 300000)
_BEST_SCORE = (5000, 10000, 15000, 20000, 25000, 30000, 40000, 50000)


def _counts(kind):
    return _DAY_COUNTS if kind == "d" else _WEEK_COUNTS


def grid():
    """Every candidate objective, in a fixed order. The key is stable: it is
    what the ledger records a claim against, so it must never be reused for
    a different thing."""
    out = []

    def add(kind, metric, arg, need):
        out.append(("%s:%s:%s:%d" % (kind, metric, arg if arg != "" else "-", need),
                    kind, metric, arg, need))

    for kind in ("d", "w"):
        cs = _counts(kind)
        for n in cs:
            add(kind, "wins", "", n)
            add(kind, "played", "", n)
        for n in cs[:6]:
            add(kind, "mate_wins", "", n)
            add(kind, "surv_rounds", "", n)
        for n in cs[:4]:
            add(kind, "surv_top3", "", n)
            add(kind, "streak", "", n + 1)
            add(kind, "ships", "", n + 1)
        for n in cs[:3]:
            add(kind, "surv_wins", "", n)
        for s in (_DAY_SCORE if kind == "d" else _WEEK_SCORE):
            add(kind, "score", "", s)
        for s in _BEST_SCORE:
            add(kind, "best", "", s)
        for t in range(1, 8):
            for n in cs[:5]:
                add(kind, "tierwin", str(t), n)
                add(kind, "tierplay", str(t), n)
            # "tier 4 or better" is a different ask from "exactly tier 4", and
            # it is the one people recognise - you fly up the tiers, you do not
            # pick one and stay.
            if t >= 2:
                for n in cs[:4]:
                    add(kind, "tierplus", str(t), n)
        for code in ship_shapes.ship_codes():
            for n in cs[:3]:
                add(kind, "shipwin", str(code), n)
            for n in cs[:2]:
                add(kind, "shipplay", str(code), n)
        for cap in DEATH_CAPS:
            for n in cs[:4]:
                add(kind, "clean", str(cap), n)
        for floor in RATING_FLOORS:
            for n in cs[:4]:
                add(kind, "big", str(floor), n)
        for region, _label in REGIONS:
            for n in cs[:4]:
                add(kind, "region", region, n)
        for n in cs[:4]:
            add(kind, "deaths", "", n * 10)
    for n in (2, 3, 4, 5, 6, 7):
        add("w", "days", "", n)
    return out


GRID = grid()

# ------------------------------------------------------------- the words
_TIERS = {1: "tier 1", 2: "tier 2", 3: "tier 3", 4: "tier 4",
          5: "tier 5", 6: "tier 6", 7: "tier 7"}
_REGION_LABEL = dict(REGIONS)


def _pl(n, one, many=None):
    return one if n == 1 else (many or (one + "s"))


def text_for(metric, arg, need, kind):
    """What the objective says. Plain, and the same shape whatever the
    numbers are, so a reader learns to skim them."""
    win = lambda n: "Win %d %s" % (n, _pl(n, "team match", "team matches"))
    if metric == "wins":
        return win(need)
    if metric == "played":
        return "Play %d %s" % (need, _pl(need, "team match", "team matches"))
    if metric == "score":
        return "Score {:,} across your matches".format(need)
    if metric == "best":
        return "Score {:,} in a single match".format(need)
    if metric == "surv_rounds":
        return "Play %d survival %s" % (need, _pl(need, "round"))
    if metric == "surv_top3":
        return "Finish in the survival top 3%s" % ("" if need == 1 else " %d times" % need)
    if metric == "surv_wins":
        return "Win %d survival %s" % (need, _pl(need, "round"))
    if metric == "tierwin":
        return "%s flying a %s ship" % (win(need), _TIERS[int(arg)])
    if metric == "tierplus":
        return "%s flying a %s ship or better" % (win(need), _TIERS[int(arg)])
    if metric == "tierplay":
        return "Play %d %s in a %s ship" % (need, _pl(need, "match", "matches"), _TIERS[int(arg)])
    if metric == "shipwin":
        return "%s flying the %s" % (win(need), ship_shapes.ship_name(int(arg)))
    if metric == "shipplay":
        return "Fly the %s in %d rated %s" % (ship_shapes.ship_name(int(arg)), need,
                                              _pl(need, "match", "matches"))
    if metric == "clean":
        cap = int(arg)
        how = "without dying" if cap == 0 else "dying no more than %d %s" % (cap, _pl(cap, "time"))
        return "%s %s" % (win(need), how)
    if metric == "big":
        return "%s worth %s rating or more" % (win(need), arg)
    if metric == "mate_wins":
        return "%s alongside a clanmate" % win(need)
    if metric == "region":
        return "Play %d %s in %s" % (need, _pl(need, "match", "matches"), _REGION_LABEL[arg])
    if metric == "streak":
        return "Win %d matches in a row" % need
    if metric == "ships":
        return "Fly %d different ships" % need
    if metric == "deaths":
        return "Lose %d ships and keep playing" % need
    if metric == "days":
        return "Play on %d different days" % need
    return "%s %s" % (metric, need)


# ------------------------------------------------------------- the money
# Bands by measured completion rate, and what each band pays. A day's set is
# three easy, two medium and one hard; the weekly set is one of each.
BANDS = (("easy", 25.0, 200, 900), ("medium", 8.0, 500, 2200), ("hard", 0.8, 1100, 5000))
# (name, the rate at or above which an objective is in this band, day pay, week pay)
RATE_FLOOR = 0.8          # under this, nobody would ever see it done - not offered
RATE_CEILING = 75.0       # over this it is not an objective, it is a formality


def band_for(rate):
    for name, floor, _d, _w in BANDS:
        if rate >= floor:
            return name
    return None


def pay_for(rate, kind):
    """Inside a band, the rarer half pays the top of the band. Rounded to
    something a person would say out loud."""
    for name, floor, day, week in BANDS:
        if rate >= floor:
            top = {"easy": 25.0, "medium": 8.0, "hard": 0.8}[name]
            nxt = {"easy": RATE_CEILING, "medium": 25.0, "hard": 8.0}[name]
            base = day if kind == "d" else week
            hi = base * (2.0 if name == "hard" else 1.6)
            # rate == nxt -> base, rate == top -> hi
            span = max(0.001, nxt - top)
            f = min(1.0, max(0.0, (nxt - rate) / span))
            v = base + (hi - base) * f
            step = 50 if v < 1000 else 100
            return int(round(v / step) * step)
    return 0
