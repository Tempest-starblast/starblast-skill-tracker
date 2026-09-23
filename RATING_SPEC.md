# How a rating is calculated

Every rule the rating engine applies, in one place, with the constant that
controls it and the file it lives in. Written because the rules are spread
across three files on two machines and the only way to answer "why did I get
that?" was to read Python.

**The numbers in this document are checked by `tests/test_rating_spec.py`.** If
someone changes a constant without changing this file, that test fails. Treat a
failure as "the document is now wrong", not as "the test is annoying".

Two machines are involved:

| where | file | what it decides |
|---|---|---|
| the site (PythonAnywhere) | `flask_app.py`, `ranks.py` | the rating maths, tiers, holds, gems |
| the droplet | `trueskill_scorer.py`, `shadow_scorer.py` | who was in the match, which side won, who is rated |

The droplet decides **who counts**; the site decides **what it's worth**. Every
gate below belongs to one or the other, and that is marked.

---

## 1. The scale

| | value | constant |
|---|---|---|
| Everyone starts at | **1000** | `STARTING_ELO` |
| Most a match can move you | **200** | `ELO_K` |
| Provisional for the first | **5** matches | `PROVISIONAL_GAMES` |
| Provisional multiplier | **×1.4** | `PROVISIONAL_K_MULT` |
| Established multiplier | **×0.8** | `ESTABLISHED_K_MULT` |

A new account moves faster so it finds its level quickly; an established one
moves slower so a single night cannot undo a season.

## 2. What one match is worth

For each rated player the engine computes an expectation and pays the surprise.

**Your side of the comparison is your own rating blended half-and-half with your
team's average.** Who stood beside you is part of how surprising the result was:
winning inside a stacked team pays less than carrying weak allies to the same
win, and losing with weak allies costs less than a stacked side losing.

The expectation is **three-way** — it accounts for both opposing teams, not just
one — via `win_expectation()`.

**A match must not create or destroy rating.** The two sides rarely hold the same
number of rated players, so the side with the larger total is damped down to
meet the smaller — never the other way round, so no individual swing is ever
inflated to balance the books. Without this the pool drifts every game.

One important caveat: **the damping is applied before each player's experience
multiplier**, on purpose, so that a deliberate provisional boost is not cancelled
out by the balancing. There is also a floor — no rating falls below 500. So a
single match nets exactly zero only when both sides hold the same mix of new and
established players; across many matches it evens out. Anything netting much
further from zero than the multipliers can explain is worth investigating, which
is what `tools_rating_impact.py drift` looks for.

## 3. Who gets rated at all — the droplet's job

| rule | value | constant |
|---|---|---|
| Rated players per side | top **8** by score | `LOCKED_ROSTER_SIZE` |
| Minimum presence to be rated | **10 minutes** | `MIN_RATED_PRESENCE_S` |
| A loser must have scored at least | **100** | `MIN_LOCK_SCORE` |
| "Joined late" means after | **30 s** | `LATE_JOIN_S` |
| Winner's minimum score | **1000** | `MIN_RATED_SCORE` |
| Winner's minimum peak score | **2000** | `MIN_RATED_PEAK` |

- **Winners** are ranked on their *closing* score; **losers** on their *peak*, so
  a high scorer wiped out by the end still counts as having been assembled.
- A **winner** needs the full ten minutes however early they arrived.
- A **loser** is excused only if they were *both* under the floor *and* joined
  late. An early quitter still takes the loss — dying on purpose is not an exit.
