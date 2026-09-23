# -*- coding: utf-8 -*-
"""Run every suite in tests/ and say what broke.

    python tests/run_all.py            # everything
    python tests/run_all.py gems shop  # only suites whose name contains these

Each suite is a standalone script that builds its own throwaway copy of
players.db in a temp directory, so they neither need a server nor touch
anything real. They exit non-zero when something fails, which is all this
needs to know.
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TIMEOUT = 300


def suites(filters):
    out = []
    for fn in sorted(os.listdir(HERE)):
        if not fn.startswith("test_") or not fn.endswith(".py"):
            continue
        name = fn[:-3]
        if filters and not any(f.lower() in name.lower() for f in filters):
            continue
        out.append(name)
    return out


def main():
    filters = [a for a in sys.argv[1:] if not a.startswith("-")]
    names = suites(filters)
    if not names:
        print("no suites match %r" % (filters,))
        return 1

    print("running %d suite(s) against %s\n" % (len(names), ROOT))
    started = time.time()
    failed, passed, checks = [], 0, 0
    for name in names:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, name + ".py")],
                               capture_output=True, text=True, timeout=TIMEOUT,
                               cwd=ROOT, encoding="utf-8", errors="replace")
            out = (r.stdout or "") + (r.stderr or "")
            code = r.returncode
        except subprocess.TimeoutExpired:
            out, code = "timed out after %ds" % TIMEOUT, 99
        tail = [ln for ln in out.strip().split("\n") if ln.strip()]
        summary = tail[-1] if tail else "(no output)"
        # Every suite ends with "N passed, M failed".
        try:
            checks += int(summary.split()[0])
        except (ValueError, IndexError):
            pass
        if code == 0:
            passed += 1
            print("  ok    %-22s %-24s %4.1fs" % (name, summary, time.time() - t0))
        else:
            failed.append((name, summary, out))
            print("  FAIL  %-22s %-24s %4.1fs" % (name, summary, time.time() - t0))

    print("\n%d/%d suites passed, %d checks, %.0fs"
          % (passed, len(names), checks, time.time() - started))
    for name, summary, out in failed:
        print("\n--- %s ---" % name)
        for ln in out.strip().split("\n"):
            if "FAIL" in ln or "Error" in ln or "Traceback" in ln:
                print("   " + ln[:160])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
