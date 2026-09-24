# -*- coding: utf-8 -*-
"""A tester sandbox is given the same money an access key grants.

Both exist so somebody can try the whole shop before it is released. They
drifted apart once - the sandbox default sat at 30,000 while an access key
handed over a million - which made the throwaway account a worse preview
than the real one. They read the same constant now, and this keeps them
that way."""
import io
import json
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

import flask_app as fa                                          # noqa: E402

fa.DB_PATH = os.path.join(tempfile.mkdtemp(prefix="sbxg"), "players.db")
shutil.copy(os.path.join(ROOT, "players.db"), fa.DB_PATH)
TMP = os.path.dirname(fa.DB_PATH)
fa.LIVE_DB_PATH = os.path.join(TMP, "live.db")
fa.REPLAY_DB_PATH = os.path.join(TMP, "replays.db")
fa._BOARD_DIR = os.path.join(TMP, "bc")
os.makedirs(fa._BOARD_DIR, exist_ok=True)
fa.init_db()
fa.app.config["TESTING"] = True
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


print("\n--- the figure itself ---")
check("an access key grants a million", fa.PREVIEW_CREDIT, 1000000)

src = io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read()
print("\n--- and the sandbox reads the same constant ---")
check("no stray 30000 default is left",
      'body.get("gems", 30000)' in src, False)
check("the sandbox default IS PREVIEW_CREDIT",
      'body.get("gems", PREVIEW_CREDIT)' in src, True)
# One call since 9.77.0 (_preview_form renders the entry page for every case).
check("the entry page quotes the same figure, not a literal",
      src.count("gems=PREVIEW_CREDIT") >= 1 and "gems=30000" not in src and "gems=1000000" not in src, True)

print("\n--- entering a sandbox really hands over the million ---")
cn = sqlite3.connect(fa.DB_PATH)
cn.execute("DELETE FROM players WHERE google_sub LIKE 'test:sandbox%'")
cn.commit()
cn.close()
c = sqlite3.connect(fa.DB_PATH)
cur = c.cursor()
with fa.app.test_request_context("/"):
    mode, name = fa._enter_sandbox(cur, {"mode": "account",
                                         "gems": fa.PREVIEW_CREDIT},
                                   "test:sandbox:99")
    c.commit()
check("an account was made", bool(name), True)
gems = cur.execute("SELECT COALESCE(gems, 0) FROM players WHERE norm_name = ?",
                   (fa.normalize_name(name),)).fetchone()[0]
check("it holds a million", gems, 1000000)
ledger = cur.execute("SELECT COALESCE(SUM(amount), 0) FROM gem_ledger "
                     "WHERE owner = ? AND amount > 0",
                     (fa.normalize_name(name),)).fetchone()[0]
check("granted through the ledger, like everything else", ledger, 1000000)

print("\n--- enough to actually try the shop ---")
prices = [i["price"] for i in fa.ship_catalog() if i["price"]]
check("a million covers the most expensive hull", max(prices) <= 1000000, True)
check("and the whole catalogue at once", sum(prices) <= 1000000, True)
c.close()

print("\n%d passed, %d failed" % (ok, fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
