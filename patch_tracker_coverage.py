"""Tracker: stop the spawn stagger blinding the master sweep, and report a
coverage figure that counts only lobbies the tracker was ever allowed to
watch.

Run from /root/starblast-tracker. Does NOT restart anything - applying this
only rewrites the file; the running process keeps its old code until it is
restarted deliberately.

Measured before writing this (20h, 03:54-23:54 UTC 12 Aug 2026):
  187 lobbies ended, 18 unwatched.
  12 of those 18 had all 7 worker slots busy - capacity, not addressed here.
  6 had a free slot. The master loop was blocked for 12s per spawn
  (12 gaps of 24-25s in 2h, against a 12s sweep), which is that window.
"""

PATH = 'auto_observer.py'

with open(PATH, encoding='utf-8') as f:
    s = f.read()
original = s


def sub(old, new, label, count=1):
    global s
    found = s.count(old)
    assert found == count, ("anchor %r: found %d, want %d"
                            % (label, found, count))
    s = s.replace(old, new, count)


def check(needle, want, label):
    got = s.count(needle)
    assert got == want, ("post-check %r: %d, want %d" % (label, got, want))


# ------------------------------------------------------------------ state
# seen_lobbies goes from id -> watched to id -> (watched, was_ever_eligible),
# so a lobby that never qualified can be told apart from one that was missed.

sub(
    "    # Coverage tracking: which NA team lobbies we have seen, and whether\n"
    "    # a worker was ever attached to each. A lobby leaving the server list\n"
    "    # means its match ended, so comparing 'ended' against 'ended while we\n"
    "    # were watching' gives a true coverage rate.\n"
    "    seen_lobbies = {}\n"
    "    ended_total = 0\n"
    "    ended_watched = 0\n",

    "    # Coverage tracking: which NA team lobbies we have seen, whether a\n"
    "    # worker was ever attached to each, and whether each was ever\n"
    "    # ELIGIBLE. A lobby leaving the server list means its match ended.\n"
    "    #\n"
    "    # Two rates, because the raw one answers the wrong question. Every\n"
    "    # team lobby lands in seen_lobbies, including ones that close before\n"
    "    # they are 20 minutes old or never hold 4 players - and a worker is\n"
    "    # never assigned to those by design. Counting them as misses means\n"
    "    # the figure can never reach 100% no matter how many workers exist,\n"
    "    # and it hides the number that can actually be acted on: of the\n"
    "    # lobbies we were allowed to watch, how many did we watch?\n"
    "    seen_lobbies = {}\n"
    "    ended_total = 0\n"
    "    ended_watched = 0\n"
    "    ended_eligible = 0\n"
    "    ended_eligible_watched = 0\n"
    "    # When the last worker was started. The stagger used to be an inline\n"
    "    # sleep inside the sweep, which stopped the master loop dead for 12s\n"
    "    # per spawn; a timestamp keeps the same spacing while the loop\n"
    "    # carries on watching for lobbies that end.\n"
    "    last_spawn_at = 0.0\n",
    "coverage state")

# ------------------------------------------------------------------ counters

sub(
    "                if nodes:\n"
    "                    live_ids = {lobby.get(\"id\") for lobby in na_team_lobbies}\n"
    "                    for gone_id in [i for i in seen_lobbies if i not in live_ids]:\n"
    "                        ended_total += 1\n"
    "                        if seen_lobbies.pop(gone_id):\n"
    "                            ended_watched += 1\n"
    "                    for lobby in na_team_lobbies:\n"
    "                        lobby_id = lobby.get(\"id\")\n"
    "                        seen_lobbies[lobby_id] = (\n"
    "                            seen_lobbies.get(lobby_id, False) or lobby_id in active_futures\n"
    "                        )\n",

    "                if nodes:\n"
    "                    live_ids = {lobby.get(\"id\") for lobby in na_team_lobbies}\n"
    "                    eligible_ids = {l.get(\"id\") for l in eligible_lobbies}\n"
    "                    for gone_id in [i for i in seen_lobbies if i not in live_ids]:\n"
    "                        was_watched, was_eligible = seen_lobbies.pop(gone_id)\n"
    "                        ended_total += 1\n"
    "                        if was_watched:\n"
    "                            ended_watched += 1\n"
    "                        # Eligibility is sticky: a lobby that qualified at\n"
    "                        # any point was one we could have taken, even if it\n"
    "                        # had aged out or been marked dead by the time it\n"
    "                        # left the list.\n"
    "                        if was_eligible:\n"
    "                            ended_eligible += 1\n"
    "                            if was_watched:\n"
    "                                ended_eligible_watched += 1\n"
    "                    for lobby in na_team_lobbies:\n"
    "                        lobby_id = lobby.get(\"id\")\n"
    "                        wasw, wase = seen_lobbies.get(lobby_id, (False, False))\n"
    "                        seen_lobbies[lobby_id] = (\n"
    "                            wasw or lobby_id in active_futures,\n"
    "                            wase or lobby_id in eligible_ids,\n"
    "                        )\n",
    "coverage counters")

