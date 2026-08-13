# -*- coding: utf-8 -*-
"""Drives the clan invite link feature through Flask's test client.

Covers who may mint a link, what a link does when it is dead, and the rule
that matters most: a link may let somebody in, but it may never move
somebody who is already in a clan.
"""
import io
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'players.db')
if os.path.exists(DB):
    os.remove(DB)

import flask_app  # noqa: E402  (creates the schema on import)

NOW = time.strftime('%Y-%m-%d %H:%M:%S')

conn = sqlite3.connect(DB)
c = conn.cursor()
c.executemany("INSERT OR IGNORE INTO clans (tag, created_at) VALUES (?, ?)",
              [('COV', NOW), ('FLR', NOW)])
# name, google_sub, clan
people = [
    ('LEADERGUY', 'discord:leader', 'COV'),
    ('COGUY',     'discord:co',     'COV'),
    ('MODGUY',    'discord:mod',    'COV'),
    ('RECRUIT1',  'discord:r1',     None),
    ('RECRUIT2',  'discord:r2',     None),
    ('OTHERGUY',  'discord:o1',     'FLR'),
]
for name, sub, clan in people:
    c.execute("INSERT INTO players (name, elo, wins, losses, clan, google_sub, strict_mode) "
              "VALUES (?, 1200, 1, 1, ?, ?, 0)", (name, clan, sub))
c.executemany("INSERT INTO clan_admins (clan, google_sub, created_at, role) VALUES (?,?,?,?)",
              [('COV', 'discord:leader', NOW, 'leader'),
               ('COV', 'discord:co',     NOW, 'coleader'),
               ('COV', 'discord:mod',    NOW, 'moderator')])
conn.commit()
conn.close()

app = flask_app.app
app.config['TESTING'] = True
cl = app.test_client()

fails = []


def check(label, cond, detail=''):
    print(('  PASS  ' if cond else '  FAIL  ') + label
          + (' :: ' + detail if detail and not cond else ''))
    if not cond:
        fails.append(label)


def signin(sub):
    with cl.session_transaction() as s:
        if sub:
            s['google_sub'] = sub
        else:
            s.pop('google_sub', None)


def q(sql, args=()):
    cn = sqlite3.connect(DB)
    cur = cn.cursor()
    cur.execute(sql, args)
    row = cur.fetchone()
    cn.close()
    return row


print("\n=== only a leader or co-leader may mint ===")

signin('discord:mod')
r = cl.post('/clan/invite/link', json={'clan': 'COV'})
check('moderator is refused', r.status_code == 403, str(r.status_code))

signin('discord:o1')
r = cl.post('/clan/invite/link', json={'clan': 'COV'})
check('outsider is refused', r.status_code == 403, str(r.status_code))

signin(None)
r = cl.post('/clan/invite/link', json={'clan': 'COV'})
check('signed out is refused', r.status_code == 401, str(r.status_code))

signin('discord:co')
r = cl.post('/clan/invite/link', json={'clan': 'COV'})
check('co-leader may mint', r.status_code == 200, str(r.status_code))

signin('discord:leader')
r = cl.post('/clan/invite/link', json={'clan': 'COV'})
check('leader may mint', r.status_code == 200, str(r.status_code))
TOKEN = r.get_json()['token']
check('url is absolute and contains the token', '/clan/join/' + TOKEN in r.get_json()['url'],
      r.get_json()['url'])

print("\n=== minting again retires the old link ===")

n_live = q("SELECT COUNT(*) FROM clan_invite_links WHERE clan='COV' AND revoked_at IS NULL")[0]
check('exactly one live link after two mints', n_live == 1, str(n_live))
old = q("SELECT revoked_at FROM clan_invite_links WHERE token != ? AND clan='COV'", (TOKEN,))
check('the co-leader link was revoked', old is not None and old[0] is not None)

print("\n=== the join page ===")

signin(None)
r = cl.get('/clan/join/' + TOKEN)
check('valid link redirects a signed-out visitor', r.status_code == 302, str(r.status_code))
check('straight to Discord', '/auth/discord?next=' in r.headers.get('Location', ''),
      r.headers.get('Location', ''))

# Everything below wants the page itself, which after 5.65.1 is only shown
# to a signed-out visitor once they have been round Discord and come back.
r = cl.get('/clan/join/' + TOKEN + '?back=1')
body = r.get_data(as_text=True)
check('the page renders on the way back', r.status_code == 200, str(r.status_code))
check('offers Discord sign-in by hand', '/auth/discord?next=/clan/join/' + TOKEN in body)
check('names the clan', 'COV' in body)

