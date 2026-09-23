# -*- coding: utf-8 -*-
"""The words say what the code does (9.71.0).

Copy goes stale in silence: the rule changes and the sentence describing
it stays. Two did today - the shop kept saying a tier hands you its ship
after that stopped being true, and the Info page listed Discord roles by
tier names retired in 9.51.0. These pin the sentences that describe rules
to the rules, and keep every language's Info page a well-formed subset of
the English one it falls back to."""
import importlib
import io
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import flask_app as fa                                          # noqa: E402
import ranks                                                    # noqa: E402
import i18n                                                     # noqa: E402

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def src(rel):
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


print("\n--- the shop describes the shop ---")
shop = src("templates/shop.html")
check("no tier hands out a ship any more, and the shop does not say it does",
      "hands you its own ship" in shop or "never for sale" in shop, False)
check("it says hulls go on sale at their tier", "go on sale to you" in shop, True)
check("and that a hull wears its own colour", "drawn in its own colour" in shop, True)
check("nothing is 'earned, not sold' now", "Earned, not sold" in shop, False)

print("\n--- the Info page names the tiers that exist ---")
top = ranks.RANK_BY_LEVEL[max(ranks.RANK_BY_LEVEL)]["name"]
bottom = ranks.RANK_BY_LEVEL[min(ranks.RANK_BY_LEVEL)]["name"]
en = importlib.import_module("info_text_en")
discord_card = next(b for t, b in en.CARDS if t == "Ranks on Discord")
check("the Discord card runs from %s down to %s" % (top, bottom),
      ("from %s at" % top) in discord_card and ("down to %s" % bottom) in discord_card, True)
retired = ("Shadow X-3", "Fly,", "to Fly", "Delta-Fighter", "U-Sniper", "Vanguard", "Crusader")
for name in retired:
    check("  no Info card names the retired tier %r" % name,
          any(name in b for _t, b in en.CARDS), False)

print("\n--- every language's Info page is a subset of the English one ---")
for code, _label in i18n.LANGS:
    m = importlib.import_module("info_text_" + code)
    check("%s has no more cards than English" % code, len(m.CARDS) <= len(en.CARDS), True)
    stale = tuple(getattr(m, "STALE", ()) or ())
    check("  %s marks only cards it has as stale" % code,
          all(0 <= i < len(m.CARDS) for i in stale), True)
    check("  %s fills every token English uses in the cards it has" % code,
          all(set(re.findall(r"\[\[[A-Z]+\]\]", en.CARDS[i][1]))
              >= set(re.findall(r"\[\[[A-Z]+\]\]", m.CARDS[i][1]))
              for i in range(len(m.CARDS))), True)

print("\n--- the sentences that were shortened ---")
check("Getting started ends plainly", "That is all it takes." in src("info_text_en.py"), True)
check("  and the old stiff form is gone", "all that is required" in src("info_text_en.py"), False)
check("the win chance says it loses the other three",
      "and loses the other three" in src("info_text_en.py"), True)
ev = src("templates/events.html")
check("the events page states the multiplier in one clause",
      "as far in an event match, win or lose" in ev, True)
app = src("flask_app.py")
check("the error page owns the fault without a fragment",
      "That is on us, not you." in app and "Not you. The page" not in app, False if "Not you. The page" in app else True)
check("no changelog entry ends on a shrug", "Fair enough." in app, False)

print("\n%d passed, %d failed" % (ok, fail))
sys.exit(1 if fail else 0)
