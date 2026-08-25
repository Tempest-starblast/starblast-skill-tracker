"""Skill-rank ladder for the leaderboard.

Seven divisions, mapped to the seven iconic ships of the tree (one per tier).
A player's division comes from their percentile among ranked (non-provisional)
players on the canonical all-time board - so the badge means "top X%", and the
emblem IS that division's ship, drawn from the game-accurate silhouettes in
ship_shapes.py.
"""
import ship_shapes

# best -> worst. `cut` is the cumulative top-fraction ceiling for the band:
# a player at percentile-fraction f (0 = #1) is in the first band with f < cut.
RANKS = [
    {"tier": 7, "key": "odyssey",  "name": "Odyssey",          "ship": 701,
     "cut": 0.03, "band": "Top 3%", "color": "#ff7b53", "glow": "rgba(255,123,83,.45)"},
    {"tier": 6, "key": "advanced", "name": "Advanced-Fighter", "ship": 601,
     "cut": 0.10, "band": "Top 10%", "color": "#e3b341", "glow": "rgba(227,179,65,.40)"},
    {"tier": 5, "key": "usniper",  "name": "U-Sniper",         "ship": 501,
     "cut": 0.22, "band": "Top 22%", "color": "#bc8cff", "glow": "rgba(188,140,255,.38)"},
    {"tier": 4, "key": "mercury",  "name": "Mercury",          "ship": 402,
     "cut": 0.40, "band": "Top 40%", "color": "#58a6ff", "glow": "rgba(88,166,255,.36)"},
    {"tier": 3, "key": "pulse",    "name": "Pulse-Fighter",    "ship": 301,
     "cut": 0.62, "band": "Top 62%", "color": "#39c5cf", "glow": "rgba(57,197,207,.34)"},
    {"tier": 2, "key": "delta",    "name": "Delta-Fighter",    "ship": 201,
     "cut": 0.82, "band": "Top 82%", "color": "#56d364", "glow": "rgba(86,211,100,.32)"},
    {"tier": 1, "key": "fly",      "name": "Fly",              "ship": 101,
     "cut": 1.01, "band": "Entry tier", "color": "#8b949e", "glow": "rgba(139,148,158,.28)"},
]

RANK_BY_KEY = {r["key"]: r for r in RANKS}


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
