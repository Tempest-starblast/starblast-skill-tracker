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


def part_weight(presence):
    """presence in [0,1] -> influence weight in [0,1]."""
    if presence is None or presence < MIN_PRESENCE:
        return 0.0
    if presence >= THETA:
        return 1.0
    return FLOOR_W + (presence - MIN_PRESENCE) / (THETA - MIN_PRESENCE) * (1.0 - FLOOR_W)


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


def compute_match(teams, winner_key):
    """teams: {team_key: [ {name, elo, games, weight} ]} - only RATED players,
    weight = participation weight (players below the floor are dropped upstream).
    winner_key: the team that won.

    Returns (results, analytics):
      results: [ {name, won, delta, weight} ] for each moved player.
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
        for m in teams[k]:
            w = m["weight"]
            if w <= 0:
                continue
            eff = (m["elo"] + strengths[k]) / 2.0
            base = win_expectation(eff, rivals)
            raw = K * ((1 - base) if won else base)   # win pays the upset; loss costs the expected win
            kmult = k_factor(m.get("games", 0)) / K
            pending.append([m["name"], won, raw * w * kmult, w])

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
    for name, won, amt, w in pending:
        delta = amt * (fg if won else -fl)
        results.append({"name": name, "won": bool(won),
                        "delta": round(delta, 2), "weight": round(w, 3)})
    analytics = {"strengths": {k: round(v, 1) for k, v in strengths.items()},
                 "expected": {k: round(v, 3) for k, v in expected.items()},
                 "winner": winner_key}
    return results, analytics
