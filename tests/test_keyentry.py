# -*- coding: utf-8 -*-
"""Tester keys as people actually paste them (9.77.0).

On 24 Sep every key tried crashed the page: a non-ASCII character reached
hmac.compare_digest. For days before that, keys read as wrong when they
carried a stray space, and access keys handed a signed-out tester the same
empty form back with no word of why. This drives the door the way a tester
does."""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="keyentry")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.PREVIEW_KEY = "master-key-for-tests-only-0123456789"
N = fa.normalize_name
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM preview_keys")
cn.execute("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)",
           ("Key Tester", N("Key Tester"), 1450, 30, 25, "sub:kt"))
c = cn.cursor()
_, SAND = fa.preview_key_make(c, "sand", 1, "sub:owner", "sandbox")
_, ACC = fa.preview_key_make(c, "acc", 1, "sub:owner", "access")
cn.commit()
cn.close()

print("\n--- clean_key keeps the key and drops the passengers ---")
k = SAND
check("a plain key is itself", fa.clean_key(k), k)
check("trailing newline and spaces", fa.clean_key("  " + k + " \n"), k)
check("zero-width space and word joiner", fa.clean_key(k[:6] + "​" + k[6:] + "⁠"), k)
check("no-break space", fa.clean_key(" " + k), k)
check("a dash a phone put in", fa.clean_key(k.replace("-", "–", 1)), k)
check("letter case is kept", fa.clean_key("sbGEM-AbC"), "sbGEM-AbC")
check("same_secret never raises on non-ASCII", fa.same_secret("sbgém-ü", "sbgem-u"), False)
check("same_secret is equality", fa.same_secret("abc", "abc"), True)

print("\n--- a sandbox key, pasted badly, still lets them in ---")
for label, pasted in (("with a newline", SAND + "\n"),
                      ("with a zero-width space", "​" + SAND),
                      ("with an en dash", SAND.replace("-", "–", 1)),
                      ("with a no-break space", SAND + " ")):
    t = fa.app.test_client()
    r = t.post("/dev/preview", data={"key": pasted})
    check("  %s -> in" % label, r.status_code, 302)

print("\n--- the master key survives the same treatment ---")
t = fa.app.test_client()
check("master key with a trailing space",
      t.post("/dev/preview", data={"key": fa.PREVIEW_KEY + " "}).status_code, 302)

print("\n--- the crash of 24 Sep is gone ---")
t = fa.app.test_client()
r = t.post("/dev/preview", data={"key": "sbgem-éèê not a key"})
check("non-ASCII junk is a 404, not a 500", r.status_code, 404)
check("  and the page says the key did not work", b'id="pvBad"' in r.data, True)
check("  with the form to try again", b'name="key"' in r.data, True)
r = t.post("/dev/preview", data={"key": ""})
check("an empty key is a 404 without the 'did not work' note", (r.status_code, b'id="pvBad"' in r.data), (404, False))

print("\n--- an access key while signed out: told, remembered, let in on return ---")
t = fa.app.test_client()
r = t.post("/dev/preview", data={"key": ACC + " "})
check("it asks them to sign in", (r.status_code, b'id="pvSignin"' in r.data), (200, True))
check("  with a way back here after Discord", b"/auth/discord?next=/dev/preview" in r.data, True)
with t.session_transaction() as s:
    check("  the key is remembered for this browser", bool(s.get("preview_pending")), True)
    check("  but they are not in yet", s.get("preview"), None)
r = t.get("/dev/preview")
check("coming back still signed out shows the same note", b'id="pvSignin"' in r.data, True)
with t.session_transaction() as s:
    s["google_sub"] = "sub:kt"                     # they signed in
r = t.get("/dev/preview")
check("back from signing in, they are let straight in", r.status_code, 302)
with t.session_transaction() as s:
    check("  as themselves, with the preview on",
          (s.get("google_sub"), s.get("preview"), s.get("preview_kind"), s.get("preview_pending")),
          ("sub:kt", True, "access", None))
q = sqlite3.connect(fa.DB_PATH)
check("  and the key's use was counted",
      q.execute("SELECT uses FROM preview_keys WHERE kind='access'").fetchone()[0], 1)
q.close()

print("\n--- a remembered key that expires meanwhile is dropped ---")
t = fa.app.test_client()
t.post("/dev/preview", data={"key": ACC})
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("UPDATE preview_keys SET expires_at = '2000-01-01 00:00:00' WHERE kind='access'")
cn.commit()
cn.close()
fa._PREVIEW_OK_CACHE.clear()
r = t.get("/dev/preview")
check("no 'your key is good' for a dead key", b'id="pvSignin"' in r.data, False)
with t.session_transaction() as s:
    check("  and it is forgotten", s.get("preview_pending"), None)

print("\n--- the box shows what was pasted and is not a password field ---")
h = fa.app.test_client().get("/dev/preview").get_data(as_text=True)
check("type is text, so no saved password is filled in", 'name="key" type="text"' in h, True)
check("no spellcheck or autocorrect on it", 'spellcheck="false"' in h and 'autocorrect="off"' in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
