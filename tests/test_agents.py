# -*- coding: utf-8 -*-
"""Free agents, the treasury tile, the shop's tier colours and the home
card's gem panel. Scratch database; the owner sees it all via preview."""
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
TMP = tempfile.mkdtemp(prefix="agents")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402
import ranks                                                    # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
L, A, B, V = "sub:lead", "sub:agent", "sub:other", "sub:visitor"

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
for t in ("players", "clans", "clan_admins", "clan_tag_styles", "clan_invites", "free_agents",
          "gem_ledger", "match_players", "name_bindings"):
    c.execute("DELETE FROM %s" % t)


def add_player(name, sub=None, clan=None, w=0, l=0, gems=0):
    c.execute("INSERT INTO players (name, norm_name, elo, wins, losses, google_sub, clan, gems) "
              "VALUES (?, ?, 1300, ?, ?, ?, ?, ?)", (name, fa.normalize_name(name), w, l, sub, clan, gems))


add_player("LEADER", L)
add_player("ACE", A, None, 12, 3)
add_player("OTHER", B, None, 2, 2)
st, _ = fa.perform_clan_create(c, L, "S2F", trusted=True)
check("S2F created", st, 200)
c.execute("UPDATE players SET clan = 'S2F' WHERE google_sub = ?", (L,))
c.execute("UPDATE clans SET gems = 500 WHERE tag = 'S2F'")
cn.commit()
fa.tag_cache_reset()


def client(sub, preview=True):
    cl = fa.app.test_client()
    with cl.session_transaction() as s:
        if sub:
            s["google_sub"] = sub
        if preview:
            s["preview"] = True
    return cl


def post(cl, url, body):
    r = cl.post(url, json=body)
    return r.status_code, r.get_json()


print("\n--- gated: nobody outside the preview sees it ---")
plain = client(A, preview=False)
check("/agents is 404 without the preview", plain.get("/agents").status_code, 404)
check("/agents/list is 404 without the preview", plain.post("/agents/list", json={}).status_code, 404)
check("/agents/hire is 404 without the preview", plain.post("/agents/hire", json={}).status_code, 404)
visitor = client(None)
check("/agents renders for a preview visitor", visitor.get("/agents").status_code, 200)

print("\n--- listing yourself ---")
ace = client(A)
st, d = post(ace, "/agents/list", {"price": 250, "note": "Fly Odyssey, EU evenings"})
check("ACE lists at 250", (st, d["ok"]), (200, True))
st, d = post(ace, "/agents/list", {"price": -5})
check("a negative price is refused", st, 400)
st, d = post(ace, "/agents/list", {"price": fa.GEM_BONUS_MAX + 1})
check("a price over the cap is refused", st, 400)
st, d = post(ace, "/agents/list", {"price": 300, "note": "x"})
check("relisting updates the price", (st, c.execute("SELECT price FROM free_agents WHERE norm_name='ACE'").fetchone()[0]), (200, 300))
check("one listing per player", c.execute("SELECT COUNT(*) FROM free_agents").fetchone()[0], 1)
lead = client(L)
st, d = post(lead, "/agents/list", {"price": 10})
check("a clan member cannot list", st, 400)
check("...and is told why", "leave it first" in d["message"], True)
st, d = post(visitor, "/agents/list", {"price": 10})
check("signed out cannot list", st, 401)

print("\n--- the page ---")
h = ace.get("/agents").get_data(as_text=True)
check("ACE sees their own listing", "Listed at 300 gems" in h, True)
check("...and the update/unlist buttons", ("Take me off" in h) and (">Update<" in h), True)
HIREBTN = '<button type="button" class="btn" data-act="hire"'
check("no hire button for yourself", HIREBTN in h, False)
h = lead.get("/agents").get_data(as_text=True)
check("the leader sees ACE for hire", 'data-name="ACE"' in h, True)
check("...with the price", "Hire for 300" in h, True)
check("...and the treasury", "S2F treasury <b>500</b>" in h, True)
check("the leader cannot list (in a clan)", "A free agent is somebody without a clan" in h, True)
h = client(B).get("/agents").get_data(as_text=True)
check("an ordinary player sees the list without a hire button", ('data-name="ACE"' in h) and (HIREBTN not in h), True)

