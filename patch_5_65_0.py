# -*- coding: utf-8 -*-
"""5.65.0 - shareable clan invite links.

Run from ~/mysite.  Edits flask_app.py, templates/clans.html and i18n.py,
and writes templates/join.html (new).  Every anchor is checked by count
before anything is written, so a failed assert leaves the tree untouched.

The link is multi-use and expires after 7 days. One live link per clan:
minting a new one revokes the old, so a leaked link is replaced rather
than accumulating alongside its replacements.
"""

import os

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
cln = Patch('templates/clans.html')
i18 = Patch('i18n.py')

assert not os.path.exists('templates/join.html'), \
    "templates/join.html already exists - refusing to overwrite it"

# ------------------------------------------------------- flask_app.py (1)
# Version and changelog.

app.sub(
    'APP_VERSION = "5.64.0"',
    'APP_VERSION = "5.65.0"',
    "version bump")

app.sub(
    'CHANGELOG = [\n',
    'CHANGELOG = [\n'
    '    {"version": "5.65.0", "at": "2026-08-13T04:00:00Z", "changes": [\n'
    '        "Clan leaders and co-leaders can now create an invite link and '
    'post it wherever their clan talks. Anyone who opens it signs in with '
    'Discord and joins with one press - no need to be added by name first, '
    'and no need for the leader to know what you play as.",\n'
    '        "A link works for as many people as open it and stops working '
    'after seven days. Leaders can revoke it at any time, and creating a '
    'new one always retires the old one, so a link that has got out can be '
    'replaced immediately.",\n'
    '        "Joining through a link follows the same rules as every other '
    'way in: you keep your own name, and if you are already in a clan you '
    'have to leave it yourself first. Nobody is moved between clans without '
    'doing it themselves.",\n'
    '    ]},\n',
    "changelog entry")

# ------------------------------------------------------- flask_app.py (2)
# The table. One row per link; uses is a counter, not a limit.

CODES_TABLE = """    c.execute('''CREATE TABLE IF NOT EXISTS clan_codes (
                    code TEXT PRIMARY KEY,
                    clan TEXT NOT NULL,
                    created_at TEXT,
                    used_at TEXT,
                    used_by TEXT
                )''')
"""

app.sub(
    CODES_TABLE,
    CODES_TABLE +
    """    # A shareable join link, as opposed to the one-time codes above:
    # those hand over a whole clan, this one only lets people into it.
    # Multi-use on purpose - a leader posts one link where their clan
    # talks and anyone who opens it can join until it expires. expires_at
    # and revoked_at are plain '%Y-%m-%d %H:%M:%S' strings, which compare
    # correctly as text, so no date parsing is needed to test a link.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_invite_links (
                    token TEXT PRIMARY KEY,
                    clan TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    revoked_at TEXT,
                    uses INTEGER DEFAULT 0
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_invite_links_clan "
              "ON clan_invite_links(clan)")
""",
    "invite link table")

# ------------------------------------------------------- flask_app.py (3)
# Returning to where you were after signing in with Discord.

app.sub(
    """def current_user():
    \"\"\"The signed-in Google account id, or None if nobody is signed in.\"\"\"
    return session.get('google_sub')
""",
    """def current_user():
    \"\"\"The signed-in Google account id, or None if nobody is signed in.\"\"\"
    return session.get('google_sub')


def safe_next(raw):
    \"\"\"A path on this site to return to after signing in, or None.

    Only our own paths. A value with a scheme, or a second leading slash,
    is a link to somebody else's site, and sending a freshly signed-in
    player there is how an invite link would be turned into a way of
    harvesting them. Anything that is not plainly local is dropped rather
    than repaired.
    \"\"\"
    s = str(raw or '')
    if not s or len(s) > 200:
        return None
    if not s.startswith('/') or s.startswith('//'):
        return None
    if '\\\\' in s or any(ch < ' ' for ch in s):
        return None
    return s
""",
    "safe_next helper")

