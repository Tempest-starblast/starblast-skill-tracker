"""Skill-tier ladder for the leaderboard.

Eight tiers by percentile, Drifter at the bottom up to Archon for the top
half-percent, and above them all Mythos: not a percentile at all but the mark
of having been number one on the board, held for ever once it is won. Each
tier's emblem is a ship of the tree, escalating in rarity and flair, drawn
from the game-accurate silhouettes in ship_shapes; Mythos wears the Odyssey
in crimson. `flair` (1-9) drives how stylised the profile theme gets.

The `key` of each tier is an opaque id and must never change: peak_div
records, the div-<key> achievements and shop refs are all written against it.
The `name` is only what a page prints, so the ladder can be renamed freely.
"""
import ship_shapes

# best -> worst. `cut` is the cumulative top-fraction ceiling for the band:
# a player at percentile-fraction f (0 = #1) is in the first band with f < cut.
# A `cut` of None is not a percentile band at all and is never handed out by
# division_for - Mythos is awarded from a career-best rank of #1, in
# gem_peak_level and division_map, not from where you sit today.
# `flair` 1..9 escalates the visual treatment on the profile (1 = plain matte,
# 8 = holographic diamond, 9 = the mythic crimson). `diamond` gets the
# glitter/shimmer treatment; `mythic` gets the crimson one.
RANKS = [
    {"level": 9, "key": "mythos",   "name": "Mythos",   "ship": 701,
     "cut": None, "band": "Once number one", "flair": 9, "mythic": True,
     "color": "#ff2e4d", "glow": "rgba(255,46,77,.6)"},
    {"level": 8, "key": "shadowx3", "name": "Archon",   "ship": 702,
     "cut": 0.005, "band": "Top 0.5%", "flair": 8, "diamond": True,
     "color": "#8ef3ff", "glow": "rgba(150,230,255,.55)"},
    {"level": 7, "key": "odyssey",  "name": "Warden",   "ship": 603,
     "cut": 0.03, "band": "Top 3%", "flair": 7,
     "color": "#ff7b53", "glow": "rgba(255,123,83,.48)"},
    {"level": 6, "key": "advanced", "name": "Vanguard", "ship": 601,
     "cut": 0.10, "band": "Top 10%", "flair": 6,
     "color": "#e3b341", "glow": "rgba(227,179,65,.42)"},
    {"level": 5, "key": "usniper",  "name": "Guard",    "ship": 501,
     "cut": 0.22, "band": "Top 22%", "flair": 5,
     "color": "#bc8cff", "glow": "rgba(188,140,255,.38)"},
    {"level": 4, "key": "mercury",  "name": "Warrior",  "ship": 406,
     "cut": 0.40, "band": "Top 40%", "flair": 4,
     "color": "#58a6ff", "glow": "rgba(88,166,255,.34)"},
    {"level": 3, "key": "pulse",    "name": "Raider",   "ship": 301,
     "cut": 0.62, "band": "Top 62%", "flair": 3,
     "color": "#2dd4bf", "glow": "rgba(45,212,191,.30)"},
    {"level": 2, "key": "delta",    "name": "Scout",    "ship": 201,
     "cut": 0.82, "band": "Top 82%", "flair": 2,
     "color": "#3fb950", "glow": "rgba(63,185,80,.26)"},
    {"level": 1, "key": "fly",      "name": "Drifter",  "ship": 101,
     "cut": 1.01, "band": "Entry tier", "flair": 1,
     "color": "#7d858f", "glow": "rgba(125,133,143,.18)"},
]

# The one tier you cannot climb to: it is won by finishing a day at #1.
MYTHOS_KEY = "mythos"
MYTHOS_LEVEL = 9


def info_table_html():
    """The ladder as a table for the Info page - built from RANKS itself, so
    a threshold can never be right in the code and wrong in the prose."""
    rows = []
    for r in RANKS:
        d = ship_shapes.ship_path(r["ship"]) or ""
        rows.append(
            '<tr><td class="rk-em"><svg viewBox="0 0 100 100" aria-hidden="true">'
            '<path d="%s" fill="%s"/></svg></td>'
            '<td class="rk-nm" style="color:%s">%s</td>'
            '<td class="rk-bd">%s</td></tr>'
            % (d, r["color"], r["color"], r["name"], r["band"]))
    # Any tier with no percentile of its own needs a word, or the prose
    # above the table ("your place among every ranked player") is wrong for
    # that row. Generated from the ladder, so it cannot drift.
    odd = [r["name"] for r in RANKS if r["cut"] is None]
    note = ""
    if odd:
        note = ('<p class="rk-note">%s is not a share of the board like the '
                'others: it is won by finishing a day at number one, and it '
                'is never lost afterwards.</p>' % " and ".join(odd))
    return ('<div class="rk-wrap"><table class="rk-tbl">'
            '<tbody>' + "".join(rows) + '</tbody></table>' + note + '</div>')


RANK_BY_KEY = {r["key"]: r for r in RANKS}
RANK_BY_LEVEL = {r["level"]: r for r in RANKS}
MYTHOS = RANK_BY_KEY[MYTHOS_KEY]
TOP_LEVEL = max(r["level"] for r in RANKS)
# The best tier you can reach by climbing, which is what the shop means by
# "the top tier" when it sells the Odyssey.
TOP_CLIMBABLE = max(r["level"] for r in RANKS if r["cut"] is not None)


def division_for(rank0, total):
    """rank0: 0-based position among ranked players (0 = best). total: how
    many ranked players there are. Returns a RANKS entry, or None. Never
    returns Mythos: that one is not a percentile."""
    if total <= 0:
        return None
    frac = rank0 / float(total)
    for r in RANKS:
        if r["cut"] is not None and frac < r["cut"]:
            return r
    return RANKS[-1]


def ship_emblem_path(code):
    return ship_shapes.ship_path(code)


def emblem_svg(code, size=16, color="#8b949e", title=None, cls="rank-emblem"):
    """Inline SVG of a ship silhouette, filled with `color`. Safe to embed."""
    d = ship_shapes.ship_path(code)
    if not d:
        return ""
    t = ('<title>%s</title>' % _esc(title)) if title else ""
    return ('<svg class="%s" viewBox="0 0 100 100" width="%d" height="%d" '
            'aria-hidden="%s" role="img" style="display:inline-block;'
            'vertical-align:middle">%s<path d="%s" fill="%s"/></svg>'
            % (cls, size, size, "false" if title else "true", t, d, color))


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
