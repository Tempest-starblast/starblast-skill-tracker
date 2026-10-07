# -*- coding: utf-8 -*-
"""The page cache (9.81.3): heavy pages are served from memory for a few
seconds, a stale copy is handed to visitors while one of them re-renders, and
nobody is ever shown another person's view or a page from before their own
change."""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
TMP = tempfile.mkdtemp(prefix="pagecache")
shutil.copy("players.db", os.path.join(TMP, "players.db"))

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(TMP, "players.db")
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
fa.app.config["PAGE_CACHE_TESTING"] = True
fa.PAGE_DB = os.path.join(TMP, "pagecache.db")
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


calls = []


@fa.app.route("/_t_cached")
def _t_cached():
    calls.append(1)
    return "v%d" % len(calls)


@fa.app.route("/_t_cookie")
def _t_cookie():
    calls.append(1)
    r = fa.app.make_response("c%d" % len(calls))
    r.set_cookie("x", "1")
    return r


@fa.app.route("/_t_post", methods=["POST"])
def _t_post():
    return "ok"


fa.PAGE_CACHE_ENDPOINTS = frozenset(("_t_cached", "_t_cookie", "info_page"))


def reset():
    fa._PAGE_CACHE.clear()
    if os.path.exists(fa.PAGE_DB):
        os.remove(fa.PAGE_DB)


def db_age(key, secs):
    c = sqlite3.connect(fa.PAGE_DB)
    c.execute("UPDATE pages SET at = ? WHERE k = ?", (time.time() - secs, fa._page_id(key)))
    c.commit()
    c.close()


def age(key, secs):
    """Make a stored page look secs old - in memory and in the shared store."""
    e = fa._PAGE_CACHE[key]
    fa._PAGE_CACHE[key] = (time.time() - secs, e[1], e[2])
    if os.path.exists(fa.PAGE_DB):
        db_age(key, secs)


def get(path, cookie=None, **kw):
    cl = fa.app.test_client()
    if cookie:
        cl.set_cookie("sbk", cookie)
    return cl.get(path, **kw)


print("\n--- hit and miss")
reset()
a = get("/_t_cached")
b = get("/_t_cached")
check("the second view comes from the cache", (b.headers.get("X-Page-Cache"), b.get_data(as_text=True)), ("hit", "v1"))
check("and the page was only built once", len(calls), 1)
c = get("/_t_cached?x=2")
check("a different query is its own page", (c.headers.get("X-Page-Cache"), len(calls)), (None, 2))
d = get("/_t_cached", cookie="someone-else")
check("a different visitor (cookie) is never handed this copy", (d.headers.get("X-Page-Cache"), len(calls)), (None, 3))
e = get("/_t_cached?nocache=1")
check("?nocache skips it", (e.headers.get("X-Page-Cache"), len(calls)), (None, 4))
check("a page that sets a cookie is never stored", (get("/_t_cookie").status_code, get("/_t_cookie").headers.get("X-Page-Cache")), (200, None))
check("pages outside the list are never cached", get("/robots.txt").headers.get("X-Page-Cache"), None)

print("\n--- stale copy while one visitor re-renders")
reset()
calls.clear()
get("/_t_cached")
key = next(iter(fa._PAGE_CACHE))
body = fa._PAGE_CACHE[key]
age(key, fa.PAGE_CACHE_FRESH_S + 5)
lk = fa._page_lock(key)
lk.acquire()                                      # someone else is re-rendering
s = get("/_t_cached")
check("an aged page is handed over, not rebuilt, while another visitor re-renders",
      (s.headers.get("X-Page-Cache"), s.get_data(as_text=True), len(calls)), ("stale", "v1", 1))
lk.release()
r = get("/_t_cached")
check("with nobody re-rendering, the first visitor rebuilds it", (r.headers.get("X-Page-Cache"), len(calls)), (None, 2))
check("and the next one gets the fresh copy", (get("/_t_cached").headers.get("X-Page-Cache"), len(calls)), ("hit", 2))
age(key, fa.PAGE_CACHE_STALE_S + 5)
check("a copy older than the stale limit is never served", (get("/_t_cached").headers.get("X-Page-Cache"), len(calls)), (None, 3))
check("the lock is released after every request", fa._page_lock(key).acquire(blocking=False), True)
fa._page_lock(key).release()

print("\n--- a change empties it and the user sees their own change")
get("/_t_cached")
cl = fa.app.test_client()
p = cl.post("/_t_post")
check("a POST clears the cache", len(fa._PAGE_CACHE), 0)
check("and marks the browser fresh", "sbfresh=" in (p.headers.get("Set-Cookie") or ""), True)
calls.clear()
cl.get("/_t_cached")
second = cl.get("/_t_cached")
check("for the next minute that visitor always gets a rebuilt page", (second.headers.get("X-Page-Cache"), len(calls)), (None, 2))
check("API posts do not wipe the cache for everyone", (fa.app.test_client().get("/_t_cached").status_code, True), (200, True))
before = len(fa._PAGE_CACHE)
fa.app.test_client().post("/api/does_not_exist")
check("a POST to /api/ leaves the cache alone", len(fa._PAGE_CACHE), before)

print("\n--- concurrent first visitors build it once")
reset()
calls.clear()
orig = _t_cached


def slow():
    time.sleep(0.4)
    return orig()


fa.app.view_functions["_t_cached"] = slow
res = []
ts = [threading.Thread(target=lambda: res.append(get("/_t_cached").get_data(as_text=True))) for _ in range(5)]
[t.start() for t in ts]
[t.join() for t in ts]
check("five at once, one build", (len(calls), sorted(set(res))), (1, ["v1"]))

print("\n--- another web worker's copy")
fa.app.view_functions["_t_cached"] = orig
reset()
calls.clear()
get("/_t_cached")
c = sqlite3.connect(fa.PAGE_DB)
check("a built page is written where every worker can read it", c.execute("SELECT COUNT(*) FROM pages").fetchone()[0], 1)
c.close()
fa._PAGE_CACHE.clear()                            # a worker that never built it
w = get("/_t_cached")
check("a different worker serves it without building",
      (w.headers.get("X-Page-Cache"), w.get_data(as_text=True), len(calls)), ("hit", "v1", 1))
k = next(iter(fa._PAGE_CACHE))
db_age(k, fa.PAGE_CACHE_STALE_S + 5)
fa._PAGE_CACHE.clear()
check("a long-dead copy is not served", (get("/_t_cached").headers.get("X-Page-Cache"), len(calls)), (None, 2))
good_db = fa.PAGE_DB
fa.PAGE_DB = os.path.join(TMP, "no", "such", "dir", "p.db")
fa._PAGE_CACHE.clear()
check("an unusable store never breaks a page", get("/_t_cached").status_code, 200)
fa.PAGE_DB = good_db

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
