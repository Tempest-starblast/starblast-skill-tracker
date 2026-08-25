"""Participation-weighted "full match" rating - the SHADOW system.

A parallel, from-zero rating that runs alongside the live Elo for review. It
mirrors the live math (prior-shrunk team-average strength, N-way win
expectation, conservation damping, provisional K) but adds the one thing the
browser tracker can't provide and the raw pipeline can: how much of the match
each player actually played, from t=0. A player present the whole match counts
fully; a late/cameo joiner counts less, both in their team's strength and in
how far their own rating moves.

Runs on its own tables (shadow_players / shadow_matches) so nothing here
touches the live board until it's proven. Constants are copies of the live
ones so the two boards are comparable; tune the participation curve here.
"""
import math

START = 1000.0
K = 200.0            # max swing (matches live ELO_K)
SCALE = 2000.0       # rating-gap scale (matches live ELO_SCALE)
PRIOR_W = 3.0        # team-strength shrink toward START (matches live)
PROVISIONAL_GAMES = 5
ESTABLISHED_GAMES = 20
PROV_K = 1.4
EST_K = 0.8
FLOOR_ELO = 500.0

# Participation curve: presence is the fraction of the match (by snapshots seen
# alive) a player was in. Below MIN they didn't really play (weight 0); at/above
# THETA they count fully; between, weight ramps from FLOOR_W up to 1.
MIN_PRESENCE = 0.15
FLOOR_W = 0.15
THETA = 0.60

# A player must have actually DONE something to be rated. Watcher bots and AFK
# clients sit in the roster the whole match with a score of 0 - being present
# is not participating. Below this final score, a player is dropped entirely.
MIN_SCORE = 1

# And they must have actually been in the match: at least this many minutes of
# presence, or they don't count at all (owner rule, 25 Aug).
MIN_MINUTES = 10

# Combat facet (owner rule, 25 Aug): "kills aren't indicative of elo or skill,
# its just a facet." So combat (score earned from inferred kills) NEVER changes
# a team's aggregate rating change or the system total - it only shifts credit
# WITHIN a team by at most +/-COMBAT_BAND: the player who did more of the
# fighting keeps a little more of a win / sheds a little less of a loss, the
# passenger a little less, and the team total is renormalised back to exactly
# what win/loss + participation decided. Set to 0.0 to make combat display-only.
COMBAT_BAND = 0.15


def part_weight(presence):
    """presence in [0,1] -> influence weight in [0,1]. (Kept for reference; the
    live model now weights by join station level, see join_weight.)"""
    if presence is None or presence < MIN_PRESENCE:
        return 0.0
    if presence >= THETA:
        return 1.0
    return FLOOR_W + (presence - MIN_PRESENCE) / (THETA - MIN_PRESENCE) * (1.0 - FLOOR_W)


def join_weight(join_level):
    """Weight by the STATION LEVEL a player joined into: -25% per level above 1.
    Join at level 1 (start of game) = 100% stake (full gain AND full loss);
    level 2 = 75%, level 3 = 50%, level 4 (max) = 25%. You're rewarded and
    charged in proportion to how invested you were from the start."""
    try:
        lvl = int(join_level)
    except (TypeError, ValueError):
        lvl = 1
    lvl = max(1, min(4, lvl))
    return max(0.25, 1.0 - 0.25 * (lvl - 1))


def win_expectation(own, rivals):
    """This side's chance of winning against all rival team strengths at once
    (N-way generalisation; one rival reduces to the classic 2-team formula)."""
    total = 1.0
    for r in rivals:
        total += 10 ** ((r - own) / SCALE)
    return 1.0 / total


def k_factor(games):
    if games < PROVISIONAL_GAMES:
        return K * PROV_K
    if games < ESTABLISHED_GAMES:
        return K
    return K * EST_K


def team_strength(members):
    """members: list of (elo, weight) for the RATED players on a team. A
    participation-weighted, prior-shrunk average - a barely-present player barely
    counts, and a thin known roster is pulled toward START."""
    sw = sum(w for _, w in members if w > 0)
    if sw <= 0:
        return START
    wsum = sum(e * w for e, w in members if w > 0)
    return (wsum + PRIOR_W * START) / (sw + PRIOR_W)


