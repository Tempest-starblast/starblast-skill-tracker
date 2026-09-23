# -*- coding: utf-8 -*-
"""What would this rating change have done to real matches?

Every rule changed since 9.55.0 was measured this way before it shipped,
each time with a throwaway script written from scratch. Twice the answer
was surprising enough to change the rule:

  * the per-team half-elo fix looked sweeping and moved ONE result in 86
    matches - which is why it shipped the same day rather than after a
    week of worrying;
  * the abandoned-comeback rule looked narrow and would have struck 19
    winners out of 115 matches, which is why the thresholds were argued
    over before it went live.

Nothing here changes anything. It reads the archive, applies a rule you
name, and prints who it would have touched.

    python tools_rating_impact.py --list
    python tools_rating_impact.py quitters --days 30
    python tools_rating_impact.py drift --days 7 --verbose

A rule is a function taking (ctx) and returning a list of findings. Add
one to RULES below; the harness handles the loading, the windowing and the
reporting.
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ---------------------------------------------------------------- loading

class Match(object):
    """One match, with its replay if there still is one.

    Replays are kept 30 days and then stripped of the playback streams, so
    a rule that needs radar or win-probability simply will not see older
    matches. `has_replay` and `playable` say which you have."""

    def __init__(self, row, replay_blob):
        (self.row_id, self.match_id, self.sys_id, self.played_at,
         self.lobby, self.reads, self.region) = row
        self.doc = None
        if replay_blob:
            try:
                self.doc = json.loads(zlib.decompress(replay_blob).decode("utf-8"))
            except Exception:                      # noqa: BLE001
                self.doc = None
        if isinstance(self.doc, list):             # the oldest shape
            self.doc = {"f": self.doc}

    @property
    def has_replay(self):
        return bool(self.doc and self.doc.get("f"))

    @property
    def playable(self):
        """Full recording, not an archived record."""
        return bool(self.doc and self.doc.get("wp") and self.doc.get("st"))

    @property
    def frames(self):
        return (self.doc or {}).get("f") or []

    @property
    def wp(self):
        return (self.doc or {}).get("wp") or []

    @property
    def end_t(self):
        return self.frames[-1][0] if self.frames else 0

    def last_seen(self):
        """name -> (elapsed seconds, frame index) of its final appearance."""
        out = {}
        for i, fr in enumerate(self.frames):
            for r in (fr[1] if len(fr) > 1 else []):
                if r and r[0]:
                    out[r[0]] = (fr[0], i)
        return out

    def winning_team_index(self):
        """From the station record: the side with modules still standing in
        the last readable frame. There is no 'dead' flag to read."""
        st = (self.doc or {}).get("st") or []
        for j in range(len(st) - 1, -1, -1):
            row = st[j]
            if not (isinstance(row, list) and row):
                continue
            counts = []
            for e in row:
                if isinstance(e, list) and len(e) >= 3 and isinstance(e[2], list):
                    counts.append(sum(1 for m in e[2] if m))
                else:
                    counts.append(-1)
            if counts and max(counts) > 0:
                return counts.index(max(counts))
        return None

    def players(self, c, won=None):
        q = ("SELECT name, norm_name, won, delta, half, score, played_s "
             "FROM match_players WHERE match_row = ?")
        args = [self.row_id]
        if won is not None:
            q += " AND won = ?"
            args.append(won)
        return c.execute(q, args).fetchall()


def load(days, limit, db_path, replay_path):
    cn = sqlite3.connect(db_path)
    c = cn.cursor()
    rc = sqlite3.connect(replay_path)
    q = ("SELECT id, match_id, sys_id, played_at, lobby_name, "
         "COALESCE(tracked_reads, 0), region FROM matches "
         "WHERE COALESCE(voided, 0) = 0")
    args = []
    if days:
        q += " AND played_at > datetime('now', ?)"
        args.append("-%d days" % days)
    q += " ORDER BY id DESC"
    if limit:
        q += " LIMIT %d" % limit
    for row in c.execute(q, args).fetchall():
        blob = None
        hit = rc.execute(
            "SELECT data FROM trueskill_replay WHERE sys_id = ? "
            "AND ABS(strftime('%s', at) - strftime('%s', ?)) < 3600 "
            "ORDER BY ABS(strftime('%s', at) - strftime('%s', ?)) LIMIT 1",
            (row[2], row[3], row[3])).fetchone()
        if hit:
            blob = hit[0]
        yield Match(row, blob), c
    rc.close()
    cn.close()


# ---------------------------------------------------------------- rules

def rule_quitters(m, c, opts):
    """Winners who left while the side was behind, and it came back.

    The live rule (trueskill_scorer.py): away more than QUIT_AWAY_S at the
    finish, team under QUIT_WP_MAX at their last sighting."""
    away_s = opts.get("away_s", 600.0)
    wp_max = opts.get("wp_max", 0.25)
    if not m.playable:
        return []
    wteam = m.winning_team_index()
    if wteam is None:
        return []
    last = m.last_seen()
    out = []
    for name, nn, won, delta, half, score, played in m.players(c, won=1):
        seen = last.get(name)
        if not seen:
            continue
        t, i = seen
        gone = m.end_t - t
        if gone <= away_s:
            continue
        p = m.wp[i][wteam] if i < len(m.wp) and len(m.wp[i]) > wteam else 0
        if p and p < wp_max:
            out.append({"name": name, "delta": delta,
                        "left_at_min": round(t / 60.0),
                        "away_min": round(gone / 60.0),
                        "wp_pct": round(p * 100)})
    return out


def rule_drift(m, c, opts):
    """Matches whose deltas net further from zero than the multipliers can
    explain.

    RATING_SPEC section 2: the two sides are damped to meet each other so a
    match does not create or destroy rating - but that damping is applied
    BEFORE each player's experience multiplier (x1.4 while provisional,
    x0.8 once established), deliberately, so a provisional boost is not
    cancelled out. There is also a floor: no rating goes below 500.

    So a match nets exactly zero only when both sides are the same mix of
    new and established players. With multipliers spanning 0.8 to 1.4 the
    honest bound on net/total is about (1.4-0.8)/(1.4+0.8) = 0.27, so
    anything past `share` is more than the multipliers can account for and
    is worth a look.

    (The first version of this rule tested for exact zero and flagged 5,498
    matches. The rule was wrong, not the engine.)"""
    share = opts.get("share", 0.35)
    rows = m.players(c)
    if len(rows) < 4:
        return []
    deltas = [(r[3] or 0) for r in rows]
    total_abs = sum(abs(d) for d in deltas)
    if total_abs < 1:
        return []
    net = sum(deltas)
    ratio = abs(net) / total_abs
    if ratio <= share:
        return []
    return [{"name": "(whole match)", "players": len(rows),
             "net": round(net, 1), "moved": round(total_abs, 1),
             "net_share": round(ratio, 2)}]


def rule_absent(m, c, opts):
    """Rated players who were present for less than a given share of the
    watch. Uses played_s, so only matches since 9.55.0 have it."""
    frac = opts.get("frac", 0.25)
    if not m.reads:
        return []
    rows = m.players(c)
    longest = max([r[6] or 0 for r in rows] or [0])
    if not longest:
        return []
    out = []
    for name, nn, won, delta, half, score, played in rows:
        if played and played < longest * frac:
            out.append({"name": name, "won": won, "delta": delta,
                        "present_pct": round(100.0 * played / longest)})
    return out


RULES = {
    "quitters": (rule_quitters,
                 "winners who abandoned a losing side and collected the comeback"),
    "absent":   (rule_absent,
                 "rated players present for under a quarter of the watch"),
    "drift":    (rule_drift,
                 "matches that net further from zero than the multipliers explain"),
}


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rule", nargs="?", help="which rule to measure")
    ap.add_argument("--days", type=int, default=30, help="how far back (default 30)")
    ap.add_argument("--limit", type=int, default=0, help="cap the matches examined")
    ap.add_argument("--verbose", action="store_true", help="list every finding")
    ap.add_argument("--list", action="store_true", help="show the rules")
    ap.add_argument("--db", default=os.path.join(HERE, "players.db"))
    ap.add_argument("--replays", default=os.path.join(HERE, "replays.db"))
    ap.add_argument("--set", action="append", default=[],
                    metavar="K=V", help="override a rule constant, e.g. --set wp_max=0.35")
    a = ap.parse_args()

    if a.list or not a.rule:
        print("rules:")
        for name, (_fn, desc) in sorted(RULES.items()):
            print("   %-10s %s" % (name, desc))
        print("\nexample: python tools_rating_impact.py quitters --days 30 --verbose")
        return 0
    if a.rule not in RULES:
        print("no such rule: %s (try --list)" % a.rule)
        return 2

    opts = {}
    for kv in a.set:
        k, _, v = kv.partition("=")
        try:
            opts[k] = float(v)
        except ValueError:
            opts[k] = v

    fn, desc = RULES[a.rule]
    print("%s\n%s\n" % (desc, "-" * len(desc)))
    if opts:
        print("overrides: %s\n" % opts)

    seen = usable = hit = 0
    findings = []
    for m, c in load(a.days, a.limit, a.db, a.replays):
        seen += 1
        if m.has_replay:
            usable += 1
        try:
            got = fn(m, c, opts)
        except Exception as err:                   # noqa: BLE001
            print("  (%s failed on %s: %s)" % (a.rule, m.match_id, str(err)[:60]))
            continue
        if got:
            hit += 1
            for g in got:
                g["match"] = m.match_id
                g["lobby"] = "%s #%s" % (m.lobby or "?", m.sys_id)
                findings.append(g)

    print("%d matches in the window, %d still have a replay" % (seen, usable))
    print("%d match(es) affected, %d player result(s)\n" % (hit, len(findings)))
    if findings:
        keys = [k for k in findings[0] if k not in ("match", "lobby")]
        print("  %-20s %-22s %s" % ("player", "lobby", "  ".join(keys)))
        for f in (findings if a.verbose else findings[:25]):
            vals = "  ".join(str(f.get(k)) for k in keys)
            print("  %-20s %-22s %s" % (str(f.get("name"))[:20], f["lobby"][:22], vals))
        if not a.verbose and len(findings) > 25:
            print("  ... %d more (--verbose for all)" % (len(findings) - 25))
        tot = sum(f.get("delta") or 0 for f in findings if isinstance(f.get("delta"), (int, float)))
        if tot:
            print("\n  rating involved: %+.1f" % tot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
