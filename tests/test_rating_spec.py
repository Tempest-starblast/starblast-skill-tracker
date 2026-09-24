# -*- coding: utf-8 -*-
"""RATING_SPEC.md must keep telling the truth.

A document describing the rating rules is worth having only as long as it
matches the code. This asserts every number the spec quotes against the
value the site actually uses, and checks the spec still mentions each rule
by name.

If this fails, the DOCUMENT is out of date, not the test. Fix the
document (and think about whether the change wanted an entry in the
changelog too)."""
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

SPEC = io.open(os.path.join(ROOT, "RATING_SPEC.md"), encoding="utf-8").read()
ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s -> got %r, wanted %r" % (name, got, want))


def spec_says(pattern, label):
    """The spec must contain this, somewhere."""
    global ok, fail
    if re.search(pattern, SPEC, re.I):
        ok += 1
        print("  PASS  the spec still documents %s" % label)
    else:
        fail += 1
        print("  FAIL  the spec no longer documents %s (looked for %r)"
              % (label, pattern))


print("\n--- the scale ---")
check("starting rating is 1000", fa.STARTING_ELO, 1000)
check("K is 200", fa.ELO_K, 200)
check("provisional for 5 matches", fa.PROVISIONAL_GAMES, 5)
check("provisional multiplier 1.4", fa.PROVISIONAL_K_MULT, 1.4)
check("established multiplier 0.8", fa.ESTABLISHED_K_MULT, 0.8)
check("a hosted event is worth 1.5x", fa.EVENT_K_MULT, 1.5)
spec_says(r"1\.5", "the event multiplier")
spec_says(r"EVENT_K_MULT", "the event multiplier's constant")
spec_says(r"\*\*1000\*\*", "the starting rating")
spec_says(r"\*\*200\*\*", "the maximum swing")

print("\n--- the gates the site owns ---")
check("winner floor score 1000", fa.MIN_RATED_SCORE, 1000)
check("winner floor peak 2000", fa.MIN_RATED_PEAK, 2000)
check("a check-in lasts 2 hours", fa.CHECKIN_VALID_SECONDS, 7200)
spec_says(r"MIN_RATED_SCORE", "the winner's score floor")
spec_says(r"CHECKIN_VALID_SECONDS", "how long a check-in lasts")

print("\n--- the ladder ---")
check("nine tiers", len(ranks.RANKS), 9)
check("Archon is the top climbable", ranks.TOP_CLIMBABLE, 8)
check("Mythos is level 9", ranks.MYTHOS_LEVEL, 9)
for r in ranks.RANKS:
    cut = r["cut"]
    # None is Mythos (awarded, not a percentile); >1 is the entry tier, which
    # the table calls "entry" rather than "top 101%".
    if cut is None or cut > 1:
        continue
    pct = ("%d" % (cut * 100)) if (cut * 100) == int(cut * 100) else ("%g" % (cut * 100))
    if not re.search(r"top\s*%s\s*%%" % re.escape(pct), SPEC, re.I):
        fail += 1
        print("  FAIL  %s's cut (top %s%%) is not in the spec table" % (r["name"], pct))
    else:
        ok += 1
        print("  PASS  %s listed at top %s%%" % (r["name"], pct))
for r in ranks.RANKS:
    if r["name"] not in SPEC:
        fail += 1
        print("  FAIL  tier %s missing from the spec" % r["name"])
    else:
        ok += 1
print("  PASS  every tier name appears in the spec")

print("\n--- operational limits that change ratings ---")
check("replays kept 30 days", fa.REPLAY_KEEP_DAYS, 30)
check("read cadence 3.27s, as measured", fa.RAW_READ_SECONDS, 3.27)
check("a result waits 360s for its replay", fa.REPLAY_GRACE_SECONDS, 360)
check("disk quota is 3 GB", fa.DISK_QUOTA_BYTES, 3 * 1024 * 1024 * 1024)
spec_says(r"3\.27", "the observer read cadence")
spec_says(r"\*\*30 days\*\*", "how long replays are kept")

print("\n--- the rules that have no constant, only behaviour ---")
for pattern, label in (
        (r"commit", "the team commit lock"),
        (r"half stake|half value", "half stake"),
        (r"left-while-losing", "the abandoned-comeback rule"),
        (r"never saves you from a loss", "that leaving still costs the loss"),
        (r"high-water mark and never lowers", "the announcement high-water mark"),
        (r"account_for_ingame_name", "the single identity authority"),
        (r"gem_peak_level", "the tier authority"),
        (r"must not create or destroy rating", "conservation"),
        (r"duplicate-name", "the two-ships-one-name hold"),
        (r"dominance-flip", "the flip exemption"),
        (r"no roster cap", "that every eligible player is rated"),
        (r"observed time", "that presence is observed time"),
        (r"count for\s+no one", "that the ineligible count for no one")):
    spec_says(pattern, label)

print("\n--- every held reason the code can emit is documented ---")
src = io.open(os.path.join(ROOT, "flask_app.py"), encoding="utf-8").read()
reasons = set(re.findall(r"'(protected|duplicate-name|left-while-losing|"
                         r"dominance-flip|resurgence|flood-cut|joined-too-late|"
                         r"thin_margin_orphan)'", src))
for reason in sorted(reasons):
    if reason in SPEC:
        ok += 1
    else:
        fail += 1
        print("  FAIL  held reason %r is not in the spec" % reason)
print("  PASS  all %d held reasons documented" % len(reasons))

print("\n%d passed, %d failed" % (ok, fail))
sys.exit(1 if fail else 0)