print("\n--- hiring ---")
other = client(B)
st, d = post(other, "/agents/hire", {"name": "ACE", "clan": "S2F"})
check("a non-officer cannot hire", st, 403)
st, d = post(lead, "/agents/hire", {"name": "NOBODY", "clan": "S2F"})
check("not on the list -> 404", st, 404)
st, d = post(lead, "/agents/hire", {"name": "ACE", "clan": "ZZZ"})
check("no such clan -> 404", st, 404)
c.execute("UPDATE clans SET gems = 100 WHERE tag = 'S2F'")
cn.commit()
st, d = post(lead, "/agents/hire", {"name": "ACE", "clan": "S2F"})
check("treasury short -> refused with both numbers", (st, "300" in d["message"] and "100" in d["message"]), (400, True))
check("...nothing moved", c.execute("SELECT clan FROM players WHERE norm_name='ACE'").fetchone()[0], None)
check("...listing still there", c.execute("SELECT COUNT(*) FROM free_agents").fetchone()[0], 1)
c.execute("UPDATE clans SET gems = 500 WHERE tag = 'S2F'")
cn.commit()
# ACE tops a three-player board, so building it pays every division award;
# that is the board's business - the hire itself must add exactly the price.
before = c.execute("SELECT COALESCE(gems,0) FROM players WHERE norm_name='ACE'").fetchone()[0]
st, d = post(lead, "/agents/hire", {"name": "ACE", "clan": "S2F"})
check("hired", (st, d["ok"]), (200, True))
check("ACE is in S2F", c.execute("SELECT clan FROM players WHERE norm_name='ACE'").fetchone()[0], "S2F")
check("treasury paid 300", c.execute("SELECT gems FROM clans WHERE tag='S2F'").fetchone()[0], 200)
# Since 9.45.0 a term of a month or more is paid across it: the first week
# on the day, the rest held and released weekly while the contract runs.
_first, _weeks, _per = fa.escrow_plan(300, fa.AGENT_CONTRACT_DEFAULT)
check("ACE received the first week, not the whole fee",
      c.execute("SELECT gems FROM players WHERE norm_name='ACE'").fetchone()[0] - before, _first)
check("the rest is held against the contract",
      [(r["total"], r["paid"], r["weeks"]) for r in fa.escrow_rows(c, nn="ACE")],
      [(300, _first, _weeks)])
check("ledger: the clan paid it all, the player has the first week",
      tuple(c.execute("SELECT COUNT(*), SUM(amount) FROM gem_ledger WHERE reason='hire'").fetchone()),
      (2, _first - 300))
check("listing gone", c.execute("SELECT COUNT(*) FROM free_agents").fetchone()[0], 0)
st, d = post(lead, "/agents/hire", {"name": "ACE", "clan": "S2F"})
check("a second click finds nothing to hire", st, 404)

print("\n--- a free hire, and a tagged name comes off at the join ---")
add_player("S2F NEWBIE", B if False else "sub:newbie", None, 1, 0)
cn.commit()
newbie = client("sub:newbie")
st, d = post(newbie, "/agents/list", {"price": 0})
check("listed for nothing", (st, "for nothing" in d["message"]), (200, True))
st, d = post(lead, "/agents/hire", {"name": "S2F NEWBIE", "clan": "S2F"})
check("hired for free", (st, d["ok"]), (200, True))
check("the tag came off the account name on joining", c.execute("SELECT name, clan FROM players WHERE google_sub='sub:newbie'").fetchone(), ("NEWBIE", "S2F"))
check("no ledger rows for a free hire", c.execute("SELECT COUNT(*) FROM gem_ledger WHERE reason='hire'").fetchone()[0], 2)

print("\n--- a listing whose player joined elsewhere is not offered ---")
add_player("GONE", "sub:gone", None, 3, 0)
cn.commit()
post(client("sub:gone"), "/agents/list", {"price": 50})
c.execute("UPDATE players SET clan = 'S2F' WHERE norm_name = 'GONE'")
cn.commit()
check("not in the list", 'data-name="GONE"' in lead.get("/agents").get_data(as_text=True), False)
st, d = post(lead, "/agents/hire", {"name": "GONE", "clan": "S2F"})
check("hiring them says so and clears the row", (st, c.execute("SELECT COUNT(*) FROM free_agents WHERE norm_name='GONE'").fetchone()[0]), (400, 0))

