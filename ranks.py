"""Skill-rank ladder for the leaderboard.

Eight divisions, mapped to iconic ships of the tree, escalating in rarity and
flair: a plain, rundown Fly at the bottom up to a shiny holographic Shadow X-3
for the top 0.1%. A player's division comes from their percentile among ranked
(non-provisional) players on the canonical all-time board, and the emblem IS
that division's ship, drawn from the game-accurate silhouettes in ship_shapes.
`flair` (1-8) drives how stylised the profile theme gets.
"""
import ship_shapes

# best -> worst. `cut` is the cumulative top-fraction ceiling for the band:
# a player at percentile-fraction f (0 = #1) is in the first band with f < cut.
# `flair` 1..8 escalates the visual treatment on the profile (1 = plain matte,
# 8 = holographic diamond). `diamond` gets the glitter/shimmer treatment.
RANKS = [
    {"level": 8, "key": "shadowx3", "name": "Shadow X-3",       "ship": 702,
     "cut": 0.005, "band": "Top 0.5%", "flair": 8, "diamond": True,
     "color": "#8ef3ff", "glow": "rgba(150,230,255,.55)"},
    {"level": 7, "key": "odyssey",  "name": "Odyssey",          "ship": 701,
     "cut": 0.03, "band": "Top 3%", "flair": 7,
     "color": "#ff7b53", "glow": "rgba(255,123,83,.48)"},
    {"level": 6, "key": "advanced", "name": "Advanced-Fighter", "ship": 601,
     "cut": 0.10, "band": "Top 10%", "flair": 6,
     "color": "#e3b341", "glow": "rgba(227,179,65,.42)"},
    {"level": 5, "key": "usniper",  "name": "U-Sniper",         "ship": 501,
     "cut": 0.22, "band": "Top 22%", "flair": 5,
     "color": "#bc8cff", "glow": "rgba(188,140,255,.38)"},
    # key stays "mercury" (opaque id, keeps existing peak_div records valid);
    # the division is shown as Crusader with the Crusader ship (406).
    {"level": 4, "key": "mercury",  "name": "Crusader",         "ship": 406,
     "cut": 0.40, "band": "Top 40%", "flair": 4,
     "color": "#58a6ff", "glow": "rgba(88,166,255,.34)"},
    {"level": 3, "key": "pulse",    "name": "Pulse-Fighter",    "ship": 301,
     "cut": 0.62, "band": "Top 62%", "flair": 3,
     "color": "#2dd4bf", "glow": "rgba(45,212,191,.30)"},
    {"level": 2, "key": "delta",    "name": "Delta-Fighter",    "ship": 201,
     "cut": 0.82, "band": "Top 82%", "flair": 2,
     "color": "#3fb950", "glow": "rgba(63,185,80,.26)"},
    {"level": 1, "key": "fly",      "name": "Fly",              "ship": 101,
     "cut": 1.01, "band": "Entry tier", "flair": 1,
     "color": "#7d858f", "glow": "rgba(125,133,143,.18)"},
]

RANK_BY_KEY = {r["key"]: r for r in RANKS}
TOP_LEVEL = max(r["level"] for r in RANKS)


def division_for(rank0, total):
    """rank0: 0-based position among ranked players (0 = best). total: how
    many ranked players there are. Returns a RANKS entry, or None."""
    if total <= 0:
        return None
    frac = rank0 / float(total)
    for r in RANKS:
        if frac < r["cut"]:
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