app.sub(
    """    state = secrets.token_urlsafe(24)
    session.permanent = True
    session['discord_state'] = state
""",
    """    state = secrets.token_urlsafe(24)
    session.permanent = True
    session['discord_state'] = state
    # Where to go once Discord sends them back. An invite link needs this:
    # without it the player signs in and lands on the front page, with no
    # sign of the clan they were trying to join.
    session['discord_next'] = safe_next(request.args.get('next'))
""",
    "remember next")

app.sub(
    """    remember_discord_user(sub_id, info.get('username') or '',
                          info.get('global_name') or info.get('username') or '')
    return redirect('/?signin=ok')
""",
    """    remember_discord_user(sub_id, info.get('username') or '',
                          info.get('global_name') or info.get('username') or '')
    back = safe_next(session.pop('discord_next', None))
    return redirect(back or '/?signin=ok')
""",
    "honour next")

# ------------------------------------------------------- flask_app.py (4)
# The routes themselves, in front of the notifier's endpoint.

ROUTES = '''INVITE_LINK_DAYS = 7


def invite_link_row(c, token):
    """One invite link by its token, or None."""
    c.execute("SELECT token, clan, created_at, expires_at, revoked_at, "
              "COALESCE(uses, 0) FROM clan_invite_links WHERE token = ?",
              (str(token or ''),))
    return c.fetchone()


def invite_link_state(row):
    """Whether a link may still be used: ok, missing, revoked or expired."""
    if not row:
        return 'missing'
    if row[4]:
        return 'revoked'
    if row[3] and row[3] <= time.strftime('%Y-%m-%d %H:%M:%S'):
        return 'expired'
    return 'ok'


INVITE_DEAD_MESSAGE = {
    'missing': "That invite link is not valid.",
    'revoked': "That invite link has been withdrawn by the clan.",
    'expired': "That invite link has expired. Ask the clan for a new one.",
}


def active_invite_link(c, tag):
    """The clan's live link, or None. Expired and revoked rows stay in the
    table - they are what tells someone holding an old link why it stopped
    working, rather than that it never existed."""
    c.execute("SELECT token, clan, created_at, expires_at, revoked_at, "
              "COALESCE(uses, 0) FROM clan_invite_links "
              "WHERE clan = ? AND revoked_at IS NULL AND expires_at > ? "
              "ORDER BY created_at DESC LIMIT 1",
              (tag, time.strftime('%Y-%m-%d %H:%M:%S')))
    return c.fetchone()


def invite_link_json(row):
    return {
        "token": row[0],
        "url": request.url_root.rstrip('/') + '/clan/join/' + row[0],
        "created_at": row[2],
        "expires_at": row[3],
        "uses": row[5],
    }


@app.route('/clan/invite/link')
def clan_invite_link_get():
    """The clan's current invite link, for the manage card."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"can_manage": False, "link": None}), 200
    conn = db()
    c = conn.cursor()
    tag = canonical_clan_tag(request.args.get('clan'))
    if not tag:
        tags = clan_admin_tags(c, sub_id)
        tag = tags[0] if tags else None
    if not tag or not may_manage(c, sub_id, tag):
        conn.close()
        return jsonify({"can_manage": False, "link": None}), 200
    row = active_invite_link(c, tag)
    out = invite_link_json(row) if row else None
    conn.close()
    return jsonify({"can_manage": True, "clan": tag, "link": out,
                    "days": INVITE_LINK_DAYS}), 200


@app.route('/clan/invite/link', methods=['POST'])
def clan_invite_link_new():
    """Mint a link, retiring whatever the clan had before.

    Leaders and co-leaders, the same people who may already invite by
    name. A moderator is there to remove people, not to recruit.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    tag = canonical_clan_tag((request.json or {}).get('clan'))
    conn = db()
    c = conn.cursor()
    if not tag or not may_manage(c, sub_id, tag):
        conn.close()
        return jsonify({"message": "Only a leader or co-leader can do that."}), 403
    now = time.time()
    stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
    ends = time.strftime('%Y-%m-%d %H:%M:%S',
                         time.localtime(now + INVITE_LINK_DAYS * 86400))
    # Retiring the old link is the point: two live links would mean
    # revoking the one that leaked still left the clan open.
    c.execute("UPDATE clan_invite_links SET revoked_at = ? "
              "WHERE clan = ? AND revoked_at IS NULL", (stamp, tag))
    token = secrets.token_urlsafe(12)
    c.execute("INSERT INTO clan_invite_links "
              "(token, clan, created_by, created_at, expires_at, uses) "
              "VALUES (?, ?, ?, ?, ?, 0)", (token, tag, sub_id, stamp, ends))
    conn.commit()
    row = invite_link_row(c, token)
    out = invite_link_json(row)
    conn.close()
    out["message"] = "Link created. Anyone who opens it can join %s." % tag
    return jsonify(out), 200


@app.route('/clan/invite/revoke', methods=['POST'])
def clan_invite_link_revoke():
    """Withdraw the clan's live link."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    tag = canonical_clan_tag((request.json or {}).get('clan'))
    conn = db()
    c = conn.cursor()
    if not tag or not may_manage(c, sub_id, tag):
        conn.close()
        return jsonify({"message": "Only a leader or co-leader can do that."}), 403
    c.execute("UPDATE clan_invite_links SET revoked_at = ? "
              "WHERE clan = ? AND revoked_at IS NULL",
              (time.strftime('%Y-%m-%d %H:%M:%S'), tag))
    changed = c.rowcount
    conn.commit()
    conn.close()
    if not changed:
        return jsonify({"message": "There was no live link to withdraw."}), 400
    return jsonify({"message": "Link withdrawn. It no longer works."}), 200


def invite_join_state(c, sub_id, clan):
    """Why this visitor can or cannot take the invite. Returns
    (state, name). The states are what join.html renders."""
    if not sub_id:
        return 'signed_out', None
    who = account_name_for(c, sub_id)
    if not who:
        return 'no_name', None
    c.execute("SELECT clan FROM players WHERE name = ?", (who,))
    row = c.fetchone()
    current = row[0] if row else None
    if current == clan:
        return 'already_in', who
    if current:
        return 'other_clan', who
    return 'ready', who


@app.route('/clan/join/<token>')
def clan_join_page(token):
    """The page an invite link opens."""
    conn = db()
    c = conn.cursor()
    row = invite_link_row(c, token)
    state = invite_link_state(row)
    clan = row[1] if row else ''
    display = clan_display(c, clan) if clan else ''
    sub_id = current_user()
    join_state, who = ('dead', None)
    if state == 'ok':
        join_state, who = invite_join_state(c, sub_id, clan)
    c.execute("SELECT COUNT(*) FROM players WHERE clan = ?", (clan,))
    size = c.fetchone()[0] if clan else 0
    c.execute("SELECT clan FROM players WHERE google_sub = ? AND clan IS NOT NULL "
              "AND clan != '' LIMIT 1", (sub_id or '',))
    mine = c.fetchone()
    conn.close()
    return render_template(
        'join.html', version=APP_VERSION, contact=CONTACT_HANDLE,
        page='clans', client_id=GOOGLE_CLIENT_ID, token=token,
        clan=clan, display=display or clan, members=size,
        link_state=state, join_state=join_state, who=who or '',
        your_clan=(mine[0] if mine else ''),
        dead_message=INVITE_DEAD_MESSAGE.get(state, '')), (200 if state == 'ok' else 410)


@app.route('/clan/join/<token>', methods=['POST'])
def clan_join_accept(token):
    """Take the invite. The same rules as every other way into a clan."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    conn = db()
    c = conn.cursor()
    row = invite_link_row(c, token)
    state = invite_link_state(row)
    if state != 'ok':
        conn.close()
        return jsonify({"message": INVITE_DEAD_MESSAGE.get(state, "That link is not valid.")}), 410
    clan = row[1]
    join_state, who = invite_join_state(c, sub_id, clan)
    if join_state == 'no_name':
        conn.close()
        return jsonify({"message": "Claim your player name first, on Manage your name - "
                                   "a clan is a list of names, so there has to be one "
                                   "to add."}), 400
    if join_state == 'already_in':
        conn.close()
        return jsonify({"message": "You are already in %s." % clan}), 400
    if join_state == 'other_clan':
        c.execute("SELECT clan FROM players WHERE name = ?", (who,))
        cur = c.fetchone()
        conn.close()
        return jsonify({"message": "You are in %s. Leave it first, then open this "
                                   "link again." % (cur[0] if cur else 'another clan')}), 400
    c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (clan, who))
    c.execute("UPDATE clan_invite_links SET uses = COALESCE(uses, 0) + 1 "
              "WHERE token = ?", (row[0],))
    # Any invitation or application already open for this player is settled
    # by their walking in, or the clan's page would keep offering a decision
    # about somebody who is already a member.
    c.execute("UPDATE clan_invites SET status = 'approved' "
              "WHERE clan = ? AND name = ? AND status = 'pending'", (clan, who))
    conn.commit()
    conn.close()
    return jsonify({"message": "You joined %s." % clan, "clan": clan}), 200


'''