print("\n--- unlist, sandbox, rename ---")
add_player("SOLO", "sub:solo", None, 1, 1)
cn.commit()
solo = client("sub:solo")
post(solo, "/agents/list", {"price": 5})
st, d = post(solo, "/agents/unlist", {})
check("unlisted", (st, c.execute("SELECT COUNT(*) FROM free_agents WHERE norm_name='SOLO'").fetchone()[0]), (200, 0))
post(solo, "/agents/list", {"price": 5})
fa.rekey_identity(c, "SOLO", "SOLO2")
cn.commit()
check("a rename carries the listing", c.execute("SELECT norm_name FROM free_agents").fetchone()[0], "SOLO2")
c.execute("DELETE FROM free_agents")
add_player("SANDY", fa.SANDBOX_SUB, None, 0, 0)
c.execute("INSERT INTO free_agents (norm_name, name, price, listed_at) VALUES ('SANDY', 'SANDY', 1, '2026-09-18')")
cn.commit()
fa._wipe_sandbox(c)
cn.commit()
check("the sandbox wipe removes its listing", c.execute("SELECT COUNT(*) FROM free_agents").fetchone()[0], 0)

print("\n--- the links ---")
h = ace.get("/social").get_data(as_text=True)
check("social links a clan member to Free agents", 'href="/agents"' in h, True)
h = client(B).get("/social").get_data(as_text=True)
check("social offers a clan-less player 'Be a free agent'", "Be a free agent" in h, True)
h = client(B, preview=False).get("/social").get_data(as_text=True)
check("...not outside the preview", "/agents" in h, False)
h = lead.get("/myclan").get_data(as_text=True)
check("Your clan links an officer to hiring", "hire a free agent" in h, True)
h = ace.get("/clans").get_data(as_text=True)
check("the Clans band offers Free agents", 'class="phcta ghost" href="/agents"' in h, True)

print("\n--- the clan page's treasury ---")
r = lead.get("/clan/S2F")
check("clan page 200", r.status_code, 200)
h = r.get_data(as_text=True)
check("gold treasury in the header band", ('<span>Treasury</span><b class="gold">200</b>' in h), True)
h = client(None, preview=False).get("/clan/S2F").get_data(as_text=True)
check("no tile, no trace, outside the preview", ("Treasury" in h) or ("b.gold" in h), False)

print("\n--- the shop wears tier colours ---")
by_level = {r["level"]: r["color"] for r in ranks.RANKS}
cat = {i["code"]: i for i in fa.ship_catalog()}
check("tier 1 hull is Fly's colour", cat[101]["color"], by_level[1])
check("the Advanced-Fighter is its rank's colour", cat[601]["color"], by_level[6])
check("the Marauder (a tier-6 hull) is Marauder's colour", cat[603]["color"], by_level[7])
other6 = [i for i in cat.values() if i["tier"] == 6 and i["code"] not in (601, 603)]
check("any other tier-6 hull is the tier's colour (Advanced-Fighter's)", {i["color"] for i in other6}, {by_level[6]})
check("tier 7's colour is Shadow's", cat[703]["tier_color"], by_level[8])
check("Shadow X-3 is Shadow's colour", cat[702]["color"], by_level[8])
check("the Odyssey keeps the mythic red", cat[701]["color"], fa.MYTHIC_COLOR)
h = ace.get("/shop").get_data(as_text=True)
check("shop 200 and tier headings coloured", 'style="color:%s">Tier 1' % by_level[1] in h, True)
check("a tier-6 hull drawn in its colour", by_level[6] in h, True)

print("\n--- the home card ---")
h = ace.get("/").get_data(as_text=True)
check("gem panel is an inset rounded panel", "align-self:start" in h and "border-radius:12px" in h and "margin:18px 18px 18px 0" in h, True)
check("narrow layout collapses with minmax(0,1fr)", "grid-template-columns:minmax(0,1fr)} }" in h, True)
for p in ("/", "/clans", "/clan/S2F", "/shop", "/achievements", "/agents", "/social", "/myclan", "/account"):
    check("%s 200" % p, ace.get(p).status_code, 200)

print("\n%d passed, %d failed" % (ok, fail))
cn.close()
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
