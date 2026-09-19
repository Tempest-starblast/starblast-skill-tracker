# -*- coding: utf-8 -*-
"""The objective catalogue: every one the site can set, and how often each is
actually done.

Two halves that must stay in step. GRID is the rule for what an objective can
be - a fact, a threshold, and the words for it - and it is generated rather
than written out, because there are hundreds. RATES is what the live board
says about each one: the share of players WITH AN ACCOUNT who, having played
at all that day, already met it. Rates are measured against the real database
by the measuring script (kept with the test suites), never estimated, and an
objective with no measured rate is never offered.

Difficulty and pay come from the rate and nothing else, so an objective a
third of the board does every day can never pay more than one that three per
cent manage. Every objective is a day's work and resets at midnight UTC.
"""

import ship_shapes

REGIONS = (("america", "North America"), ("europe", "Europe"), ("asia", "Asia"))
DEATH_CAPS = (0, 1, 2, 3)
RATING_FLOORS = (10, 15, 20, 25, 30)
SURV_PLACES = (3, 5, 10)
SURV_FIELDS = (10, 15, 20)

_N = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15)
_SCORE = (2000, 5000, 10000, 15000, 20000, 30000, 40000, 60000, 80000)
_BEST = (5000, 10000, 15000, 20000, 25000, 30000, 40000, 50000)
_ELO = (10, 20, 30, 50, 75, 100, 150)
_DEATHS = (10, 20, 30, 50)


def grid():
    """Every candidate objective, in a fixed order. The key is stable - the
    ledger records a claim against it - so a key must never be reused for a
    different thing."""
    out = []

    def add(metric, arg, need):
        out.append(("%s:%s:%d" % (metric, arg if arg != "" else "-", need), metric, arg, need))

    for n in _N[:8]:
        add("wins", "", n)
    for n in _N:
        add("played", "", n)
    for s in _SCORE:
        add("score", "", s)
    for s in _BEST:
        add("best", "", s)
    for e in _ELO:
        add("elo", "", e)
    for n in _N[:6]:
        add("surv_rounds", "", n)
        add("mate_wins", "", n)
    for n in _N[:4]:
        add("surv_wins", "", n)
        add("streak", "", n + 1)
        add("ships", "", n + 1)
        add("deaths", "", _DEATHS[n - 1])
    for place in SURV_PLACES:
        for n in _N[:4]:
            add("surv_place", str(place), n)
    for field in SURV_FIELDS:
        add("surv_bigwin", str(field), 1)
        add("surv_bigtop", str(field), 1)
    for n in (2, 3, 4):
        add("tiers", "", n)
    for t in range(1, 8):
        for n in _N[:5]:
            add("tierwin", str(t), n)
            add("tierplay", str(t), n)
        add("tierclean", str(t), 1)
        if t >= 2:
            for n in _N[:4]:
                add("tierplus", str(t), n)
    for code in ship_shapes.ship_codes():
        for n in _N[:4]:
            add("shipwin", str(code), n)
            add("shipplay", str(code), n)
        add("shipclean", str(code), 1)
        add("shipbig", str(code), 1)
    for cap in DEATH_CAPS:
        for n in _N[:4]:
            add("clean", str(cap), n)
    for floor in RATING_FLOORS:
        for n in _N[:4]:
            add("big", str(floor), n)
    for region, _label in REGIONS:
        for n in _N[:4]:
            add("region", region, n)
        for n in _N[:3]:
            add("regionwin", region, n)
    return out


GRID = grid()

# ------------------------------------------------------------- the words
_TIERS = dict((t, "tier %d" % t) for t in range(1, 8))
_REGION_LABEL = dict(REGIONS)


def _pl(n, one, many=None):
    return one if n == 1 else (many or (one + "s"))


def _win(n):
    return "Win %d %s" % (n, _pl(n, "team match", "team matches"))


