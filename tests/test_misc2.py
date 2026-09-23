# -*- coding: utf-8 -*-
"""9.36.0: free-agent contracts, replays by player, Merge a name under Names."""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="misc2")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "boardcache")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.OWNER_SUBS = set(fa.OWNER_SUBS) | {"sub:owner"}

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def q(sql, *args):
    cn = sqlite3.connect(fa.DB_PATH)
    r = cn.execute(sql, args).fetchall()
    cn.close()
    return r


def w(sql, *args):
    cn = sqlite3.connect(fa.DB_PATH)
    cn.execute(sql, args)
    cn.commit()
    cn.close()


OWN, ACE, BOB = fa.normalize_name("Owner One"), fa.normalize_name("Ace Pilot"), fa.normalize_name("Bob")
w("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub, clan) VALUES (?,?,?,?,?,?,?)", "Owner One", OWN, 1700, 12, 3, "sub:owner", "TST")
w("INSERT INTO players(name, norm_name, elo, wins, losses, google_sub) VALUES (?,?,?,?,?,?)", "Ace Pilot", ACE, 1600, 8, 2, "sub:ace")
w("INSERT INTO players(name, norm_name, elo, wins, losses) VALUES (?,?,?,?,?)", "Bob", BOB, 1400, 2, 2)
w("INSERT INTO clans(tag, created_by, created_at) VALUES (?,?,?)", "TST", "sub:owner", "2026-09-01 00:00:00")
w("INSERT INTO clan_admins(google_sub, clan, role) VALUES (?,?,?)", "sub:owner", "TST", "leader")
cn = sqlite3.connect(fa.DB_PATH)
fa.gem_grant(cn.cursor(), "clan", "TST", 10000, "backfill", "v1")
cn.commit()
cn.close()

owner = fa.app.test_client()
with owner.session_transaction() as s:
    s["google_sub"] = "sub:owner"
    s["preview"] = True
ace = fa.app.test_client()
with ace.session_transaction() as s:
    s["google_sub"] = "sub:ace"
    s["preview"] = True

print("\n--- contracts ---")
r = ace.post("/agents/list", json={"price": 500, "note": "hi", "days": 14}).get_json()
check("listing names the term", (r["ok"], r.get("days"), "2 weeks contract" in r["message"]), (True, 14, True))
r = ace.post("/agents/list", json={"price": 500, "note": "hi", "days": 180}).get_json()
check("six months is a term", (r["ok"], r.get("days"), "6 months" in r["message"]), (True, 180, True))
check("stored on the listing", q("SELECT days FROM free_agents WHERE norm_name=?", ACE), [(180,)])
r = ace.post("/agents/list", json={"price": 500, "note": "hi", "days": 99}).get_json()
check("an unoffered term snaps to the default", r.get("days"), fa.AGENT_CONTRACT_DEFAULT)
ace.post("/agents/list", json={"price": 500, "note": "hi", "days": 14})
h = ace.get("/agents").get_data(as_text=True)
check("page: the select and my term", ('id="agDays"' in h) and ('value="14" selected' in h) and ("2 weeks contract" in h) and (">1 year</option>" in h), True)
h = owner.get("/agents").get_data(as_text=True)
check("page: tile shows the term, the button says it", ("<b>2 weeks</b> contract" in h) and ("&middot; 2 weeks</button>" in h), True)
r = owner.post("/agents/hire", json={"name": "Ace Pilot", "clan": "TST"}).get_json()
check("hire: joined on a 2-week contract", (r["ok"], r.get("days"), "2 weeks contract" in r["message"]), (True, 14, True))
row = q("SELECT clan, contract_clan, contract_until FROM players WHERE norm_name=?", ACE)[0]
until = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 14 * 86400))
check("player row carries clan + term", (row[0], row[1], (row[2] or "")[:10]), ("TST", "TST", until))
r = ace.post("/clan/leave", json={}).get_json()
check("cannot leave before it is up", (r["ok"], "under contract with TST until %s" % until in r["message"]), (False, True))
check("still in the clan", q("SELECT clan FROM players WHERE norm_name=?", ACE), [("TST",)])
h = owner.get("/myclan").get_data(as_text=True)
check("Your clan roster shows the contract", ('class="mcstat mccontract"' in h) and (until in h), True)
h = ace.get("/account").get_data(as_text=True)
check("account band says under contract", ("under contract until %s" % until) in h, True)
h = owner.get("/clan/TST").get_data(as_text=True)
check("public clan page does not say it (gems only, and no roster stat)", "mccontract" in h, False)
w("UPDATE players SET contract_until = '2020-01-01 00:00:00' WHERE norm_name = ?", ACE)
r = ace.post("/clan/leave", json={}).get_json()
check("once the term is up, leaving works and clears it", (r["ok"], q("SELECT clan, contract_clan, contract_until FROM players WHERE norm_name=?", ACE)), (True, [(None, None, None)]))