app.sub(
    "@app.route('/api/notify_state')\n",
    ROUTES + "@app.route('/api/notify_state')\n",
    "invite link routes")

# ---------------------------------------------------- templates/clans.html

DELETE_BLOCK = """  <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line)">
    <p class="desc">Deleting releases every member."""

cln.sub(
    DELETE_BLOCK,
    """  <div id="inviteBox" style="display:none;margin-top:16px;padding-top:14px;
       border-top:1px solid var(--line)">
    <h3 class="sub">{{ t('Invite link') }}</h3>
    <p class="desc">One link anyone can open to join. Post it where your clan talks
       &mdash; whoever follows it signs in and joins themselves, so you do not need to
       know what they play as. It stops working after seven days.</p>
    <div id="inviteNone" style="display:none">
      <button class="primary" onclick="makeInvite()">{{ t('Create link') }}</button>
    </div>
    <div id="inviteHas" style="display:none">
      <div class="row">
        <input type="text" id="inviteUrl" readonly onclick="this.select()">
        <button onclick="copyInvite()">{{ t('Copy') }}</button>
      </div>
      <p class="cmeta" id="inviteMeta"></p>
      <button class="ghost" style="margin-top:10px" onclick="revokeInvite()">{{ t('Revoke') }}</button>
    </div>
    <p class="msg" id="inviteMsg"></p>
  </div>

""" + DELETE_BLOCK,
    "invite card")

