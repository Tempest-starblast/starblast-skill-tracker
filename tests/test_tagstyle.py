# -*- coding: utf-8 -*-
"""One tag, many stylings: attribution by clan tag, the leader's styling
list, the member's pick, and where the worn tag shows. Scratch database."""
import inspect
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="tagtest")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
# The board bundle is persisted to BASE_DIR/boardcache and honoured for five
# minutes by version - a suite run just before this one would otherwise
# serve ITS board here. Each suite gets its own cache directory.
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True

STY = "S" + chr(0x1105) + "F" + chr(0x336)               # SᄅF̶
ARROW = chr(0x219D)
DEFAULT = STY + " " + ARROW                                # SᄅF̶ ↝  (what niwu wrote)
BOLD = chr(0x1D412) + chr(0x1D7D0) + chr(0x1D405)          # 𝐒𝟐𝐅
L, A, B, C, D1, D2, E = ("sub:lead", "sub:bhu", "sub:kai", "sub:zed",
                         "sub:dup1", "sub:dup2", "sub:srw")

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
c = cn.cursor()
for t in ("players", "name_bindings", "clans", "clan_admins", "clan_tag_styles",
          "clan_invites", "clan_codes"):
    c.execute("DELETE FROM %s" % t)
rows = [
    # (name, game_name, sub, clan, wins, losses)
    ("NIWU", None, L, None, 0, 0),                # will create S2F, becomes its leader
    ("BHU", None, A, "S2F", 3, 1),                # tag-free account name
    (STY + " KAI", None, B, "S2F", 2, 2),         # account name carries the tag
    ("ZED", None, C, None, 5, 5),                 # not a member
    ("DUP", None, D1, "S2F", 1, 0),               # two members, one bare name
    ("S2F DUP", None, D2, "S2F", 1, 0),
    ("JACK", None, E, "SRW", 4, 0),               # member of the longer tag
    (STY + " FASTIK", None, None, "S2F", 6, 2),   # on the roster, no account (leader-added)
    ("SANDBOX", "GHOST", fa.SANDBOX_SUB, "S2F", 0, 0),
]
for name, game, sub, clan, w, l in rows:
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, game_name, google_sub, clan) "
              "VALUES (?, ?, 1200, ?, ?, ?, ?, ?)",
              (name, fa.normalize_name(name), w, l, game, sub, clan))
# the clans, made the way the site makes them (writes the first styling)
st, _ = fa.perform_clan_create(c, L, DEFAULT, trusted=True)
check("S2F created from its styled spelling", st, 200)
c.execute("UPDATE players SET clan = 'S2F' WHERE google_sub = ?", (L,))
st, _ = fa.perform_clan_create(c, E, "SRW", trusted=True)
check("SRW created", st, 200)
# The orphan row an outsider makes by typing the tag - inserted AFTER the
# clan exists, because creating a clan sweeps rows already carrying its tag
# onto the roster (that is the site's own rule, and correct).
c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan) "
          "VALUES ('S2F ZED', ?, 1200, 1, 0, NULL, NULL)", (fa.normalize_name("S2F ZED"),))
cn.commit()
fa._PLAY_CACHE["ts"] = 0.0
fa.tag_cache_reset()

c.execute("SELECT tag, display_tag FROM clans WHERE tag = 'S2F'")
check("the key is S2F and the default styling is what was written", tuple(c.fetchone()), ("S2F", DEFAULT))
check("one styling row written on create", [s for _i, s in fa.clan_styles(c, "S2F")], [DEFAULT])


def who(name, sys_id=5):
    return fa.account_for_ingame_name(c, name, sys_id)


