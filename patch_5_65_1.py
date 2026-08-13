# -*- coding: utf-8 -*-
"""5.65.1 - an invite link goes straight to Discord.

Run from ~/mysite. Edits flask_app.py and templates/join.html.

Opening a link while signed out used to show a page with a Discord button
on it. Now it redirects to Discord immediately and the player comes back
to the accept prompt, so the link is one click rather than two.

The redirect carries back=1 on the return path. If they come back still
signed out - cookies refused, or they pressed Cancel on Discord - that
marker is what stops the page bouncing them to Discord again forever.
"""


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
jn = Patch('templates/join.html')

# ------------------------------------------------------------ flask_app.py

app.sub(
    'APP_VERSION = "5.65.0"',
    'APP_VERSION = "5.65.1"',
    "version bump")

app.sub(
    'CHANGELOG = [\n',
    'CHANGELOG = [\n'
    '    {"version": "5.65.1", "at": "2026-08-13T04:30:00Z", "changes": [\n'
    '        "An invite link now takes you straight to the Discord sign-in '
    'instead of showing a page with a sign-in button on it. Once you are '
    'back, the clan and the Accept button are waiting. If you are already '
    'signed in the link opens on the Accept button directly, as before.",\n'
    '    ]},\n',
    "changelog entry")

app.sub(
    """    sub_id = current_user()
    join_state, who = ('dead', None)
    if state == 'ok':
        join_state, who = invite_join_state(c, sub_id, clan)
""",
    """    sub_id = current_user()
    join_state, who = ('dead', None)
    if state == 'ok':
        join_state, who = invite_join_state(c, sub_id, clan)
    # Straight to Discord rather than a page whose only purpose is a button
    # to Discord. back=1 is on the return path so that coming back still
    # signed out - cookies refused, or Cancel pressed on Discord's screen -
    # lands on the page with something to read instead of being bounced
    # round the same loop again.
    returned = bool(request.args.get('back'))
    if state == 'ok' and join_state == 'signed_out' and not returned:
        conn.close()
        return redirect('/auth/discord?next='
                        + quote('/clan/join/' + token + '?back=1', safe=''))
""",
    "redirect to discord")

app.sub(
    """        link_state=state, join_state=join_state, who=who or '',
        your_clan=(mine[0] if mine else ''),
""",
    """        link_state=state, join_state=join_state, who=who or '',
        your_clan=(mine[0] if mine else ''), returned=returned,
""",
    "pass returned to template")

# -------------------------------------------------------------- join.html

jn.sub(
    """  {% if join_state == 'signed_out' %}
  <p class="desc" style="text-align:center">Sign in to accept. Only your Discord
     account id and handle are read &mdash; no email, and nothing that could be used
     to contact you.</p>
""",
    """  {% if join_state == 'signed_out' %}
  {% if returned %}
  <p class="desc" style="text-align:center">That did not sign you in. If you pressed
     Cancel, try again. If you have cookies turned off for this site, sign-in cannot
     work until they are allowed.</p>
  {% endif %}
  <p class="desc" style="text-align:center">Sign in to accept. Only your Discord
     account id and handle are read &mdash; no email, and nothing that could be used
     to contact you.</p>
""",
    "explain a failed return")

jn.sub(
    '<a class="dbtn2" href="/auth/discord?next=/clan/join/{{ token }}">Sign in with Discord</a>',
    '<a class="dbtn2" href="/auth/discord?next=/clan/join/{{ token }}%3Fback%3D1">Sign in with Discord</a>',
    "manual button keeps the guard")

# ---------------------------------------------------------- post-mortems

app.check('APP_VERSION = "5.65.1"', 1, "new version")
app.check("returned = bool(request.args.get('back'))", 1, "guard computed once")
app.check("returned=returned", 1, "guard reaches the template")
app.check("'/auth/discord?next='", 1, "one redirect to discord")
jn.check("{% if returned %}", 1, "failed-return message")

for p in (app, jn):
    assert p.text != p.original, "%s: nothing changed" % p.path
    save(p.path, p.text)
    print("patched %s (%+d chars)" % (p.path, len(p.text) - len(p.original)))

print("\n5.65.1 (invite link goes straight to Discord) written.")
print("Now: python3 -m py_compile flask_app.py i18n.py")
