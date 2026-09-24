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

print("\n--- the Info page states the rules the code runs (9.75.0) ---")
# Each of these was on the page and false when it was audited on 24 Sep.
en_src = src("info_text_en.py")
false_claims = (
    ("results arrive within a minute", "within a minute"),
    ("a claim completes when the name wins", "wins a tracked match"),
    ("two even teams move by one point", "exactly one point"),
    ("half stake for losers too", "winners and losers alike"),
    ("one flat 1,000 floor win or lose", "[[MINSCORE]]"),
    ("any replay can be played back forever", "any of them can be played back"),
    ("on the board as soon as you win", "as soon as you win"),
    ("a single K for everyone", "[[K]]"),
)
for what, phrase in false_claims:
    check("English Info no longer says %s" % what, phrase in en_src, False)
for rel in ("templates/play.html", "templates/account.html", "templates/settings.html"):
    s = src(rel)
    check("%s no longer says results land within a minute" % rel, "within a minute" in s, False)
    check("%s no longer says a win completes a claim" % rel, "wins a tracked match" in s, False)

import info_i18n                                                # noqa: E402
with fa.app.test_request_context():
    vals = dict(elo=fa.STARTING_ELO, k=fa.ELO_K, minscore=fa.MIN_RATED_SCORE,
                contact=fa.CONTACT_HANDLE, newgames=fa.PROVISIONAL_GAMES,
                knew=int(round(fa.ELO_K * fa.PROVISIONAL_K_MULT)),
                kest=int(round(fa.ELO_K * fa.ESTABLISHED_K_MULT)),
                minpeak=fa.MIN_RATED_PEAK, minlose=fa.MIN_LOCK_SCORE,
                replaydays=fa.REPLAY_KEEP_DAYS)
    rules = en.CARDS[3][1] + en.CARDS[5][1] + en.CARDS[16][1]
    for tok in ("[[NEWGAMES]]", "[[KNEW]]", "[[KEST]]", "[[MINPEAK]]", "[[MINLOSE]]",
                "[[REPLAYDAYS]]"):
        check("  English Info states %s from the code" % tok, tok in rules, True)
    check("the new-player swing is 280 and the settled one 160",
          (vals["knew"], vals["kest"]), (280, 160))
    for code, _label in i18n.LANGS:
        pg = info_i18n.page(code, **vals)
        text = "".join(str(c) for c in pg["cards"])
        check("  %s: every token filled on the rendered page" % code,
              bool(re.search(r"\[\[[A-Z]+\]\]", text)), False)
        check("  %s: the new-player swing is on the page" % code, "280" in text, True)
        m = importlib.import_module("info_text_" + code)
        check("  %s: no card falls back to English" % code,
              tuple(getattr(m, "STALE", ()) or ()), ())

r = fa.app.test_client().get("/info")
h = r.get_data(as_text=True)
# A token is [[CAPS]]; the page's own script has [[523.25, 0], ...] in it.
check("/info renders with the numbers in",
      (r.status_code, bool(re.search(r"\[\[[A-Z]+\]\]", h)), "280" in h, "160" in h),
      (200, False, True, True))
for code in ("de", "zh", "fa"):
    h = fa.app.test_client().get("/info?lang=" + code).get_data(as_text=True)
    check("  /info?lang=%s has no unfilled token" % code,
          bool(re.search(r"\[\[[A-Z]+\]\]", h)), False)

print("\n%d passed, %d failed" % (ok, fail))
sys.exit(1 if fail else 0)
