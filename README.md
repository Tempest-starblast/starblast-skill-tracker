# Starblast Team Mode Skill Tracker — website

The full source of the site at https://starblastelo.pythonanywhere.com — the
leaderboard, rating logic, check-ins, claims, Protection, and the API the
tracker bot reports finished matches to.

Published so anyone can verify what the site does and does not do with player
data. The short version, checkable in this code:

- **No IP addresses are recorded.** Not on Play, not on sign-in, not on
  reports or claims. Search this repository for `client_ip` — the only use
  is an irreversible keyed hash (`ip_source()`) feeding rate limits, whose
  key lives outside both the code and the database, and whose entries expire
  within two days.
- **Sign-in stores an opaque account id** (plus your username, for Discord —
  the narrowest scope Discord offers). No email, no password, ever.
- Ratings move by the Elo-style rules in the game-end handler
  (`/api/game_end`); the changelog on the site records every behavior change.

## Layout

- `flask_app.py` — the whole site: routes, rating math, moderation,
  changelog, bot API.
- `templates/` — every page.

## Secrets

None are in this repository. The deployment reads them from files beside the
code (see the `.example` files): API keys for the tracker bot, the rate-limit
hash key, and the Discord OAuth secret.

## Running it

A standard Flask app: `flask_app.py` exposes `app`; point any WSGI host at
it. It creates its SQLite database and tables on first run.