r = cl.get('/clan/join/nosuchtoken')
check('unknown token is 410', r.status_code == 410, str(r.status_code))
check('says it is not valid', 'not valid' in r.get_data(as_text=True))

print("\n=== a link nobody may use ===")

cn = sqlite3.connect(DB)
cc = cn.cursor()
past = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - 86400))
cc.execute("INSERT INTO clan_invite_links (token, clan, created_by, created_at, expires_at, uses) "
           "VALUES ('EXPIRED1', 'COV', 'discord:leader', ?, ?, 0)", (past, past))
cc.execute("INSERT INTO clan_invite_links (token, clan, created_by, created_at, expires_at, "
           "revoked_at, uses) VALUES ('REVOKED1', 'COV', 'discord:leader', ?, ?, ?, 0)",
           (NOW, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400)), NOW))
cn.commit()
cn.close()

signin('discord:r1')
r = cl.get('/clan/join/EXPIRED1')
check('expired link is 410', r.status_code == 410, str(r.status_code))
check('expired says so', 'expired' in r.get_data(as_text=True).lower())
r = cl.post('/clan/join/EXPIRED1', json={})
check('expired cannot be accepted', r.status_code == 410, str(r.status_code))

r = cl.get('/clan/join/REVOKED1')
check('revoked link is 410', r.status_code == 410, str(r.status_code))
check('revoked says withdrawn', 'withdrawn' in r.get_data(as_text=True).lower())
r = cl.post('/clan/join/REVOKED1', json={})
check('revoked cannot be accepted', r.status_code == 410, str(r.status_code))
check('nobody joined by a dead link',
      q("SELECT clan FROM players WHERE name='RECRUIT1'")[0] is None)

print("\n=== joining ===")

signin(None)
r = cl.post('/clan/join/' + TOKEN, json={})
check('signed out cannot accept', r.status_code == 401, str(r.status_code))

signin('discord:nobody')
r = cl.get('/clan/join/' + TOKEN)
check('account with no name is told to claim one',
      'Claim yours' in r.get_data(as_text=True))
r = cl.post('/clan/join/' + TOKEN, json={})
check('account with no name cannot accept', r.status_code == 400, str(r.status_code))

signin('discord:r1')
r = cl.post('/clan/join/' + TOKEN, json={})
check('a free player joins', r.status_code == 200, str(r.status_code))
check('roster actually changed', q("SELECT clan FROM players WHERE name='RECRUIT1'")[0] == 'COV')
check('use was counted',
      q("SELECT uses FROM clan_invite_links WHERE token=?", (TOKEN,))[0] == 1)

signin('discord:r2')
r = cl.post('/clan/join/' + TOKEN, json={})
check('the same link works for a second person', r.status_code == 200, str(r.status_code))
check('second use counted',
      q("SELECT uses FROM clan_invite_links WHERE token=?", (TOKEN,))[0] == 2)

print("\n=== a link never moves anyone between clans ===")

signin('discord:o1')
r = cl.get('/clan/join/' + TOKEN)
check('member of another clan is told to leave first',
      'leave that clan' in r.get_data(as_text=True))
r = cl.post('/clan/join/' + TOKEN, json={})
check('and is refused', r.status_code == 400, str(r.status_code))
check('still in their old clan',
      q("SELECT clan FROM players WHERE name='OTHERGUY'")[0] == 'FLR')

signin('discord:r1')
r = cl.post('/clan/join/' + TOKEN, json={})
check('joining twice is refused', r.status_code == 400, str(r.status_code))
check('use was not counted twice',
      q("SELECT uses FROM clan_invite_links WHERE token=?", (TOKEN,))[0] == 2)

print("\n=== revoking ===")

signin('discord:mod')
r = cl.post('/clan/invite/revoke', json={'clan': 'COV'})
check('moderator cannot revoke', r.status_code == 403, str(r.status_code))

signin('discord:leader')
r = cl.post('/clan/invite/revoke', json={'clan': 'COV'})
check('leader revokes', r.status_code == 200, str(r.status_code))
r = cl.post('/clan/invite/revoke', json={'clan': 'COV'})
check('revoking twice says there was nothing to do', r.status_code == 400, str(r.status_code))

cn = sqlite3.connect(DB)
cn.execute("UPDATE players SET clan = NULL WHERE name = 'RECRUIT2'")
cn.commit()
cn.close()
signin('discord:r2')
r = cl.post('/clan/join/' + TOKEN, json={})
check('a revoked link stops working immediately', r.status_code == 410, str(r.status_code))