def _combat_mults(members):
    """Within ONE team, a bounded, team-neutral credit nudge from combat (score
    earned from inferred kills). Returns {name: multiplier in [1-BAND, 1+BAND]}.
    Average combat -> 1.0 (no change); a carrier -> up to 1+BAND; a passenger
    with no kills -> down to ~1-BAND. tanh keeps it smooth and bounded. The
    CALLER renormalises so the team total is preserved - so this only ever
    RESHUFFLES credit inside a team, never inflates the system (kill-farming
    cannot raise anyone's absolute rating). A facet, per the owner rule."""
    if COMBAT_BAND <= 0:
        return {m["name"]: 1.0 for m in members}
    vals = [(m["name"], max(0.0, float(m.get("combat", 0) or 0))) for m in members]
    if sum(1 for _, v in vals if v > 0) < 2:      # nothing to differentiate
        return {n: 1.0 for n, _ in vals}
    mean = sum(v for _, v in vals) / len(vals)
    if mean <= 0:
        return {n: 1.0 for n, _ in vals}
    return {n: 1.0 + COMBAT_BAND * math.tanh(v / mean - 1.0) for n, v in vals}


def compute_match(teams, winner_key):
    """teams: {team_key: [ {name, elo, games, weight, combat, kills, deaths,
    caliber} ]} - only RATED players, weight = participation weight (players
    below the floor are dropped upstream). winner_key: the team that won.

    Returns (results, analytics):
      results: [ {name, won, delta, weight, combat, kills, deaths, caliber,
                  cmult} ] for each moved player.
      analytics: {strengths, expected, winner} for the review page.
    """
    keys = list(teams.keys())
    strengths = {k: team_strength([(m["elo"], m["weight"]) for m in teams[k]])
                 for k in keys}
    expected = {}
    for k in keys:
        rivals = [strengths[o] for o in keys if o != k]
        expected[k] = win_expectation(strengths[k], rivals) if rivals else 1.0

    pending = []
    for k in keys:
        won = (k == winner_key)
        rivals = [strengths[o] for o in keys if o != k] or [START]
        mults = _combat_mults(teams[k])
        tmp = []
        for m in teams[k]:
            w = m["weight"]
            if w <= 0:
                continue
            eff = (m["elo"] + strengths[k]) / 2.0
            base = win_expectation(eff, rivals)
            raw = K * ((1 - base) if won else base)   # win pays the upset; loss costs the expected win
            kmult = k_factor(m.get("games", 0)) / K
            tmp.append([m, won, raw * w * kmult, w, mults.get(m["name"], 1.0)])
        # combat facet: multiply each player's magnitude by their combat nudge,
        # then rescale the team back to its pre-nudge total so the aggregate
        # (and thus conservation below) is untouched. Credit only moves WITHIN
        # the team.
        base_sum = sum(t[2] for t in tmp)
        adj_sum = sum(t[2] * t[4] for t in tmp)
        rescale = (base_sum / adj_sum) if adj_sum else 1.0
        for t in tmp:
            t[2] = t[2] * t[4] * rescale
        pending.extend(tmp)

    # A match neither creates nor destroys rating: damp the heavier side to the
    # lighter (never inflate a swing to balance the books).
    tg = sum(p[2] for p in pending if p[1])
    tl = sum(p[2] for p in pending if not p[1])
    fg = fl = 1.0
    if tg > 0 and tl > 0:
        if tg > tl:
            fg = tl / tg
        else:
            fl = tg / tl

    results = []
    for m, won, amt, w, cm in pending:
        delta = amt * (fg if won else -fl)
        results.append({"name": m["name"], "won": bool(won),
                        "delta": round(delta, 2), "weight": round(w, 3),
                        "combat": int(m.get("combat", 0) or 0),
                        "kills": int(m.get("kills", 0) or 0),
                        "deaths": int(m.get("deaths", 0) or 0),
                        "caliber": int(m.get("caliber", 0) or 0),
                        "cmult": round(cm, 3)})
    analytics = {"strengths": {k: round(v, 1) for k, v in strengths.items()},
                 "expected": {k: round(v, 3) for k, v in expected.items()},
                 "winner": winner_key}
    return results, analytics