cln.sub(
    """      document.querySelector('#manageCard h2').textContent = 'Your clan \\u2014 ' + myClan.tag;
      drawRoster(myClan);
""",
    """      document.querySelector('#manageCard h2').textContent = 'Your clan \\u2014 ' + myClan.tag;
      drawRoster(myClan);
      loadInvite();
""",
    "load invite with roster")

cln.sub(
    "async function claimClan(){\n",
    """function showInvite(d){
  const box = document.getElementById('inviteBox');
  // A moderator sees the roster but not this: the server would refuse them
  // anyway, and a button that always fails is worse than no button.
  box.style.display = d.can_manage ? 'block' : 'none';
  if (!d.can_manage) return;
  const has = !!d.link;
  document.getElementById('inviteHas').style.display = has ? 'block' : 'none';
  document.getElementById('inviteNone').style.display = has ? 'none' : 'block';
  if (has){
    document.getElementById('inviteUrl').value = d.link.url;
    const used = d.link.uses === 1 ? '1 person has joined'
                                   : d.link.uses + ' people have joined';
    document.getElementById('inviteMeta').textContent =
      'Expires ' + d.link.expires_at.slice(0, 10) + ' \\u2014 ' + used + ' with this link.';
  }
}
async function loadInvite(){
  if (!myClan) return;
  try{
    const d = await (await fetch('/clan/invite/link?clan='
                                 + encodeURIComponent(myClan.tag))).json();
    showInvite(d);
  }catch(e){}
}
async function makeInvite(){
  if (!myClan) return;
  try{
    const [r, d] = await post('/clan/invite/link', {clan: myClan.tag});
    say('inviteMsg', r.ok, d.message || 'Could not create a link.');
    if (r.ok) loadInvite();
  }catch(e){ say('inviteMsg', false, 'Server connection error.'); }
}
async function revokeInvite(){
  if (!myClan) return;
  try{
    const [r, d] = await post('/clan/invite/revoke', {clan: myClan.tag});
    say('inviteMsg', r.ok, d.message);
    if (r.ok) loadInvite();
  }catch(e){ say('inviteMsg', false, 'Server connection error.'); }
}
function copyInvite(){
  const el = document.getElementById('inviteUrl');
  el.select();
  // execCommand is deprecated but clipboard.writeText needs a secure
  // context and permission, and this button has to work for everyone.
  let ok = false;
  try{ ok = document.execCommand('copy'); }catch(e){ ok = false; }
  if (!ok && navigator.clipboard){
    navigator.clipboard.writeText(el.value).then(function(){
      say('inviteMsg', true, 'Link copied.');
    }).catch(function(){ say('inviteMsg', false, 'Select the link and copy it.'); });
    return;
  }
  say('inviteMsg', ok, ok ? 'Link copied.' : 'Select the link and copy it.');
}
async function claimClan(){
""",
    "invite js")