# ------------------------------------------------------------------ report

sub(
    "                coverage = f\"{round(100 * ended_watched / ended_total)}%\" if ended_total else \"n/a\"\n"
    "                print(f\"\\n[Master Sweep] NA Team Lobbies: {len(na_team_lobbies)} (Eligible/20min+: {len(eligible_lobbies)}) | Currently Active Workers: {active_count} | Coverage: {ended_watched}/{ended_total} matches ended while watched ({coverage})\", flush=True)\n",

    "                coverage = f\"{round(100 * ended_watched / ended_total)}%\" if ended_total else \"n/a\"\n"
    "                # The watchable rate is the one to judge the tracker by;\n"
    "                # the raw rate is kept beside it so nothing is hidden.\n"
    "                watchable = (f\"{round(100 * ended_eligible_watched / ended_eligible)}%\"\n"
    "                             if ended_eligible else \"n/a\")\n"
    "                print(f\"\\n[Master Sweep] NA Team Lobbies: {len(na_team_lobbies)} (Eligible/20min+: {len(eligible_lobbies)}) | Currently Active Workers: {active_count} | Watchable: {ended_eligible_watched}/{ended_eligible} ({watchable}) | All lobbies: {ended_watched}/{ended_total} ({coverage})\", flush=True)\n",
    "coverage report")

# ------------------------------------------------------------------ stagger
# The sleep is replaced by a gate. Spacing is unchanged - one worker per
# WORKER_SPAWN_STAGGER seconds - but the sweep is no longer held up, so
# lobby ends are still noticed while workers are being placed.

sub(
    "                for lobby in eligible_lobbies:\n"
    "                    sys_id = lobby.get(\"id\")\n"
    "                    if sys_id not in active_futures:\n",

    "                # At most one worker per sweep, and never two inside the\n"
    "                # stagger window. Starting several clients at once drove\n"
    "                # load average to 41 and killed the driver, so the spacing\n"
    "                # matters - but it does not have to be bought with a\n"
    "                # blocked master loop.\n"
    "                may_spawn = (time.time() - last_spawn_at) >= WORKER_SPAWN_STAGGER\n"
    "                for lobby in eligible_lobbies:\n"
    "                    if not may_spawn:\n"
    "                        break\n"
    "                    sys_id = lobby.get(\"id\")\n"
    "                    if sys_id not in active_futures:\n",
    "spawn gate")

sub(
    "                        active_count += 1\n"
    "                        # Never start two clients back to back.\n"
    "                        time.sleep(WORKER_SPAWN_STAGGER)\n",

    "                        active_count += 1\n"
    "                        # Never start two clients back to back. This was\n"
    "                        # an inline sleep of the stagger interval, which\n"
    "                        # blocked the whole sweep - 12s per spawn in which\n"
    "                        # no ending lobby was noticed and no other worker\n"
    "                        # could be placed. The next sweep picks up the\n"
    "                        # next lobby instead, at the same spacing.\n"
    "                        last_spawn_at = time.time()\n"
    "                        may_spawn = False\n",
    "spawn stagger")

# --------------------------------------------------------------- post-mortem

check("time.sleep(WORKER_SPAWN_STAGGER)", 0, "no inline stagger sleep left")
check("last_spawn_at", 3, "stagger timestamp uses")   # init, gate, set
check("ended_eligible_watched", 4, "watchable numerator uses")
check("ended_eligible ", 3, "watchable denominator uses")
check("seen_lobbies.get(lobby_id, False)", 0, "old bool form gone")
check("was_watched, was_eligible = seen_lobbies.pop(gone_id)", 1, "tuple unpack")
assert s != original, "nothing changed"

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(s)
print("patched %s (%+d chars)" % (PATH, len(s) - len(original)))
print("NOT restarted - the running tracker still has the old code.")
