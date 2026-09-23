# -*- coding: utf-8 -*-
"""The bot ping switch: one setting, honoured by every feed, set from the
website or from Discord."""
import io, os, shutil, sqlite3, sys, tempfile, warnings
warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site, from this file
sys.path.insert(0, ROOT); os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="ping"); shutil.copy("players.db", os.path.join(TMP, "players.db"))
import flask_app as fa
fa.DB_PATH = os.path.join(TMP, "players.db"); fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db"); fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True); fa.init_db(); fa.app.config["TESTING"] = True
fa._load_api_keys = lambda: {"testkey"}
KEY = {"X-API-Key": "testkey"}
N = fa.normalize_name
ok = fail = 0
def check(name, got, want):
    global ok, fail
    if got == want: ok += 1; print("  PASS  %s" % name)
    else: fail += 1; print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))

cn = sqlite3.connect(fa.DB_PATH)
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub) VALUES (?,?,?,?,?,?)",
           ("Loud One", N("Loud One"), 1500, 20, 10, "sub:loud"))
cn.execute("INSERT INTO players(name,norm_name,elo,wins,losses,google_sub) VALUES (?,?,?,?,?,?)",
           ("Quiet One", N("Quiet One"), 1500, 20, 10, "sub:quiet"))
cn.execute("INSERT INTO discord_links(discord_id, account_sub, username, linked_at) VALUES (?,?,?,?)",
           ("111", "sub:loud", "loud#1", fa._stamp()))
cn.execute("INSERT INTO discord_links(discord_id, account_sub, username, linked_at) VALUES (?,?,?,?)",
           ("222", "sub:quiet", "quiet#2", fa._stamp()))
cn.commit(); cn.close()

def q(sql, *a):
    c = sqlite3.connect(fa.DB_PATH); r = c.execute(sql, a).fetchall(); c.close(); return r

print("\n--- the default is what the site has always done ---")
cn = sqlite3.connect(fa.DB_PATH); c = cn.cursor()
check("nobody starts opted out", (fa.pings_off(c, "sub:loud"), fa.pings_off(c, "sub:quiet")), (False, False))
check("and the snowflake is handed over", fa.pingable_discord_id(c, "sub:quiet"), "222")
cn.close()

print("\n--- from the website ---")
cl = fa.app.test_client()
check("signed out cannot read it", cl.get("/api/my/pings").status_code, 401)
with cl.session_transaction() as s: s["google_sub"] = "sub:quiet"
d = cl.get("/api/my/pings").get_json()
check("it reads as on, with Discord linked", (d["pings"], d["discord"]), (True, True))
d = cl.post("/api/my/pings", json={"pings": False}).get_json()
check("turning it off answers plainly", (d["ok"], d["pings"]), (True, False))
check("and it stuck", q("SELECT no_ping FROM players WHERE google_sub='sub:quiet'"), [(1,)])

print("\n--- every feed honours the one setting ---")
cn = sqlite3.connect(fa.DB_PATH); c = cn.cursor()
check("the results feed stops handing over the snowflake", fa.pingable_discord_id(c, "sub:quiet"), None)
check("...but not for anybody else", fa.pingable_discord_id(c, "sub:loud"), "111")
check("the account is still reachable, which is a different question",
      fa.discord_id_for_owner(c, "sub:quiet"), "222")
cn.close()
r = fa.app.test_client().get("/api/bot/rankroles", headers=KEY).get_json()
by = {m["discord_id"]: m for m in (r.get("members") or [])}
if "222" in by: check("rank-ups is told not to ping them", by["222"]["ping"], False)
if "111" in by: check("and to ping the other one", by["111"]["ping"], True)
check("the roster still carries both", set(by) >= {"111", "222"} or by == {}, True)

print("\n--- from Discord ---")
b = fa.app.test_client()
check("the endpoint needs the key", b.get("/api/bot/pings?discord_id=222").status_code, 401)
d = b.get("/api/bot/pings?discord_id=222", headers=KEY).get_json()
check("it reads back off", (d["ok"], d["pings"]), (True, False))
d = b.post("/api/bot/pings", headers=KEY, json={"discord_id": "222", "pings": True}).get_json()
check("and turns it back on", d["pings"], True)
check("which the website agrees with", cl.get("/api/my/pings").get_json()["pings"], True)
d = b.get("/api/bot/pings?discord_id=999", headers=KEY).get_json()
check("a Discord with no account here is told so", (d["ok"], d["linked"]), (False, False))
check("and one with no id at all is a bad request",
      b.get("/api/bot/pings", headers=KEY).status_code, 400)

print("\n--- the check-in nudge is the loudest one, so it goes first ---")
cn = sqlite3.connect(fa.DB_PATH); c = cn.cursor()
fa.set_pings(c, "sub:quiet", False); cn.commit(); cn.close()
check("off means off for the DM too", fa.pings_off(sqlite3.connect(fa.DB_PATH).cursor(), "sub:quiet"), True)
h = cl.get("/account").get_data(as_text=True)
check("the switch is on the account page", 'id="pings"' in h, True)
check("and says what it does", "stop notifying you" in h, True)

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