# ------------------------------------------------------------------ i18n
# KEYS and every language list must stay the same length - i18n.py asserts
# it at import, and a mismatch would take the site down on load.

i18.sub(
    '    "Search all", "Page",\n'
    ']\n',
    '    "Search all", "Page",\n'
    '    "Invite link", "Create link", "Copy", "Revoke", "Accept invite",\n'
    ']\n',
    "new keys")

for lang, tail, extra in [
    ("es", '"Buscar en todo","Página"],',
     '"Enlace de invitación","Crear enlace","Copiar","Revocar","Aceptar invitación"'),
    ("fr", '"Tout chercher","Page"],',
     '"Lien d\'invitation","Créer le lien","Copier","Révoquer","Accepter l\'invitation"'),
    ("de", '"Alle durchsuchen","Seite"],',
     '"Einladungslink","Link erstellen","Kopieren","Widerrufen","Einladung annehmen"'),
    ("it", '"Cerca ovunque","Pagina"],',
     '"Link d\'invito","Crea link","Copia","Revoca","Accetta l\'invito"'),
    ("ru", '"Искать везде","Страница"],',
     '"Ссылка-приглашение","Создать ссылку","Копировать","Отозвать","Принять приглашение"'),
    ("vi", '"Tìm tất cả","Trang"],',
     '"Liên kết mời","Tạo liên kết","Sao chép","Thu hồi","Chấp nhận lời mời"'),
    ("zh", '"搜索全部","页"],',
     '"邀请链接","创建链接","复制","撤销","接受邀请"'),
]:
    i18.sub(tail, tail[:-2] + "," + extra + "],", "%s values" % lang)

# ------------------------------------------------------------- join.html