print("\n--- the tag is evidence: any styling + a member's name -> the member ---")
check("plain S2F + tag-free member", who("S2F BHU"), "BHU")
check("the leader's styling + member", who(DEFAULT + " BHU"), "BHU")
check("a bold-letter styling nobody registered + member", who(BOLD + " BHU"), "BHU")
check("brackets", who("[S2F] BHU"), "BHU")
check("glued to the name", who(STY + "BHU"), "BHU")
check("member whose ACCOUNT name carries the tag, typed plain", who("S2F KAI"), STY + " KAI")
check("member whose account carries the tag, typed bold", who(BOLD + " KAI"), STY + " KAI")
check("tag at the end", who("BHU | S2F"), "BHU")
check("a leader-added member with no account, typed plain", who("S2F FASTIK"), STY + " FASTIK")
check("...and typed bold", who(BOLD + " FASTIK"), STY + " FASTIK")

print("\n--- and nothing else ---")
check("an outsider under the tag maps to nobody", who("S2F ZED"), None)
check("no tag: the clan rule stays out of it", who("BHU"), None)
check("two members with one bare name: neither", who("S2F DUP"), None)
check("the sandbox member never", who("S2F GHOST"), None)
check("the tag alone is nobody", who("S2F"), None)
check("longest tag first: SRW JACK is SRW's JACK, not SR's W JACK", who("SRW JACK"), "JACK")

print("\n--- a binding for this lobby and a play name both outrank it ---")
c.execute("INSERT INTO name_bindings (sub, in_game_name, sys_id, ship_id, region, bound_at) "
          "VALUES (?, 'S2F BHU', 7, 3, 'america', '2026-09-17 00:00:00')", (C,))
cn.commit()
check("bound lobby -> the bound account", who("S2F BHU", 7), "ZED")
check("other lobby -> the member", who("S2F BHU", 8), "BHU")
c.execute("UPDATE players SET game_name = 'S2F BHU' WHERE google_sub = ?", (C,))
cn.commit()
fa._PLAY_CACHE["ts"] = 0.0
check("a declared play name wins over the clan rule", who("S2F BHU", 8), "ZED")
c.execute("UPDATE players SET game_name = NULL WHERE google_sub = ?", (C,))
cn.commit()
fa._PLAY_CACHE["ts"] = 0.0

print("\n--- the leader's styling list ---")
app = fa.app.test_client()


def login(client, sub):
    with client.session_transaction() as s:
        s["google_sub"] = sub
        s.pop("preview", None)


def post(client, url, body):
    r = client.post(url, json=body)
    return r.status_code, r.get_json()


lead = fa.app.test_client()
login(lead, L)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": "[S2F]"})
check("leader adds a bracket styling", st, 200)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": BOLD})
check("leader adds a bold-letter styling", st, 200)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": "SZF"})
check("a styling that folds to another tag is refused", st, 400)
check("...and the message says why", "different tag" in (d or {}).get("message", ""), True)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": "[S2F]"})
check("a duplicate styling is refused", st, 400)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": ""})
check("an empty styling is refused", st, 400)
member = fa.app.test_client()
login(member, A)
st, d = post(member, "/clan/style", {"clan": "S2F", "action": "add", "shown": "(S2F)"})
check("an ordinary member cannot add one", st, 403)
fa.tag_cache_reset()
styles = fa.clan_styles(c, "S2F")
check("three stylings, the default first", [s for _i, s in styles], [DEFAULT, "[S2F]", BOLD])
for n in range(3):
    st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": "S2F" + "!" * (n + 1)})
check("the sixth styling goes in", st, 200)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "add", "shown": "S2F?"})
check("the seventh is refused", st, 400)
for n in range(3):
    sid = [i for i, s in fa.clan_styles(c, "S2F") if s == "S2F" + "!" * (n + 1)][0]
    post(lead, "/clan/style", {"clan": "S2F", "action": "remove", "id": sid})
fa.tag_cache_reset()
check("back to three", len(fa.clan_styles(c, "S2F")), 3)