print("\n--- replays by player ---")
# The no-result replay table lives in the replay database and is created by
# the tracker's ingest, so a scratch copy has to make it by hand.
rc = sqlite3.connect(fa.REPLAY_DB_PATH)
rc.execute("CREATE TABLE IF NOT EXISTS trueskill_replay (match_key TEXT, sys_id INTEGER, at TEXT, name TEXT, "
           "region TEXT, dur_s INTEGER, reason TEXT, no_result INTEGER)")
rc.commit()
rc.close()
cn = sqlite3.connect(fa.DB_PATH)
c = cn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS match_replays (match_row INTEGER PRIMARY KEY, data BLOB, created_at TEXT)")
c.execute("INSERT INTO matches(match_id, sys_id, played_at, lobby_name) VALUES (?,?,?,?)", ("m1", 100, "2026-09-10 10:00:00", "Alpha"))
m1 = c.lastrowid
c.execute("INSERT INTO matches(match_id, sys_id, played_at, lobby_name) VALUES (?,?,?,?)", ("m2", 101, "2026-09-11 10:00:00", "Beta"))
m2 = c.lastrowid
for mid, names in ((m1, ("Ace Pilot", "Bob")), (m2, ("Bob",))):
    c.execute("INSERT INTO match_replays(match_row, data, created_at) VALUES (?,?,?)", (mid, b"x", "2026-09-11 00:00:00"))
    for n in names:
        c.execute("INSERT INTO match_players(match_row, name, norm_name, won, delta) VALUES (?,?,?,?,?)", (mid, n, fa.normalize_name(n), 1, 1.0))
c.execute("INSERT INTO survival_results(key, ended_at, region, lobby, winner, elim_field_size, data) VALUES (?,?,?,?,?,?,?)",
          ("500|2026-09-12 10:00:00", "2026-09-12 10:00:00", "europe", "500", "Ace Pilot", 9, '{"winner":"Ace Pilot","fighters":[],"elim_field_size":9}'))
c.execute("INSERT INTO survival_results(key, ended_at, region, lobby, winner, elim_field_size, data) VALUES (?,?,?,?,?,?,?)",
          ("501|2026-09-12 11:00:00", "2026-09-12 11:00:00", "europe", "501", "Zed", 7, '{"winner":"Zed","fighters":[],"elim_field_size":7}'))
cn.commit()
cn.close()
fa._REPLAY_COUNT_CACHE.clear()
h = owner.get("/replays").get_data(as_text=True)
check("the search box", 'name="who"' in h, True)
check("no filter: both matches", ("/replay/%d'" % m1 in h) and ("/replay/%d'" % m2 in h), True)
h = owner.get("/replays?who=ace%20pilot").get_data(as_text=True)
check("Ace's matches only (case and spacing do not matter)", ("/replay/%d'" % m1 in h) and ("/replay/%d'" % m2 not in h), True)
check("count in the band", "<b class=\"blue\">1</b>" in h, True)
h = owner.get("/replays?who=nobody").get_data(as_text=True)
check("nobody: the empty line explains", "No replays match that search. A player search" in h, True)
h = owner.get("/replays?who=Bob&page=1").get_data(as_text=True)
check("Bob: both, and the pager carries the name", ("/replay/%d'" % m1 in h) and ("/replay/%d'" % m2 in h) and ("&amp;who=Bob" in h), True)
h = owner.get("/replays?mode=survival&who=ace").get_data(as_text=True)
check("survival: the rounds they won", ("500%7C2026" in h or "500|2026" in h) and ("501" not in h.split("<tbody>")[1]), True)

print("\n--- Merge a name under Names ---")
h = owner.get("/account").get_data(as_text=True)
names_panel = h.split('data-panel="names"')[2].split("</section>")[0] if h.count('data-panel="names"') > 2 else h.split('<section class="panel" data-panel="names"')[1].split("</section>")[0]
check("merge card in the Names panel with the link", ('id="mergeCard"' in names_panel) and ('href="/merge"' in names_panel), True)
check("menu still has it too", 'href="/merge"' in h.split('id="tabmore"')[1].split("</nav>")[0], True)

print("\n--- everything answers ---")
for p in ("/replays", "/replays?mode=survival&who=x", "/agents", "/myclan", "/account", "/clans", "/changelog"):
    check("%s 200" % p, owner.get(p).status_code, 200)
h = owner.get("/changelog").get_data(as_text=True)
check("changelog says replays by player, not contracts", ("searched by player" in h) and ("contract" not in h.lower()), True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
