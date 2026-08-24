"""Re-check every current member of clan IS under the fixed tag matcher
(7.2.1) and demote the ones who only ever matched the English word "is".

Self-contained copy of the new rule so it can run without importing the
site: a token match must touch a non-space separator or lead the name;
the fused-prefix pass (normalized name starts with the tag) still counts.
Dry-run by default; --apply writes.
"""
import re
import sqlite3
import sys
import unicodedata

DB = "/home/StarblastElo/mysite/players.db"
TAG = "IS"
APPLY = "--apply" in sys.argv


def norm(name):
    d = unicodedata.normalize('NFD', name or '')
    s = ''.join(ch for ch in d if not unicodedata.combining(ch))
    return ''.join(ch for ch in unicodedata.normalize('NFC', s)
                   if ch.isalnum()).upper()


def qualifies(raw):
    upper = str(raw or '').upper()
    for m in re.finditer(r'(?<![A-Z0-9])' + re.escape(TAG) + r'(?![A-Z0-9])',
                         upper):
        before = upper[m.start() - 1] if m.start() > 0 else None
        after = upper[m.end()] if m.end() < len(upper) else None
        if (m.start() == 0
                or (before is not None and not before.isspace())
                or (after is not None and not after.isspace())):
            return True
    key = norm(raw)
    return key.startswith(TAG) and len(key) > len(TAG)


conn = sqlite3.connect(DB)
c = conn.cursor()
rows = c.execute("SELECT rowid, name FROM players WHERE clan = ?", (TAG,)).fetchall()
keep, demote = [], []
for pid, name in rows:
    (keep if qualifies(name) else demote).append((pid, name))

print("clan %s: %d members - %d keep the tag, %d matched only the word:"
      % (TAG, len(rows), len(keep), len(demote)))
for _, name in demote:
    print("   demote:", name)

if not APPLY:
    print("\nDRY RUN - re-run with --apply to write.")
    raise SystemExit(0)

c.executemany("UPDATE players SET clan = '' WHERE rowid = ?",
              [(pid,) for pid, _ in demote])
conn.commit()
print("\ndemoted %d player(s); %d genuine members remain." %
      (len(demote), len(keep)))
conn.close()