def text_for(metric, arg, need):
    """What the objective says. The same shape whatever the numbers are, so a
    reader learns to skim them."""
    if metric == "wins":
        return _win(need)
    if metric == "played":
        return "Play %d %s" % (need, _pl(need, "team match", "team matches"))
    if metric == "score":
        return "Score {:,} across your matches".format(need)
    if metric == "best":
        return "Score {:,} in a single match".format(need)
    if metric == "elo":
        return "Gain %d rating" % need
    if metric == "surv_rounds":
        return "Play %d survival %s" % (need, _pl(need, "round"))
    if metric == "surv_wins":
        return "Win %d survival %s" % (need, _pl(need, "round"))
    if metric == "surv_place":
        p = int(arg)
        return ("Finish in the survival top %d" % p) + ("" if need == 1 else " %d times" % need)
    if metric == "surv_bigwin":
        return "Win a survival round with %s or more in it" % arg
    if metric == "surv_bigtop":
        return "Finish top 3 in a survival round of %s or more" % arg
    if metric == "streak":
        return "Win %d matches in a row" % need
    if metric == "ships":
        return "Fly %d different ships" % need
    if metric == "tiers":
        return "Fly ships from %d different tiers" % need
    if metric == "deaths":
        return "Lose %d ships and keep playing" % need
    if metric == "mate_wins":
        return "%s alongside a clanmate" % _win(need)
    if metric == "tierwin":
        return "%s flying a %s ship" % (_win(need), _TIERS[int(arg)])
    if metric == "tierplus":
        return "%s flying a %s ship or better" % (_win(need), _TIERS[int(arg)])
    if metric == "tierplay":
        return "Play %d %s in a %s ship" % (need, _pl(need, "match", "matches"), _TIERS[int(arg)])
    if metric == "tierclean":
        return "Win in a %s ship without dying" % _TIERS[int(arg)]
    if metric == "shipwin":
        return "%s flying the %s" % (_win(need), ship_shapes.ship_name(int(arg)))
    if metric == "shipplay":
        return "Fly the %s in %d rated %s" % (ship_shapes.ship_name(int(arg)), need,
                                              _pl(need, "match", "matches"))
    if metric == "shipclean":
        return "Win in the %s without dying" % ship_shapes.ship_name(int(arg))
    if metric == "shipbig":
        return "Win a match worth 20+ rating in the %s" % ship_shapes.ship_name(int(arg))
    if metric == "clean":
        cap = int(arg)
        how = "without dying" if cap == 0 else "dying no more than %d %s" % (cap, _pl(cap, "time"))
        return "%s %s" % (_win(need), how)
    if metric == "big":
        return "%s worth %s rating or more" % (_win(need), arg)
    if metric == "region":
        return "Play %d %s in %s" % (need, _pl(need, "match", "matches"), _REGION_LABEL[arg])
    if metric == "regionwin":
        return "%s in %s" % (_win(need), _REGION_LABEL[arg])
    return "%s %s" % (metric, need)


# ------------------------------------------------------------- the money
# Three bands by measured completion rate. A day's set is three easy, two
# medium and one hard, so the bands are what the rotation draws from.
EASY, MEDIUM, HARD = 25.0, 8.0, 0.3
BANDS = (("easy", EASY, 200, 350), ("medium", MEDIUM, 450, 800), ("hard", HARD, 1000, 2500))
RATE_CEILING = 80.0       # above this it is not an objective, it is a formality


def band_for(rate):
    """easy / medium / hard, or None for one nobody has ever done (or one
    everybody does without trying)."""
    if rate is None or rate > RATE_CEILING:
        return None
    for name, floor, _lo, _hi in BANDS:
        if rate >= floor:
            return name
    return None


def pay_for(rate):
    """Within a band, the rarer end pays the top of the band."""
    band = band_for(rate)
    if not band:
        return 0
    top = {"easy": EASY, "medium": MEDIUM, "hard": HARD}[band]
    nxt = {"easy": RATE_CEILING, "medium": EASY, "hard": MEDIUM}[band]
    lo, hi = [(b[2], b[3]) for b in BANDS if b[0] == band][0]
    f = min(1.0, max(0.0, (nxt - rate) / max(0.001, nxt - top)))
    v = lo + (hi - lo) * f
    step = 50 if v < 1000 else 100
    return int(round(v / step) * step)