print("\n=== what the manage card is told ===")

signin('discord:leader')
d = cl.get('/clan/invite/link?clan=COV').get_json()
check('leader can manage', d['can_manage'] is True)
check('no live link after revoking', d['link'] is None)
signin('discord:mod')
d = cl.get('/clan/invite/link?clan=COV').get_json()
check('moderator is told they cannot manage', d['can_manage'] is False)
signin(None)
d = cl.get('/clan/invite/link?clan=COV').get_json()
check('signed out is told they cannot manage', d['can_manage'] is False)

print("\n=== sign-in return path cannot leave the site ===")

for bad in ['https://evil.example/x', '//evil.example/x', 'http://evil.example',
            'evil.example', '/\\evil.example', '/x\nSet-Cookie: a=b', '']:
    check('rejected: %r' % bad, flask_app.safe_next(bad) is None)
for good in ['/clan/join/abc', '/settings', '/clan/COV']:
    check('allowed: %r' % good, flask_app.safe_next(good) == good)

print("\n=== a pending invitation is settled by walking in ===")

cn = sqlite3.connect(DB)
cc = cn.cursor()
cc.execute("UPDATE players SET clan = NULL WHERE name = 'RECRUIT2'")
cc.execute("INSERT INTO clan_invites (clan, name, invited_by, created_at, status, direction) "
           "VALUES ('COV', 'RECRUIT2', 'discord:leader', ?, 'pending', 'invite')", (NOW,))
cc.execute("INSERT INTO clan_invite_links (token, clan, created_by, created_at, expires_at, uses) "
           "VALUES ('FRESH123', 'COV', 'discord:leader', ?, ?, 0)",
           (NOW, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400))))
cn.commit()
cn.close()

signin('discord:r2')
r = cl.post('/clan/join/FRESH123', json={})
check('joins through the new link', r.status_code == 200, str(r.status_code))
st = q("SELECT status FROM clan_invites WHERE name='RECRUIT2' AND clan='COV'")[0]
check('the old invitation is no longer pending', st == 'approved', st)

print("\n=== a signed-out visitor is sent straight to Discord ===")

cn = sqlite3.connect(DB)
cn.execute("INSERT INTO clan_invite_links (token, clan, created_by, created_at, expires_at, uses) "
           "VALUES ('LIVE9999', 'COV', 'discord:leader', ?, ?, 0)",
           (NOW, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400))))
cn.commit()
cn.close()

signin(None)
r = cl.get('/clan/join/LIVE9999')
loc = r.headers.get('Location', '')
check('signed out is redirected', r.status_code == 302, str(r.status_code))
check('sent to Discord', '/auth/discord?next=' in loc, loc)
check('return path is the invite', 'clan%2Fjoin%2FLIVE9999' in loc, loc)
check('return path carries the loop guard', 'back%3D1' in loc, loc)

# The guard: back again, still signed out. Must render, never redirect, or
# a browser refusing cookies would ping-pong to Discord forever.
r = cl.get('/clan/join/LIVE9999?back=1')
check('coming back signed out renders instead of looping',
      r.status_code == 200, str(r.status_code))
check('and says why', 'did not sign you in' in r.get_data(as_text=True))

# A dead link must not send anybody to Discord: signing in would achieve
# nothing and the site would have handed Discord a pointless round trip.
r = cl.get('/clan/join/EXPIRED1')
check('expired link does not redirect to Discord', r.status_code == 410, str(r.status_code))
r = cl.get('/clan/join/nosuchtoken')
check('unknown link does not redirect to Discord', r.status_code == 410, str(r.status_code))

signin('discord:free_agent')
cn = sqlite3.connect(DB)
cn.execute("INSERT INTO players (name, elo, wins, losses, clan, google_sub, strict_mode) "
           "VALUES ('FREEAGENT', 1200, 1, 1, NULL, 'discord:free_agent', 0)")
cn.commit()
cn.close()
r = cl.get('/clan/join/LIVE9999')
check('an already signed-in visitor is not redirected', r.status_code == 200, str(r.status_code))
check('and gets the accept prompt', 'onclick="accept()"' in r.get_data(as_text=True))

check('the guard survives safe_next', flask_app.safe_next('/clan/join/LIVE9999?back=1')
      == '/clan/join/LIVE9999?back=1')

print("\n=== other pages still render ===")
for path in ['/clans', '/changelog', '/']:
    r = cl.get(path)
    check('%s renders' % path, r.status_code == 200, str(r.status_code))

print("\n" + ("ALL CHECKS PASSED" if not fails else "FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