JOIN_HTML = '''{% extends "base.html" %}
{% block title %}Join {{ display }} - Starblast Skill Tracker{% endblock %}
{% block css %}
.joinbox{text-align:center;padding:8px 0 4px}
.jointag{font-size:30px;font-weight:800;color:var(--text);letter-spacing:.5px}
.joinsub{font-size:13px;color:var(--muted);margin-top:6px}
.joinbtn{margin-top:18px}
.dbtn2{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:8px;
  background:#5865F2;color:#fff;font-weight:700;font-size:14px;text-decoration:none}
{% endblock %}
{% block body %}
<h1 class="ptitle">Clan invitation</h1>

{% if link_state != 'ok' %}
<div class="card">
  <p class="desc">{{ dead_message }}</p>
  <p class="desc"><a style="color:var(--green);font-weight:600" href="/clans">See every clan &rarr;</a></p>
</div>
{% else %}
<div class="card">
  <div class="joinbox">
    <div class="jointag">{{ display }}</div>
    <div class="joinsub">{{ members }} member{{ '' if members == 1 else 's' }}</div>
  </div>

  {% if join_state == 'signed_out' %}
  <p class="desc" style="text-align:center">Sign in to accept. Only your Discord
     account id and handle are read &mdash; no email, and nothing that could be used
     to contact you.</p>
  <p style="text-align:center" class="joinbtn">
    <a class="dbtn2" href="/auth/discord?next=/clan/join/{{ token }}">Sign in with Discord</a>
  </p>

  {% elif join_state == 'no_name' %}
  <p class="desc">You are signed in, but no leaderboard name is yours yet. A clan is a
     list of names, so there has to be one to add. Claim yours on
     <a style="color:var(--green);font-weight:600" href="/settings">Manage your name</a>
     and then open this link again.</p>

  {% elif join_state == 'already_in' %}
  <p class="desc">You are already in {{ display }}, as <b>{{ who }}</b>. Nothing to do.</p>
  <p class="desc"><a style="color:var(--green);font-weight:600"
     href="/clan/{{ clan }}">Open the clan page &rarr;</a></p>

  {% elif join_state == 'other_clan' %}
  <p class="desc"><b>{{ who }}</b> is in {{ your_clan }}. You have to leave that clan
     yourself before joining another &mdash; nobody is moved between clans by a link.
     Leave from
     <a style="color:var(--green);font-weight:600" href="/clan/{{ your_clan }}">{{ your_clan }}</a>,
     then open this link again.</p>

  {% else %}
  <p class="desc" style="text-align:center">Joining as <b>{{ who }}</b>.</p>
  <p style="text-align:center" class="joinbtn">
    <button class="primary" onclick="accept()">{{ t('Accept invite') }}</button>
  </p>
  {% endif %}

  <p class="msg" id="joinMsg"></p>
</div>
{% endif %}

<p class="foot">Questions? Ask {{ contact }} on Discord.</p>

<script>
async function accept(){
  const m = document.getElementById('joinMsg');
  try{
    const r = await fetch('/clan/join/{{ token }}', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    m.className = 'msg ' + (r.ok ? 'ok' : 'err');
    m.textContent = d.message;
    if (r.ok) setTimeout(function(){ location.href = '/clan/{{ clan }}'; }, 1200);
  }catch(e){
    m.className = 'msg err';
    m.textContent = 'Server connection error.';
  }
}
</script>
{% endblock %}
'''

# ---------------------------------------------------------- post-mortems

app.check('APP_VERSION = "5.65.0"', 1, "new version")
app.check('"version": "5.65.0"', 1, "changelog entry")
app.check("clan_invite_links", 8, "table used throughout")
app.check("def safe_next", 1, "one safe_next")
app.check("@app.route('/clan/join/<token>')", 1, "join page route")
app.check("@app.route('/clan/join/<token>', methods=['POST'])", 1, "join accept route")
app.check("if not tag or not may_manage(c, sub_id, tag):", 3, "every route is gated")
cln.check("loadInvite()", 4, "invite wired in: defined, plus load, make and revoke")
cln.check("t('Invite link')", 1, "heading translated")

for p in (app, cln, i18):
    assert p.text != p.original, "%s: nothing changed" % p.path
    save(p.path, p.text)
    print("patched %s (%+d chars)" % (p.path, len(p.text) - len(p.original)))

save('templates/join.html', JOIN_HTML)
print("wrote templates/join.html (%d chars)" % len(JOIN_HTML))

print("\n5.65.0 (clan invite links) written.")
print("Now: python3 -m py_compile flask_app.py i18n.py")
