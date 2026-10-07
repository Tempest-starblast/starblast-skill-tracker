# -*- coding: utf-8 -*-
"""Finishing order of the teams in a team match, read off the station telemetry.

A team is out when its station is destroyed - every module reads dead. Each raw
read carries `sh`, one entry per team with `dead` (modules at zero) and `n`
(modules in total), so the moment a team went out is in the reads. The winner
finished first; the others are placed by how long they lasted: the one that
went out LATER finished second.

Two things keep this honest:
  * the moment is the start of the team's last unbroken stretch of dead reads,
    so a one-read glitch (a rejoin, a half-loaded lobby) is not an elimination,
    and reads with no station data are skipped rather than counted either way;
  * when the order of the two losers rests on a gap smaller than MIN_GAP_S - two
    stations going down within a couple of reads, or neither going down at all -
    no order is claimed. The caller falls back to something else (and says so)
    rather than guessing.

Used by the scorer (trueskill_scorer.build_game_end) and read by the site."""

MIN_GAP_S = 5.0      # reads come every ~3 s; closer than two reads is a coin toss
# When a match ends every station can read dead at once - the winner's too - so
# two losers that "went out" in the last half-minute then say nothing about which
# lasted longer. With the winner's station still standing there is no blur: the
# match ends exactly when the second-to-last station falls, so a close finish
# between the two losers is real and is trusted down to MIN_GAP_S.
END_WINDOW_S = 30.0


def _dead_all(sh_entry):
    """True when this team's station reads fully destroyed, False when it reads
    anything else, None when there is no reading."""
    if not isinstance(sh_entry, dict):
        return None
    dead, n = sh_entry.get("dead"), sh_entry.get("n")
    if dead is None or not n:
        return None
    return dead >= n


def team_out_times(reads, n_teams=3):
    """{team index: seconds since the first read when its station went out, or
    None if it was still standing at the last reading}."""
    reads = sorted((r for r in reads if isinstance(r, dict)), key=lambda r: r.get("ts") or 0)
    if not reads:
        return {i: None for i in range(n_teams)}
    t0 = reads[0].get("ts") or 0
    out = {}
    for i in range(n_teams):
        # (ts, destroyed?) for every read that has a reading for this team
        series = []
        for r in reads:
            sh = r.get("sh")
            if isinstance(sh, list) and i < len(sh):
                d = _dead_all(sh[i])
                if d is not None:
                    series.append(((r.get("ts") or 0), d))
        if not series or not series[-1][1]:
            out[i] = None                    # standing at the last reading (or never read)
            continue
        j = len(series) - 1
        while j > 0 and series[j - 1][1]:
            j -= 1
        out[i] = round(series[j][0] - t0, 1)
    return out


def finish_order(reads, winner, losing):
    """The teams' places.

    winner  - index of the winning team; losing - indexes of the others.
    Returns {"places": {team index: 1|2|3}, "out_s": {team index: seconds|None},
             "basis": "elimination" | "two-team" | "unknown"}.
    "unknown" still places the winner first; the losers are left out."""
    try:
        n_teams = max([winner] + list(losing)) + 1
        out = team_out_times(reads, max(3, n_teams))
        out = {k: v for k, v in out.items() if k == winner or k in losing}
        places = {winner: 1}
        if len(losing) == 1:
            places[losing[0]] = 2
            return {"places": places, "out_s": out, "basis": "two-team"}
        if len(losing) != 2:
            return {"places": places, "out_s": out, "basis": "unknown"}
        a, b = losing
        ta, tb = out.get(a), out.get(b)
        stamps = [r.get("ts") or 0 for r in reads if isinstance(r, dict)]
        end_s = (max(stamps) - min(stamps)) if stamps else 0
        if ta is None and tb is None:
            basis_ok = False                 # neither went down: the lasting is a tie
        elif ta is None or tb is None:
            basis_ok = True                  # one stood to the end, the other did not
        else:
            blur = (out.get(winner) is not None
                    and ta >= end_s - END_WINDOW_S and tb >= end_s - END_WINDOW_S)
            basis_ok = abs(ta - tb) >= MIN_GAP_S and not blur
        if not basis_ok:
            return {"places": places, "out_s": out, "basis": "unknown"}
        a_later = ta is None or (tb is not None and ta > tb)
        places[a if a_later else b] = 2
        places[b if a_later else a] = 3
        return {"places": places, "out_s": out, "basis": "elimination"}
    except Exception:
        return {"places": {winner: 1}, "out_s": {}, "basis": "unknown"}
