# -*- coding: utf-8 -*-
"""Loads the real leaderboard page through Flask's test client against a
synthetic board of 2,700 players, and checks what the browser would get."""
import io
import os
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'players.db')
if os.path.exists(DB):
    os.remove(DB)

import flask_app  # noqa: E402  (creates the schema on import)

PER = flask_app.PER_PAGE
N = 2700

# A board wide enough to page, with the awkward names this project actually
# has: leading spaces, symbol letters, CJK, and a shared prefix so search
# has to discriminate.
conn = sqlite3.connect(DB)
c = conn.cursor()
rows = []
for i in range(N):
    if i == 0:
        name = 'SEMNOME'
    elif i == 411:
        name = 'SEMNOX'            # rank 412 -> page 9
    elif i == 1903:
        name = 'SEMNO_PLAYER'      # rank 1904 -> page 39
    elif i % 7 == 3:
        name = '  ₣ⱠⱤ⇝PLAYER%04d' % i
    elif i % 11 == 5:
        name = '玩家%04d' % i
    else:
        name = 'PLAYER%04d' % i
    # elo descends with i so rank == i+1 exactly, which makes every
    # assertion below a statement about a known number.
    rows.append((name, 20000 - i, N - i, i, 'FLR' if i % 7 == 3 else None, 0))
c.executemany(
    "INSERT INTO players (name, elo, wins, losses, clan, strict_mode) "
    "VALUES (?,?,?,?,?,?)", rows)
conn.commit()
conn.close()

app = flask_app.app
app.config['TESTING'] = True
cl = app.test_client()

fails = []


def check(label, cond, detail=''):
    print(('  PASS  ' if cond else '  FAIL  ') + label + (' :: ' + detail if detail and not cond else ''))
    if not cond:
        fails.append(label)


def ranks(html):
    return [int(m) for m in re.findall(r'<td class="rank">(\d+)</td>', html)]


print('\n=== page 1 ===')
r = cl.get('/')
h = r.get_data(as_text=True)
check('200', r.status_code == 200, str(r.status_code))
check('exactly %d rows' % PER, len(ranks(h)) == PER, str(len(ranks(h))))
check('ranks are 1..%d' % PER, ranks(h) == list(range(1, PER + 1)), str(ranks(h)[:3]))
check('says 2700 ranked', '2700 player' in h)
check('page 1 / 54 shown', 'Page 1 / 54' in h or '1 / 54' in h)
check('page is under 120 KB', len(h) < 120000, '%d bytes' % len(h))
print('        page weight: %d bytes' % len(h))

print('\n=== page 2 keeps board ranks ===')
h2 = cl.get('/?page=2').get_data(as_text=True)
check('ranks are 51..100', ranks(h2) == list(range(PER + 1, 2 * PER + 1)), str(ranks(h2)[:3]))

print('\n=== last page and clamping ===')
hl = cl.get('/?page=54').get_data(as_text=True)
check('last page ends at 2700', ranks(hl)[-1] == 2700, str(ranks(hl)[-1:]))
hc = cl.get('/?page=999')
check('?page=999 clamps, no error', hc.status_code == 200, str(hc.status_code))
check('clamps to the last page', ranks(hc.get_data(as_text=True))[-1] == 2700)
hz = cl.get('/?page=0')
check('?page=0 clamps to 1', ranks(hz.get_data(as_text=True))[0] == 1)
hb = cl.get('/?page=abc')
check('?page=abc does not 500', hb.status_code == 200, str(hb.status_code))

print('\n=== search reaches the whole board ===')
hs = cl.get('/?q=SEMNO').get_data(as_text=True)
sr = ranks(hs)
check('finds all three SEMNO*', sr == [1, 412, 1904], str(sr))
check('true board ranks, not 1,2,3', 412 in sr and 1904 in sr)
check('reports the match count', '3 player' in hs)
check('still says 2700 ranked', '2700 player' in hs)
hn = cl.get('/?q=NOTAPLAYERATALL').get_data(as_text=True)
check('empty search says so', 'No player on this board matches' in hn)
check('empty search does not crash', len(ranks(hn)) == 0)

print('\n=== find= resolves a player to their page ===')
rf = cl.get('/?period=all&region=all&find=SEMNOX')
check('302 redirect', rf.status_code == 302, str(rf.status_code))
loc = rf.headers.get('Location', '')
print('        -> %s' % loc)
check('lands on page 9', 'page=9' in loc, loc)
check('keeps the #p- fragment', '#p-SEMNOX' in loc, loc)
hf = cl.get(loc.split('#')[0]).get_data(as_text=True)
check('rank 412 is on that page', 412 in ranks(hf))
check('row id is present for :target', 'id="p-SEMNOX"' in hf)

rmiss = cl.get('/?find=NOBODYHERE')
check('unknown find falls back to page 1', rmiss.status_code == 200, str(rmiss.status_code))

print('\n=== filters survive paging ===')
hq = cl.get('/?q=SEMNO&page=1').get_data(as_text=True)
check('q is kept in pager links', 'q=SEMNO' in hq)
hr = cl.get('/?region=america&page=2')
check('region board pages too', hr.status_code == 200, str(hr.status_code))

print('\n=== unicode names survive the round trip ===')
hu = cl.get('/?q=玩家').get_data(as_text=True)
check('CJK search works', len(ranks(hu)) > 0, str(len(ranks(hu))))
hcl = cl.get('/?q=FLR').get_data(as_text=True)
check('clan tag search works', len(ranks(hcl)) > 0, str(len(ranks(hcl))))

print('\n=== the bot API is untouched ===')
rb = cl.get('/api/bot/top?period=all&region=all')
check('/api/bot/top still answers', rb.status_code in (200, 401, 403), str(rb.status_code))
if rb.status_code == 200:
    data = rb.get_json()
    n = len(data.get('players', data) if isinstance(data, dict) else data)
    check('bot/top NOT limited to 50', n != PER, 'returned %d' % n)
    print('        bot/top returned %d entries' % n)

print('\n=== other pages still render ===')
# /info is left out: it 500s on an empty test DB on unpatched code too,
# because max_age_seconds has never been pushed by a tracker here. Verified
# against the pristine file before excluding it.
for p in ['/clans', '/changelog', '/play', '/reports']:
    rr = cl.get(p)
    check('%s renders' % p, rr.status_code == 200, str(rr.status_code))

print('\n' + ('ALL CHECKS PASSED' if not fails else 'FAILED: ' + ', '.join(fails)))
sys.exit(1 if fails else 0)