- **Bots are never rated** (`BOTS`, from the game's default nicknames).

## 4. Which team you are on — the commit lock

A name **commits** to a team once it has **10 minutes** of presence
(`MIN_PLAYER_MIN`, `shadow_scorer.py`). After that, appearances on any other
team are discarded entirely.

Two things people get wrong:

- **The ten minutes is one budget for the whole match, not ten per team.** Nine
  minutes on A then one on B commits you to **B**.
- **Never committing falls back to the team you started on.** There is no
  uncommitted escape.

One name appears in exactly one team's roster in the result, always.

## 5. Half stake

A winning-side player whose first sighting **on the winning team** is in the back
half of the watch is paid at half value.

Measured on the winner's own roster, not the lobby: time spent on a team that
went on to lose is not early service to the team that won. (Before 9.56.0 it used
the lobby-wide first sighting, which paid a late switcher in full.)

## 6. Leaving a side that looks beaten

A winner who was away for **more than 10 minutes** at the finish
(`QUIT_AWAY_S = 600`), whose team's win probability at their **last sighting**
was under **25 %** (`QUIT_WP_MAX = 0.25`), is removed from the winning roster
before the maths. The players who stayed are then rated as the smaller, weaker
side they actually were.

- No win **and no loss** — they are simply not in that match.
- **Leaving never saves you from a loss.** This only removes a win you were not
  there for. Walk out on a side that goes on to lose and you take that loss in
  full. The asymmetry is deliberate and `tests/test_quitters.py` guards it.
- A read the win-probability model declines to call (`wp_row` returning zeros)
  **never** strips anybody. Silence is not evidence.

## 7. Results that are held, not rated

Written to `held_results` with a reason, and shown to the player in plain words
on their account page. Nothing ever vanishes unexplained.

| reason | what happened |
|---|---|
| `protected` | Protection is on and no check-in was found for this match |
| `duplicate-name` | Two ships flew one name at once — unattributable |
| `left-while-losing` | §6 above |
| `dominance-flip` | Led every rival by a distance, then lost to a side that filled up mid-match |
| `resurgence` | The winner had collapsed to almost nobody and came back |
| `flood-cut` | The match was swarmed by scripted ships |
| `joined-too-late` | Checked in under ten minutes before the end |
| `thin_margin_orphan` | Ended while nobody was watching closely enough to call it |

## 8. Identity — whose result is it?

`account_for_ingame_name()` decides, in this order:

1. **A check-in binding for this lobby.** Proof that one particular ship was this
   account, scoped to the lobby so a check-in is never a standing claim.
2. **A declared play name.** An account that has said it plays as this name gets
   the result — **no check-in needed**.
3. **A clan tag.** The tag in any of its stylings, plus the name of a member of
   that clan, is that member — when exactly one member matches. Two members who
   read alike identify neither.

Protection still holds a protected account's result unless it was checked in.
A check-in is valid for **7200 s** (`CHECKIN_VALID_SECONDS`).

**Anything that decides whether a name reaches an account must call this
function.** The check-in reminder kept its own older rule and told people their
matches would not count when they would (fixed 9.59.0).

## 9. The tiers

Percentile cuts over established players, from `ranks.py`. A tier is *reached*,
never lost — `peak_div` is a high-water mark.

| level | tier | cut | ship |
|---|---|---|---|
| 9 | Mythos | — finish a day at #1 | 701 Odyssey |
| 8 | Archon | top 0.5 % | 702 |
| 7 | Warden | top 3 % | 603 |
| 6 | Paladin | top 10 % | 601 |
| 5 | Guard | top 22 % | 501 |
| 4 | Warrior | top 40 % | 406 |
| 3 | Raider | top 62 % | 301 |
| 2 | Scout | top 82 % | 201 |
| 1 | Drifter | entry | 101 |

`TOP_CLIMBABLE = 8` — Archon is the highest tier reachable by rating. Mythos is
only ever awarded by finishing a day at number one.

**The tier a player is treated as having comes from `gem_peak_level()`**, which
is the authority for hull purchases, ship ownership and achievements. A preview
session's tier picker must never feed it on a real account — that was a
buy-anything switch until 9.59.0.

## 10. Announcements

`discord_rank_state.announced_level` is a **high-water mark and never lowers**.
The bot announces when the live level beats it. If it followed a player back down
the ladder it would re-arm itself, and anyone hovering on a percentile boundary —
Archon's is half a percent wide — gets congratulated for the same tier
repeatedly. One player was welcomed to Archon six times in three days.

## 11. Operational limits that affect ratings

| | value | constant |
|---|---|---|
| Observer read cadence | ~**3.2 s** | `RAW_READ_SECONDS` |
| Replays kept | **30 days**, then archived | `REPLAY_KEEP_DAYS` |
| A result waits for its replay | **360 s** | `REPLAY_GRACE_SECONDS` |
| Account disk quota | **3 GB** | `DISK_QUOTA_BYTES` |

The read cadence matters because anything deriving a duration from a read count
must use it. It was 10 s — the cadence of a browser tracker retired months
earlier — which reported a 70-minute match as 218.

---

## Changing any of this

1. Write the change.
2. Run `python tools_rating_impact.py --days 30` and read what it would have done
   to real matches. Every rating rule changed since 9.55.0 was measured this way
   first, and two were revised because the measurement was surprising.
3. Update this document and `tests/test_rating_spec.py`.
4. Run `python tests/run_all.py`.
