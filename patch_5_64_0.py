"""5.63.0 - paginate the leaderboard, 50 players a page.

Run from ~/mysite.  Edits flask_app.py, templates/index.html and i18n.py.
Every anchor is checked by count before anything is written, so a failed
assert leaves all three files untouched.
"""

PER = 50

# ---------------------------------------------------------------- helpers

def load(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def save(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


class Patch(object):
    def __init__(self, path):
        self.path = path
        self.text = load(path)
        self.original = self.text

    def sub(self, old, new, label, count=1):
        found = self.text.count(old)
        assert found == count, ("%s: anchor %r found %d, want %d"
                                % (self.path, label, found, count))
        self.text = self.text.replace(old, new, count)

    def check(self, needle, want, label):
        got = self.text.count(needle)
        assert got == want, ("%s: post-check %r is %d, want %d"
                             % (self.path, label, got, want))


app = Patch('flask_app.py')
idx = Patch('templates/index.html')
i18 = Patch('i18n.py')

# ------------------------------------------------------- flask_app.py (1)
# quote() builds the redirect that resolves a region link to a page.

app.sub(
    "import unicodedata\n",
    "import unicodedata\nfrom urllib.parse import quote\n",
    "urllib import")

app.sub(
    'APP_VERSION = "5.62.1"',
    'APP_VERSION = "5.64.0"',
    "version bump")

# 5.64.0 is the tracker change, already live on the droplet since
# 2026-08-13 00:54 UTC. It is recorded here because the changelog and
# APP_VERSION live on the site whatever machine the change was made on.
app.sub(
    'CHANGELOG = [\n',
    'CHANGELOG = [\n'
    '    {"version": "5.64.0", "at": "2026-08-13T00:54:00Z", "changes": [\n'
    '        "The tracker now reports two coverage figures instead of one. '
    'The old number counted every lobby that closed, including ones that '
    'were never old enough or busy enough to be worth attaching to - so it '
    'could never reach 100% however well the tracker did its job.",\n'
    '        "The new Watchable figure counts only the matches the tracker '
    'was allowed to watch, which is the number that actually says whether '
    'it is keeping up. The old figure is still printed beside it.",\n'
    '        "Fixed: starting a worker stopped the tracker\'s main loop for '
    'twelve seconds, and during that pause it noticed nothing - not a match '
    'ending, not another lobby waiting for a worker. It happened twelve '
    'times in two hours. Workers are still started twelve seconds apart, '
    'but the loop now keeps watching while they start.",\n'
    '    ]},\n'
    '    {"version": "5.63.0", "at": "2026-08-12T23:00:00Z", "changes": [\n'
    '        "The leaderboard is now shown 50 players at a time instead of '
    'every player at once. The page was 1.2 MB of one table and took several '
    'seconds to arrive; it is now about a fortieth of that.",\n'
    '        "A place on the board is still the place on the whole board - '
    'the player ranked 412th is #412 on page 9, not #12.",\n'
    '        "The search box still filters as you type, but now only across '
    'the page you are on. Search all players searches every player on the '
    'board and pages through what it finds.",\n'
    '        "The region link on a player\'s row still opens that region\'s '
    'board at that player, whichever page they turn out to be on.",\n'
    '    ]},\n',
    "changelog entry")

app.sub(
    'PERIOD_SQL = {"day": "-1 day", "week": "-7 days", "month": "-30 days"}\n',
    'PERIOD_SQL = {"day": "-1 day", "week": "-7 days", "month": "-30 days"}\n'
    '\n'
    '# How many rows of the leaderboard are sent at once. Every player on one\n'
    '# page was 1.2 MB of HTML for 2,600 rows, and nobody scrolls that far -\n'
    '# they search. Ranking is unaffected: the board is still sorted whole\n'
    '# and then sliced, so a page boundary is only ever a display cut.\n'
    'PER_PAGE = %d\n' % PER,
    "PER_PAGE constant")

# ------------------------------------------------------- flask_app.py (2)
# Read the paging arguments alongside the existing ones.

# bot_top_route() has this same two-line check, so the anchor carries the
# comment above it, which only the leaderboard has.
_REGION_CHECK = (
    "    # North Americans - and the selector says which you are looking at.\n"
    "    if region not in REGION_KEYS and region != ALL_REGIONS:\n"
    "        region = ALL_REGIONS\n")

app.sub(
    _REGION_CHECK,
    _REGION_CHECK +
    "    # Which slice to show, what to search the whole board for, and which\n"
    "    # player to resolve to a page. `pnum`, not `page` - `page` is already\n"
    "    # the template's name for which nav item is lit.\n"
    "    try:\n"
    "        pnum = int(request.args.get('page', 1))\n"
    "    except (TypeError, ValueError):\n"
    "        pnum = 1\n"
    "    q = (request.args.get('q') or '').strip()\n"
    "    find = (request.args.get('find') or '').strip()\n",
    "paging args")

# ------------------------------------------------------- flask_app.py (3)
# Rank is decided once, on the sorted whole board, and travels with the row.
# Without this a searched or paged row would renumber itself from 1.

app.sub(
    "    leaderboard_data = []\n"
    "    for name, elo, wins, losses, clan, protected in rows:\n",
    "    leaderboard_data = []\n"
    "    for rank, (name, elo, wins, losses, clan, protected) in enumerate(\n"
    "            rows, 1):\n",
    "enumerate the sorted board")

app.sub(
    '            "name": name, "display": display_name(name, clan),\n',
    '            "rank": rank,\n'
    '            "name": name, "display": display_name(name, clan),\n',
    "carry rank onto the row")

# ------------------------------------------------------- flask_app.py (4)
# Resolve `find` to a page, then search, then slice. The redirect keeps the
# row id in the URL fragment so the existing tr:target highlight still fires.

app.sub(
    "    conn = db()\n"
    "    c = conn.cursor()\n"
    "    # Only trust a recent push. A stale row would claim a match is being\n"
    "    # watched long after the tracker stopped, which is worse than saying\n"
    "    # nothing at all.\n"
    "    conn.close()\n",
    "    conn = db()\n"
    "    c = conn.cursor()\n"
    "    # Only trust a recent push. A stale row would claim a match is being\n"
    "    # watched long after the tracker stopped, which is worse than saying\n"
    "    # nothing at all.\n"
    "    conn.close()\n"
    "\n"
    "    # A region link names a player, not a page - which page they sit on\n"
    "    # is a property of the board being opened, so only this route can\n"
    "    # know it. Redirecting (rather than rendering) keeps #p-<name> in the\n"
    "    # address bar, which is what the :target highlight matches on.\n"
    "    if find:\n"
    "        fkey = normalize_name(find)\n"
    "        for p in leaderboard_data:\n"
    "            if normalize_name(p['name']) == fkey:\n"
    "                return redirect('/?period=%s&region=%s&page=%d#p-%s' % (\n"
    "                    period, region, (p['rank'] - 1) // PER_PAGE + 1,\n"
    "                    quote(p['name'], safe='')))\n"
    "        # Not ranked on this board at all - show page one rather than\n"
    "        # a dead end.\n"
    "\n"
    "    # `total` stays the size of the whole board: it is the count the page\n"
    "    # reports, and a search must not appear to shrink the leaderboard.\n"
    "    total_ranked = len(leaderboard_data)\n"
    "    if q:\n"
    "        qkey = normalize_name(q)\n"
    "        leaderboard_data = [p for p in leaderboard_data\n"
    "                            if qkey in p['search']]\n"
    "    found = len(leaderboard_data)\n"
    "    pages = max(1, (found + PER_PAGE - 1) // PER_PAGE)\n"
    "    # Clamped, not 404'd: ?page=900 is a stale link, not an error.\n"
    "    pnum = min(max(pnum, 1), pages)\n"
    "    start = (pnum - 1) * PER_PAGE\n"
    "    leaderboard_data = leaderboard_data[start:start + PER_PAGE]\n",
    "find/search/slice")

app.sub(
    "                           version=APP_VERSION, page='leaderboard',\n"
    "                           total=len(leaderboard_data))\n",
    "                           version=APP_VERSION, page='leaderboard',\n"
    "                           pnum=pnum, pages=pages, q=q, found=found,\n"
    "                           total=total_ranked)\n",
    "render args")

# ---------------------------------------------------- templates/index.html

idx.sub(
    "tbody tr:target td:first-child{box-shadow:inset 3px 0 0 var(--green)}\n",
    "tbody tr:target td:first-child{box-shadow:inset 3px 0 0 var(--green)}\n"
    ".pager{display:flex;gap:8px;align-items:center;justify-content:center;\n"
    "  flex-wrap:wrap;margin:18px 0 4px}\n"
    ".pager .pill{min-width:0}\n"
    ".pager .pill.off{opacity:.35;pointer-events:none}\n"
    ".pinfo{font-size:13px;color:var(--dim);padding:0 4px;white-space:nowrap}\n"
    "a.ghost{display:inline-flex;align-items:center;padding:0 14px;\n"
    "  border-radius:7px;font-size:13px;font-weight:600;text-decoration:none;\n"
    "  background:transparent;border:1px solid #3a3a3a;color:var(--muted)}\n"
    "a.ghost:hover{background:#2a2a2a;color:#fff}\n",
    "pager css")

# One URL builder for every link that has to survive paging, so a filter
# can never be dropped by one link and kept by another.
idx.sub(
    '{% block body %}\n',
    '{% block body %}\n'
    '{% macro board(p=1, per=none, reg=none, term=none) -%}\n'
    '/?period={{ per if per is not none else period }}'
    '&amp;region={{ reg if reg is not none else region }}'
    '{% if p and p > 1 %}&amp;page={{ p }}{% endif %}'
    '{% set qq = term if term is not none else q %}'
    '{% if qq %}&amp;q={{ qq|urlencode }}{% endif %}\n'
    '{%- endmacro %}\n',
    "board() macro")

idx.sub(
    '<p class="psub">{{ total }} player{{ \'\' if total == 1 else \'s\' }} '
    'ranked here, best first.</p>\n',
    '<p class="psub">{{ total }} player{{ \'\' if total == 1 else \'s\' }} '
    'ranked here, best first.{% if pages > 1 %} '
    '{{ t(\'Page\') }} {{ pnum }} / {{ pages }}.{% endif %}</p>\n',
    "subtitle")

idx.sub(
    '       href="/?period={{ period }}&amp;region={{ key }}">{{ t(label) }}</a>\n',
    '       href="{{ board(1, reg=key) }}">{{ t(label) }}</a>\n',
    "region pills keep the search")

idx.sub(
    '           href="/?period={{ key }}&amp;region={{ region }}">\n',
    '           href="{{ board(1, per=key) }}">\n',
    "period menu keeps the search")

# Instant filtering stays; it just cannot see past the rows it was sent, so
# the box also submits, and that search is done over the whole board.
idx.sub(
    '  <div class="row">\n'
    '    <input type="text" id="q" placeholder="{{ t(\'Player\') }}..." autocomplete="off" oninput="filter()"\n'
    '           onkeydown="if(event.key===\'Enter\'){event.preventDefault();filter();}">\n'
    '    <button class="ghost" onclick="document.getElementById(\'q\').value=\'\';filter()">{{ t(\'Clear\') }}</button>\n'
    '  </div>\n'
    '  <p class="msg" id="count"></p>\n',
    '  <form class="row" method="get" action="/">\n'
    '    <input type="hidden" name="period" value="{{ period }}">\n'
    '    <input type="hidden" name="region" value="{{ region }}">\n'
    '    <input type="text" id="q" name="q" value="{{ q }}"\n'
    '           placeholder="{{ t(\'Player\') }}..." autocomplete="off" oninput="filter()">\n'
    '    <button type="submit" class="ghost">{{ t(\'Search all\') }}</button>\n'
    '    <a class="ghost" href="{{ board(1, term=\'\') }}">{{ t(\'Clear\') }}</a>\n'
    '  </form>\n'
    '  <p class="msg" id="count"></p>\n'
    '  {% if q %}<p class="msg">{{ found }} player{{ \'\' if found == 1 else \'s\' }}'
    ' on the whole board match &quot;{{ q }}&quot;.</p>{% endif %}\n',
    "search form")

idx.sub(
    '  <td class="rank">{{ loop.index }}</td>\n',
    '  <td class="rank">{{ p.rank }}</td>\n',
    "rank is the board rank")

idx.sub(
    '    href="/?period={{ period }}&amp;region={{ p.region }}#p-{{ p.name|urlencode }}"\n',
    '    href="/?period={{ period }}&amp;region={{ p.region }}'
    '&amp;find={{ p.name|urlencode }}"\n',
    "region link resolves to a page")

idx.sub(
    '<tr><td colspan="{{ 6 if region == \'all\' else 5 }}" class="empty">\n'
    '  {% if gain %}Nobody has played a tracked match in this window yet.\n'
    '  {% else %}Nobody is on the leaderboard yet.{% endif %}\n'
    '</td></tr>\n',
    '<tr><td colspan="{{ 6 if region == \'all\' else 5 }}" class="empty">\n'
    '  {% if q %}No player on this board matches &quot;{{ q }}&quot;.\n'
    '  {% elif gain %}Nobody has played a tracked match in this window yet.\n'
    '  {% else %}Nobody is on the leaderboard yet.{% endif %}\n'
    '</td></tr>\n',
    "empty state covers a search")

idx.sub(
    '</table>\n'
    '</div>\n',
    '</table>\n'
    '</div>\n'
    '\n'
    '{% if pages > 1 %}\n'
    '<nav class="pager" aria-label="Leaderboard pages">\n'
    '  <a class="pill {% if pnum == 1 %}off{% endif %}"\n'
    '     href="{{ board(1) }}" aria-label="First page">&laquo;</a>\n'
    '  <a class="pill {% if pnum == 1 %}off{% endif %}"\n'
    '     href="{{ board(pnum - 1) }}" rel="prev" aria-label="Previous page">&lsaquo;</a>\n'
    '  <span class="pinfo">{{ t(\'Page\') }} {{ pnum }} / {{ pages }}</span>\n'
    '  <a class="pill {% if pnum == pages %}off{% endif %}"\n'
    '     href="{{ board(pnum + 1) }}" rel="next" aria-label="Next page">&rsaquo;</a>\n'
    '  <a class="pill {% if pnum == pages %}off{% endif %}"\n'
    '     href="{{ board(pages) }}" aria-label="Last page">&raquo;</a>\n'
    '</nav>\n'
    '{% endif %}\n',
    "pager")

idx.sub(
    "  document.getElementById('none').style.display = shown ? 'none' : '';\n"
    "  document.getElementById('count').textContent = q ? (shown + ' of ' + rows.length + ' players') : '';\n",
    "  document.getElementById('none').style.display = shown ? 'none' : '';\n"
    "  // Says 'on this page' because that is all this can see. Searching the\n"
    "  // rest of the board is the submit button, which goes to the server.\n"
    "  document.getElementById('count').textContent =\n"
    "    q ? (shown + ' of ' + rows.length + ' on this page') : '';\n",
    "filter counts say what they mean")

# ------------------------------------------------------------------ i18n
# KEYS and every language list must stay the same length - i18n.py asserts
# it at import, and a mismatch would take the site down on load.

i18.sub(
    '    "Redeem", "Your request", "Rank", "Language", "Approve", "Win rate",\n'
    ']\n',
    '    "Redeem", "Your request", "Rank", "Language", "Approve", "Win rate",\n'
    '    "Search all", "Page",\n'
    ']\n',
    "new keys")

for lang, tail, extra in [
    ("es", '"Aprobar","Tasa de victorias"],', '"Buscar en todo","Página"'),
    ("fr", '"Approuver","Taux de victoire"],', '"Tout chercher","Page"'),
    ("de", '"Genehmigen","Siegquote"],', '"Alle durchsuchen","Seite"'),
    ("it", '"Approva","Tasso di vittorie"],', '"Cerca ovunque","Pagina"'),
    ("ru", '"Одобрить","Процент побед"],', '"Искать везде","Страница"'),
    ("vi", '"Duyệt","Tỷ lệ thắng"],', '"Tìm tất cả","Trang"'),
    ("zh", '"批准","胜率"],', '"搜索全部","页"'),
]:
    i18.sub(tail, tail[:-2] + "," + extra + "],", "%s values" % lang)

# ---------------------------------------------------------- post-mortems

app.check("PER_PAGE", 6, "PER_PAGE uses")
app.check('APP_VERSION = "5.64.0"', 1, "new version")
app.check('"version": "5.64.0"', 1, "tracker changelog entry")
app.check('"version": "5.63.0"', 1, "pagination changelog entry")
app.check("5.62.1", 1, "old version survives in changelog only")
app.check("total=total_ranked)", 1, "total is the whole board")
app.check("loop.index", 0, "no loop.index left in flask_app")
idx.check("{{ p.rank }}", 1, "rank cell")
idx.check("loop.index", 0, "no loop.index left in the table")
idx.check("#p-{{ p.name|urlencode }}", 0, "no raw anchor links left")
idx.check("{{ board(", 7, "every paging link uses the macro")

for p in (app, idx, i18):
    assert p.text != p.original, "%s: nothing changed" % p.path
    save(p.path, p.text)
    print("patched %s (%+d chars)" % (p.path, len(p.text) - len(p.original)))

print("\n5.63.0 (pagination) + 5.64.0 (tracker changelog) written.")
print("Now: python3 -m py_compile flask_app.py i18n.py")
