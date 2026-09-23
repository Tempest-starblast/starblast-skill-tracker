# -*- coding: utf-8 -*-
"""Take a backup before changing the database, and throw the old ones away.

Every script in this repository that writes to players.db copies it first.
None of them ever cleaned up, and on 23 Sep 2026 roughly two gigabytes of
`players.db.bak-*` files - one per migration going back to the 14th - were
most of what filled a 3 GB account and took the site down.

So backups go through here. It keeps the newest KEEP and deletes the rest,
of that prefix only, and it refuses to run at all if the disk is nearly
full, because the one thing worse than no backup is a half-written one
that fails partway and leaves nothing usable.

    from dbbackup import backup
    path = backup(DB_PATH, 'quitfix')      # players.db.bak-pre-quitfix-<stamp>
"""
import os
import shutil
import time

# How many backups of a given prefix to keep. Two: the one just taken, and
# the one before it in case the trouble started earlier than you thought.
KEEP = 2
# Refuse below this much free space. A copy of players.db is ~130 MB, and a
# backup that dies half-written is worse than none.
MIN_FREE_BYTES = 400 * 1024 * 1024


def _free_bytes(path):
    try:
        return shutil.disk_usage(os.path.dirname(path) or ".").free
    except OSError:
        return None


def existing(db_path, prefix=None):
    """Every backup of this database, newest first."""
    d = os.path.dirname(os.path.abspath(db_path)) or "."
    base = os.path.basename(db_path) + ".bak-"
    if prefix:
        base += "pre-%s-" % prefix
    out = []
    try:
        for fn in os.listdir(d):
            if fn.startswith(base):
                full = os.path.join(d, fn)
                try:
                    out.append((os.path.getmtime(full), full))
                except OSError:
                    pass
    except OSError:
        return []
    out.sort(reverse=True)
    return [p for _t, p in out]


def prune(db_path, prefix, keep=KEEP):
    """Delete all but the newest `keep` backups of this prefix."""
    gone = []
    for path in existing(db_path, prefix)[keep:]:
        try:
            os.remove(path)
            gone.append(path)
        except OSError:
            pass
    return gone


def backup(db_path, prefix, keep=KEEP):
    """Copy `db_path` aside, then prune older copies of the same prefix.

    Returns the new backup's path. Raises OSError if there is not enough
    room, rather than leaving a truncated file behind."""
    free = _free_bytes(db_path)
    need = 0
    try:
        need = os.path.getsize(db_path)
    except OSError:
        pass
    if free is not None and free < max(MIN_FREE_BYTES, need * 2):
        raise OSError("not enough free disk for a backup: %.0f MB free, "
                      "%.0f MB needed" % (free / 1e6, max(MIN_FREE_BYTES, need * 2) / 1e6))

    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = "%s.bak-pre-%s-%s" % (db_path, prefix, stamp)
    shutil.copy(db_path, dest)
    dropped = prune(db_path, prefix, keep)
    if dropped:
        print("[backup] %s  (removed %d older: %s)"
              % (dest, len(dropped),
                 ", ".join(os.path.basename(p) for p in dropped)))
    else:
        print("[backup] %s" % dest)
    return dest


def sweep(db_path, keep=KEEP):
    """Prune EVERY prefix of this database at once - for tidying up after
    scripts that predate this module. Returns what was deleted."""
    groups = {}
    for path in existing(db_path):
        fn = os.path.basename(path)
        tail = fn.split(".bak-pre-", 1)[-1] if ".bak-pre-" in fn else fn
        # strip the trailing -<date>-<time>
        key = "-".join(tail.split("-")[:-2]) or tail
        groups.setdefault(key, []).append(path)
    gone = []
    for key, paths in groups.items():
        for path in paths[keep:]:
            try:
                os.remove(path)
                gone.append(path)
            except OSError:
                pass
    return gone


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "players.db"
    if "--sweep" in sys.argv:
        gone = sweep(target)
        print("swept %d old backup(s)" % len(gone))
        for p in gone:
            print("   " + os.path.basename(p))
    else:
        for p in existing(target):
            print("%9.0f MB  %s" % (os.path.getsize(p) / 1e6, os.path.basename(p)))