print("\n--- the member's pick ---")
bracket = [i for i, s in fa.clan_styles(c, "S2F") if s == "[S2F]"][0]
bold_id = [i for i, s in fa.clan_styles(c, "S2F") if s == BOLD][0]
srw_id = fa.clan_styles(c, "SRW")[0][0]
st, d = post(member, "/account/tagstyle", {"id": srw_id})
check("another clan's styling is refused", st, 400)
st, d = post(member, "/account/tagstyle", {"id": bracket})
check("BHU wears [S2F]", st, 200)
fa.tag_cache_reset()
check("the worn map says so", fa.worn_tag_map(c).get("BHU"), "[S2F]")
check("player_tag for BHU", fa.player_tag(c, "BHU", "S2F"), "[S2F]")
check("player_tag for KAI is the clan default", fa.player_tag(c, STY + " KAI", "S2F"), DEFAULT)
outsider = fa.app.test_client()
login(outsider, C)
st, d = post(outsider, "/account/tagstyle", {"id": bracket})
check("not in a clan -> refused", st, 400)

print("\n--- where it shows ---")
r = app.get("/player/BHU")
check("profile 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("profile badge is the worn styling", ">[S2F]</a>" in h, True)
r = app.get("/player/" + (STY + " KAI"))
check("KAI's profile 200", r.status_code, 200)
check("KAI's badge is the clan default", (">" + DEFAULT + "</a>") in r.get_data(as_text=True), True)
r = app.get("/")
check("board 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("board row wears [S2F] for BHU", ">[S2F]</a>" in h, True)
_key = getattr(fa, "API_SECRET", "") or ""
if _key:
    r = app.get("/api/bot/top?n=50", headers={"X-API-Key": _key})
    check("bot top 200", r.status_code, 200)
    rows_js = (r.get_json() or {}).get("players") or []
    bhu = next((x for x in rows_js if x.get("name") == "BHU"), None)
    check("bot top carries the worn styling", (bhu or {}).get("clan_display"), "[S2F]")
else:
    print("  SKIP  bot top (no API secret on this machine)")
r = member.get("/account")
check("account page 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("account page offers the chooser", 'id="tagStyle"' in h, True)
check("...with [S2F] selected", ('value="%d" selected>[S2F]' % bracket) in h, True)
r = lead.get("/myclan")
check("myclan 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("myclan lists the stylings", h.count("styleAct('remove'"), 3)
check("myclan marks the default", ">default<" in h, True)

print("\n--- default and remove ---")
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "default", "id": bold_id})
check("make bold the default", st, 200)
c.execute("SELECT display_tag FROM clans WHERE tag = 'S2F'")
check("clans.display_tag follows", c.fetchone()[0], BOLD)
fa.tag_cache_reset()
check("KAI (no pick) now shows bold", fa.player_tag(c, STY + " KAI", "S2F"), BOLD)
check("BHU keeps the pick", fa.player_tag(c, "BHU", "S2F"), "[S2F]")
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "remove", "id": bracket})
check("remove the styling BHU wears", st, 200)
fa.tag_cache_reset()
c.execute("SELECT tag_style FROM players WHERE name = 'BHU'")
check("BHU's pick is cleared", c.fetchone()[0], None)
check("BHU shows the default again", fa.player_tag(c, "BHU", "S2F"), BOLD)
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "remove", "id": bold_id})
check("remove the default: allowed while another remains", st, 200)
c.execute("SELECT display_tag FROM clans WHERE tag = 'S2F'")
check("the remaining styling becomes the default", c.fetchone()[0], DEFAULT)
last = fa.clan_styles(c, "S2F")[0][0]
st, d = post(lead, "/clan/style", {"clan": "S2F", "action": "remove", "id": last})
check("the last styling cannot go", st, 400)
check("attribution still works with one styling", who(BOLD + " BHU", 9), "BHU")

print("\n--- the words ---")
src = inspect.getsource(fa)
check("late check-in message says the match counts anyway",
      "the match still counts for your account under" in src, True)
import info_text_en as en                                       # noqa: E402
body = dict(en.CARDS)["Clans"]
check("Info: a match under your clan's tag counts for you", "counts for you" in body, True)
r = app.get("/info")
check("info 200", r.status_code, 200)
r = app.get("/changelog")
check("changelog 200", r.status_code, 200)
check("changelog has the entry", "Tag stylings" in r.get_data(as_text=True), True)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
