from flask import Flask, request, jsonify, render_template, session, redirect
import re
import unicodedata
from urllib.parse import quote
import random
import json
import sqlite3
import os
import time
import secrets
import hmac
import hashlib
from datetime import timedelta
import i18n
import info_i18n

app = Flask(__name__)

APP_VERSION = "6.27.1"

# Shown wherever a player needs to reach a human.
CONTACT_HANDLE = "justtempest"
# The site owner (the bot application owner id). Gates the owner-only
# sandbox switch. A set so a second identity can be added if needed.
OWNER_SUBS = {"discord:1078474542026076160"}
# The throwaway account the owner impersonates for testing. Never a
# real person; its rows are wiped on entry so each test starts blank.
SANDBOX_SUB = "test:sandbox"

# One name per Google account. A network was never a person - everyone
# behind one home, school or mobile connection shared a single address, so
# the old per-network cap both let one player take several names from
# different networks and stopped several real players sharing one.
MAX_NAMES_PER_ACCOUNT = 1

# Protection can only be flipped once a day. Without a cooldown it is a
# switch you could throw the moment a match looked like going badly: leave
# it off while winning, turn it on to void the losses. The rating only means
# something if the choice is made in advance and lived with.
PROTECTION_COOLDOWN_HOURS = 24

# A claim is unproven by definition, so an unlimited supply of them is just
# a way to bury the real ones - and every new claim raises an alert.
MAX_PENDING_CLAIMS = 3

# How many times an account name may be changed after it is first set. The
# name is an identity other players recognise on the board, so it is not a
# thing to churn - but one correction for a typo or a rethink is fair.
MAX_ACCOUNT_NAME_CHANGES = 1

# Bug reports allowed from one address per day. High enough that somebody
# working through several real problems is never blocked, low enough that
# the page cannot be used to flood the review queue.
MAX_REPORTS_PER_DAY = 10

# What a report can be about. The kind is only a label to sort by - every
# one of them lands in the same list.
REPORT_KINDS = [
    ("bug", "Something is broken"),
    ("result", "A match result is wrong"),
    ("name", "Someone is using my name"),
    ("idea", "Suggestion"),
    ("other", "Something else"),
]

# Wins needed, AFTER the claim is filed, before a name is handed over.
# This is a cost, not a proof: a Starblast name is not a credential, so
# nothing observed in game can tell the real owner from somebody wearing
# their name. What it does is make taking someone's name require actually
# playing as them and winning, while the claim sits publicly on that
# player's page for the real owner to see and report.
CLAIM_WINS_REQUIRED = 1

# A match the tracker gave up on may still have been running when it walked
# away, so scoring it is a judgement call. Late games fill up with bots as
# real players drift off, and a game thinned out to a handful of genuine
# players is effectively over - calling that one by score is safe. One that
# still has a real crowd in it is very much alive, and guessing a winner
# there would hand out ratings for a match nobody had finished.
ABANDON_MAX_REAL_PLAYERS = 10

STARTING_ELO = 1000
ELO_K = 200    # max elo swing for a single match, approached as the result gets more lopsided
ELO_SCALE = 2000  # rating-gap scale: bigger = ratings must differ more before the odds shift sharply

# Anchored to this file's own directory rather than a bare relative path,
# since different hosts (PythonAnywhere vs the droplet) run this with
# different working directories.
# How long a request will wait for the write lock before giving up. The
# tracker writes every few seconds, so a user's write regularly has to
# queue behind one; five seconds - sqlite3's default - was short enough
# that saving a name failed outright during a busy push.
DB_TIMEOUT_SECONDS = 30

# What the tracker's own lobby push will wait. It re-sends the complete
# state every sweep, so a push that cannot get the lock has lost nothing
# by giving up - whereas holding on past the tracker's 10-second client
# timeout means the reply is thrown away AND a web worker was blocked for
# the whole time. Must stay comfortably under that client timeout.
PUSH_TIMEOUT_SECONDS = 4


def db(timeout=None):
    """A connection that waits its turn instead of failing.

    Pass a shorter timeout for anything that runs on a schedule and will
    be retried anyway. Blocking such a request only ties up a web worker
    while its caller has already given up on it.
    """
    if timeout is None:
        timeout = DB_TIMEOUT_SECONDS
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    # timeout= covers the driver's own retry loop; busy_timeout covers
    # locks hit inside a statement SQLite is already executing. Both are
    # needed, and they are cheap.
    conn.execute("PRAGMA busy_timeout = %d" % int(timeout * 1000))
    return conn


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'players.db')

# Only the tracker bot should be able to report match results - this
# endpoint is reachable by anyone on the internet, so require a shared
# secret to prevent random visitors from POSTing fake match results.
#
# Keys live in api_keys.txt beside this file, one per line - never in the
# source, which is public. Several keys are valid at once, so a key can
# be rotated with no window in which real match reports are dropped.
def _load_api_keys():
    try:
        with open(os.path.join(BASE_DIR, 'api_keys.txt')) as _f:
            return {ln.strip() for ln in _f if ln.strip()}
    except OSError:
        return set()


def api_key_ok(key):
    return bool(key) and key in _load_api_keys()


# --- Live match state (owner-only win-probability view) --------------------
# The website cannot reach the tracker (PythonAnywhere blocks outbound calls),
# so a small feed process on the droplet tails the tracker's per-read log and
# POSTs each watched lobby's live team scores/counts to /api/live/state. Kept
# in its OWN sqlite file so these frequent writes never contend with players.db.
LIVE_DB_PATH = os.path.join(BASE_DIR, 'live.db')
LIVE_STALE_SECONDS = 70    # a lobby not updated within this is treated as gone
LIVE_TRAJ_CAP = 60         # recent reads kept per lobby (for the sparkline)
LIVE_TEAMS = ("team_1", "team_2", "team_3")

# Trained win-probability model: a conditional logit over the alive teams,
# trained on ~143k ten-second reads across 1011 matches (see winprob notes).
# Features per team: score_share, count_share, score_margin, count_margin,
# top_score, top_count, then each share/margin x game-progress.
_WP_W = [1.1295076628447995, 0.46926494423388093, 1.5665834227690387,
         0.5415906485501419, 0.08886121945581577, 0.20478138329227297,
         -0.23838655751300555, -0.7290679303463938, 0.23254840970750054,
         0.22969712735760298]
_WP_TSCALE = 1400.0


def win_probability(counts, scores, elapsed_seconds=None, weights=None,
                    skills=None):
    """Each team's probability of winning, from current counts + scores (and
    how long the match has run). A team with 0 players is out (probability 0).
    Returns {team_key: prob} summing to 1 over the teams that can still win.

    `weights` lets the daily-retrained model override the built-in defaults.
    A 13-weight model adds roster skill: `skills` maps team -> mean leaderboard
    Elo of its current players (unknown players count as STARTING_ELO). Skill
    is worth the most early, before the score has separated - so two of the
    three skill terms fade as the match progresses. With no skill data the
    skill features are neutral and the model behaves like the 10-feature one."""
    import math
    W = _WP_W
    if weights and len(weights) in (10, 13):
        W = weights
    keys = list(LIVE_TEAMS)
    score = {k: max(0.0, float(scores.get(k, 0) or 0)) for k in keys}
    count = {k: max(0, int(counts.get(k, 0) or 0)) for k in keys}
    alive = [k for k in keys if count[k] > 0]
    if not alive:
        tot = sum(score.values()) or 1.0
        return {k: score[k] / tot for k in keys}
    if len(alive) == 1:
        return {k: (1.0 if k == alive[0] else 0.0) for k in keys}
    if elapsed_seconds is None:
        prog = min(1.0, max(score.values()) / 74000.0)
    else:
        prog = min(1.0, max(0.0, float(elapsed_seconds)) / _WP_TSCALE)
    ssum = sum(score[k] for k in alive) + 1.0
    nsum = sum(count[k] for k in alive) + 1.0
    smax = max(score[k] for k in alive)
    nmax = max(count[k] for k in alive)
    util = {}
    for k in alive:
        s, n = score[k], count[k]
        os_ = max((score[j] for j in alive if j != k), default=0.0)
        on_ = max((count[j] for j in alive if j != k), default=0)
        ss = s / ssum
        cs = n / nsum
        sm = (s - os_) / ssum
        cm = (n - on_) / nsum
        tsc = 1.0 if s == smax else 0.0
        tcc = 1.0 if n == nmax else 0.0
        x = [ss, cs, sm, cm, tsc, tcc, ss * prog, sm * prog, cs * prog, cm * prog]
        if len(W) == 13:
            sk = {j: float((skills or {}).get(j) or 1000.0) for j in alive}
            sk_sum = sum(sk.values()) or 1.0
            rival = max((sk[j] for j in alive if j != k), default=1000.0)
            sk_margin = (sk[k] - rival) / 1000.0
            x += [sk_margin, sk_margin * (1.0 - prog),
                  sk[k] / sk_sum - 1.0 / len(alive)]
        util[k] = sum(W[i] * x[i] for i in range(len(W)))
    m = max(util.values())
    ex = {k: math.exp(util[k] - m) for k in alive}
    z = sum(ex.values())
    out = {k: 0.0 for k in keys}
    for k in alive:
        out[k] = ex[k] / z
    return out


def live_db():
    conn = sqlite3.connect(LIVE_DB_PATH, timeout=5)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("CREATE TABLE IF NOT EXISTS live ("
                 "sys_id INTEGER PRIMARY KEY, updated REAL, elapsed REAL, "
                 "region TEXT, name TEXT, payload TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS model ("
                 "id INTEGER PRIMARY KEY, weights TEXT, meta TEXT, updated REAL)")
    return conn


def load_live_model():
    """Current win-probability weights + metadata, set by the daily retrain.
    Falls back to the built-in weights until the first retrain has run."""
    try:
        conn = live_db()
        r = conn.execute("SELECT weights, meta FROM model WHERE id=1").fetchone()
        conn.close()
        if r and r[0]:
            w = json.loads(r[0])
            meta = json.loads(r[1]) if r[1] else {}
            if isinstance(w, list) and len(w) in (10, 13):
                return w, meta
    except Exception:
        pass
    return None, None



# Format-only validation (letters, length) isn't content moderation -
# this is a public site, so also screen the name's content.
#
# Two lists, because a blanket substring match causes real false
# positives on an 8-character namespace: "SPIC" is inside "SPICY",
# "COON" inside "RACCOON", "RAPE" inside "GRAPE", "ANAL" inside
# "ANALOG". So only unambiguous terms are matched anywhere in the name;
# short words with innocent uses are rejected only as the entire name.
BLOCKED_SUBSTRINGS = {
    # racial / ethnic
    'NIGG', 'NIGA', 'NIBBA', 'NEGRO', 'NEGRIT', 'CHINK', 'GOOK', 'WETBACK',
    'BEANER', 'JIGABOO', 'DARKIE', 'DARKY', 'SAMBO', 'RAGHEAD',
    'GYPPO', 'HONKY', 'ZIPPERHEAD',
    # homophobic / transphobic / ableist
    'FAGG', 'FAGOT', 'TRANNY', 'SHEMALE', 'RETARD', 'MONGOLOID',
    # hate movements
    'NAZI', 'HITLER', 'HEIL', 'KKK',
    # sexual violence / exploitation
    'RAPIST', 'MOLEST', 'PEDO',
    # profanity
    'FUCK', 'SHIT', 'CUNT', 'BITCH', 'WHORE', 'SLUT', 'PISS',
    # FOREIGN-LANGUAGE profanity. Only ever applied to names typed
    # into /register, never to auto-registered winners.
    'PUTA', 'PUTO', 'MIERDA', 'MERDA', 'CARALHO', 'PENDEJO',
    'CABRON', 'CHINGA', 'TANGINA',
    'SIBAL', 'SHIBAL', 'SSIBAL', 'GAESAEKI', 'BYUNGSIN',
    'CAONIMA', 'WOCAO', 'DIAOSI',
    'BLYAT', 'BLYAD', 'PIZDA', 'MUDAK', 'KURWA', 'CHUJ', 'JEBAC',
    'MERDE', 'CONNARD', 'SALOPE', 'ENCULE',
    'SCHEISS', 'FOTZE', 'WICHSER',
    'CAZZO', 'STRONZO', 'VAFFAN',
    'OROSPU', 'SIKTIR', 'AMCIK',
    'KUSO', 'CHUTIYA', 'BHENCHOD', 'SHARMUTA',
    'TWAT', 'WANK', 'JIZZ', 'PORN', 'PENIS', 'VAGINA',
}

# Rejected only when they make up the whole name.
BLOCKED_EXACT = {
    'SPIC', 'COON', 'KIKE', 'PAKI', 'JAP', 'WOP', 'MICK', 'CHING',
    'DYKE', 'HOMO', 'FAG', 'TARD', 'SPAZ',
    'RAPE', 'ANAL', 'SEX', 'CUM', 'DICK', 'COCK', 'TITS', 'ASS',
    # Foreign terms that collide with innocent words/names as
    # substrings: VERGA<-VERGARA, SUKA<-ASUKA, SHABI<-SHABIR,
    # SIK<-SIKH, PIC<-PICTURE, GAND<-GANDHI, CAO is a Chinese surname.
    'VERGA', 'SUKA', 'SHABI', 'SIK', 'PIC', 'GAND', 'FIGA', 'KUS',
}


def normalize_name(name):
    """Identity key for a player name.

    OCR reads the same person inconsistently - BERU has appeared as
    ".BERU", "BE R U" and "BERU" in one day, and BEL RIOSE / BELRIOSE split
    almost 50/50. Without collapsing those, whether you are rated for a
    match depends on how the pixels happened to read that time, which makes
    the leaderboard a coin flip. Case, spaces and punctuation are ignored
    when deciding WHO someone is; the name as typed is still displayed.

    Letters and digits are judged by str.isalnum(), which is Unicode-aware,
    so Chinese, Cyrillic, Arabic, Korean and Greek names keep their
    characters. Stripping to A-Z0-9 used to reduce every one of them to the
    empty string, which made them all look like the same player and pushed
    their results onto whichever single row happened to hold that key.

    Accents are folded away first, because OCR is not reliable about them:
    JOSE and JOSE with an accent are one player, not two. Decomposing and
    recomposing leaves Hangul and Chinese untouched."""
    decomposed = unicodedata.normalize('NFD', name or '')
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    recomposed = unicodedata.normalize('NFC', stripped)
    return ''.join(ch for ch in recomposed if ch.isalnum()).upper()


# The 44 names Starblast hands out to anyone who joins without typing
# one. They are NOT bots - they are ordinary players who left the field
# blank - which is exactly why they must never be rated: dozens of
# different people share each one, so the record would belong to nobody.
# It also closes an obvious exploit, since registering "Vader" would
# otherwise collect the elo of every anonymous Vader on the servers.
# Matched on the normalised key, so "R.D. Olivaw" and "RD OLIVAW" both hit.
DEFAULT_NAMES = {normalize_name(n) for n in [
    "Arkady Darell", "Bel Riose", "Cleon I", "Dors Venabili", "Ebling Mis",
    "Gaal Dornick", "Hari Seldon", "Hober Mallow", "Janov Pelorat",
    "The Mule", "Preem Palver", "R.D. Olivaw", "R.G. Reventlov",
    "Raych Seldon", "Salvor Hardin", "Wanda Seldon", "Yugo Amaryl",
    "James T. Kirk", "Leonard McCoy", "Hikaru Sulu", "Montgomery Scott",
    "Spock", "Picard", "Christine Chapel", "Nyota Uhura", "Pavel Chekov",
    "Ford", "Zaphod", "Marvin", "Anakin", "Luke", "Leia", "Ackbar",
    "Tarkin", "Jabba", "Rey", "Kylo", "Han", "Vader", "D.A.R.Y.L.",
    "HAL 9000", "HAL", "Lyta Alexander", "Stephen Franklin", "Lennier",
]}


def is_default_name(name):
    """True for a Starblast default nickname - shared by many anonymous
    players, so it can never identify one person."""
    return normalize_name(name) in DEFAULT_NAMES


# Clans are player-declared tags, not something Starblast exposes, so this
# is a curated list rather than anything auto-detected. Guessing would be
# worse than useless: MR MEESEEKS and MRNUKE share a prefix and are not a
# clan. Add tags here as the community reports them.
# Empty while clans are rebuilt by hand. init_db seeds this list into the
# clans table on every import, so leaving the old tags here would restore
# them the next time the site reloaded - and because all_clan_tags reads
# that table, emptying it also stops detect_clan tagging anybody
# automatically, which is the whole point: the old tags were matched
# against names read off the screen and were often wrong.
BUILTIN_CLAN_TAGS = []

# One account cannot mint tags indefinitely, or the short ones would all be
# squatted within a day.
MAX_CLANS_PER_ACCOUNT = 2


def all_clan_tags(c=None):
    """Every clan tag that exists, longest first.

    Longest first is what makes SRW beat SR when both could match a name,
    so it is done here rather than left to each caller to remember.
    """
    own = c is None
    if own:
        conn = db()
        c = conn.cursor()
    tags = [r[0] for r in c.execute("SELECT tag FROM clans").fetchall()]
    if own:
        conn.close()
    return sorted(tags, key=len, reverse=True)


def display_name(name, clan, shown=None):
    """What a visitor sees, with the clan tag taken out.

    The badge beside the name already says the tag; printing it twice is
    noise. Three passes, and the stored name is never touched - this is
    display only.
    """
    if not name or not clan:
        return name
    key = clean_clan_tag(clan)
    if not key:
        return name
    # 1. The exact styled tag on the front. Only the stored styling can
    #    say that the star in ꞨⱤ✧ is the tag's while the crown after it
    #    is the player's - both read as nothing.
    if shown and shown != key and name.startswith(shown) and len(name) > len(shown):
        rest = name[len(shown):].lstrip(')]}>\u3011\u3017\u300d\u300f').lstrip(' -_:.')
        if any(ch.isalnum() for ch in rest):
            return rest

    # 2. Any WORD that reads as the tag, wherever it sits - front, end or
    #    middle. A word that merely contains it is left alone: SRJACKEE
    #    reads as SRJACKEE, not SR.
    words = name.split()
    kept = [w for w in words if clean_clan_tag(w) != key]
    if len(kept) != len(words) and any(ch.isalnum() for w in kept for ch in w):
        return ' '.join(kept)

    # 3. A tag fused to the front of one word: COVHADE, 「L7」KASANE.
    #    Shortest match, so only the tag's own letters come off.
    for i in range(1, min(len(name) - 1, 13) + 1):
        if clean_clan_tag(name[:i]) == key:
            rest = name[i:].lstrip(')]}>\u3011\u3017\u300d\u300f').lstrip(' -_:.').strip()
            # Never hand back nothing, and never hand back decoration
            # alone: a player whose whole name is the tag keeps it.
            if any(ch.isalnum() for ch in rest):
                return rest
            break
    return name


# Names that are ordinary words or real given names in their own right.
# detect_clan's fused-prefix pass is weak evidence - ISAAC begins with IS
# exactly the way ISCABYBARA does - so a name that is simply a real name is
# never auto-tagged from a prefix alone. Deliberately consulted ONLY by the
# prefix pass: a tag set apart as its own token ("[IS] AAC") is strong
# evidence and stays trusted, and a clan admin can add anyone by hand, so a
# real member who happens to be called Isaac is one click away rather than
# permanently excluded.
COMMON_PERSONAL_NAMES = {
    "AARON", "ABBY", "ABEL", "ABIGAIL", "ADAM", "ADRIAN", "AIDEN", "ALAN", "ALBERT", "ALEX",
    "ALEXA", "ALEXANDER", "ALEXIS", "ALFRED", "ALICE", "ALICIA", "ALLAN", "ALLEN", "ALLISON",
    "ALMA", "ALVIN", "AMANDA", "AMBER", "AMELIA", "AMY", "ANA", "ANDRE", "ANDREA", "ANDREW",
    "ANGEL", "ANGELA", "ANGELO", "ANITA", "ANNA", "ANNE", "ANNIE", "ANTHONY", "ANTONIO",
    "APRIL", "ARIA", "ARIANA", "ARIEL", "ARNOLD", "ARTHUR", "ASHLEY", "ASHTON", "AUBREY",
    "AUDREY", "AUGUST", "AURORA", "AUSTIN", "AVA", "AVERY", "BAILEY", "BARBARA", "BARRY",
    "BEATRICE", "BECKY", "BELLA", "BENJAMIN", "BERNARD", "BETH", "BETTY", "BEVERLY", "BILL",
    "BILLY", "BLAKE", "BOB", "BOBBY", "BRAD", "BRADLEY", "BRANDON", "BRENDA", "BRENDAN",
    "BRENT", "BRETT", "BRIAN", "BRIANA", "BRIDGET", "BROOKE", "BRUCE", "BRUNO", "BRYAN",
    "CALEB", "CALVIN", "CAMERON", "CAMILA", "CANDACE", "CARL", "CARLA", "CARLOS", "CARMEN",
    "CAROL", "CAROLINE", "CARRIE", "CARTER", "CASEY", "CASSIE", "CATHERINE", "CECIL", "CEDRIC",
    "CELIA", "CHAD", "CHARLES", "CHARLIE", "CHARLOTTE", "CHASE", "CHELSEA", "CHERYL",
    "CHESTER", "CHLOE", "CHRIS", "CHRISTIAN", "CHRISTINA", "CHRISTINE", "CHRISTOPHER",
    "CLAIRE", "CLARA", "CLARENCE", "CLARK", "CLAUDIA", "CLAYTON", "CLIFFORD", "CLINT", "CODY",
    "COLE", "COLIN", "CONNOR", "CONRAD", "CORY", "COURTNEY", "COVEN", "COVENANT", "COVER",
    "COVERT", "COVID", "CRAIG", "CRYSTAL", "CURTIS", "CYNTHIA", "DAISY", "DAKOTA", "DALE",
    "DALTON", "DAMIAN", "DAN", "DANA", "DANIEL", "DANIELLE", "DANNY", "DARIUS", "DARREN",
    "DARRYL", "DAVE", "DAVID", "DAWN", "DEAN", "DEBBIE", "DEBORAH", "DELIA", "DENISE",
    "DENNIS", "DEREK", "DERRICK", "DESMOND", "DEVIN", "DIANA", "DIANE", "DIEGO", "DILLON",
    "DOMINIC", "DON", "DONALD", "DONNA", "DORIS", "DOROTHY", "DOUGLAS", "DREW", "DUANE",
    "DUSTIN", "DYLAN", "EARL", "EDDIE", "EDGAR", "EDITH", "EDUARDO", "EDWARD", "EDWIN",
    "ELAINE", "ELEANOR", "ELENA", "ELI", "ELIAS", "ELIJAH", "ELISE", "ELIZABETH", "ELLA",
    "ELLEN", "ELLIE", "ELLIOT", "ELSIE", "EMANUEL", "EMILIO", "EMILY", "EMMA", "EMMANUEL",
    "ENRIQUE", "ERIC", "ERICA", "ERIK", "ERIN", "ERNEST", "ESTHER", "ETHAN", "EUGENE", "EVA",
    "EVAN", "EVELYN", "EZRA", "FAITH", "FELIPE", "FELIX", "FERNANDO", "FIONA", "FLORA",
    "FLOYD", "FOREST", "FORREST", "FRANCES", "FRANCIS", "FRANK", "FRANKLIN", "FRED", "FREDDIE",
    "FREDERICK", "FROST", "FUSION", "GABRIEL", "GABRIELA", "GAIL", "GALAXY", "GAMER",
    "GARRETT", "GARY", "GAVIN", "GENE", "GEORGE", "GERALD", "GHOST", "GIANT", "GILBERT",
    "GINA", "GLADYS", "GLEN", "GLENN", "GLITCH", "GLORIA", "GOBLIN", "GOFER", "GOFISH",
    "GOLDEN", "GORDON", "GRACE", "GRACIE", "GRANT", "GRAVITY", "GREG", "GREGORY", "GRIFFIN",
    "GUSTAVO", "GWEN", "HAILEY", "HANNAH", "HAROLD", "HARRY", "HARVEY", "HAYDEN", "HAZEL",
    "HEATHER", "HECTOR", "HEIDI", "HELEN", "HENRY", "HERBERT", "HERMAN", "HOLLY", "HOMER",
    "HOPE", "HOWARD", "HUGO", "HUNTER", "IAN", "ICEBERG", "IDA", "IGNACIO", "IMOGEN", "IMPACT",
    "INES", "INFERNO", "INGRID", "IRENE", "IRIS", "IRMA", "IRVIN", "ISAAC", "ISABEL",
    "ISABELLA", "ISABELLE", "ISADORA", "ISAIAH", "ISAIAS", "ISHAAN", "ISHAN", "ISLA", "ISLAM",
    "ISLAND", "ISLANDS", "ISLE", "ISMAEL", "ISOLATE", "ISOTOPE", "ISSAC", "ISSUE", "ISSUES",
    "IVAN", "IVY", "JACK", "JACKIE", "JACKSON", "JACOB", "JADE", "JAIME", "JAKE", "JAMES",
    "JAMIE", "JANE", "JANET", "JANICE", "JARED", "JASMINE", "JASON", "JAVIER", "JAY", "JAYDEN",
    "JEAN", "JEFF", "JEFFREY", "JENNA", "JENNIFER", "JENNY", "JEREMY", "JEROME", "JERRY",
    "JESSE", "JESSICA", "JESUS", "JILL", "JIM", "JIMMY", "JOAN", "JOANNA", "JOE", "JOEL",
    "JOEY", "JOHN", "JOHNNY", "JON", "JONAS", "JONATHAN", "JORDAN", "JORGE", "JOSE", "JOSEPH",
    "JOSH", "JOSHUA", "JOYCE", "JUAN", "JUDITH", "JUDY", "JULIA", "JULIAN", "JULIE", "JULIO",
    "JUNE", "JUSTIN", "KAI", "KAITLYN", "KAREN", "KARL", "KARLA", "KATE", "KATHERINE",
    "KATHLEEN", "KATHRYN", "KATHY", "KATIE", "KATRINA", "KAY", "KAYLA", "KEITH", "KELLY",
    "KELVIN", "KEN", "KENDRA", "KENNETH", "KENT", "KERRY", "KEVIN", "KIM", "KIMBERLY", "KIRK",
    "KRIS", "KRISTEN", "KRISTIN", "KYLE", "KYLIE", "LANCE", "LARRY", "LAURA", "LAUREN",
    "LAWRENCE", "LEAH", "LEE", "LEO", "LEON", "LEONARD", "LEROY", "LESLIE", "LESTER", "LEWIS",
    "LIAM", "LILA", "LILIAN", "LILY", "LINDA", "LINDSAY", "LIONEL", "LISA", "LLOYD", "LOGAN",
    "LOIS", "LOLA", "LORENZO", "LORI", "LOUIS", "LOUISE", "LUCAS", "LUCIA", "LUCILLE", "LUCY",
    "LUIS", "LUKE", "LYDIA", "LYNN", "MABEL", "MACK", "MADDIE", "MADELINE", "MADISON",
    "MAGGIE", "MALCOLM", "MANUEL", "MARC", "MARCEL", "MARCO", "MARCOS", "MARCUS", "MARGARET",
    "MARIA", "MARIAN", "MARIE", "MARILYN", "MARIO", "MARION", "MARISA", "MARISOL", "MARK",
    "MARLENE", "MARSHALL", "MARTHA", "MARTIN", "MARVIN", "MARY", "MASON", "MATEO", "MATTHEW",
    "MAURICE", "MAX", "MAXWELL", "MAYA", "MEGAN", "MELANIE", "MELISSA", "MELVIN", "MERCEDES",
    "MEREDITH", "MIA", "MICHAEL", "MICHELLE", "MIGUEL", "MIKE", "MILDRED", "MILES", "MILO",
    "MIRANDA", "MITCHELL", "MOLLY", "MONICA", "MORGAN", "MURIEL", "MURRAY", "MYRA", "NADIA",
    "NANCY", "NAOMI", "NATALIE", "NATASHA", "NATHAN", "NATHANIEL", "NEIL", "NELLIE", "NELSON",
    "NICHOLAS", "NICK", "NICOLE", "NIGEL", "NINA", "NOAH", "NOEL", "NOELLE", "NORA", "NORMA",
    "NORMAN", "OCTAVIO", "OLGA", "OLIVER", "OLIVIA", "OMAR", "OPAL", "ORLANDO", "OSCAR",
    "OSWALD", "OWEN", "PABLO", "PAIGE", "PAM", "PAMELA", "PATRICIA", "PATRICK", "PAUL",
    "PAULA", "PEARL", "PEDRO", "PEGGY", "PENELOPE", "PERCY", "PERRY", "PETE", "PETER",
    "PHILIP", "PHILLIP", "PHOEBE", "PIERCE", "PRESTON", "PRISCILLA", "QUENTIN", "QUINN",
    "RACHEL", "RAFAEL", "RALPH", "RAMON", "RANDALL", "RANDY", "RAOUL", "RAUL", "RAY",
    "RAYMOND", "REBECCA", "REGINA", "REGINALD", "RENE", "REUBEN", "REX", "RHONDA", "RICARDO",
    "RICHARD", "RICK", "RICKY", "RILEY", "RITA", "ROB", "ROBERT", "ROBERTA", "ROBIN", "RODNEY",
    "RODOLFO", "ROGER", "ROLAND", "ROMAN", "RONALD", "RONNIE", "ROSA", "ROSE", "ROSEMARY",
    "ROSS", "ROWAN", "ROXANNE", "ROY", "RUBEN", "RUBY", "RUSSELL", "RUTH", "RYAN", "SABRINA",
    "SADIE", "SALLY", "SALVADOR", "SAM", "SAMANTHA", "SAMUEL", "SANDRA", "SANTIAGO", "SARA",
    "SARAH", "SASHA", "SAWYER", "SCARLETT", "SCOTT", "SEAN", "SEBASTIAN", "SELENA", "SERGIO",
    "SETH", "SHANE", "SHANNON", "SHARON", "SHAUN", "SHAWN", "SHEILA", "SHELBY", "SHELDON",
    "SHERRY", "SHIRLEY", "SIDNEY", "SIENNA", "SIERRA", "SILAS", "SIMON", "SKYLAR", "SOFIA",
    "SOLOMON", "SONIA", "SOPHIA", "SOPHIE", "SPENCER", "SRSLY", "STACY", "STAN", "STANLEY",
    "STELLA", "STEPHANIE", "STEPHEN", "STEVE", "STEVEN", "STEWART", "STUART", "SUE", "SUSAN",
    "SYDNEY", "SYLVIA", "TABITHA", "TAMARA", "TANYA", "TARA", "TAYLOR", "TED", "TERESA",
    "TERRENCE", "TERRY", "THEO", "THEODORE", "THERESA", "THOMAS", "TIFFANY", "TIM", "TIMOTHY",
    "TINA", "TOBY", "TODD", "TOM", "TOMMY", "TONI", "TONY", "TRACY", "TRAVIS", "TREVOR",
    "TRICIA", "TRISTAN", "TROY", "TYLER", "TYRONE", "ULYSSES", "URSULA", "VALERIE", "VANESSA",
    "VERA", "VERNON", "VERONICA", "VICTOR", "VICTORIA", "VINCENT", "VIOLA", "VIOLET", "VIRGIL",
    "VIRGINIA", "VIVIAN", "WADE", "WALLACE", "WALTER", "WANDA", "WARREN", "WAYNE", "WENDY",
    "WESLEY", "WHITNEY", "WILBUR", "WILEY", "WILLIAM", "WILLIE", "WILSON", "WINSTON", "WYATT",
    "XAVIER", "YOLANDA", "YVETTE", "YVONNE", "ZACHARY", "ZANE", "ZOE", "ZOEY",
}


def detect_clan(raw_name, tags=None):
    """Clan tag for a name as the tracker actually read it, or None.

    Must run on the RAW OCR name: the stored name is already normalised,
    and normalising destroys the brackets and spaces that make a tag
    unambiguous ("F4 * YISUS" and "[SR] BOB" both lose their separator).

    Two passes, strongest evidence first. A tag standing alone as its own
    token is near-certain. A fused prefix (F4ISAAC) is likely but not
    safe - SRSLY starts with SR and belongs to nobody - so longer tags win
    ties and the prefix pass is deliberately last.
    """
    if not raw_name:
        return None
    if tags is None:
        tags = all_clan_tags()
    upper = str(raw_name).upper()
    for tag in tags:
        if re.search(r'(?<![A-Z0-9])' + re.escape(tag) + r'(?![A-Z0-9])', upper):
            return tag
    key = normalize_name(raw_name)
    if key.upper() in COMMON_PERSONAL_NAMES:
        return None
    for tag in tags:
        if key.startswith(tag) and len(key) > len(tag):
            return tag
    return None


# Letters people write with symbols. Starblast names are full of these -
# the tag pasted as ₣ⱠⱤ⇝ is F, L, R with an arrow stuck on the end -
# and treating a currency sign as punctuation threw the letter away, so
# ₣ⱠⱤ⇝ became ⱠⱤ and ₵ØV became ØV. Uppercase keys: the text is
# upper-cased before this is applied.
TAG_FOLD = {
    "₣": "F", "₤": "L", "£": "L", "Ⱡ": "L", "Ł": "L",
    "₵": "C", "¢": "C", "₡": "C",
    "Ø": "O", "Ɵ": "O", "Ő": "O",
    "₦": "N", "Ñ": "N", "Ń": "N",
    "₱": "P", "Ᵽ": "P", "ᵽ": "P",
    "₮": "T", "Ŧ": "T", "Ⱦ": "T",
    "₴": "S", "Ꞩ": "S", "Ş": "S", "Š": "S",
    "₭": "K", "Ꝁ": "K",
    "¥": "Y", "Ɏ": "Y",
    "€": "E", "Ɇ": "E",
    "₹": "R", "Ɽ": "R",
    "Ƀ": "B", "฿": "B",
    "Đ": "D", "Ð": "D",
    "Ħ": "H", "Ɨ": "I", "ᵹ": "G", "Ǥ": "G",
    "Ꞷ": "W", "₩": "W", "Ʉ": "U", "Ʌ": "A",
    "Ⱥ": "A", "Ȼ": "C", "Ɍ": "R", "Ɖ": "D", "Ɗ": "D", "Ƒ": "F",
    "Ɠ": "G", "Ɫ": "L", "Ɱ": "M", "Ɲ": "N", "Ƥ": "P", "Ƭ": "T",
    "Ʋ": "V", "Ƴ": "Y", "Ƶ": "Z", "Ǝ": "E", "Ꝁ": "K", "Ꞣ": "K",
}


def clean_clan_tag(text):
    """A clan tag as stored: alphanumerics only, uppercased, Unicode kept.

    Real tags on this leaderboard are not ASCII - [G\u039e], \u20b5\u00d8V, \u0141S and
    \u2325\u0191\u1566 are all live clans. Stripping to A-Z0-9 reduced those to a single
    letter or to nothing, which made them fail the length check and be
    impossible to claim at all. isalnum() is Unicode-aware, so a Greek or
    Latin-extended letter counts as a letter, while brackets, arrows and
    currency signs are still dropped.
    """
    raw = ''.join(TAG_FOLD.get(ch, ch) for ch in str(text or '').upper())
    # NFKD takes the accents off everything ordinary, so É and E are one
    # clan - and it can MINT letters: the subscript ₜ only becomes a t
    # here. Uppercase again, or that t stays lowercase in the key.
    raw = unicodedata.normalize('NFKD', raw).upper()
    plain = ''.join(ch for ch in raw if ch.isalnum() and ch.isascii())
    if plain:
        return plain
    # A tag with no Latin letters in it at all - Cyrillic, Chinese - keeps
    # whatever letters it does have rather than becoming nothing.
    return ''.join(ch for ch in raw if ch.isalnum())


def canonical_clan_tag(text, tags=None):
    """The existing clan tag this text refers to, or None.

    Lets /clan/f4 and /clan/F4 reach the same page. Anything not on the
    curated list resolves to nothing on purpose: an arbitrary /clan/XYZ
    would otherwise render an empty roster and read as a real clan that
    simply has no members yet.
    """
    key = clean_clan_tag(text)
    if tags is None:
        tags = all_clan_tags()
    for known in tags:
        if known == key:
            return known
    return None


# What each role is allowed to do. Ordered, so "outranks" is a comparison
# rather than a table of special cases.
CLAN_ROLES = ('moderator', 'coleader', 'leader')
CLAN_ROLE_LABELS = {'leader': 'Leader', 'coleader': 'Co-leader',
                    'moderator': 'Moderator'}


def clan_rank(role):
    """How senior a role is. 0 means no role at all."""
    return CLAN_ROLES.index(role) + 1 if role in CLAN_ROLES else 0


def clan_role(c, sub_id, tag):
    """This account's role in one clan, or None."""
    if not sub_id or not tag:
        return None
    c.execute("SELECT COALESCE(role, 'leader') FROM clan_admins "
              "WHERE google_sub = ? AND clan = ?", (sub_id, tag))
    row = c.fetchone()
    return row[0] if row else None


def player_clan_role(c, name, tag):
    """The role of a member, found by their player name. None for the rank
    and file - most members have no account at all."""
    c.execute("SELECT google_sub FROM players WHERE name = ?", (name,))
    row = c.fetchone()
    if not row or not row[0]:
        return None
    return clan_role(c, row[0], tag)


def may_kick(actor_role, target_role):
    """Whether one role may take another out of the clan.

    Strictly outrank: a moderator cannot kick a moderator and a co-leader
    cannot kick a co-leader. Only that rule stops two equals removing each
    other, and it is why the leader - who outranks everyone - is safe.
    """
    return clan_rank(actor_role) > 0 and clan_rank(actor_role) > clan_rank(target_role)


def may_manage(c, sub_id, tag):
    """Roster work: inviting, accepting applications, setting the region.
    Leaders and co-leaders. A moderator is there to remove people, not to
    reshape the clan."""
    return clan_rank(clan_role(c, sub_id, tag)) >= clan_rank('coleader')


def is_clan_leader(c, sub_id, tag):
    """Deleting the clan, and handing out co-leader. Leader only.

    A co-leader may not appoint another co-leader: they cannot kick one
    either, so they could otherwise create power they are unable to undo.
    """
    return clan_role(c, sub_id, tag) == 'leader'


def clan_display_map(c):
    """{key: what to show}, for every clan that styles its tag."""
    c.execute("SELECT tag, display_tag FROM clans WHERE display_tag IS NOT NULL "
              "AND display_tag != '' AND display_tag != tag")
    return {r[0]: r[1] for r in c.fetchall()}


def clan_display(c, tag):
    """One clan's tag as its leader wrote it."""
    if not tag:
        return tag
    c.execute("SELECT display_tag FROM clans WHERE tag = ?", (tag,))
    row = c.fetchone()
    return (row[0] if row and row[0] else tag)


def clan_admin_tags(c, sub_id):
    """Every clan tag this signed-in account is an admin of."""
    if not sub_id:
        return []
    return [r[0] for r in c.execute(
        "SELECT clan FROM clan_admins WHERE google_sub = ? ORDER BY clan",
        (sub_id,)).fetchall()]


def join_admin_names(c, sub_id, tag):
    """Put an admin's own names into the clan they now run.

    An admin missing from their own roster reads as a mistake, and without
    this every one of them would have to add themselves by hand. Names
    already in another clan are left where they are: being handed one clan
    is not a reason to pull someone out of a different one.
    """
    c.execute("SELECT name, clan FROM players WHERE google_sub = ?", (sub_id,))
    joined, elsewhere = [], []
    for name, clan in c.fetchall():
        if clan == tag:
            continue
        if clan:
            elsewhere.append(name)
            continue
        c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (tag, name))
        joined.append(name)
    return joined, elsewhere


def join_own_clans(c, sub_id):
    """Put this account's names into any clan it is an admin of.

    Called whenever a name appears on an account, not only when the clan
    is claimed: somebody can be approved and claim their tag before they
    have registered a name at all, and an admin missing from their own
    roster reads as a bug.
    """
    landed = []
    for tag in clan_admin_tags(c, sub_id):
        got, _elsewhere = join_admin_names(c, sub_id, tag)
        landed.extend((tag, nm) for nm in got)
    return landed


def curated_clans(c):
    """Clans that have at least one admin.

    Their rosters are decided by a person, so automatic tag detection must
    not add anyone to them. Detection reads the tag out of whatever name the
    player typed in game, which means anyone can put a clan's tag in their
    name and land on its page - that is the whole problem admins exist to
    fix, and it would keep happening if detection stayed on.
    """
    return {r[0] for r in c.execute("SELECT DISTINCT clan FROM clan_admins").fetchall()}


def is_valid_name_format(name):
    """Shape only, judged on the normalised form so that "BEL RIOSE" and
    "BELRIOSE" are the same 8-letter name. Applied to BOTH manual
    registration and auto-registered winners, because it is what keeps OCR
    garbage (long fragments, stray dialog text) out of the table."""
    key = normalize_name(name)
    if not key or len(key) > 16:
        return False
    if len(key) == 1:
        # A lone narrow character is nearly always a misread roster - the
        # stray "f" that ended up on the board came in that way. A lone wide
        # one is different: a single Chinese, Japanese or Korean character is
        # an ordinary whole name, so those are let through. A single Latin,
        # Cyrillic or Greek letter is not, since it carries no more meaning
        # than a smudge and is far more likely to be one.
        if unicodedata.east_asian_width(key) not in ('W', 'F'):
            return False
    # At least one letter, so a bare number is never a name.
    if not any(ch.isalpha() for ch in key):
        return False
    # Digits used to be banned at the end of a name. That guarded against
    # the dominant OCR failure - the score column bleeding into the name,
    # which always landed as trailing digits (COMMANDER BERU10031,
    # HANGRYHIPPO9117). Nothing is read off the screen any more, so a
    # trailing digit is just what the player typed, and the rule was
    # turning away real names like Tempest1.
    return True


def is_blocked_word(name):
    """Content moderation, applied ONLY to names typed into /register.

    Deliberately NOT applied to auto-registration: those names are ones
    starblast.io already allowed the player to use in-game, and silently
    dropping them would erase real players from a leaderboard meant to
    rank them. Refusing a typed name is harmless by comparison - the
    player simply picks another one."""
    upper_name = name.upper()
    if upper_name in BLOCKED_EXACT:
        return True
    return any(bad in upper_name for bad in BLOCKED_SUBSTRINGS)


# Sign in with Google. This client ID is public by design - it is
# embedded in the page the browser loads - so it belongs in the source.
# There is deliberately no client secret: the ID token flow never uses
# one, which means there is no credential here that could leak.
GOOGLE_CLIENT_ID = "260312209654-l622tb8126pfmhc1nued92r1d1a8mlvv.apps.googleusercontent.com"

# Discord is a second sign-in provider alongside Google. Its identities are
# namespaced "discord:<id>" and stored in the very same google_sub column,
# so every comparison already written against that column keeps working
# untouched - no migration, no schema change, and a bare value still means
# a Google account. Only the numeric id decides who you are; the username
# is kept alongside it purely so a human reviewing a claim can see who
# filed it, and is refreshed on every sign-in because people rename.
DISCORD_CLIENT_ID = "1535552558376943686"
DISCORD_REDIRECT_URI = "https://starblastelo.pythonanywhere.com/auth/discord/callback"
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_API = "https://discord.com/api/v10"

# Unlike the Google flow - which verifies a token the browser already holds
# and so needs no secret at all - the Discord code exchange is server to
# server and must prove who it is. Kept in a file for the same reason as
# the session key: it never rides along in a backup or a pasted console
# line. Missing means Discord sign-in is simply offered as unavailable.
try:
    with open(os.path.join(BASE_DIR, 'discord_secret.txt')) as _f:
        DISCORD_CLIENT_SECRET = _f.read().strip()
except OSError:
    DISCORD_CLIENT_SECRET = ""

# Signing key for session cookies, kept in a file rather than in this
# source so it is never carried along in a backup or pasted into a
# console. If it is ever lost everyone is simply signed out again; no
# player data depends on it.
try:
    with open(os.path.join(BASE_DIR, 'flask_secret.txt')) as _f:
        app.secret_key = _f.read().strip()
except OSError:
    # Never take the leaderboard down over a missing key. Sign-ins just
    # will not survive a restart until the file is put back.
    app.secret_key = secrets.token_hex(32)

# Rate limiting needs "is this the same source as before?", never the
# address itself. What is stored is a keyed one-way hash; the key lives
# beside the code, not in the database, so the stored tag cannot be
# turned back into an address even by someone holding the whole database.
try:
    with open(os.path.join(BASE_DIR, 'ip_hash_secret.txt')) as _f:
        IP_HASH_SECRET = _f.read().strip()
except OSError:
    # No key file means tags do not survive a restart. Rate limiting
    # degrades gracefully; nothing identifying is ever written.
    IP_HASH_SECRET = secrets.token_hex(32)


def source_tag(value):
    """An opaque, irreversible tag for a rate-limit subject.

    Hashed rather than stored plainly so rate_events can never be joined
    back to a person, whatever the subject happens to be.
    """
    return hmac.new(IP_HASH_SECRET.encode(), str(value).encode(),
                    hashlib.sha256).hexdigest()[:32]


def ip_source():
    """An opaque, irreversible tag for the visitor's network."""
    return source_tag(client_ip())


def rate_hit(c, kind, limit, window, src=None):
    """Record one event for this source; True when it is over the limit.

    The table holds (kind, tag, time) and nothing else - no account, no
    name, nothing to join a person to. Entries expire within two days.

    A src must be given for anything arriving through the bot: those
    requests all come from one machine, so the network default would put
    every Discord user in one bucket and let any of them use up the
    limit for everybody.
    """
    src = src or ip_source()
    c.execute("DELETE FROM rate_events WHERE created_at < datetime('now', '-2 days')")
    c.execute("SELECT COUNT(*) FROM rate_events WHERE kind = ? AND src = ? "
              "AND created_at > datetime('now', ?)", (kind, src, window))
    if (c.fetchone() or [0])[0] >= limit:
        return True
    c.execute("INSERT INTO rate_events (kind, src, created_at) VALUES (?,?,?)",
              (kind, src, time.strftime('%Y-%m-%d %H:%M:%S')))
    return False

app.config.update(
    SESSION_COOKIE_SECURE=True,    # the site is HTTPS-only
    SESSION_COOKIE_HTTPONLY=True,  # page scripts cannot read the cookie
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)


def init_db():
    conn = db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (
                    name TEXT PRIMARY KEY,
                    elo INTEGER DEFAULT ''' + str(STARTING_ELO) + ''',
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0
                )''')
    # Existing databases predate this column, so add it in place rather
    # than requiring a manual migration or a wipe.
    # An account has two names now. `name` is the account name - the
    # identity on the leaderboard, deliberately hard to change. `game_name`
    # is what they currently type into Starblast, which they change as
    # often as they like and which is declarative only: it never routes a
    # result on its own, or anyone could claim to be playing as a name and
    # collect its matches. The check-in binding is what actually decides
    # whose result is whose.
    for _ddl in ("ALTER TABLE players ADD COLUMN game_name TEXT",
                 "ALTER TABLE players ADD COLUMN name_changes INTEGER DEFAULT 0",
                 "ALTER TABLE players ADD COLUMN clan_joined_at TEXT"):
        try:
            c.execute(_ddl)
        except sqlite3.OperationalError:
            pass

    c.execute('''CREATE TABLE IF NOT EXISTS checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player TEXT NOT NULL,
                    sys_id INTEGER NOT NULL,
                    ip TEXT,
                    created_at TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS live_lobbies (
                    sys_id INTEGER PRIMARY KEY,
                    name TEXT,
                    players INTEGER,
                    age INTEGER,
                    updated_at TEXT
                )''')
    # Whatever the tracker last told us about itself. Kept as a tiny
    # key/value table so the site never has to keep its own copy of the
    # tracker's settings in sync by hand.
    c.execute('''CREATE TABLE IF NOT EXISTS tracker_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    c.execute("PRAGMA table_info(live_lobbies)")
    if 'watching' not in [row[1] for row in c.fetchall()]:
        # Whether a worker is actually on this lobby. The site can see which
        # lobbies are live but only the tracker knows which it is watching,
        # and that is the difference between a game that will be scored and
        # one that will not.
        c.execute("ALTER TABLE live_lobbies ADD COLUMN watching INTEGER DEFAULT 0")
    c.execute('''CREATE TABLE IF NOT EXISTS claim_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    ip TEXT,
                    note TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'pending'
                )''')
    # Clan tags live here rather than in the source, so players can start
    # their own without a code change.
    c.execute('''CREATE TABLE IF NOT EXISTS clans (
                    tag TEXT PRIMARY KEY,
                    created_by TEXT,
                    created_at TEXT
                )''')
    for builtin in BUILTIN_CLAN_TAGS:
        c.execute("INSERT OR IGNORE INTO clans (tag, created_by, created_at) VALUES (?, NULL, NULL)",
                  (builtin,))
    # Where the clan plays. Set by its leader and nothing else - this is a
    # statement about the clan, not a measurement of it, so it is never
    # guessed from the regions its members happen to have played in.
    try:
        c.execute("ALTER TABLE clans ADD COLUMN region TEXT")
    except sqlite3.OperationalError:
        pass
    # The tag as its leader wrote it. The tag column is a key - folded to
    # plain letters so every styling of a clan is the same clan - and a key
    # is a poor thing to show people.
    try:
        c.execute("ALTER TABLE clans ADD COLUMN display_tag TEXT")
    except sqlite3.OperationalError:
        pass
    # A clan admin is a Google account trusted to decide who is in one clan.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clan TEXT NOT NULL,
                    google_sub TEXT NOT NULL,
                    created_at TEXT
                )''')
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clan_admins ON clan_admins(clan, google_sub)")
    # leader, coleader or moderator. Everyone who ran a clan before roles
    # existed was its leader, which is what the default gives them.
    try:
        c.execute("ALTER TABLE clan_admins ADD COLUMN role TEXT DEFAULT 'leader'")
    except sqlite3.OperationalError:
        pass
    c.execute("UPDATE clan_admins SET role = 'leader' WHERE role IS NULL OR role = ''")
    # One-time codes are how admin is handed out. The site owner cannot see
    # anyone's Google account id, so there has to be something to pass along
    # out of band - a code sent on Discord is that something.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_codes (
                    code TEXT PRIMARY KEY,
                    clan TEXT NOT NULL,
                    created_at TEXT,
                    used_at TEXT,
                    used_by TEXT
                )''')
    # A shareable join link, as opposed to the one-time codes above:
    # those hand over a whole clan, this one only lets people into it.
    # Multi-use on purpose - a leader posts one link where their clan
    # talks and anyone who opens it can join until it expires. expires_at
    # and revoked_at are plain '%Y-%m-%d %H:%M:%S' strings, which compare
    # correctly as text, so no date parsing is needed to test a link.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_invite_links (
                    token TEXT PRIMARY KEY,
                    clan TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    revoked_at TEXT,
                    uses INTEGER DEFAULT 0
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_invite_links_clan "
              "ON clan_invite_links(clan)")
    # A player with an account is invited, not added. See clan_add().
    # direction: 'invite' (admin asked player) or 'application' (player asked
    # clan). Who has to approve depends on which way round it is.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clan TEXT NOT NULL,
                    name TEXT NOT NULL,
                    invited_by TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'pending'
                )''')
    # Whether the bot has already put an application in front of a leader.
    # An application can be made on the website, where there is nothing to
    # reach Discord with, so the bot asks for the ones it has not sent yet
    # rather than the site pushing them and losing any made while the bot
    # was restarting.
    try:
        c.execute("ALTER TABLE clan_invites ADD COLUMN notified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Individual matches. Only aggregate totals were ever stored before, so
    # there was no way to answer "did my game count?" without reading the
    # tracker's logs by hand, and no way to rebuild a clan's record or repair
    # a rating that had been polluted. match_id is unique so the same match
    # arriving twice cannot be written down twice.
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT UNIQUE,
                    sys_id INTEGER,
                    played_at TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS match_players (
                    match_row INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    norm_name TEXT NOT NULL,
                    won INTEGER NOT NULL,
                    delta REAL,
                    half INTEGER DEFAULT 0
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_mp_norm ON match_players(norm_name)")
    # The name actually used in that match. Rosters are rewritten to account
    # names at the door, so without this the name someone played under is
    # lost the moment the result is credited.
    try:
        c.execute("ALTER TABLE match_players ADD COLUMN played_as TEXT")
    except sqlite3.OperationalError:
        pass
    # The player's final in-game score for that match, straight off the
    # game's own scoreboard. NULL for matches recorded before this existed,
    # and for a player the board had already dropped by match end.
    try:
        c.execute("ALTER TABLE match_players ADD COLUMN score INTEGER")
    except sqlite3.OperationalError:
        pass
    # Which side a player was on: 'win', 'lose1' or 'lose2'. The DB knew
    # won/lost but not WHICH losing team, so the results feed could not
    # show teams. NULL on rows from before this - all already announced.
    try:
        c.execute("ALTER TABLE match_players ADD COLUMN team TEXT")
    except sqlite3.OperationalError:
        pass
    for _mcol in ('lobby_name TEXT', 'tracked_reads INTEGER'):
        try:
            c.execute('ALTER TABLE matches ADD COLUMN ' + _mcol)
        except sqlite3.OperationalError:
            pass
    # Which region a match was played in - the leaderboard filters on it and
    # the site cannot infer it after the fact.
    try:
        c.execute("ALTER TABLE matches ADD COLUMN region TEXT DEFAULT 'america'")
    except sqlite3.OperationalError:
        pass
    # Whether this match has been posted to the Discord results feed.
    # Backfilled to 1 when the column is born so the bot does not replay
    # every historical match on first run - history is not news.
    c.execute("PRAGMA table_info(matches)")
    if 'announced' not in [r[1] for r in c.fetchall()]:
        c.execute("ALTER TABLE matches ADD COLUMN announced INTEGER DEFAULT 0")
        c.execute("UPDATE matches SET announced = 1")
    try:
        pass
    except sqlite3.OperationalError:
        pass
    c.execute("CREATE INDEX IF NOT EXISTS idx_matches_region ON matches(region, played_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mp_row ON match_players(match_row)")

    # One row per clan per match, so a clan that fielded five players in a
    # winning match still records exactly one win. Summing members' individual
    # win columns counted the same match once per member, which made a clan's
    # record scale with its size rather than its results.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_results (
                    clan TEXT NOT NULL,
                    sys_id INTEGER NOT NULL,
                    won INTEGER NOT NULL,
                    created_at TEXT
                )''')
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clan_results ON clan_results(clan, sys_id)")
    c.execute("PRAGMA table_info(clan_invites)")
    inv_cols = [row[1] for row in c.fetchall()]
    if 'direction' not in inv_cols:
        c.execute("ALTER TABLE clan_invites ADD COLUMN direction TEXT DEFAULT 'invite'")
    # A result nobody has looked at yet lights the account counter and
    # glows on its first view. Backfilled as already-seen when the
    # column is born: history is not news - only results recorded
    # after this shipped should ever count.
    c.execute("PRAGMA table_info(match_players)")
    _mp_cols = [row[1] for row in c.fetchall()]
    if 'seen' not in _mp_cols:
        c.execute("ALTER TABLE match_players ADD COLUMN seen INTEGER DEFAULT 0")
        c.execute("UPDATE match_players SET seen = 1")
    c.execute("""CREATE TABLE IF NOT EXISTS bug_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT,
                    body TEXT NOT NULL,
                    contact TEXT,
                    google_sub TEXT,
                    ip TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'open'
                )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bug_open ON bug_reports(status, id)")
    # Results that were deliberately NOT counted, kept anyway. Protection
    # tells the site to ignore matches its owner did not check into, and
    # until now those simply evaporated - so if protection was ever wrong,
    # or a name turned out to be held by the wrong person, there was
    # nothing left to look at. These are never shown on the site and never
    # touch a rating; they are a record that the match happened.
    c.execute("""CREATE TABLE IF NOT EXISTS held_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    sys_id INTEGER,
                    region TEXT,
                    name TEXT NOT NULL,
                    norm_name TEXT NOT NULL,
                    played_as TEXT,
                    won INTEGER NOT NULL,
                    score INTEGER,
                    reason TEXT NOT NULL,
                    played_at TEXT
                )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_held_norm ON held_results(norm_name, id)")
    c.execute('''CREATE TABLE IF NOT EXISTS name_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    reported_by TEXT,
                    ip TEXT,
                    note TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'open'
                )''')
    # Discord accounts already granted the server's Player role, so the
    # bot's poll does not grant twice. Sub only - no handles, no dates
    # beyond when it was granted.
    c.execute('''CREATE TABLE IF NOT EXISTS discord_role_grants (
                    sub TEXT PRIMARY KEY,
                    granted_at TEXT
                )''')
    # The game's own deathmatch ladder, snapshotted daily by the bot
    # (the free tier here cannot fetch starblast.io itself). account_id
    # is the game's stable ECP id, so across days this table remembers
    # which names an account has worn - claim-dispute evidence.
    c.execute('''CREATE TABLE IF NOT EXISTS game_ladder (
                    day TEXT NOT NULL,
                    region TEXT NOT NULL,
                    position INTEGER,
                    account_id TEXT NOT NULL,
                    name TEXT,
                    norm_name TEXT,
                    official REAL,
                    live REAL,
                    custom TEXT,
                    PRIMARY KEY (day, region, account_id)
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_ladder_norm "
              "ON game_ladder(norm_name, day)")
    c.execute('''CREATE TABLE IF NOT EXISTS rate_events (
                    kind TEXT NOT NULL,
                    src TEXT NOT NULL,
                    created_at TEXT
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_rate_events "
              "ON rate_events(kind, src, created_at)")
    # Permission to run a clan at all. Requested by a player, decided by
    # the site owner in Discord. Kept separate from clans/clan_admins
    # because it is about the person, not any one tag - a denial has to
    # survive them trying again with a different clan.
    c.execute('''CREATE TABLE IF NOT EXISTS clan_leader_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    google_sub TEXT NOT NULL,
                    handle TEXT,
                    tag TEXT,
                    note TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'pending',
                    decided_at TEXT,
                    decided_by TEXT
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_leader_req "
              "ON clan_leader_requests(google_sub, status)")
    # Whether the person the decision belongs to has seen it on the
    # account page. Decisions happen on the site or in Discord; either
    # way the red counter runs on these until the page shows them.
    for _seen_alter in (
            "ALTER TABLE claim_requests ADD COLUMN seen INTEGER DEFAULT 0",
            "ALTER TABLE clan_invites ADD COLUMN seen INTEGER DEFAULT 0",
            "ALTER TABLE clan_leader_requests ADD COLUMN seen INTEGER DEFAULT 0"):
        try:
            c.execute(_seen_alter)
        except sqlite3.OperationalError:
            pass
    # Whether the bot has shown this to the owner yet. A request made on the
    # website has no way to reach Discord by itself, so the bot collects
    # them the same way it collects applications.
    try:
        c.execute("ALTER TABLE clan_leader_requests ADD COLUMN notified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    c.execute("PRAGMA table_info(claim_requests)")
    claim_cols = [row[1] for row in c.fetchall()]
    if 'verify_from' not in claim_cols:
        # The match id the claim was filed at. Wins only count from here on,
        # so filing a claim on a name that has already won a hundred games
        # does not instantly hand it over.
        c.execute("ALTER TABLE claim_requests ADD COLUMN verify_from INTEGER DEFAULT 0")
    if 'google_sub' not in claim_cols:
        # Capturing the claimant's account at claim time is what lets an
        # approval bind to a person rather than to whatever address they
        # happened to be on - phones change theirs constantly.
        c.execute("ALTER TABLE claim_requests ADD COLUMN google_sub TEXT")
    try:
        c.execute("ALTER TABLE claim_requests ADD COLUMN notified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    c.execute("PRAGMA table_info(players)")
    existing_cols = [row[1] for row in c.fetchall()]
    if 'reg_ip' not in existing_cols:
        c.execute("ALTER TABLE players ADD COLUMN reg_ip TEXT")
    if 'norm_name' not in existing_cols:
        c.execute("ALTER TABLE players ADD COLUMN norm_name TEXT")
    if 'strict_mode' not in existing_cols:
        # Off by default on purpose: registering a name must NOT quietly
        # change how it is rated. Protection is something a player turns
        # on, not something that happens to them.
        c.execute("ALTER TABLE players ADD COLUMN strict_mode INTEGER DEFAULT 0")
    if 'clan' not in existing_cols:
        c.execute("ALTER TABLE players ADD COLUMN clan TEXT")
    if 'prot_changed_at' not in existing_cols:
        c.execute("ALTER TABLE players ADD COLUMN prot_changed_at TEXT")
    if 'clan_locked' not in existing_cols:
        # Set when a tag is taken off a name by hand. Without it the backfill
        # in /api/game_end would put the tag straight back the next time that
        # player was read, so every correction would quietly undo itself.
        c.execute("ALTER TABLE players ADD COLUMN clan_locked INTEGER DEFAULT 0")
    if 'google_sub' not in existing_cols:
        # Proof of ownership is moving from "same network" to "same Google
        # account". An IP is not an identity: phones change theirs
        # constantly, and everyone behind one home or school connection
        # shares a single address.
        c.execute("ALTER TABLE players ADD COLUMN google_sub TEXT")

    # One row per identity. Without this a manually registered "Tempest"
    # and an auto-added "TEMPEST" would coexist as two players.
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_players_norm ON players(norm_name)")
    # Live lobbies now carry the region they were played in.
    try:
        c.execute("ALTER TABLE live_lobbies ADD COLUMN region TEXT DEFAULT 'america'")
    except sqlite3.OperationalError:
        pass
    c.execute("CREATE INDEX IF NOT EXISTS idx_players_google_sub ON players(google_sub)")

    # Which in-game name belongs to which account, and how we know. A
    # binding is created when a Play check-in is followed by that ship id
    # appearing in the lobby - the ship id is what makes this exact, since
    # a name alone cannot separate two players who share one.
    c.execute('''CREATE TABLE IF NOT EXISTS name_bindings (
        sub TEXT NOT NULL,
        in_game_name TEXT NOT NULL,
        sys_id INTEGER,
        ship_id INTEGER,
        region TEXT,
        bound_at TEXT,
        PRIMARY KEY (sub, in_game_name)
    )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_bind_name ON name_bindings(in_game_name)")
    # A binding is per match, so the match has to be part of its key. An
    # earlier build keyed on (sub, in_game_name) alone, which meant playing
    # under the same name in a second lobby REPLACED the first lobby's
    # binding - losing credit for a match that had not been scored yet.
    c.execute("PRAGMA table_info(name_bindings)")
    _nb = c.fetchall()
    if _nb and not any(col[1] == 'sys_id' and col[5] for col in _nb):
        c.execute("""CREATE TABLE IF NOT EXISTS name_bindings_v2 (
            sub TEXT NOT NULL,
            in_game_name TEXT NOT NULL,
            sys_id INTEGER,
            ship_id INTEGER,
            region TEXT,
            bound_at TEXT,
            PRIMARY KEY (sub, in_game_name, sys_id)
        )""")
        c.execute("INSERT OR IGNORE INTO name_bindings_v2 "
                  "(sub, in_game_name, sys_id, ship_id, region, bound_at) "
                  "SELECT sub, in_game_name, sys_id, ship_id, region, bound_at "
                  "FROM name_bindings")
        c.execute("DROP TABLE name_bindings")
        c.execute("ALTER TABLE name_bindings_v2 RENAME TO name_bindings")
        c.execute("CREATE INDEX IF NOT EXISTS idx_bind_name ON name_bindings(in_game_name)")

    # Raw sightings from the tracker: this ship id appeared under this name
    # at this moment. Kept briefly - only long enough to match a check-in.
    c.execute('''CREATE TABLE IF NOT EXISTS appearances (
        sys_id INTEGER,
        ship_id INTEGER,
        name TEXT,
        region TEXT,
        at TEXT
    )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_appear_sys ON appearances(sys_id, at)")

    # A check-in is now made by an ACCOUNT, not by a name - the whole point
    # is that we do not yet know which name you will play under.
    try:
        c.execute("ALTER TABLE checkins ADD COLUMN sub TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE checkins ADD COLUMN bound INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Discord handles, one row per identity. Deliberately its own table
    # rather than a players column: the handle belongs to the account, not
    # to any one name, and keeping it out of players means nothing that
    # reads the leaderboard ever touches it.
    # What OCR used to read, and who the game says it actually was. One
    # row per distinct pairing, with a count - a misreading that repeats is
    # a real mapping, a one-off is noise. Collected only; renaming players
    # from this is a deliberate migration, never automatic.
    c.execute('''CREATE TABLE IF NOT EXISTS name_map (
        ocr_name TEXT NOT NULL,
        real_name TEXT NOT NULL,
        seen INTEGER DEFAULT 0,
        first_seen TEXT,
        last_seen TEXT,
        PRIMARY KEY (ocr_name, real_name)
    )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_name_map_real ON name_map(real_name)")

    c.execute('''CREATE TABLE IF NOT EXISTS discord_users (
        sub TEXT PRIMARY KEY,
        username TEXT,
        display TEXT,
        updated_at TEXT
    )''')

    # Keep the identity key in step with every row.
    for (row_name,) in c.execute("SELECT name FROM players").fetchall():
        c.execute("UPDATE players SET norm_name = ? WHERE name = ?",
                  (normalize_name(row_name), row_name))
    conn.commit()
    conn.close()


def client_ip():
    """The visitor's real network address, from a header they cannot forge.

    PythonAnywhere's proxy sets X-Real-IP itself, overwriting anything the
    visitor sends, so it can be believed. X-Forwarded-For cannot: the proxy
    appends the real address to whatever the visitor chose to put there, so
    [0] is entirely attacker-controlled and only [-1] is trustworthy.
    Reading [0] previously let anyone impersonate another network - renaming
    or removing a name that was not theirs, and bypassing the per-network cap.

    request.remote_addr is never a valid fallback here: it is the internal
    load balancer (10.0.x.x), identical for every visitor to the site, so
    using it would make the whole internet look like one shared owner.
    """
    real = (request.headers.get('X-Real-IP') or '').strip()
    if real:
        return real
    xff = (request.headers.get('X-Forwarded-For') or '').strip()
    if xff:
        return xff.split(',')[-1].strip()
    return ''


@app.context_processor
def inject_auth():
    """The sign-in control sits in the shared header, so every template needs
    the client id and whether somebody is signed in."""
    return {"client_id": GOOGLE_CLIENT_ID, "signed_in": bool(current_user()),
            "is_owner": current_user() in OWNER_SUBS,
            "dev_testing": bool(session.get("dev_real_owner"))}


@app.route('/register', methods=['POST'])
def register():
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in with Google or Discord first - use the buttons at the top of the page. Names are tied to an account so nobody else can take yours."}), 401
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"message": "No name provided"}), 400

    name = data['name'].strip()
    if not is_valid_name_format(name):
        return jsonify({"message": "Name must be 1-16 letters or digits, and cannot end in a digit."}), 400
    if is_blocked_word(name):
        return jsonify({"message": "That name isn't allowed. Please choose another."}), 400
    if is_default_name(name):
        return jsonify({"message": "That is one of Starblast's default names, given to anyone who joins without typing one. Too many players share it for it to be tracked. Pick a name of your own in game."}), 400

    conn = db()
    c = conn.cursor()
    # Two registrations arriving together could both pass the count check
    # below and both insert, putting a network over the cap. Taking the
    # write lock up front serialises them.
    c.execute("BEGIN IMMEDIATE")

    # One name per account. Only a successful registration takes the slot,
    # so a rejected name (already taken, blocked word, bad format) costs
    # nothing and the player can just try another. Removing a name via
    # /unregister frees the slot again.
    c.execute("SELECT name FROM players WHERE google_sub = ?", (sub_id,))
    already = [row[0] for row in c.fetchall()]
    if len(already) >= MAX_NAMES_PER_ACCOUNT:
        conn.close()
        return jsonify({"message": f"Your account already has a name: '{already[0]}'. Remove it first if you want a different one."}), 403

    c.execute("SELECT name FROM players WHERE norm_name = ?", (normalize_name(name),))
    if c.fetchone():
        conn.close()
        return jsonify({"message": f"'{name}' is already registered."}), 400

    c.execute(
        "INSERT INTO players (name, elo, wins, losses, reg_ip, norm_name, google_sub) VALUES (?, ?, 0, 0, ?, ?, ?)",
        (name, STARTING_ELO, None, normalize_name(name), current_user())
    )
    conn.commit()
    conn.close()
    return jsonify({"message": f"'{name}' registered successfully!"}), 200


@app.route('/unregister', methods=['POST'])
def unregister():
    """Remove a name you registered - your account only, and only while it
    has no match history. Deleting a played name would be an elo reset
    button: winners are auto-registered at STARTING_ELO, so anyone could
    wipe a bad rating and be back at baseline after their next win."""
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"message": "No name provided"}), 400
    name = data['name'].strip()

    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, wins, losses, reg_ip FROM players WHERE norm_name = ?", (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{name}' is not registered."}), 404

    stored_name, wins, losses, reg_ip = row
    if (wins or 0) > 0 or (losses or 0) > 0:
        conn.close()
        return jsonify({"message": "That name has already played matches, so it can no longer be removed."}), 403
    ok, err = owner_check(c, stored_name, reg_ip)
    if not ok:
        conn.close()
        return jsonify({"message": err}), 403

    c.execute("DELETE FROM players WHERE name = ?", (stored_name,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"'{stored_name}' has been removed."}), 200


def team_rating(names, elo_map):
    """A roster's strength: average elo of its top 2 rated players. Missing/
    unregistered players are assumed to be at STARTING_ELO, and if fewer
    than 2 names are given the rest are padded with STARTING_ELO too - so
    an unknown/average opposing side reads as a rating of STARTING_ELO."""
    values = [elo_map.get(normalize_name(n), STARTING_ELO) for n in names]
    while len(values) < 2:
        values.append(STARTING_ELO)
    values.sort(reverse=True)
    return (values[0] + values[1]) / 2


def expected_score(own_elo, opponent_rating):
    """Classic elo win probability: how likely `own_elo` was to beat
    `opponent_rating`, given their current ratings."""
    return 1 / (1 + 10 ** ((opponent_rating - own_elo) / ELO_SCALE))


@app.route('/live')
def live_view():
    """Owner-only page: watch live win probabilities for every tracked match."""
    if not is_site_owner():
        return redirect('/')
    return render_template('live.html', page='live', version=APP_VERSION)


@app.route('/api/live/state', methods=['POST'])
def live_state_ingest():
    """The droplet feed posts one watched lobby's live team state here every
    ~10s. Stored in live.db (a separate file) for the owner-only /live view.
    Authenticated with the same shared key the tracker uses for results."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    d = request.json or {}
    try:
        sys_id = int(d.get("sys_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "bad sys_id"}), 400
    counts = d.get("counts") or {}
    scores = d.get("scores") or {}
    top = d.get("top") or {}
    region = str(d.get("region") or "")[:16]
    name = str(d.get("name") or "")[:40]
    elapsed = float(d.get("elapsed") or 0)
    now = time.time()
    ct = {k: int(counts.get(k, 0) or 0) for k in LIVE_TEAMS}
    sc = {k: int(scores.get(k, 0) or 0) for k in LIVE_TEAMS}
    # Roster skill: who is on each team right now, joined to the leaderboard.
    # A player the board does not know counts as a fresh 1000 - same rule the
    # trainer uses, so live and training see skill identically.
    skill = {}
    rosters = d.get("rosters") or {}
    if isinstance(rosters, dict) and any(rosters.values()):
        try:
            _sc = db(timeout=3)
            _scc = _sc.cursor()
            for k in LIVE_TEAMS:
                names = [str(n)[:32] for n in (rosters.get(k) or [])][:16]
                if not names:
                    continue
                elos, games, known = [], 0, 0
                for nm in names:
                    row = _scc.execute(
                        "SELECT elo, COALESCE(wins,0), COALESCE(losses,0) "
                        "FROM players WHERE norm_name = ?",
                        (normalize_name(nm),)).fetchone()
                    if row:
                        known += 1
                        elos.append(float(row[0]))
                        games += row[1] + row[2]
                    else:
                        elos.append(1000.0)
                # The model uses the two best players, not the team average:
                # measured on 1,015 matches, one strong player carries real
                # predictive weight that a mean of eight would bury.
                top2 = sorted(elos, reverse=True)[:2]
                skill[k] = {"elo": round(sum(elos) / len(elos), 1),
                            "top2": round(sum(top2) / len(top2), 1),
                            "known": known, "n": len(names), "games": games}
            _sc.close()
        except sqlite3.Error:
            skill = {}
    conn = live_db()
    c = conn.cursor()
    row = c.execute("SELECT payload FROM live WHERE sys_id=?", (sys_id,)).fetchone()
    traj = []
    if row:
        try:
            traj = (json.loads(row[0]) or {}).get("traj", [])
        except Exception:
            traj = []
    # A reset (a new match starting in the same lobby) begins a fresh trajectory.
    if elapsed < 12 and traj:
        traj = []
    traj.append([round(elapsed, 1), ct, sc])
    traj = traj[-LIVE_TRAJ_CAP:]
    payload = {"counts": ct, "scores": sc,
               "top": {k: str(top.get(k, "") or "")[:24] for k in LIVE_TEAMS},
               "skill": skill, "traj": traj}
    c.execute("INSERT INTO live (sys_id, updated, elapsed, region, name, payload) "
              "VALUES (?,?,?,?,?,?) ON CONFLICT(sys_id) DO UPDATE SET "
              "updated=excluded.updated, elapsed=excluded.elapsed, "
              "region=excluded.region, name=excluded.name, payload=excluded.payload",
              (sys_id, now, elapsed, region, name, json.dumps(payload)))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 200


@app.route('/api/live/matches')
def live_matches():
    """Owner-only: every actively-watched lobby with live win probabilities."""
    if not is_site_owner():
        return jsonify({"error": "Not allowed."}), 403
    now = time.time()
    out = []
    w, model_meta = load_live_model()
    try:
        conn = live_db()
        c = conn.cursor()
        rows = c.execute("SELECT sys_id, updated, elapsed, region, name, payload "
                         "FROM live WHERE updated > ? ORDER BY region, sys_id",
                         (now - LIVE_STALE_SECONDS,)).fetchall()
        conn.close()
    except Exception:
        rows = []
    for sys_id, updated, elapsed, region, name, payload in rows:
        try:
            p = json.loads(payload) or {}
        except Exception:
            continue
        counts = p.get("counts", {})
        scores = p.get("scores", {})
        top = p.get("top", {})
        pskill = p.get("skill") or {}
        skills = {k: ((pskill.get(k) or {}).get("top2")
                      or (pskill.get(k) or {}).get("elo")) for k in LIVE_TEAMS}
        probs = win_probability(counts, scores, elapsed, weights=w, skills=skills)
        traj = p.get("traj", [])
        history = []
        for row in traj[-40:]:
            try:
                t, ct, sc = row
                hp = win_probability(ct, sc, t, weights=w, skills=skills)
                history.append([round(t, 0), round(hp["team_1"], 3),
                                round(hp["team_2"], 3), round(hp["team_3"], 3)])
            except Exception:
                pass
        teams = [{"key": k, "label": "Team %s" % k[-1],
                  "score": int(scores.get(k, 0) or 0),
                  "count": int(counts.get(k, 0) or 0),
                  "top": top.get(k, ""),
                  "skill": pskill.get(k) or None,
                  "prob": round(probs.get(k, 0.0), 4)} for k in LIVE_TEAMS]
        out.append({"sys_id": sys_id, "region": region, "name": name,
                    "elapsed": int(elapsed), "age": round(now - updated, 1),
                    "teams": teams, "history": history})
    return jsonify({"matches": out, "count": len(out),
                    "model": model_meta or {"builtin": True}}), 200


@app.route('/api/live/model', methods=['POST'])
def live_model_update():
    """The daily retrain on the droplet posts refreshed win-probability weights
    here (same shared key as the tracker). Weights live in live.db, so the model
    improves without any code deploy. Rejected unless it is 10 valid numbers."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    d = request.json or {}
    w = d.get("weights")
    meta = d.get("meta") or {}
    if not (isinstance(w, list) and len(w) in (10, 13)
            and all(isinstance(x, (int, float)) for x in w)):
        return jsonify({"error": "weights must be 10 or 13 numbers"}), 400
    conn = live_db()
    conn.execute("INSERT INTO model (id, weights, meta, updated) VALUES (1,?,?,?) "
                 "ON CONFLICT(id) DO UPDATE SET weights=excluded.weights, "
                 "meta=excluded.meta, updated=excluded.updated",
                 (json.dumps(w), json.dumps(meta), time.time()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 200


@app.route('/api/live/skill_export')
def live_skill_export():
    """Everything the daily retrain needs to know player skill AT MATCH TIME:
    each rated player's current elo/wins/losses, plus every match delta with
    its timestamp. The trainer walks the deltas backwards from the current
    rating, so a match from last week is judged by last week's ratings - not
    today's, which would let the model peek at the future."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    players = {}
    for norm, elo, w_, l_ in c.execute(
            "SELECT norm_name, elo, COALESCE(wins,0), COALESCE(losses,0) "
            "FROM players WHERE COALESCE(wins,0)+COALESCE(losses,0) > 0 "
            "AND norm_name IS NOT NULL"):
        players[norm] = [round(float(elo), 2), w_, l_]
    history = [[at, norm, d] for at, norm, d in c.execute(
        "SELECT m.played_at, mp.norm_name, mp.delta FROM match_players mp "
        "JOIN matches m ON m.id = mp.match_row WHERE mp.delta IS NOT NULL "
        "ORDER BY m.played_at")]
    conn.close()
    return jsonify({"players": players, "history": history,
                    "starting_elo": STARTING_ELO}), 200


@app.route('/api/game_end', methods=['POST'])
def game_end():
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Send every name through the bindings BEFORE anything else looks at
    # it, so a result played under any name lands on the right account.
    # Done at the door on purpose: nothing below here has to know that
    # accounts exist, so the rating rules are untouched.
    try:
        _conn = db()
        _c = _conn.cursor()
        _seen = {}
        _played_as = {}
        _sys = data.get('sys_id')

        def _to_account(nm):
            if nm not in _seen:
                _seen[nm] = account_for_ingame_name(_c, nm, _sys) or nm
            acct = _seen[nm]
            # Keep the original spelling against the account it was
            # credited to, so the match can show what they were called
            # even though the rating went somewhere else.
            if acct != nm:
                _played_as[acct] = nm
            return acct

        for _key in ('winning_team', 'losing_team_1', 'losing_team_2',
                     'all_players', 'half_elo', 'ambiguous'):
            _val = data.get(_key)
            if isinstance(_val, list):
                data[_key] = [_to_account(str(x)) for x in _val]
        # Scores are keyed by the same in-game names, and have to land on
        # the same account rows the results do.
        _sc = data.get('scores')
        if isinstance(_sc, dict):
            data['scores'] = {_to_account(str(k)): v for k, v in _sc.items()}
        data['played_as_map'] = _played_as
        _conn.close()
    except sqlite3.Error:
        pass

    winning_team = data.get('winning_team', [])
    losing_team_1 = data.get('losing_team_1', [])
    losing_team_2 = data.get('losing_team_2', [])
    losing_all = losing_team_1 + losing_team_2
    sys_id = data.get('sys_id')
    ambiguous = {normalize_name(n) for n in data.get('ambiguous', [])}
    # Players the tracker first saw in the back half of a match. They used
    # to be dropped from the result entirely, which meant somebody who
    # joined late and won came out level with somebody who never played.
    # Now they earn half. The winning team's top five are never in here -
    # the tracker exempts them before sending, because the roster panel is
    # ordered by score and those are the players who decided it.
    half_elo = {normalize_name(n) for n in data.get('half_elo', [])}

    # A team that led by a distance and lost anyway to a side that
    # filled up mid-match. The tracker decides this - only it can see
    # the scoreboard over time and who arrived - and the site applies
    # it: that team is not rated at all, and the winners take half,
    # because arriving late in numbers is not the same as beating the
    # lead that was already there.
    dominance_exempt = {normalize_name(n)
                        for n in (data.get('dominance_exempt') or [])}
    if data.get('winners_half'):
        half_elo |= {normalize_name(n) for n in winning_team}

    # A whole-match hold: the tracker sets hold_reason when a result is
    # too uncertain to rate but too real to lose - today that is the
    # thin-margin orphan rescue (the match ended unwatched and the
    # winner would be a score guess). Every player lands in
    # held_results for review; nothing is rated, nothing is discarded,
    # and the tracker's match_log keeps the full record for a later
    # decision.
    hold_reason = data.get('hold_reason')
    if hold_reason:
        hconn = db()
        hc = hconn.cursor()
        hmid = str(data.get('match_id') or ('sys%s-%s' % (sys_id, int(time.time()))))
        hnow = time.strftime('%Y-%m-%d %H:%M:%S')
        hpa = data.get('played_as_map') or {}
        hsc = data.get('scores') if isinstance(data.get('scores'), dict) else {}
        hwinners = {str(n) for n in winning_team}
        heveryone = list(dict.fromkeys(
            [str(n) for n in winning_team] + [str(n) for n in losing_all]))
        for hname in heveryone:
            hs = hsc.get(hname)
            try:
                hs = int(hs) if hs is not None else None
            except (TypeError, ValueError):
                hs = None
            hc.execute("INSERT INTO held_results (match_id, sys_id, region, name, norm_name, "
                       "played_as, won, score, reason, played_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (hmid, sys_id, str(data.get('region') or 'america'), hname,
                        normalize_name(hname), hpa.get(hname) or hname,
                        1 if hname in hwinners else 0, hs, str(hold_reason)[:40], hnow))
        hconn.commit()
        hconn.close()
        print("[game_end] held whole match %s (%s): %d players"
              % (hmid, hold_reason, len(heveryone)), flush=True)
        return jsonify({"status": "held", "reason": str(hold_reason)[:40],
                        "players": len(heveryone)}), 200

    def scaled(raw, key):
        """Half the swing for a late arrival, full for everyone else.

        No rounding. Ratings are stored with decimals precisely so that half
        a swing is a real half - while these were whole numbers, an even
        match was worth one point and half of it rounded straight back to
        one, which made the rule do nothing at all."""
        if key in half_elo:
            raw *= 0.5
        return raw

    conn = db()
    c = conn.cursor()

    # Only names whose owner switched protection ON are restricted to
    # lobbies they checked into. Everyone else - including registered
    # players who left it off - is rated automatically as always. That defeats impersonation, because an
    # impersonator cannot check in - doing so needs control of the owning
    # network. Names with no owner keep the old automatic behaviour, so
    # the leaderboard still grows on its own.
    c.execute("SELECT name FROM players WHERE strict_mode = 1")
    protected = {normalize_name(row[0]) for row in c.fetchall()}
    checked_in = set()
    if sys_id is not None and protected:
        c.execute("SELECT player FROM checkins WHERE sys_id = ? AND created_at > datetime('now', ?)",
                  (sys_id, f'-{CHECKIN_VALID_SECONDS} seconds'))
        checked_in = {normalize_name(row[0]) for row in c.fetchall()}

    def protected_without_checkin(player_name):
        key = normalize_name(player_name)
        return key in protected and key not in checked_in

    # What the game's own scoreboard said each player finished with.
    # Rewritten to account names at the door along with the rosters, so
    # the keys here match the names skip() will be asked about.
    final_scores = data.get('scores') if isinstance(data.get('scores'), dict) else {}

    # The tracker flags a name it saw more than once in the same lobby.
    # Two identical names means one is an impersonator and there is no way
    # to tell which, so neither is rated.
    def skip_reason(player_name):
        """Why this player is not rated, or None if they are.

        Split out from skip() so a drop can be recorded with its cause.
        The order matters and matches the original: the cheapest and most
        certain tests come first.
        """
        if not normalize_name(player_name):
            return 'unreadable-name'
        if is_default_name(player_name):
            return 'default-name'
        if final_scores.get(player_name) == 0:
            return 'zero-score'
        if normalize_name(player_name) in ambiguous:
            return 'duplicate-name'
        if protected_without_checkin(player_name):
            return 'protected'
        if normalize_name(player_name) in dominance_exempt:
            return 'dominance-flip'
        return None

    def skip(player_name):
        # A name that normalises to nothing - one written entirely in
        # characters this strips, so Chinese, Cyrillic, Arabic, Korean or
        # Greek - would otherwise be looked up as the empty string, and match
        # whichever single row happens to hold it. Every such player's result
        # landed on one unrelated player. They cannot be told apart from each
        # other either, so the only honest thing is to rate none of them.
        if not normalize_name(player_name):
            return True
        if is_default_name(player_name):
            return True
        # Finished on exactly 0 points: present, but never played. Rating
        # them hands wins to spectators idling in small lobbies - and a
        # 0-score "player" should not count towards the abandoned-match
        # real-player threshold either, which this shares.
        if final_scores.get(player_name) == 0:
            return True
        if normalize_name(player_name) in dominance_exempt:
            return True
        return normalize_name(player_name) in ambiguous or protected_without_checkin(player_name)

    _in_w, _in_l = list(winning_team), list(losing_all)
    # Anyone whose result is being withheld by PROTECTION specifically.
    # The other reasons are noise (bots, unreadable names) or genuinely
    # unknowable (two people using one name), but a protected player is a
    # real person whose real match is being set aside on purpose - that is
    # worth being able to look up later.
    _held = [(p, 1, 'protected') for p in _in_w if skip_reason(p) == 'protected']
    _held += [(p, 0, 'protected') for p in _in_l if skip_reason(p) == 'protected']
    # Kept too: a result set aside because the match was flipped is a
    # real match somebody played, and why it went unrated should be
    # answerable later.
    _held += [(p, 0, 'dominance-flip') for p in _in_l
              if skip_reason(p) == 'dominance-flip']
    winning_team = [p for p in winning_team if not skip(p)]
    losing_all = [p for p in losing_all if not skip(p)]
    _lost = [p for p in _in_l if p not in losing_all]
    print("[game_end] sys=%s region=%s got W=%d L=%d -> kept W=%d L=%d%s"
          % (sys_id, data.get('region'), len(_in_w), len(_in_l),
             len(winning_team), len(losing_all),
             ("  DROPPED LOSERS: %r" % (_lost[:8],)) if _lost else ""),
          flush=True)

    # skip() has already dropped the game's own default nicknames, names read
    # twice in one lobby, and anything normalising to nothing - so what is
    # left is the count of genuine, distinct players.
    if data.get('abandoned'):
        real_players = len({normalize_name(p) for p in winning_team + losing_all})
        if real_players >= ABANDON_MAX_REAL_PLAYERS:
            conn.close()
            return jsonify({
                "status": "not_scored",
                "real_players": real_players,
                "reason": (f"abandoned mid-match with {real_players} real players still in it - "
                           f"{ABANDON_MAX_REAL_PLAYERS} or more means it was still being played"),
            }), 200

    # Winners get auto-registered at STARTING_ELO if they aren't already
    # in the table, so they have a pre-match rating to base the strength
    # calculation on - then the elo change below is applied on top.
    # Losers are still never inserted.
    # Clans with an admin are off limits to automatic tagging - their roster
    # is whatever their admin says it is.
    curated = curated_clans(c)
    known_tags = all_clan_tags(c)
    for player in winning_team + losing_all:
        if is_valid_name_format(player):
            tag = detect_clan(player, known_tags)
            c.execute(
                "INSERT OR IGNORE INTO players (name, elo, wins, losses, norm_name, clan) VALUES (?, ?, 0, 0, ?, ?)",
                (player, STARTING_ELO, normalize_name(player),
                 None if tag in curated else tag)
            )
    # An existing row predates clan tracking, or the tag was unreadable last
    # time. Fill it in when we finally see one, but never overwrite a tag we
    # already have with nothing - and never re-tag a name whose tag was taken
    # off by hand, or the correction would be undone on that player's next match.
    for player in winning_team + losing_all:
        tag = detect_clan(player, known_tags)
        if tag and tag not in curated:
            c.execute("UPDATE players SET clan = ? WHERE norm_name = ? "
                      "AND (clan IS NULL OR clan = '') "
                      "AND (clan_locked IS NULL OR clan_locked = 0)",
                      (tag, normalize_name(player)))
    conn.commit()

    # Snapshot pre-match elo for everyone involved, so both sides' elo
    # changes are based on ratings as they stood before this match.
    all_names = list(set(winning_team + losing_all))
    elo_map = {}
    if all_names:
        placeholders = ",".join("?" for _ in all_names)
        keys = [normalize_name(n) for n in all_names]
        placeholders = ",".join("?" for _ in keys)
        c.execute(f"SELECT norm_name, elo FROM players WHERE norm_name IN ({placeholders})", keys)
        elo_map = dict(c.fetchall())

    losing_team_rating = team_rating(losing_all, elo_map)
    winning_team_rating = team_rating(winning_team, elo_map)

    # Expected-outcome elo: the swing depends on how surprising the result
    # was for THIS player, using their own current elo vs the opposing
    # side's strength - not a flat amount for the whole team. A big
    # underdog win nets close to ELO_K; beating clearly weaker opponents
    # nets close to 0. Losing as a big favorite costs close to ELO_K;
    # losing as a big underdog (an "expected" loss) costs close to 0.
    # (name, won, delta) for every player the result actually moved, so the
    # match is written down exactly as it was applied.
    applied = []

    updated_winners = []
    for player in winning_team:
        own_elo = elo_map.get(normalize_name(player), STARTING_ELO)
        gain = scaled(ELO_K * (1 - expected_score(own_elo, losing_team_rating)),
                      normalize_name(player))
        c.execute(
            "UPDATE players SET elo = ROUND(elo + ?, 2), wins = wins + 1 WHERE norm_name = ?",
            (gain, normalize_name(player))
        )
        if c.rowcount > 0:
            updated_winners.append(player)
            applied.append((player, 1, round(gain, 2)))

    updated_losers = []
    for player in losing_all:
        own_elo = elo_map.get(normalize_name(player), STARTING_ELO)
        loss = scaled(ELO_K * expected_score(own_elo, winning_team_rating),
                      normalize_name(player))
        c.execute(
            "UPDATE players SET elo = ROUND(MAX(500, elo - ?), 2), losses = losses + 1 WHERE norm_name = ?",
            (loss, normalize_name(player))
        )
        if c.rowcount > 0:
            updated_losers.append(player)
            applied.append((player, 0, -round(loss, 2)))

    # Write the match itself down. INSERT OR IGNORE plus the empty check
    # means a match reported twice is stored once, matching the elo guard.
    if applied:
        match_id = str(data.get('match_id') or f"sys{sys_id}-{int(time.time())}")
        now_ts = time.strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT OR IGNORE INTO matches (match_id, sys_id, played_at, "
                  "region, lobby_name, tracked_reads) VALUES (?, ?, ?, ?, ?, ?)",
                  (match_id, sys_id, now_ts, str(data.get('region') or 'america'),
                   (str(data.get('lobby_name'))[:60] if data.get('lobby_name') else None),
                   int(data.get('tracked_reads') or 0)))
        c.execute("SELECT id FROM matches WHERE match_id = ?", (match_id,))
        mrow = c.fetchone()
        if mrow:
            c.execute("SELECT COUNT(*) FROM match_players WHERE match_row = ?", (mrow[0],))
            if c.fetchone()[0] == 0:
                scores = data.get('scores') if isinstance(data.get('scores'), dict) else {}
                team_of = {}
                for _nm in winning_team:
                    team_of[normalize_name(_nm)] = 'win'
                for _nm in losing_team_1:
                    team_of[normalize_name(_nm)] = 'lose1'
                for _nm in losing_team_2:
                    team_of[normalize_name(_nm)] = 'lose2'
                for pname, won, delta in applied:
                    raw_score = scores.get(pname)
                    try:
                        raw_score = int(raw_score) if raw_score is not None else None
                    except (TypeError, ValueError):
                        raw_score = None
                    # Falls back to the credited name, which is the right
                    # answer when no rewrite happened - an unclaimed player
                    # played as exactly who they appear to be.
                    played_as = (data.get('played_as_map') or {}).get(pname) or pname
                    c.execute("INSERT INTO match_players (match_row, name, norm_name, won, delta, half, score, played_as, team) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (mrow[0], pname, normalize_name(pname), won, delta,
                               1 if normalize_name(pname) in half_elo else 0,
                               raw_score, played_as,
                               team_of.get(normalize_name(pname),
                                           'win' if won else 'lose1')))

    if _held:
        _mid = str(data.get('match_id') or ('sys%s-%s' % (sys_id, int(time.time()))))
        _now = time.strftime('%Y-%m-%d %H:%M:%S')
        _pa = data.get('played_as_map') or {}
        for _name, _won, _reason in _held:
            _sc = final_scores.get(_name)
            try:
                _sc = int(_sc) if _sc is not None else None
            except (TypeError, ValueError):
                _sc = None
            c.execute("INSERT INTO held_results (match_id, sys_id, region, name, norm_name, "
                      "played_as, won, score, reason, played_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (_mid, sys_id, str(data.get('region') or 'america'), _name,
                       normalize_name(_name), _pa.get(_name) or _name, _won, _sc,
                       _reason, _now))
        conn.commit()
        print("[game_end] held %d result(s): %r"
              % (len(_held), [(n, r) for n, _, r in _held][:6]), flush=True)

    # Wins no longer complete claims (removed 17 Aug 2026, 6.16.0).
    # The old rule completed a claim when the NAME next won - which an
    # impostor could satisfy by waiting for the real owner to win.
    # Claims now complete through the deathmatch-ladder proof in the
    # bot, or by the owner deciding by hand.
    # A clan's record is counted per match, not per member. sys_id is what
    # makes that possible - without it there is no way to tell two members of
    # one match apart from two separate matches, so nothing is recorded.
    if sys_id is not None:
        def clans_of(names):
            found = set()
            for n in names:
                c.execute("SELECT clan FROM players WHERE norm_name = ?", (normalize_name(n),))
                r = c.fetchone()
                if r and r[0]:
                    found.add(r[0])
            return found

        won_clans = clans_of(winning_team)
        lost_clans = clans_of(losing_all) - won_clans
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        for tag in won_clans:
            c.execute("INSERT OR IGNORE INTO clan_results (clan, sys_id, won, created_at) "
                      "VALUES (?, ?, 1, ?)", (tag, sys_id, now))
        for tag in lost_clans:
            c.execute("INSERT OR IGNORE INTO clan_results (clan, sys_id, won, created_at) "
                      "VALUES (?, ?, 0, ?)", (tag, sys_id, now))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "updated_winners": updated_winners,
        "updated_losers": updated_losers
    }), 200


# Newest first. Add a new dict here whenever APP_VERSION is bumped.
CHANGELOG = [
    {"version": "6.27.1", "at": "2026-08-18T21:45:00Z", "changes": [
        "Skill in the win-probability model is now judged by each team's two best players rather than the team average - tested head-to-head on 1,015 matches, the star-player signal predicts better, especially early in a match before the score separates.",
    ]},
    {"version": "6.27.0", "at": "2026-08-18T21:20:00Z", "changes": [
        "The win-probability model now knows who is playing, not just the score. Each team's live roster is matched to the leaderboard, and player ratings feed the prediction - so a strong player joining a team raises its chances immediately, most of all early in a match. Training uses each player's rating as it was at the time of each past match, never today's.",
    ]},
    {"version": "6.26.0", "at": "2026-08-18T20:40:00Z", "changes": [
        "The win-probability model now retrains automatically every day on the latest matches, and only replaces itself when the new version scores at least as well. The admin live view shows when it last trained and how accurate it is.",
    ]},
    {"version": "6.25.0", "at": "2026-08-18T20:10:00Z", "changes": [
        "Added an admin-only live view that shows each tracked match's win probability for every team, updating in real time. The estimate comes from a model trained on ~143,000 ten-second snapshots across 1,011 past matches.",
    ]},
    {"version": "6.24.0", "at": "2026-08-18T19:07:15Z", "changes": [
        "Ratings now use a full chess-style Elo scale. Everyone starts at 1000, and most players sit between about 500 and 1800. Nobody can bottom out at zero any more - the lowest a rating can fall is 500. Every existing rating and its full match history was converted exactly, so the standings are unchanged; only the numbers are bigger.",
    ]},
    {"version": "6.23.0", "at": "2026-08-18T03:40:00Z", "changes": [
        "The Discord invite is now on the main leaderboard page too, not only the Clans page.",
    ]},
    {"version": "6.22.0", "at": "2026-08-18T03:10:00Z", "changes": [
        "Each match in the results feed now names the server it was played on, its number, and how long the match was tracked for.",
    ]},
    {"version": "6.21.0", "at": "2026-08-18T02:40:00Z", "changes": [
        "The match-results feed now shows the flipped team too. When a team led big and lost to late reinforcements, it takes no loss - so it used to just vanish from the result, making a three-team match look like two. It is now listed as flipped, with a note, so every side is accounted for.",
    ]},
    {"version": "6.20.0", "at": "2026-08-18T02:00:00Z", "changes": [
        "The Discord match-results feed now shows the teams - winners together, each losing team on its own line - with every player's skill change beside their name.",
    ]},
    {"version": "6.19.0", "at": "2026-08-18T01:20:00Z", "changes": [
        "The Discord server has a live match-results feed now: as each tracked match finishes, the bot posts its winners and losers to a match-results channel. Only matches from here on are posted - the history stays where it is.",
    ]},
    {"version": "6.18.0", "at": "2026-08-18T00:45:00Z", "changes": [
        "Long games are no longer dropped at 90 minutes. A watcher now only gives up a match at the time limit if another game is actually waiting for the slot - if nothing is queued, it stays on your game until it truly ends. And a game being watched stays on the live list however long it runs, instead of vanishing at 90 minutes.",
    ]},
    {"version": "6.17.0", "at": "2026-08-18T00:05:00Z", "changes": [
        "Owner tooling: the site owner can step into a blank sandbox account from Your account to experience the site as a new player - claiming, naming and all - with a banner always offering the way straight back. Nothing done in the sandbox touches the real account.",
    ]},
    {"version": "6.16.0", "at": "2026-08-17T23:20:00Z", "changes": [
        "Claims changed how they complete. Winning a tracked match no longer transfers a name - that could complete an impostor's claim off the real owner's win. Instead: file the claim, then prove the name is yours with one ranked Deathmatch game in Starblast (the bot walks you through it and watches the game's own ladder react, any region). No ECP, or the check fails? The claim waits for the owner to decide by hand.",
    ]},
    {"version": "6.15.0", "at": "2026-08-17T22:30:00Z", "changes": [
        "Name claims can now lean on the game itself: Starblast publishes its deathmatch ladder, and the bot keeps a daily copy. In a dispute, a claimant who says a ranked name is theirs can prove it by playing one deathmatch game while we watch their live rating move - control of the account, not knowledge of a public number. The ladder history also remembers which names an account has worn.",
    ]},
    {"version": "6.14.1", "at": "2026-08-17T21:15:00Z", "changes": [
        "Tightened the flipped-match rule within the hour: on its first evening it was excusing roughly one loss in three, because it counted every new face over a whole match - and teams churn constantly. Now only players who arrive AFTER your team is already dominating, and who then stay at least five minutes, count as reinforcements. Genuine flips are still covered; ordinary comings and goings are not.",
    ]},
    {"version": "6.14.0", "at": "2026-08-17T21:40:00Z", "changes": [
        "Flipped matches no longer punish the team that was winning. If your team led every rival by three quarters again for a solid minute, and then lost to a side that filled up with fresh players mid-match, nobody on your team takes the loss and the winners earn half. ECP players count double towards that, because those are the arrivals that turn a game.",
        "Measured before shipping: a big lead alone reverses in about a third of all matches, so the lead is never enough on its own - the other side has to have visibly reloaded.",
    ]},
    {"version": "6.13.0", "at": "2026-08-17T20:40:00Z", "changes": [
        "The Discord guide now spells out both ways a claim goes through: it is sent to the owner to approve, and it also completes on its own the next time that name wins a tracked match. Claiming a name that is not yours on purpose is a permanent ban from the leaderboard and the server.",
        "Added a private claim-disputes channel for the cases where two people say the same name is theirs - invisible unless you are given the Claim Dispute role, so both sides can be heard in one place.",
    ]},
    {"version": "6.12.0", "at": "2026-08-17T20:15:00Z", "changes": [
        "Claiming a name counts as joining: file a claim and the Discord server opens up straight away, instead of leaving you waiting as a guest until the claim completes on your next tracked win.",
    ]},
    {"version": "6.11.0", "at": "2026-08-17T19:55:00Z", "changes": [
        "You can join the leaderboard entirely from Discord now: the server has a register channel with a 60-second walkthrough, and running /setname there is all it takes. The Player role - which opens the rest of the server - is now given for being on the leaderboard and nothing else, so it means something.",
    ]},
    {"version": "6.10.3", "at": "2026-08-17T19:40:00Z", "changes": [
        "Dropped a leftover NA: the bot now says it is watching team mode, and two page titles that still called this the NA leaderboard were corrected. Every region has been covered for a while - the wording had not caught up.",
    ]},
    {"version": "6.10.2", "at": "2026-08-17T19:25:00Z", "changes": [
        "The bot has a face: a new profile picture (a podium with a gold star), a banner, and a proper About Me on its Discord profile.",
    ]},
    {"version": "6.10.1", "at": "2026-08-17T19:05:00Z", "changes": [
        "The Discord bot is called Starblast Team Mode Skill Bot now, matching the leaderboard's name. Same bot, same commands.",
    ]},
    {"version": "6.10.0", "at": "2026-08-17T18:50:00Z", "changes": [
        "Discord roles hand themselves out now: joining the server makes you a Guest automatically, and the Player role arrives on its own - the moment you sign up on the leaderboard with Discord, the first time you use any bot command, or with the Unlock button. Signed up before joining? You land as a Player straight away.",
    ]},
    {"version": "6.9.1", "at": "2026-08-17T18:20:00Z", "changes": [
        "The Discord server got proper roles: newcomers can read everything and chat in general, and one press of the Unlock button in start-here opens the rest - match-finding, clans, suggestions and voice. Announcements and the guides stay read-only for everyone.",
    ]},
    {"version": "6.9.0", "at": "2026-08-17T17:55:00Z", "changes": [
        "The community has a home: the official Discord server is open, with announcements, a how-it-works guide, match-finding and clan channels, a suggestions box and the bot ready for /rank, /top and /play. The invite lives on the Clans page - come in.",
    ]},
    {"version": "6.8.1", "at": "2026-08-17T17:05:00Z", "changes": [
        "Tightened the ten-minute rule on the losing side: it only excuses players who JOINED after the match was being watched. Being there from the start and leaving early is quitting, and quitting never dodges a loss. Winners are unchanged - under ten minutes of play earns nothing, whenever you arrived.",
    ]},
    {"version": "6.8.0", "at": "2026-08-17T16:35:00Z", "changes": [
        "A match now only counts for the people who actually played it: anyone present for under ten minutes of the watched match is left out of the rating entirely - a winner that brief earns nothing, and a loser that brief is not punished for a defeat that was not theirs. Matches watched for under ten minutes rate everyone as before, since a short watch cannot prove who played.",
    ]},
    {"version": "6.7.0", "at": "2026-08-17T05:50:00Z", "changes": [
        "Closed the protection loss-dodge: a check-in that has been tied to a ship you actually played stays with that match forever - checking into another lobby no longer cancels it, so a lost match cannot be shaken off mid-game. Only a check-in you never played is replaced by your next one.",
        "Playing under one of the game's 44 default commander names (Hari Seldon, HAL 9000, Spock and friends) now switches Protection on automatically and keeps it on - lots of players wear those names at once, so only matches you check into can safely count as yours. Pick a name of your own and Protection is yours to control again.",
    ]},
    {"version": "6.6.0", "at": "2026-08-17T05:15:00Z", "changes": [
        "The changelog announces itself now: when something new has shipped since you last read it, a red dot sits on the menu button. Opening the menu moves it to the Changelog entry; reading the changelog clears it, and everything released since your last visit is tagged NEW at the top of its entry. Your first visit sets the starting point - no dot until something actually changes.",
    ]},
    {"version": "6.5.0", "at": "2026-08-17T04:55:00Z", "changes": [
        "Invitations can be taken back: a Cancel next to the Invited marker on the player's profile, and a new Invited list on Your clan showing every invitation still waiting, each with its own Cancel. A cancelled invitation simply disappears from the player's account.",
    ]},
    {"version": "6.4.3", "at": "2026-08-17T04:20:00Z", "changes": [
        "The invite control on profiles is a proper labelled button now - + Invite to your clan, aligned with the name - with an are-you-sure step before anything is sent. Once sent it settles into an Invited marker, and it stays that way on later visits while the invitation is open.",
    ]},
    {"version": "6.4.2", "at": "2026-08-17T03:55:00Z", "changes": [
        "Inviting players who are already in another clan is OFF - it went out earlier tonight by misunderstanding and lasted under an hour. Invitations are for players without a clan; anyone in a clan leaves it first, by their own hand. The green invite icon stays, on clanless profiles only, and any cross-clan invitations filed in that hour were cancelled.",
    ]},
    {"version": "6.4.1", "at": "2026-08-17T03:35:00Z", "changes": [
        "For a few minutes after 6.4.0 the red counter read zero for everyone - the new match counter was asked one query too late, after its database handle had closed. Caught by the tests and fixed on the spot.",
    ]},
    {"version": "6.4.0", "at": "2026-08-17T03:05:00Z", "changes": [
        "Every match you play announces itself now: win or lose, the result counts on the red badge and glows as NEW in Recent matches on Your account the first time you look. Once seen, it goes back to normal.",
        "Clan leaders can invite players who are already in another clan - the invite is the green + next to the name on their profile, it waits on that player's own account page, and moving is entirely their choice.",
        "The Remove clan tag button now only appears for the name's owner and that clan's own staff. It always refused everyone else - but it should never have been offered to them either.",
    ]},
    {"version": "6.3.0", "at": "2026-08-17T02:10:00Z", "changes": [
        "Clan invitations finally have somewhere to land: Your account now has an Invites & updates box where you accept or decline, and a red counter on your name in the header shows how many things are waiting for you.",
        "Decisions come back to you in the same box - name claims, clan applications and requests to run a clan - whether they were decided on the site or in Discord.",
        "The Apply button on clan pages works now; it was never being shown. And a clan leader visiting the profile of a player who has no clan can invite them from right there.",
    ]},
    {"version": "6.2.1", "at": "2026-08-16T21:55:00Z", "changes": [
        "A nearly-empty leftover lobby could trap its region's watcher in a loop: watched for a minute, released as not a match, and immediately watched again - fourteen times in half an hour tonight, which parked the whole Asia region since it runs a single watcher. A released leftover now gets a proper cool-down before anyone looks at it again; if its match actually ends in the meantime, the result is still scored within seconds.",
    ]},
    {"version": "6.2.0", "at": "2026-08-16T20:35:00Z", "changes": [
        "A match that ends while no watcher is attached to it is now scored within seconds of it vanishing from the live server list, instead of waiting for the next restart - one result nearly slipped away exactly that way today.",
        "The one exception: if such a match would be decided by a score margin too close to call after minutes of nobody watching, the result is set aside for review instead of guessed - kept, never thrown away.",
    ]},
    {"version": "6.1.1", "at": "2026-08-16T20:10:00Z", "changes": [
        "A watcher could keep watching a lobby that had already ended - the game kept feeding it leftover data, so the finished match sat unscored until the watcher's saved progress went stale and the result was lost. Watchers now double-check the live server list every few minutes, however healthy things look, and a finished match is scored within minutes.",
    ]},
    {"version": "6.1.0", "at": "2026-08-16T19:45:00Z", "changes": [
        "About a third of the watchers now speak to the browser directly instead of through the layer that has been failing all week. Every call they make has a hard time limit, so this kind of watcher cannot freeze - if the browser dies on one, it walks away in seconds. Running side by side with the old kind for a few days; if they prove more reliable, they all switch.",
    ]},
    {"version": "6.0.2", "at": "2026-08-16T18:50:00Z", "changes": [
        "Found why watchers were dying on arrival: abandoning a dead browser connection quietly poisoned the thread it ran on, and every later watcher given that thread died instantly. Threads now clean themselves on the way in. All five watchers are up.",
    ]},
    {"version": "6.0.1", "at": "2026-08-16T18:10:00Z", "changes": [
        "Coverage quietly dropped to one watcher this afternoon: new watchers were dying the moment they started, without a trace. Deaths are now logged with their cause, and ten in a row forces a clean restart on its own.",
    ]},
    {"version": "6.0.0", "at": "2026-08-16T08:30:00Z", "changes": [
        "This is the Starblast Team Mode Skill Leaderboard now - a leaderboard you climb, not a tracker you have to think about. The Discord bot speaks the same language. Older entries keep their original wording. Everything below is what version 5 built:",
        "Names are read from the game itself, not from the screen. The board restarted on 10 August, and every result since is exact - no misread letters, no split identities.",
        "The rating rules settled: a losing team pays as its fullest line-up so leaving early dodges nothing; joining a watched match late counts half; a score of exactly zero is never rated; and a winner who was there from the start and stayed is paid even after leaving before the end.",
        "Clans, end to end: request one, the owner approves, claim your tag - shown exactly as you style it. Rosters, ranks, invite links, applications, regions, and one Your clan page to run it all.",
        "Two names per account: the account name your rating lives under, and the play name your ship wears. Claims move a name you actually play to your account, and Protection makes your rating count only matches you checked into.",
        "Eight languages, the Info page fully translated in all of them.",
        "A new layout: your name, rating and rank in the header on every page, navigation at the bottom on phones with Play at its centre, a podium over the leaderboard, and a Your account page with your stats, history and settings together.",
        "A Discord bot with 30 commands that does nearly everything the site does - check in, claim, browse the boards - with no browser and no sign-in.",
        "Privacy: no IP addresses are stored, anywhere, at all.",
        "And a long war on lost matches, won in stages: watchers survive restarts through checkpoints, a match that ends unwatched is scored from its last saved state, stuck watchers are caught within minutes, and lingering spectators cannot hold a finished match open.",
    ]},
    {"version": "5.98.2", "at": "2026-08-16T07:45:00Z", "changes": [
        "Players who never scored no longer count as still playing when deciding a match is over, so lingering spectators cannot hold a finished match open.",
    ]},
    {"version": "5.98.1", "at": "2026-08-16T07:20:00Z", "changes": [
        "A watched match is now resumed after a restart even when only a couple of players remain in the lobby - winding down no longer makes a finished match invisible.",
    ]},
    {"version": "5.98.0", "at": "2026-08-16T06:55:00Z", "changes": [
        "A match that ends while its watcher is down is now scored anyway, from the watcher's last saved state. Until now those results were simply lost - that is what happened to two winners this week.",
        "A watcher that loses its browser connection now walks away instantly instead of freezing for twelve minutes while shutting down.",
    ]},
    {"version": "5.97.0", "at": "2026-08-16T04:40:00Z", "changes": [
        "Claiming a clan now asks you to set your account name first, so every clan shows who runs it from day one.",
    ]},
    {"version": "5.96.1", "at": "2026-08-16T02:50:00Z", "changes": [
        "The ! note now lists current known issues instead of the old testing text.",
    ]},
    {"version": "5.96.0", "at": "2026-08-16T02:20:00Z", "changes": [
        "Signed in, the top corner now shows your account box - name, rating, rank - with Sign out under it, instead of a line of text. The testing note is a red ! beside the leaderboard title.",
    ]},
    {"version": "5.95.0", "at": "2026-08-16T01:55:00Z", "changes": [
        "The testing banner is now a small ! beside the Leaderboard title - hover it for the note.",
    ]},
    {"version": "5.94.0", "at": "2026-08-16T01:40:00Z", "changes": [
        "The navigation is four tabs now: Leaderboard, Play, Clans, and a menu holding Your account, Your clan, Report, Info and Changelog.",
    ]},
    {"version": "5.93.0", "at": "2026-08-16T01:15:00Z", "changes": [
        "Shorter words everywhere. Pages now say things once and briefly; the Info page keeps the full explanations.",
    ]},
    {"version": "5.92.0", "at": "2026-08-16T01:20:00Z", "changes": [
        "The site has a new layout. Your name, rating and rank now sit in the header on every page, the way a game shows you your own trophies. On a phone the navigation moved to the bottom of the screen where your thumb already is, with Play in the middle.",
        "The leaderboard opens with the top three on a podium and a proper Play button instead of dropping you straight into a wall of rows.",
        "Settings has become Your account: your rating, rank, record, per-region results and recent matches, with your name, claims and Protection settings on the same page. Old /settings links land there.",
    ]},
    {"version": "5.91.0", "at": "2026-08-15T23:20:00Z", "changes": [
        "Withdrawing a claim now gives you back that day's try. Claims are limited to three a day, and until now a withdrawn one still counted - so filing a claim, taking it back to fix a note, and filing again could lock you out for the day with nothing actually waiting.",
        "The lockout message also told the wrong story - it said you had three claims waiting when you had none. The daily limit and the waiting limit now each say which one you hit.",
    ]},
    {"version": "5.90.0", "at": "2026-08-15T22:15:00Z", "changes": [
        "Today's instability turned out to be the machine running out of memory. Each watched match runs a full copy of the game, about half a gigabyte each, and seven at once was more than the server holds - the browser quietly killed parts of itself to cope, which is what kept knocking watchers over.",
        "Three changes: the tracker watches five matches at a time instead of seven, so it fits; the game pages no longer load advertising and tracking scripts, which were costing real memory on frames nobody ever sees (about a gigabyte freed); and a watcher that dies can no longer leave its copy of the game running behind it.",
        "Five matches watched reliably beats seven watched badly - this morning it was effectively two.",
    ]},
    {"version": "5.89.0", "at": "2026-08-15T20:35:00Z", "changes": [
        "Found and fixed what has been eating matches all day. All seven watchers share one browser, and when a watcher lost its connection to it the code treated that as a passing glitch and carried on - so the watcher then sat frozen, holding a live match, until the whole tracker was restarted twelve minutes later. That is why games ended with nothing recorded.",
        "A lost connection now ends that one watch immediately. The lobby goes straight back into the pool and another watcher picks it up where the last one left off, so one failure costs a few seconds on one match instead of stalling everything.",
        "If you won a match today between about 04:30 and 20:30 and it never appeared, this is why. Those results cannot be recovered - the tracker never saw how they ended.",
    ]},
    {"version": "5.88.0", "at": "2026-08-15T13:25:00Z", "changes": [
        "Fewer matches than usual were tracked between about 04:30 and 13:15 today. Five of the seven watchers lost their connection to the game within seconds of each other and then sat holding their lobbies without reading anything, so only two were doing any work. Four matches they were holding ended without being scored. If you won one in that window and nothing happened, that is why.",
        "The safeguard meant to catch this only asked whether ANY watcher was still reading, and the two healthy ones kept answering yes for nearly nine hours. It now checks each watcher separately, so one getting stuck is caught within twelve minutes instead of going unnoticed all day.",
    ]},
    {"version": "5.87.0", "at": "2026-08-15T04:45:00Z", "changes": [
        "Clan tags can be up to 16 characters now. The old limit was 6, counted on the plain-letter reading rather than on what you type - so FV HAWKS came out as FVHAWKS, seven characters, and was turned away as too long. Two characters is still the minimum.",
    ]},
    {"version": "5.86.0", "at": "2026-08-15T04:05:00Z", "changes": [
        "You are now credited for a win if you were in the match from the moment it started being watched and stayed in it, even if you had left before the very end. Only players still on screen in the final moment used to be paid. That is fair when a match ends on a station kill, but most matches wind down instead - and then who happens to still be on screen is close to random. One player was there from the first read, won, and got nothing, while somebody who wandered into the emptying lobby was credited.",
        "This only adds people. Nobody who was paid before is paid less, and joining late still counts half as it always did.",
    ]},
    {"version": "5.85.0", "at": "2026-08-14T23:20:00Z", "changes": [
        "The Info page is now translated too. Picking a language used to change the buttons and headings while every explanation stayed in English, which made the language picker close to useless for the people who most needed it. All of it - every card on Info - is now in Espanol, Francais, Deutsch, Italiano, Russian, Vietnamese and Chinese as well.",
        "That page also had two things on it that were no longer true: it told you to pick a language at the bottom of the page, which moved to the header yesterday, and it did not mention that a name reading the same as one already on the board is offered to you to claim.",
    ]},
    {"version": "5.84.0", "at": "2026-08-14T22:55:00Z", "changes": [
        "The language picker has moved out of the footer and into the header, next to the sign-in buttons, where it can be reached without scrolling past the whole page.",
        "Accessibility, properly this time. The plus and cross buttons on Your clan now say what they do and which member they belong to instead of being read out as punctuation, the protected tick and the clan crown have names, keyboard focus is visible everywhere rather than only on one menu, and the dimmest grey has been lightened to clear the contrast threshold it was under.",
    ]},
    {"version": "5.83.0", "at": "2026-08-14T22:45:00Z", "changes": [
        "Your clan now says so when you have no leaderboard name of your own. Running a clan does not require one, but without it you never appear on your own roster and the clan reads as though nobody runs it - which was true of two of the five leaders here and explained nowhere.",
    ]},
    {"version": "5.82.0", "at": "2026-08-14T22:35:00Z", "changes": [
        "The leaderboard now says the thing people ask about most, right above the table: only matches shown as tracked on Play count towards your rating. Check before you join.",
        "First visit shows a one-line New here strip - open Play, join a tracked match, win - with a cross to dismiss it for good.",
        "A line by the search box explains that typing filters the page you are on while Search all looks through the whole board.",
    ]},
    {"version": "5.81.0", "at": "2026-08-14T22:20:00Z", "changes": [
        "Saving your account name now notices when somebody already on the leaderboard reads the same as the name you typed - a plain name against a styled version of it. It names that row, says what record it holds, and offers to claim it, because that row is where your matches are being recorded. Two players spent today at 0-0 while their results piled up on a row they did not own.",
        "If the similar name is genuinely not you, Use my name anyway saves the name exactly as you typed it.",
    ]},
    {"version": "5.80.1", "at": "2026-08-14T16:55:00Z", "changes": [
        "The member list on Your clan reads properly now. Skill, record, win rate and join date each sit under their own label instead of running together on one line, and a row lights up as you move over it so it is clear which member the buttons belong to.",
    ]},
    {"version": "5.80.0", "at": "2026-08-14T16:50:00Z", "changes": [
        "An invite link now asks for both names in order: sign in, pick your account name - the one you appear under on the leaderboard, and we suggest the name you play under - then say what you are called in game right now, and accept. That second name is how your ship is spotted in a lobby.",
        "Leave the second one blank and your account name is used, which is what most people want anyway.",
    ]},
    {"version": "5.79.1", "at": "2026-08-14T06:20:00Z", "changes": [
        "Corrected the Info page, which had the two names the wrong way round. Your account name is the leaderboard row that is yours; your play name is what you are called in game right now. It is the play name that has to match your ship, and checking in is what carries the result from one to the other.",
    ]},
    {"version": "5.79.0", "at": "2026-08-14T06:10:00Z", "changes": [
        "The Info page has been rewritten. It is shorter, in plainer words, and it now covers the parts of the site that did not exist when it was written - clans, ranks, applying, invite links, the Your clan tab, languages and the Discord bot.",
        "It opens with the three steps that actually get you on the leaderboard, and ends with the four questions people ask most.",
    ]},
    {"version": "5.78.0", "at": "2026-08-14T06:00:00Z", "changes": [
        "Settings now asks once for the name you play under, instead of making you choose between two boxes. If nobody has that name it is simply yours; if it is already on the leaderboard the page offers to claim it and explains why that takes a tracked win.",
        "Nothing about existing accounts changed - the same two rules, the same refusals, asked as one question.",
    ]},
    {"version": "5.77.0", "at": "2026-08-14T06:15:00Z", "changes": [
        "Clan members with no special rank now read as Member rather than leaving the rank column blank. Everyone in a clan is a member; some are also something else.",
    ]},
    {"version": "5.76.2", "at": "2026-08-14T06:05:00Z", "changes": [
        "The testing notice no longer floats beside the page on a wide screen, where it sat on top of the content. It is the same narrow, centred note at every window size.",
    ]},
    {"version": "5.76.1", "at": "2026-08-14T05:55:00Z", "changes": [
        "The testing notice is genuinely narrower now. The last attempt resized a different notice that is not the one on screen.",
    ]},
    {"version": "5.76.0", "at": "2026-08-14T05:50:00Z", "changes": [
        "A name that opens with a clan's own styled tag now joins that clan when it is created, even with no space after it - ꞨⱤ✧ʲᵃᶜᵏᶦᵉᵉ is wearing ꞨⱤ✧ as plainly as anyone. Nobody types a clan's exact styling by accident.",
        "Clans whose tag is written in plain letters get no such shortcut, so COVID19 still has nothing to do with COV.",
    ]},
    {"version": "5.75.2", "at": "2026-08-14T05:40:00Z", "changes": [
        "The testing notice is narrower now. It ran the full width of the page and crowded what was under it.",
    ]},
    {"version": "5.75.1", "at": "2026-08-14T05:30:00Z", "changes": [
        "The clan tag is now taken out of a shown name wherever it sits, not only at the front - so OSAMA ꞨⱤ✧ reads as OSAMA with the tag on its badge, instead of carrying it twice.",
    ]},
    {"version": "5.75.0", "at": "2026-08-14T05:20:00Z", "changes": [
        "A clan tag now counts wherever it stands on its own in a name, not only at the front - so OSAMA ꞨⱤ✧ is wearing the tag just as ꞨⱤ✧ OSAMA is, and joins the clan when it is created.",
        "A tag buried inside a longer word still does not count. COVID19 is not in COV and SRSLY is not in SR - matching on part of a word is what got clan detection switched off in the first place.",
    ]},
    {"version": "5.74.4", "at": "2026-08-14T05:35:00Z", "changes": [
        "The tag taken off the front of a member's shown name is now the styled tag exactly - so a star that is part of the tag comes off with it, and a crown that is part of the name stays. Reading letters alone could never tell those apart.",
    ]},
    {"version": "5.74.3", "at": "2026-08-14T05:25:00Z", "changes": [
        "Stripping the clan tag off the front of a member's shown name now takes only the tag's own letters. Stars, crowns and other decoration next to the tag belong to the player and stay on the name - a leading crown was being swallowed along with the tag.",
    ]},
    {"version": "5.74.2", "at": "2026-08-14T05:10:00Z", "changes": [
        "The approval card the site owner sees now shows a requested clan tag exactly as it was typed - ꞨⱤ, not SR. It was being simplified on the way in, which made the request look like something the player never wrote.",
        "The claim box no longer says to paste the tag exactly as it appears in your name - for names with the tag woven into decoration there is no such thing, and following the old wording created a clan named after a whole player name. It now asks for the tag as you want it shown.",
        "The SR clan, born under that misunderstanding as SRT47, is now the SR clan showing as ꞨⱤ, which is what its leader asked for in every one of his requests.",
    ]},
    {"version": "5.74.1", "at": "2026-08-14T04:55:00Z", "changes": [
        "Fixed: a clan tag containing subscript letters could end up with a lowercase letter in its key, making SRt47 and SRT47 two different clans. Keys are all capitals again, and the one affected clan was re-keyed.",
        "Fixed: a newly created clan never stored the tag as its leader typed it, so it showed the plain-letter form. New clans now keep the typed form, like the older ones do.",
        "When a clan request is approved or turned down but the player cannot be messaged - usually because they are not in the Discord server - the owner is now told, instead of the message quietly going nowhere.",
    ]},
    {"version": "5.74.0", "at": "2026-08-14T04:00:00Z", "changes": [
        "A turned-down clan request no longer closes the door. The Clans page and /clanrequest offer the form again, with a note that the last answer was no - so asking again is allowed, and done knowingly.",
    ]},
    {"version": "5.73.2", "at": "2026-08-14T03:45:00Z", "changes": [
        "The clan tag's box now sits level with the name beside it. It was hanging below the line, because names here are all capitals and the box was aligned to where lowercase letters would descend.",
    ]},
    {"version": "5.73.1", "at": "2026-08-14T03:40:00Z", "changes": [
        "The clan tag in front of a name is now the same size as the name itself, wherever the pair appears - it was a small chip before and read like a footnote.",
    ]},
    {"version": "5.73.0", "at": "2026-08-14T00:40:00Z", "changes": [
        "Clan tags on the leaderboard now show exactly as their leader wrote them - Ⱡ7 rather than L7. The plain-letter form is only used behind the scenes, for links and for telling stylings of the same tag apart.",
        "Search now reads symbol letters. Typing L7 finds Ⱡ7, DARKWARRIOR finds a name written in fancy lettering, and pasting the fancy form still works. Names in Cyrillic or Chinese are searched as themselves.",
        "A member whose in-game name carries the tag - however it is spelt, (Ⱡ7) or 「L7」 or ₵ØV - has it taken off the shown name, since the badge in front already says it. Ratings still follow the real name underneath; only what you see changed.",
    ]},
    {"version": "5.72.0", "at": "2026-08-14T00:10:00Z", "changes": [
        "The look now follows starblast.io itself, taken from the game's own menu: the Play typeface, its pale ice-blue text and cyan glow, flat translucent panels with thin borders, and square corners. The glossy glass of the last version is gone.",
        "The background drifts. Two layers of stars move at different speeds and one of them twinkles, the way the game's menu does, and the title carries the game's slow pulse. If your system asks for reduced motion, everything holds still.",
    ]},
    {"version": "5.71.0", "at": "2026-08-13T23:59:00Z", "changes": [
        "A new look for the whole site: deep-space background with painted nebulae and stars, glass panels, and Starblast's ion greens and blues. The layout, the pages and every control are exactly where they were - only the skin changed.",
        "Skill numbers glow, the top tab bar is glassy, medals are gilded, and your own row on any board is tinted. All of it is one stylesheet - no images, no fonts to download, nothing slower than before.",
    ]},
    {"version": "5.70.1", "at": "2026-08-13T21:35:00Z", "changes": [
        "Fixed: the + and Remove buttons on Your clan did nothing at all. The player's name was written into the button in a way that ended the HTML attribute early, so there was no working handler to run - names full of symbol letters made it obvious.",
        "Remove is now a small x the same size as +, and asks before it does anything: press it and you get Yes, remove them or No, keep them.",
    ]},
    {"version": "5.70.0", "at": "2026-08-13T21:30:00Z", "changes": [
        "Ranks are now given from a + button next to the member on Your clan, which opens a short list of what you can make them. Typing out a name to promote somebody you are looking at was silly, and these names are full of letters nobody can type.",
        "The + only appears where a rank could actually be changed - never on yourself, never on the leader, and not on a co-leader unless you are the leader.",
    ]},
    {"version": "5.69.0", "at": "2026-08-13T21:20:00Z", "changes": [
        "A clan's own page is now purely public: the roster, its numbers, and who runs it. Everything a leader does - the invite link, applications, adding and removing, ranks, the region, deleting - is on Your clan, and only there.",
        "The two things that belong to the visitor rather than to the clan stay on the public page: asking to join, and leaving a clan you are in.",
    ]},
    {"version": "5.68.0", "at": "2026-08-13T20:55:00Z", "changes": [
        "The Clans page no longer manages your clan - the roster, the invite link and the rest of it are on the Your clan tab, and having them in two places only made it harder to find either.",
        "Your clan always shows who is waiting to join, and says so plainly when nobody is. It used to hide the whole section when the list was empty, which read as though the page could not do it at all.",
    ]},
    {"version": "5.67.0", "at": "2026-08-13T20:35:00Z", "changes": [
        "People who run a clan now have a Your clan tab of their own. It holds the invite link, anyone waiting to join, the roster, ranks, the region and deleting the clan - one page instead of pieces spread across two.",
        "The tab only appears if you actually run a clan, and each part of it only appears to the ranks allowed to use it: moderators see the roster, co-leaders also see the link and the region, and only the leader can delete.",
    ]},
    {"version": "5.66.0", "at": "2026-08-13T04:50:00Z", "changes": [
        "An invite link now takes you the whole way. Sign in with Discord, type the name you play under, and accept - all on the one page. It used to stop after signing in and send you off to Settings to set a name, then back again.",
        "If the name you type is already on the leaderboard, the page offers to claim it instead and explains what that means, rather than just refusing.",
    ]},
    {"version": "5.65.1", "at": "2026-08-13T04:30:00Z", "changes": [
        "An invite link now takes you straight to the Discord sign-in instead of showing a page with a sign-in button on it. Once you are back, the clan and the Accept button are waiting. If you are already signed in the link opens on the Accept button directly, as before.",
    ]},
    {"version": "5.65.0", "at": "2026-08-13T04:00:00Z", "changes": [
        "Clan leaders and co-leaders can now create an invite link and post it wherever their clan talks. Anyone who opens it signs in with Discord and joins with one press - no need to be added by name first, and no need for the leader to know what you play as.",
        "A link works for as many people as open it and stops working after seven days. Leaders can revoke it at any time, and creating a new one always retires the old one, so a link that has got out can be replaced immediately.",
        "Joining through a link follows the same rules as every other way in: you keep your own name, and if you are already in a clan you have to leave it yourself first. Nobody is moved between clans without doing it themselves.",
    ]},
    {"version": "5.64.0", "at": "2026-08-13T00:54:00Z", "changes": [
        "The tracker now reports two coverage figures instead of one. The old number counted every lobby that closed, including ones that were never old enough or busy enough to be worth attaching to - so it could never reach 100% however well the tracker did its job.",
        "The new Watchable figure counts only the matches the tracker was allowed to watch, which is the number that actually says whether it is keeping up. The old figure is still printed beside it.",
        "Fixed: starting a worker stopped the tracker's main loop for twelve seconds, and during that pause it noticed nothing - not a match ending, not another lobby waiting for a worker. It happened twelve times in two hours. Workers are still started twelve seconds apart, but the loop now keeps watching while they start.",
    ]},
    {"version": "5.63.0", "at": "2026-08-12T23:00:00Z", "changes": [
        "The leaderboard is now shown 50 players at a time instead of every player at once. The page was 1.2 MB of one table and took several seconds to arrive; it is now about a fortieth of that.",
        "A place on the board is still the place on the whole board - the player ranked 412th is #412 on page 9, not #12.",
        "The search box still filters as you type, but now only across the page you are on. Search all players searches every player on the board and pages through what it finds.",
        "The region link on a player's row still opens that region's board at that player, whichever page they turn out to be on.",
    ]},
    {"version": "5.62.1", "at": "2026-08-12T22:05:00Z", "changes": [
        "Fixed the last few places on a clan page that printed the plain-letter form of a tag instead of the way its leader wrote it - the Join heading and the line telling you which clan you are in.",
    ]},
    {"version": "5.62.0", "at": "2026-08-12T21:20:00Z", "changes": [
        "Fixed: a clan tag written with symbol letters lost them. ₣ⱠⱤ⇝ was read as ⱠⱤ and ₵ØV as ØV, because a currency sign is punctuation as far as the computer is concerned - so the F and the C were thrown away with the brackets.",
        "Symbol letters are now read as the letters they stand for, so ₣ⱠⱤ⇝ is the clan FLR and ₵ØV is COV. Tags written in Cyrillic or Chinese are kept as they are.",
        "A clan is now shown the way its leader wrote it. The plain-letter form is still what the site matches on, so every styling of a tag is one clan, but what you see is what was typed.",
    ]},
    {"version": "5.61.0", "at": "2026-08-12T21:05:00Z", "changes": [
        "The site owner can now grant a name claim straight from the Discord message, instead of the claimant having to win a tracked match first. Claims still complete on their own that way - this is a shortcut, not a replacement.",
        "Granting by hand makes every check the automatic path makes: the name must not already belong to someone, and the account must be under its name limit.",
    ]},
    {"version": "5.60.0", "at": "2026-08-12T20:55:00Z", "changes": [
        "New claims are now sent to the site owner on Discord as they are filed. Nothing has to be approved - a claim still completes on its own when the name next wins a tracked match - but it is now visible while it is happening.",
        "A claim on a name can now be withdrawn while it is still waiting, on Settings or with /claimwithdraw in Discord. Until now a claim sent by mistake could only be waited out.",
        "Settings shows the claims you have waiting, which it never did before - you had to remember what you had asked for.",
    ]},
    {"version": "5.59.0", "at": "2026-08-12T20:30:00Z", "changes": [
        "The site can now be read in Spanish, French, German, Italian, Russian, Vietnamese and Chinese as well as English. Pick a language at the bottom of any page; it is remembered, and the site also follows your browser's language the first time you arrive.",
        "Buttons, table headings and labels are translated. The longer explanations stay in English for now, so that there is one copy of them to keep accurate.",
    ]},
    {"version": "5.58.2", "at": "2026-08-12T20:15:00Z", "changes": [
        "The Clans page now links straight to your own clan's page, where ranks and the region live. Both pages offered to manage a clan and only one of them could do all of it, which was needlessly confusing.",
    ]},
    {"version": "5.58.1", "at": "2026-08-12T20:10:00Z", "changes": [
        "Fixed: claiming a clan and redeeming a code were still shown to people who already run a clan, and to people who had not been approved. Signing in was re-showing those two boxes after the page had already decided to hide them.",
        "Fixed: the example tag under the claim box printed its own escape codes instead of the characters.",
    ]},
    {"version": "5.58.0", "at": "2026-08-12T20:20:00Z", "changes": [
        "Clans now have ranks. A leader can appoint co-leaders and moderators, on the clan page or with /clanrole in Discord.",
        "A moderator can remove ordinary members, and nothing else - not the region, not the roster, not the clan.",
        "A co-leader can do everything the leader can except delete the clan, remove another co-leader, or appoint one. Appointing co-leaders stays with the leader, because a co-leader cannot remove one - they would be creating power they could not take back.",
        "Nobody can remove someone of their own rank or above, which is what keeps the leader safe and stops two equals removing each other.",
    ]},
    {"version": "5.57.0", "at": "2026-08-12T20:00:00Z", "changes": [
        "The Clans page now starts with requesting a clan rather than claiming one. You ask, the site owner approves it on Discord, and only then do you name your tag - which is how it already worked in Discord, so the two now match.",
        "A request made on the website reaches the owner on Discord by itself. The bot collects new requests and shows them with Approve and Deny on the message.",
        "Claiming a tag and redeeming a one-time code are still there, but only appear once you have been approved - they were the first thing on the page before, for people who could not yet use them.",
    ]},
    {"version": "5.56.0", "at": "2026-08-12T19:40:00Z", "changes": [
        "A clan member's leaderboard name now carries the clan tag in front of it, everywhere the name is shown - the leaderboard, their profile, and the clan roster. The tag is a link to the clan.",
        "The tag is put on when the name is displayed, from the clan the player is in, rather than written into the name itself. Join a clan and it appears; leave and it goes. The stored name stays exactly as the game reported it, which is what every match result is matched against.",
        "Joining a clan no longer changes the name you declare you play as. That was the wrong place for it.",
    ]},
    {"version": "5.55.0", "at": "2026-08-12T19:30:00Z", "changes": [
        "You can apply to join a clan, and its leader decides. Applications show up on the clan page and are sent to the leader on Discord with the applicant's rank, skill, record and win rate, with Accept and Deny on the message itself.",
        "Being accepted puts the clan tag on the front of the name you say you play as, and it stays there: change your name while in the clan and the tag goes back on the front automatically.",
        "The tag is added to your declared name only. Your leaderboard name is whatever the tracker read out of the game, and rewriting that here would stop your matches landing on your account - so to wear the tag in game you still have to change it in Starblast.",
    ]},
    {"version": "5.53.0", "at": "2026-08-12T19:10:00Z", "changes": [
        "Clan leaders can now say which region their clan plays in - North America, Europe or Asia. It shows on the clan page and in the clan table, and clicking it opens that region's leaderboard.",
        "The region is set by the leader on the clan page or with /clanregion in Discord, and can be cleared again. It is never guessed from where members happen to have played: it is the clan's own statement about itself.",
    ]},
    {"version": "5.52.0", "at": "2026-08-12T18:55:00Z", "changes": [
        "Clans are now ranked against each other by the average skill of their members, in the same kind of table as everything else on the site - medals for the top three, size, combined record and win rate, and every row opens the clan.",
        "Ranking starts at two members. A one-person clan's average is only that person's rating, so a single strong player would sit above every real clan and the table would say nothing. Smaller clans are still listed underneath, just not placed.",
        "Every member now shows the date they joined the clan. The date is stamped wherever the joining happens - the site, the Discord bot, or the tracker spotting a tag in someone's name - so no route can forget it.",
        "Members who were already in a clan before dates were kept show a dash rather than an invented date.",
    ]},
    {"version": "5.51.0", "at": "2026-08-12T18:17:00Z", "changes": [
        "A clan page is now something you can use, not just read. Members are ranked by skill and clicking one opens their profile, admins are marked, and if you run the clan the controls to add and remove members are on the page itself.",
        "You can leave a clan you are in, including if you run it - running a clan and being on its roster are separate things, so leaving does not cost you the clan.",
        "Clan leaders are shown as such on their own profile page.",
    ]},
    {"version": "5.50.0", "at": "2026-08-12T18:06:00Z", "changes": [
        "A clan leader is now on their own roster. If you had not set a name yet when you claimed the clan, you are added the moment you set one rather than having to add yourself.",
    ]},
    {"version": "5.49.1", "at": "2026-08-12T17:53:00Z", "changes": [
        "Tightened which players a new clan picks up. A tag now has to stand on its own in the name - in brackets, as the first word, or as the whole name - so claiming COV takes the players wearing [COV] and not somebody called COVID19.",
    ]},
    {"version": "5.49.0", "at": "2026-08-12T17:47:00Z", "changes": [
        "Running a clan is now something you ask for. Use /clanrequest in Discord and the site owner gets it as a message with an approve or deny button; you hear back either way. Until you are approved you cannot create a clan, and a refusal stands until it is looked at again.",
        "When an approved leader creates their clan, every player already using that tag who has no account joins it automatically - the roster is there from the start. Anyone who does have an account is still invited and has to accept.",
        "All existing clans have been cleared so the new system starts from nothing.",
    ]},
    {"version": "5.48.0", "at": "2026-08-12T16:25:00Z", "changes": [
        "Clan leaders who cannot pass the usual check - your name has to already carry the tag - can now be given a one-time code instead. Redeem it on the Clans page or with /clanredeem and the clan is yours, no matter what your name says.",
        "A clan can be deleted by whoever runs it, from the website or Discord. Members are released and keep their ratings and match history in full; only the clan itself goes.",
    ]},
    {"version": "5.47.0", "at": "2026-08-12T16:07:00Z", "changes": [
        "Clans are reopening, and you claim yours yourself: paste your tag on the Clans page or use /clanclaim in Discord. To claim a tag you need a name of your own that already plays under it, so nobody can take a clan that is not theirs.",
        "Once a clan is yours you can add and remove members from either the website or Discord. Anyone with an account gets an invitation they have to accept rather than being put in a clan without being asked.",
        "Tags that are not plain English letters work now. [G\u039e], \u20b5\u00d8V, \u0141S and similar were being cut down to a single letter and could not be claimed at all.",
    ]},
    {"version": "5.46.0", "at": "2026-08-12T15:28:00Z", "changes": [
        "You can message the bot directly now. Every command works in a DM with it - press Play, check your rank, set your name, report something - without posting in a channel. Useful if you would rather not have your rating discussed in public.",
        "The commands moved from being registered in the one server to being registered everywhere, which is what makes DMs possible. If a command looks briefly missing or doubled up right after this, it is Discord catching up and it settles on its own.",
    ]},
    {"version": "5.45.0", "at": "2026-08-12T15:17:00Z", "changes": [
        "Commands the bot mentions are clickable now. Where it used to tell you to run /setname, that is a link you press to open the command with nothing to retype - and /help is a full list of them, all clickable, grouped by what you are trying to do.",
    ]},
    {"version": "5.44.1", "at": "2026-08-12T05:22:00Z", "changes": [
        "Rank numbers on the leaderboard sat off to one side of their little grey box. The box was being padded from the inside, which pushed the number to its right edge.",
    ]},
    {"version": "5.44.0", "at": "2026-08-12T04:54:00Z", "changes": [
        "/play, /gamename, /claim and /report now look like the rest of the bot. The match list shows a green or amber dot and the region flag for each game, and replies are proper cards - green when something worked, red when it did not.",
        "/play was offering buttons for the wrong matches. The list arrives with games already being watched at the top, so the four buttons were going to half-elo matches while the full-elo ones - worth twice as much - got none. Full elo now comes first, and there are more buttons.",
    ]},
    {"version": "5.43.0", "at": "2026-08-12T04:42:00Z", "changes": [
        "The bot\u2019s cards were redrawn properly. A player card leads with the rating, shows recent form as a row of green and red squares, and lists each region with its flag. The stripe down the side turns green or red with how the last few matches went.",
        "The leaderboard shows medals for the top three and reads as a list rather than a cramped grid, which is far easier on a phone.",
        "A rank now says what it is out of - #4 of 1990 rather than just #4.",
    ]},
    {"version": "5.42.0", "at": "2026-08-12T04:33:00Z", "changes": [
        "The bot looks like a 2026 bot now. Player lookups, match history and the leaderboard are drawn with Discord\u2019s newer message layout - a proper card with an accent stripe, sections and separators - instead of the old plain box.",
        "Nothing about what they show has changed, only how they look. The leaderboard and the region breakdown are still lined-up tables, because Discord has no real table and a monospace block is the only thing that stays aligned on every device.",
    ]},
    {"version": "5.41.0", "at": "2026-08-12T04:23:00Z", "changes": [
        "/rank in Discord now shows where someone actually plays - their record and rating in each region, the same split the profile page has - and has buttons to open their recent matches or their full profile.",
    ]},
    {"version": "5.40.0", "at": "2026-08-12T04:17:00Z", "changes": [
        "/top in Discord can now show the combined board across every region, the same view the website opens on, and pages through it with Next and Back instead of stopping at the first handful.",
        "/changelog in Discord shows what changed recently, so you do not have to open the site to find out.",
    ]},
    {"version": "5.39.0", "at": "2026-08-12T04:08:00Z", "changes": [
        "Three more things you can do from Discord instead of the site: /gamename sets the name you actually play under, /claim files a claim on a name already on the board, and /report sends a bug report.",
        "These follow exactly the same rules as the website, because both now run the same code instead of two copies that could drift apart.",
        "Limits on claims and reports count per account when they arrive from Discord. Counting them per network would have let one person use up everyone else\u2019s allowance.",
    ]},
    {"version": "5.38.0", "at": "2026-08-12T03:45:00Z", "changes": [
        "You can press Play from Discord now. /play lists the live matches with a button on each - press one and you are checked in, told which name to play under, and given a link straight into the lobby. No sign-in, because Discord already knows who you are.",
        "Checking in from Discord means no browser connects to this site at all, so there is nothing for it to see. It is the most private way to use the tracker.",
        "The site no longer even calculates a visitor address in the places it was still doing so and discarding the result.",
    ]},
    {"version": "5.37.0", "at": "2026-08-11T23:30:00Z", "changes": [
        "The site no longer records IP addresses. Not when you press Play, not on reports, claims or registrations - and signing in with Google or Discord never stored one to begin with. Every address previously stored has been wiped from the database.",
        "Rate limiting - the only thing addresses were ever used for - now works on an irreversible coded tag whose key is kept outside the database, and the tags themselves expire within two days. Nothing in the database can identify your connection. See the new Privacy section on the Info tab.",
        "Corrected the claim wording in a few places: a claim completes on its own once the name wins a tracked match after you file it. Nothing is approved by hand.",
    ]},
    {"version": "5.36.1", "at": "2026-08-11T21:34:00Z", "changes": [
        "Hardening on top of tonight\u2019s reconnect fix, after watching it handle its first live matches: a feed that keeps reading all zeros can never, however long it persists, be mistaken for the real state of the match. Zeros are refused as a baseline outright. Two matches this evening were already scored correctly through disconnects that would previously have corrupted them.",
    ]},
    {"version": "5.36.0", "at": "2026-08-11T21:10:00Z", "changes": [
        "Fixed a class of wrong winners. Starblast drops every spectator - the tracker included - every 12 minutes, and for about half a minute after reconnecting the tracker sees a half-loaded lobby: two or three players, near-zero scores. It used to believe that view, which is how one match tonight was scored on 1,366 points against a real 235,145. Readings taken in that window are now set aside and the last trusted picture of the match is what gets scored.",
        "A watcher whose feed freezes on one unchanging frame now notices within a minute and reconnects, instead of reporting the frozen frame as the ending.",
        "Every decided match now writes its full rosters, team split and deciding scores to a permanent record, so a disputed result can be recomputed instead of argued about.",
    ]},
    {"version": "5.35.0", "at": "2026-08-11T05:42:42Z", "changes": [
        "On the Play and Settings pages the first box sat almost flush against the heading above it. It now has the same breathing room as every other page.",
    ]},
    {"version": "5.34.0", "at": "2026-08-11T05:27:14Z", "changes": [
        "The \u201cReport this name\u201d button on a player\u2019s page did nothing when you clicked it. It now works on every profile. This also fixes the \u201cThis is my name, report it\u201d button shown when someone has claimed your name, so name reports get through again.",
    ]},
    {"version": "5.33.0", "at": "2026-08-11T05:20:00Z", "changes": [
        "The explanations that used to sit beside every box and button have moved to the Info tab. Each page is now the thing itself - the leaderboard, the match list, your settings - instead of repeating the same paragraphs in the corner of every screen. Anything the site tells you about your own account, and every warning and error, is untouched.",
    ]},
    {"version": "5.32.0", "at": "2026-08-11T05:07:00Z", "changes": [
        "The Region column on the combined leaderboard now spells the region out in full, and clicking it opens that region\u2019s leaderboard scrolled to your own row rather than making you hunt for yourself.",
        "Fixed the border on the testing notice: one edge was a brighter yellow than the other three.",
    ]},
    {"version": "5.31.0", "at": "2026-08-11T04:56:00Z", "changes": [
        "On the combined leaderboard, the region each player mostly plays in is now its own column beside Record and Win%, instead of a small tag squeezed in after the name.",
    ]},
    {"version": "5.30.0", "at": "2026-08-11T04:56:00Z", "changes": [
        "New Info tab: every explanation on the site compiled in one place - how the tracker watches matches, how the rating moves, full against half elo, account and in-game names, claiming, Protection, clans and reporting. The old How-it-works page now leads there.",
    ]},
    {"version": "5.29.0", "at": "2026-08-11T04:45:00Z", "changes": [
        "Pressing Play copies your in-game name to the clipboard so you can paste it straight into Starblast. The name cannot be put into the link itself - Starblast fills its name box from its own browser storage and ignores anything in the address, and no site is allowed to write another site storage - so pasting is as close as this can get.",
    ]},
    {"version": "5.28.0", "at": "2026-08-11T04:30:00Z", "changes": [
        "The combined leaderboard shows NA, EU or AS beside each name - the region that player turns up in most. Their profile still has the full split if they play in more than one.",
    ]},
    {"version": "5.27.0", "at": "2026-08-11T04:02:00Z", "changes": [
        "Pressing Play now matches you to the next ship that appears under the name you play as, rather than simply the next ship to appear. In a busy lobby the old rule could match you to another player who happened to join first.",
        "Keep the name on the Play page the same as the one in your ship. If nothing matches, the match still counts under the name you played - it is just not linked to your account.",
    ]},
    {"version": "5.26.0", "at": "2026-08-11T03:55:00Z", "changes": [
        "Matches not yet being watched are marked full elo on the Play list, next to the half elo mark on the ones already running. Only half of them were labelled before, which left the rest ambiguous.",
        "How this works now explains full against half instead of a check-in deadline that no longer exists.",
    ]},
    {"version": "5.25.0", "at": "2026-08-11T03:48:00Z", "changes": [
        "Joining a match that is already being watched counts for half, on either side. Before, the split depended on whether your team had already filled up, so somebody who walked in after the tracker started could still earn a full win if their team had room. What matters is whether you were in the match when the watch began.",
        "Matches already being watched are marked half elo on the Play list, so you can see what joining one is worth before you join it.",
        "The live list says when a lobby is too small to be tracked instead of claiming it is waiting for a free slot, and a lobby is dropped once it is 90 minutes old rather than three hours - the old limit was set to catch a 21-hour zombie, so 100-minute lobbies still looked like they were about to be picked up.",
        "Matches no longer close for check-in, and the disabled button says Not tracked rather than Closed, which is what it actually means.",
    ]},
    {"version": "5.23.0", "at": "2026-08-11T03:28:00Z", "changes": [
        "The name box on Play is just called In game name now, with one line under it. It was headed Your account and took three paragraphs to explain itself before you reached the field.",
    ]},
    {"version": "5.22.1", "at": "2026-08-11T03:22:00Z", "changes": [
        "Fixed being signed out the moment you changed tab. Signing in was working the whole time - the check the pages use to see whether you are signed in had been broken twenty minutes earlier and was failing on every request, so every page decided you were a stranger.",
    ]},
    {"version": "5.22.0", "at": "2026-08-11T03:15:00Z", "changes": [
        "The name you play under is edited on Play, in the account box at the top, and nowhere else - it was in Settings as well, which made it unclear which one mattered.",
        "It now defaults to your account name instead of starting empty, since most people play under the name they signed up with. Change it whenever you like; your results still go to your account either way.",
    ]},
    {"version": "5.21.0", "at": "2026-08-11T03:10:00Z", "changes": [
        "The name box on the Play page now changes the name you play under, not your account name. It was still editing your account identity - the one thing that should not be changed casually on the way into a match - left over from when there was only one name. Your account name is shown there for reference and is edited in Settings.",
    ]},
    {"version": "5.20.1", "at": "2026-08-11T03:00:00Z", "changes": [
        "The changelog now shows when each release went out, stamped in Eastern time with the zone written on each line. Releases from before 10 August have no time against them because none was ever recorded - a blank rather than a guess.",
    ]},
    {"version": "5.20.0", "at": "2026-08-11T02:47:00Z", "changes": [
        "Matches that protection sets aside are now kept rather than discarded. They still do not count towards any rating and are not shown anywhere - that is the whole point of protection - but if protection ever turns out to have been wrong, or a name turns out to be held by the wrong person, the match is still on record instead of gone.",
    ]},
    {"version": "5.19.0", "at": "2026-08-11T02:40:00Z", "changes": [
        "Protection can be switched on straight away - it no longer waits until you have played a tracked match. That requirement meant your first match was always the unprotected one, and after a board reset it locked everybody out at once. Protection is most useful before somebody plays under your name, not after.",
    ]},
    {"version": "5.18.0", "at": "2026-08-11T02:34:00Z", "changes": [
        "Your account now has two names. The account name is your identity on the leaderboard and can be changed once. The name you play under is separate, can be changed as often as you like, and is just so people know who you are in game - it never decides where a result goes on its own.",
        "Match history shows the name you actually played under, so a game played as something else still reads correctly on your profile. Matches where it matched your account name show a dash.",
        "A name already sitting on the leaderboard still cannot be taken as an account name - claiming it is what proves it is yours.",
    ]},
    {"version": "5.17.0", "at": "2026-08-11T02:08:00Z", "changes": [
        "Match times are shown in your own time zone. They were being printed exactly as the server stores them, which is UTC - so a game played at nine in the evening in New York appeared as one in the morning the following day. Hovering a time shows the full date and time.",
    ]},
    {"version": "5.16.1", "at": "2026-08-10T23:32:00Z", "changes": [
        "Scores now stick. A player's recorded score is their latest one from the game's scoreboard - previously the tracker only kept the final scoreboard it saw, and since a lobby empties out as a match ends, that last board held only the final few players and everyone else's score was lost. If you left before the end, your score is the one you left with.",
    ]},
    {"version": "5.16.0", "at": "2026-08-10T23:26:00Z", "changes": [
        "Losing a match now puts you on the board just like winning one does. Only winners were ever being added; anyone whose first tracked match was a loss bounced off the record entirely, which is why the fresh board was filling up with winners and no losers.",
    ]},
    {"version": "5.15.0", "at": "2026-08-10T23:13:00Z", "changes": [
        "Matches are no longer thrown away when everyone leaves at the end. If every team had been marked out but one still had players in it, the result was refused as undecidable - even though a team with players plainly did not lose to teams with nobody in them. That team now wins. This was discarding whole matches, which is why the board had been filling up with winners and almost no losers.",
        "If a lobby ends up completely empty, the result is now settled on damage and score instead of being refused outright. It still refuses when nothing can separate the teams - it will not guess a winner.",
        "A finished lobby stops showing as Tracked about a minute after it empties, rather than three. The longer wait was inherited from a rule guarding against misreads, and a lobby reading one player six times over is not a misread.",
    ]},
    {"version": "5.14.1", "at": "2026-08-10T23:03:00Z", "changes": [
        "The board has been wiped again. Skill on the combined all-regions view was reading five points too high - a player on 6.0 showed as 11.0 - and one match recorded its winners without recording anyone who lost, so nothing on it was worth keeping. Both the site and the Discord bot are fixed.",
    ]},
    {"version": "5.14.0", "at": "2026-08-10T22:52:00Z", "changes": [
        "How a team is decided for rating has changed. A team's line-up is locked in at its fullest, up to eight players. If that team loses, everyone in the locked line-up takes the loss - leaving early no longer avoids it. If it wins, whoever is there at the end is paid, and anyone who joined after the line-up had settled gets half rather than full.",
        "Far more matches now record your in-game score. Scores were being matched up through a team lookup that quietly dropped anyone it could not place, which is why one game showed a score and the next showed nothing.",
        "The tracker no longer loses matches when it restarts or crashes. Each match being watched is now saved as it goes, so an interruption costs about ten seconds of watching instead of the whole game.",
        "Seven matches are watched at once rather than eight. Eight game clients did not fit in the server's memory and were taking the tracker down with them roughly every eight hours - and every one of those crashes lost every match then in progress.",
        "Lobbies with fewer than four players are no longer picked up, and a game that empties out is released instead of being watched to the end. One lobby sat with a single player in it for 55 minutes holding a slot a real match could have used.",
        "These are tracker-side changes from earlier today that should have been listed when they shipped and were not.",
    ]},
    {"version": "5.13.0", "at": "2026-08-10T22:16:00Z", "changes": [
        "The board has been wiped and started over from nothing - no players, no matches, no accounts. Everything from before today is gone deliberately.",
        "There is now a standing notice on every page: expect further resets over the coming week while the switch away from reading names off the screen is tested.",
    ]},
    {"version": "5.12.0", "at": "2026-08-10T21:03:00Z", "changes": [
        "You can press Play at any point during a match now, not just in the first ten minutes. Turning up late already counts for half, so the deadline was solving a problem that half points had solved better - and it meant joining a game in progress could not be rated at all.",
        "The leaderboard opens on a combined board of every player across all three regions. The regional boards are still there in the same selector.",
        "Your profile now shows where you stand in each region you have played in, alongside your overall rank and the size of each field.",
    ]},
    {"version": "5.11.1", "at": "2026-08-10T16:25:00Z", "changes": [
        "A match where every player on a team has left is now decided instead of refused: a team with nobody on it cannot win, so the last populated team takes it. Quiet lobbies that wound down with intact stations used to end unscored because nothing had destroyed a station.",
    ]},
    {"version": "5.11.0", "at": "2026-08-10T16:15:00Z", "changes": [
        "A player who finishes a match with exactly 0 points is no longer rated for it, win or lose. The game itself is saying they never played - anyone who mines or fights for even a minute has points - and in small lobbies an idle spectator was collecting real wins. Matches from before scores were recorded are untouched.",
        "One player's record built entirely this way has been removed from the leaderboard.",
    ]},
    {"version": "5.10.2", "at": "2026-08-10T05:41:00Z", "changes": [
        "Tracker-side housekeeping: the last of the screenshot-era machinery has been deleted rather than just switched off, and the awards experiment from earlier tonight has been removed completely. No visible change - matches are watched, scored and reported exactly as before, by reading the game itself.",
    ]},
    {"version": "5.10.1", "at": "2026-08-10T04:37:00Z", "changes": [
        "Leaderboard is the first tab now, with Play second.",
    ]},
    {"version": "5.10.0", "at": "2026-08-10T04:19:00Z", "changes": [
        "Match history now records each player's final in-game score, read from the game's own scoreboard at the moment the match ended. It shows in the Recent matches table on every profile; matches recorded before today have no score to show.",
    ]},
    {"version": "5.9.0", "at": "2026-08-10T03:25:00Z", "changes": [
        "The Discord bot can now show any of the three regional leaderboards, over any time window, rather than just one board.",
        "New Discord commands: set or change your name, turn protection on and off, and list the matches being tracked right now by region.",
    ]},
    {"version": "5.8.0", "at": "2026-08-10T03:12:00Z", "changes": [
        "The time-period picker on the leaderboard is no longer a plain browser dropdown - it matches the rest of the page, and each option says what it covers, since Monthly means the last 30 days rather than this calendar month.",
        "Each period is now its own address, so a particular view can be bookmarked or opened in a new tab.",
    ]},
    {"version": "5.7.3", "at": "2026-08-10T03:03:00Z", "changes": [
        "Fixed saving your name failing outright on accounts that hold more than one name. It was trying to rename every name on the account at once.",
        "Saving the name you already have now simply confirms it instead of erroring.",
        "Fixed the live match list going stale: the tracker's updates were being held up waiting for the database and abandoned before they finished.",
    ]},
    {"version": "5.7.2", "at": "2026-08-10T02:51:00Z", "changes": [
        "Names can end in a number again - Tempest1 and Halo3 were being turned away. That rule existed because names used to be read off the screen and the score column bled into them as trailing digits; names now come from the game itself, so it was only rejecting real ones.",
    ]},
    {"version": "5.7.1", "at": "2026-08-10T02:49:00Z", "changes": [
        "Fixed saving your name sometimes failing with a connection error. The tracker writes to the database every few seconds and a save that landed in the middle of one gave up after five seconds instead of waiting its turn.",
    ]},
    {"version": "5.7.0", "at": "2026-08-10T02:39:00Z", "changes": [
        "There is a Report tab now. If something is broken, a result looks wrong, or somebody is playing under your name, say so there - you do not need an account to file one, though leaving a way to reach you means you can get an answer.",
    ]},
    {"version": "5.6.0", "at": "2026-08-10T02:34:00Z", "changes": [
        "You can set and change your name on the Play page now, instead of going to Settings for it.",
        "There is no separate check-in step any more. Press Play on the match you are about to join and that is it - the tracker notes the moment, watches for the next ship to appear in that lobby, and takes that to be you. Play under any name you like.",
        "Because you are matched to a ship rather than to a name, two players called the same thing no longer interfere with each other - each one's result goes to their own account.",
        "Fixed: being matched to a name in one match used to credit that account for every later match anyone played under the same name. A match is now credited only to the ship that was actually identified in it.",
        "Fixed: two people pressing Play on the same lobby could both be matched to the same ship, so one collected the other's result.",
    ]},
    {"version": "5.5.0", "at": "2026-08-10T02:25:00Z", "changes": [
        "Workers are no longer stuck in their own region. Each region still gets its guaranteed share, but if one has nothing to watch its idle slots are lent to whichever region has the most matches going uncovered - and handed straight back as soon as it needs them. Where two regions want the same spare slot, it goes to the one whose match started most recently, because there is more of it left to watch.",
        "Dead lobbies no longer appear under live matches. An empty system the game never closed can sit on the server list for a day looking like a match; one had been showing for 27 hours.",
    ]},
    {"version": "5.4.1", "changes": [
        "Players added to the board by winning now keep their name exactly as it is in game. Spaces were being stripped, so CODE BLUE appeared as CODEBLUE. Names already added that way have been corrected.",
    ]},
    {"version": "5.4.0", "changes": [
        "Ratings have been reset and the leaderboard is starting fresh. If you had signed in, your account and your name are still there - only the record is cleared.",
        "North America, Europe and Asia are now three separate leaderboards rather than one board you can filter. You land on North America; the region buttons switch between them, and there is no combined view, because beating a North American and beating a European are not the same result.",
        "Your profile now shows where you play: a record split by region, and your main server under your name.",
        "Live matches on the Play page are picked one region at a time instead of all being listed together.",
    ]},
    {"version": "5.3.0", "changes": [
        "Clans are switched off and every existing clan has been cleared. Tags were guessed from the front of a name, and names used to be read off the screen, so a lot of those memberships were wrong. They will be put back by hand once there is real data to build them from.",
        "A confirmed rating now carries a tick on the leaderboard and on the player's own page. Click it to see what it means: that player has Protection on, so only matches they checked into count.",
        "Turning Protection off now says plainly that your rating stops being confirmed, rather than only describing what changes.",
        "The tracker now watches 8 matches at once - three in North America, three in Europe and two in Asia.",
        "The tracker no longer takes screenshots of the game at all. Names, scores and stations have come from the game itself for a while, but a picture was still being captured and thrown away several times a minute for every match being watched.",
    ]},
    {"version": "5.2.0", "changes": [
        "A match too old for the tracker to pick up is now labelled as such on Play, instead of saying it is starting shortly. An empty lobby nobody fought over can sit there for a day looking alive, and one was showing 26 hours old with a Check in button beside it - checking into it would never have counted.",
    ]},
    {"version": "5.1.1", "changes": [
        "Fixed the new day/week/month and region views listing some players twice. Names are recorded in matches exactly as they are played, decorations and all, so anyone whose name carries symbols or extra spacing was being counted separately from their own leaderboard entry - and shown without their protection mark.",
    ]},
    {"version": "5.1.0", "changes": [
        "The leaderboard can now be filtered by region and by day, week or month. All time shows your rating; any shorter window shows how much rating you gained in it, because a rating is a single running number and cannot be cut into weeks.",
        "Pressing Play now checks in your account rather than a name, so you no longer need to be playing under your account name for a match to count. Play under whatever name you like - the first ship to appear in that match is taken as yours.",
        "Claiming a name now makes it your account name, so a new player can claim the row their wins have been landing on without having to pick a different name first.",
        "Protected players are marked on the leaderboard, so a rating backed by matches the player confirmed can be told apart from one built automatically.",
        "Live matches are grouped by region on the Play page.",
    ]},
    {"version": "5.0.0", "changes": [
        "Ratings have been reset. The tracker no longer reads names off the screen - it reads them from the game itself - so names are now exactly what you play with, and the old board was built on names that were often misread.",
        "Your rating now belongs to your account rather than to a name. Set an account name in Settings, and press Play before a match so the tracker knows which ship is yours. Play under whatever name you like; the matches still count for you.",
        "Because the tracker identifies you by your ship rather than by your name, two players sharing a name no longer interfere with each other.",
        "Matches in Europe and Asia are now tracked as well as North America, and the leaderboard can be filtered by region and by day, week, month or all time.",
        "Clans are switched off while this settles. Existing clans have been cleared and will be rebuilt from real data.",
    ]},
    {"version": "4.11.0", "changes": [
        "Fair warning: ratings are likely to be reset in the next few days. The tracker now reads player names straight from the game instead of reading them off the screen, and a lot of the board was built up under names that were misread.",
        "Some of those are being matched back to the right player automatically. Where that is not possible, the cleanest fix is to start the leaderboard fresh rather than leave wrong records standing.",
        "Nothing you do in the meantime is wasted - matches are still being tracked throughout, and this notice will come down once the decision is made either way.",
    ]},
    {"version": "4.10.0", "changes": [
        "Names are now recorded exactly as they appear in game - spaces, capitals, symbols and all. The tracker used to read them off the screen, which turned Arturo Barnes into ARTUROBARNES and LINDSEY into INDSEY, and every misreading became a separate player with its own rating.",
        "Where a name was misread badly enough to create a duplicate, the two are being matched back together rather than deleted, so nobody loses the matches they played.",
        "Whether a station has actually been destroyed now comes from the game itself instead of being judged from the health bar, so matches that were previously too ambiguous to score can be called.",
    ]},
    {"version": "4.9.0", "changes": [
        "Ordinary names are no longer pulled into a clan just because they happen to start with its tag. ISAAC was being read as a member of IS, the same way SRSLY would look like SR.",
        "This only affects the guesswork. A name written with its tag set apart, like '[IS] AAC', is still recognised, and clan admins can still add anyone by hand - so a real member who happens to be called Isaac just gets added the normal way.",
        "Names already tagged this way have been corrected and will not be re-tagged.",
    ]},
    {"version": "4.8.0", "changes": [
        "You can now sign in with Discord as well as Google. Either one gives you the same account features - registering a name, claiming, protection and clans all work the same way.",
        "The two are separate accounts, though. Signing in with Discord when you already have a name under Google gives you a second, empty account rather than your existing one, so stick to whichever you started with.",
        "There is now a Discord bot for the tracker. It can look up any player, show the leaderboard, list the matches being tracked right now, compare two players, and register a name for you without leaving Discord.",
        "A name you register through the bot belongs to your Discord account, so signing in here with Discord afterwards finds it waiting for you.",
        "A claim filed from a Discord account now shows that account when it is reviewed, so a claim can be checked against the person who actually asked for it instead of an anonymous id.",
    ]},
    {"version": "4.7.0", "changes": [
        "A match the tracker has to give up on part way through is now scored if it had already thinned out to fewer than 10 real players, and left unscored if it was still busy. Before this nothing was recorded either way, so a game that had effectively finished counted for nobody.",
        "Bots and repeated names do not count towards that total, so a late game that has filled up with bots is judged on the real players actually left in it.",
        "A busy match is still never scored while it might be running. Guessing a winner there would hand out ratings for a game nobody had finished.",
    ]},
    {"version": "4.6.1", "changes": [
        "Play now shows which match you are checked into. Before this there was no sign of it after reloading the page, so it looked as though checking in had not worked.",
        "Checking into a second match still cancels the first - that has always been the case, and it is now spelled out on the button instead of happening quietly.",
    ]},
    {"version": "4.6.0", "changes": [
        "New Play tab. Everything you do before a match is in one place now - which matches are being tracked, checking in, and claiming your name if you do not have it yet.",
        "Player search moved onto the leaderboard. There were two separate lists of the same players before, which was confusing for no reason.",
        "Checking in has moved out of Settings and onto Play, next to the list of live matches.",
    ]},
    {"version": "4.5.0", "changes": [
        "You can now check in to a match right up until the tracker starts watching it, instead of only during the first 10 minutes. There used to be a gap between minutes 10 and 20 where a protected player could neither check in nor be picked up, so a match joined then could never count for them.",
        "The check-in list now shows which matches are being tracked, which are about to be, and which you can still check in to - pick one and check in from there.",
    ]},
    {"version": "4.4.0", "changes": [
        "The live match list now tells you why a game is not being tracked, instead of just saying it is not. A lobby that is too new shows how long until it can be picked up, and one that is old enough shows whether it is waiting for a free slot.",
        "Matches are only picked up once they are 20 minutes old, because games rarely finish before then and a slot spent on a fresh lobby is one not watching a match that is about to end.",
    ]},
    {"version": "4.3.0", "changes": [
        "The leaderboard now shows which matches are being watched right now. Only a few can be tracked at once, so if your lobby is not on that list your game will not be scored - and until now there was no way to know that in advance.",
        "Lobbies that are live but not being watched are shown too, so you can pick one that counts.",
    ]},
    {"version": "4.2.0", "changes": [
        "You can now claim a name yourself instead of waiting for it to be approved by hand. Sign in, claim the name, then win one tracked match playing as it and the name becomes yours.",
        "While a claim is open it is shown on that player's page for anyone to see, with a report button. If somebody tries to take your name, you will be able to see it happening.",
        "Added a report button to every player page. Reporting never changes anything on its own - it raises it to be looked at by hand, because the site cannot tell who is really behind a name.",
        "Winning a match is a cost, not proof of identity. Anyone can type any name in game, so nothing the tracker sees can prove who you are. The point is that taking someone else's name now means playing as them and winning while they watch it happen.",
        "One name per account applies to claiming as well as registering.",
    ]},
    {"version": "4.1.0", "changes": [
        "Your player page now lists your recent matches - when you played, whether you won, and exactly how much your skill moved. Until now only running totals were kept, so there was no way to check whether a particular game had counted.",
        "Matches are recorded from today onwards. Games played before this exist only in your totals, so the list starts empty and fills as you play.",
        "A match that counted for half, because you joined in the second half of it, is marked as such in the list.",
    ]},
    {"version": "4.0.1", "changes": [
        "Removed seven reserved names that had never played a match and were tied only to a network. They did nothing except stop the real player from registering that name properly, and any of them can now be taken again by signing in.",
        "Names with a match history were left alone, even where they were only tied to a network. Deleting one would hand its owner a fresh rating, which is the one thing name removal has never been allowed to do.",
    ]},
    {"version": "4.0.0", "changes": [
        "Every name is now tied to a Google account, and one account holds one name. Signing in takes a couple of seconds and there is now a button for it in the top right of every page.",
        "Being on the same network no longer counts as owning a name. It never really proved anything - everyone in a house, a school or on mobile data shares one address, so housemates and strangers alike could rename, remove or protect each other's names. Ownership is your account now, and nothing else.",
        "If your name was only tied to a network, you can still play and still be rated exactly as before. To rename, remove or protect it you now need to sign in and claim it, which is approved by hand.",
        "Registering a name requires signing in first.",
    ]},
    {"version": "3.8.0", "changes": [
        "Long matches were being given up on partway through and counted for nobody. The tracker stopped watching a match after 45 minutes, which is shorter than some games actually run, so everyone in them got nothing at all. It now watches for up to 90 minutes. This was happening around 16 times a day.",
        "One known case: a game in lobby 9161 that ran about 74 minutes and scored nobody. There is no way to award it now, since the tracker never saw who won.",
        "Fixed a second version of the winning-team bug from earlier today. That fix only covered one of the two ways a match can be wrapped up, so a match finished the other way could still credit the wrong players.",
        "IS and GOF are now tracked as clans.",
        "Isagi Yoichi was removed from IS. The name happens to start with the same two letters but is not a member of the clan.",
    ]},
    {"version": "3.7.0", "changes": [
        "A clan's record now covers every match its members have played, instead of only those since clan tracking was added. It was showing far fewer games than the members had actually played.",
        "Turning protection on or off now asks you to confirm first, and reminds you it cannot be changed again for 24 hours.",
    ]},
    {"version": "3.6.0", "changes": [
        "Skill is now tracked to one decimal place. Whole numbers were too coarse - most of the leaderboard sat on the same rating, and half a point of change simply rounded away to nothing.",
        "Because of that, half elo for joining late now genuinely means half.",
        "Ranks are far more meaningful as a result. Players used to share a rank in large blocks because so many of them had the identical whole number.",
    ]},
    {"version": "3.5.0", "changes": [
        "Fixed the winning team being taken from the fullest moment of a match rather than the end of it. If someone joined partway through and carried the game, they were left out of the result while players who had already quit collected the win. The winner list is now everyone who played for that team, top scorers first.",
        "Joining late no longer wipes out your rating for the match. It used to remove you from the result completely. You now earn half, and the winning team's top five earn full no matter when they arrived.",
        "Clan admins are marked with a crown on their clan's page.",
    ]},
    {"version": "3.4.0", "changes": [
        "Clan admins now join their own clan automatically. Redeeming an admin code, or starting a clan, adds the names on your account to that clan's roster. A name already in another clan is left where it is.",
    ]},
    {"version": "3.3.1", "changes": [
        "Single-character names are allowed again when the character is Chinese, Japanese or Korean, where one character is an ordinary whole name. A single Latin letter is still rejected, because those come from misread rosters rather than players.",
    ]},
    {"version": "3.3.0", "changes": [
        "Names in other alphabets are now tracked properly. Chinese, Cyrillic, Arabic, Korean and Greek names used to be reduced to nothing internally, so they could not be told apart from each other and were not rated at all. They now keep their characters and are treated like any other name.",
        "Player search matches those names too.",
        "Accents no longer split one player into two. JOSE and JOSE with an accent are now the same player, since the tracker cannot reliably tell them apart when reading a roster.",
    ]},
    {"version": "3.2.2", "changes": [
        "Removed two rows that were not real players. One was a single stray letter from a misread roster. The other held a record built from several different players whose names share no Latin letters, merged together by the bug fixed above - there is no record of whose results were whose, so the number could not be repaired, only removed.",
    ]},
    {"version": "3.2.1", "changes": [
        "Fixed results from players whose names use no Latin letters - Chinese, Cyrillic, Arabic, Korean or Greek - being credited to a completely unrelated player. Those names all reduced to nothing internally, so they were treated as the same person. They are no longer rated at all, which is the only honest option while they cannot be told apart.",
    ]},
    {"version": "3.2.0", "changes": [
        "Protection can only be turned on for a name that has actually played a tracked match. Before this, someone could register a name they had never played - any name not yet on the leaderboard - switch protection on, and quietly stop that player's wins from ever counting. Turning protection off is still always allowed.",
        "Starting a clan now requires a name of your own that plays under the tag. Creating a clan switches off automatic tagging for it, so without this anyone could grab a real clan's tag before its leader did and decide who counted as a member.",
        "There is now a limit on how many name claims you can have open at once.",
        "When a clan admin removes someone from their clan, that player can now be picked up by other clans normally. Previously the removal blocked them from ever being tagged again, anywhere.",
        "Names must be at least two characters. Single letters were coming from misread rosters, not real players.",
    ]},
    {"version": "3.1.1", "changes": [
        "Fixed check-in being broken. The lobby picker under Settings was sending the wrong field, so every check-in was rejected. If you tried to check in since the site was rebuilt into tabs, it did not work - it does now.",
    ]},
    {"version": "3.1.0", "changes": [
        "Clans have a win record again, counted properly. One match your clan won is one win, no matter how many of your members were in it. The old total added up each member's wins separately, so a clan of five that won one match looked like it had won five.",
        "Clan records start from today. The old per-player totals cannot be split back into the matches they came from, so there is nothing honest to carry over.",
        "Protection can now only be turned on or off once a day. Without that limit it was a switch you could flip the moment a match looked like going badly - leave it off while winning, turn it on to void the losses.",
    ]},
    {"version": "3.0.0", "changes": [
        "The site is now split into tabs - Leaderboard, Players, Clans, Changelog and Settings - instead of everything being piled onto one page. Each does one thing.",
        "New Clans page listing every clan, and you can apply to join one from it. The clan's admin decides.",
        "New Players page for searching anyone the tracker has rated, so the leaderboard is just the leaderboard again.",
        "Everything about your own name now lives under Settings.",
        "Clan pages no longer show a combined win total. It was the sum of unrelated matches different members happened to play, which looked like a team record while measuring nothing of the sort.",
        "The rating is now called skill throughout, and the site is the Starblast NA Team Mode Skill Tracker.",
    ]},
    {"version": "2.8.0", "changes": [
        "If you are signed in when you claim a name, the claim now remembers your account. Once it is approved the name is yours on any device, instead of only from the network you claimed it on. Sign in first if you can - claims still work without it, but they are tied to your address.",
    ]},
    {"version": "2.7.0", "changes": [
        "Anyone can start a clan. Sign in on the Clans page and pick a 2 to 4 character tag - you become its admin and invite your members. Clans are no longer limited to the eight the tracker already knew about.",
        "A clan tag is no longer repeated in the name next to it. COVHADE now shows as HADE with a COV badge beside it. Nothing about your name actually changed - this is only how it is displayed.",
        "A brand new clan never picks up members automatically, only by invitation. Otherwise a short tag would sweep in every player whose name happens to start with those letters.",
    ]},
    {"version": "2.6.0", "changes": [
        "Clans can now have admins, who decide who is actually in the clan. Anyone could put a clan's tag in their name and end up on that clan's page, which is what this fixes. To get an admin for your clan, ask justtempest on Discord for a code, then enter it on the new Clans page.",
        "Once a clan has an admin, players are no longer added to it automatically. The roster is whatever the admin says it is.",
        "An admin cannot simply put you in a clan. If you have an account, you get an invitation on Manage your name and nothing happens until you accept it. Only players with no account can be added directly, and only when the clan's tag really is in their name.",
    ]},
    {"version": "2.5.0", "changes": [
        "Clan tags now show on the leaderboard. If the tracker has seen you playing under F4, FV, L7, G4, SR, COV, ACW or SRW, a small tag appears next to your name.",
        "Clan tags are clickable. Selecting one opens that clan's page, listing every member on the leaderboard with their record and the clan's combined win rate.",
        "A clan tag can now be taken off a name. Tags are worked out from the name the tracker read in game, so they can be wrong - a name that merely starts with the same letters could be tagged by mistake. Your player page now has a Remove clan tag button, and once a tag is removed it will not come back on its own.",
    ]},
    {"version": "2.4.0", "changes": [
        "The tracker now records which clan a player belongs to, for F4, FV, L7, G4, SR, COV, ACW and SRW. Nothing is shown on the leaderboard yet - this release only starts collecting it, because the clan tag is visible when a match is read and is lost afterwards, so it has to be captured as matches finish.",
    ]},
    {"version": "2.3.0", "changes": [
        "Names with numbers in them are now tracked. Players like KINGDUCK5TER, 98e and the F4 clan were being skipped entirely - they could win a match and receive nothing, with no warning anywhere.",
        "Names still cannot END in a number. That is not arbitrary: when the tracker misreads the roster it glues your score onto your name, which always produces trailing digits. Blocking those keeps the misreads out while letting real numbered names in.",
    ]},
    {"version": "2.2.1", "changes": [
        "HAL is no longer tracked. It is short for HAL 9000, one of Starblast's default names, and the tracker was only blocking the full spelling - so the shortened form was collecting wins that belonged to several different anonymous players. Its record has been removed.",
    ]},
    {"version": "2.2.0", "changes": [
        "You can now check in up to 10 minutes after a match starts, instead of 5. The limit still exists so nobody can wait to see who is winning before deciding whether to check in.",
    ]},
    {"version": "2.1.1", "changes": [
        "Backfill: the changes below were made to the tracker earlier and were never written up here. Nothing in this list is new today - they are recorded now because every change should be visible to you, and these were not.",
        "Matches are now only scored once the lobby has actually closed. Before this, a dropped connection looked identical to a match ending, so games still in progress could be scored - one player lost rating mid-match while well ahead. A lost connection now just reconnects and reports nothing.",
        "Quitting a match you are losing does not dodge the loss. If a team that was full collapses to almost nobody, it counts as eliminated and the penalty falls on its top players from when it was at full strength, not on whoever happened to still be there.",
        "Fixed matches silently going unscored. A stalled connection could leave the tracker reading an empty roster for the rest of the match with no error, and after any reconnect the game's welcome popup was never dismissed, so it never saw the player list again.",
        "Fixed a case where finishing a match could report it twice, which would have applied the rating change twice.",
        "Fixed loading-screen and disconnect text being read as player names, which could put things like 'Warping t' on the board and stop a wiped-out team from counting as eliminated.",
        "The tracker only watches lobbies that are at least 20 minutes old, since matches rarely end before then, and it watches the oldest ones first as those are closest to finishing.",
    ]},
    {"version": "2.1.0", "changes": [
        "The tracker now watches 3 matches at once instead of 2, so fewer games finish unseen. The server it runs on was upgraded to make this possible - it had been running out of processing power, which also meant player names were sometimes misread.",
    ]},
    {"version": "2.0.0", "changes": [
        "Out of beta. The version also jumps to 2.0 because signing in with Google replaced identifying you by your internet connection, which is a real change to how the site decides a name is yours.",
        "You are now rated if you were on the roster during the first half of the time the tracker watched your match, instead of only the first few seconds. The old rule was strict enough to miss people who genuinely played. Turning up in the second half still earns nothing, and quitting a losing match still does not dodge the loss.",
    ]},
    {"version": "Beta 1.21.0", "changes": [
        "Search now finds every player whose name contains what you typed, instead of needing the exact name. Searching 'fire' lists everyone with 'fire' anywhere in their name, and capitals, spaces and punctuation are ignored - so 'belriose' finds 'BEL RIOSE'. Results filter as you type.",
    ]},
    {"version": "Beta 1.20.1", "changes": [
        "The leaderboard table now fits on a phone screen without needing a sideways swipe to see win rate and Elo.",
    ]},
    {"version": "Beta 1.20.0", "changes": [
        "Check in, Claim, Rename and Remove no longer use pop-up browser dialogs. Check in now shows the live match list right on the page; the others show a small inline form. Nothing about what they do has changed, only how you interact with them.",
    ]},
    {"version": "Beta 1.19.0", "changes": [
        "The leaderboard now shows each player's win-loss record and win rate, not just their Elo. Players tied on Elo are now ordered by win rate, so a tie in rating no longer means an arbitrary order.",
    ]},
    {"version": "Beta 1.18.1", "changes": [
        "Check in, Claim, Rename and Remove now show a clear error if your browser blocks their pop-up dialog, instead of silently doing nothing.",
    ]},
    {"version": "Beta 1.18.0", "changes": [
        "Added a Sign in with Google button on the Manage page. Signing in shows your registered names as one-click options, and is now how a name gets tied to you - your network address is still accepted for names registered before this, but no longer required.",
    ]},
    {"version": "Beta 1.17.0", "changes": [
        "Your name is now tied to a Google account instead of to your internet connection. This fixes two real problems: your phone changes its address constantly, so a name could stop being yours; and everyone sharing one home or school connection counted as the same person, which meant they could rename or remove each other's names.",
        "Nothing to do if you already registered - the first time you sign in and touch your name from your usual connection, it attaches itself to your account.",
    ]},
    {"version": "Beta 1.16.0", "changes": [
        "Groundwork for signing in with Google. Nothing changes for you yet - the sign-in button, and the move away from identifying you by your network, come next.",
    ]},
    {"version": "Beta 1.15.1", "changes": [
        "Fixed a flaw that let someone appear to be on your network. It could be used to rename, remove, or check in under a name that was not theirs, and to get around the two-names-per-network limit. Your network address is now read from a source visitors cannot fake.",
        "The message shown when a network has used up its two names no longer lists what those names are.",
    ]},
    {"version": "Beta 1.15.0", "changes": [
        "Fixed a rare case where a match could report an empty winning team and rate nobody, caused by a disconnect briefly overwriting a full roster with a single stray name.",
        "Names can now be up to 16 letters, matching Starblast's own limit, instead of 8. Longer real names like GOLD LEADER and MASTER OF GOON can now be tracked.",
    ]},
    {"version": "Beta 1.14.0", "changes": [
        "Starblast's 44 default names (Hari Seldon, Zaphod, Vader, Spock and the rest) are no longer tracked. They are given to anyone who joins without typing a name, so dozens of different people share each one and the record belonged to nobody. Three were already on the board and have been removed.",
        "They also cannot be registered - otherwise claiming one would have collected the rating of every anonymous player using it.",
    ]},
    {"version": "Beta 1.13.0", "changes": [
        "Your name is now matched ignoring spaces, punctuation and capitals. The tracker reads the same player several ways - BERU has shown up as .BERU and BE R U in a single day - and previously each spelling was treated as a different person, so whether a match counted for you depended on how it happened to be read. All spellings now land on one record.",
    ]},
    {"version": "Beta 1.12.0", "changes": [
        "Turning up near the end of a match no longer earns you the win. You are only rated if you were already on the roster when the tracker started watching. This applies to losses too - joining a doomed match late will not cost you rating either.",
    ]},
    {"version": "Beta 1.11.2", "changes": [
        "Fixed a case where an unreadable scoreboard silently handed the win to the first team. If the scores cannot separate the teams, the match is no longer scored at all.",
    ]},
    {"version": "Beta 1.11.1", "changes": [
        "Simplified the Manage page and made Protection a proper on/off switch.",
        "You can only have one check-in live at a time - a new one cancels the last, so nobody can check into every match at once and then join whichever is winning.",
    ]},
    {"version": "Beta 1.10.0", "changes": [
        "Protection is now an opt-in toggle on the Manage page, and it is OFF by default. Registering a name no longer changes how it is rated.",
        "With protection ON, only matches you check into count - that is what stops someone playing under your name from moving your rating. With it off, everything counts as normal.",
    ]},
    {"version": "Beta 1.9.2", "changes": [
        "Fixed a bug introduced with check-in that made the tracker stop watching a match early, so some matches went unscored.",
    ]},
    {"version": "Beta 1.9.0", "changes": [
        "Moved check in, claim, rename and remove onto their own Manage your name page so the leaderboard is not cluttered.",
    ]},
    {"version": "Beta 1.8.0", "changes": [
        "Added Check in. Once your name has an owner, only matches you checked into count towards your rating - so nobody can play under your name and move it.",
        "Check-in is only open during a match's first 5 minutes, so nobody can wait to see who is winning before deciding it counts.",
        "If the same name appears twice in one lobby, neither is rated - there is no way to tell which is the real player.",
        "Fixed disconnect dialog text being mistaken for player names, which could stop a wiped-out team from registering as eliminated.",
    ]},
    {"version": "Beta 1.7.0", "changes": [
        "You can now request to claim a name that appeared automatically after a win. Those names have no owner, so claims are reviewed by hand before being granted - message justtempest on Discord to confirm it is you.",
    ]},
    {"version": "Beta 1.6.0", "changes": [
        "You can now change a name you registered - your elo, wins and losses carry over.",
        "Removing a name now asks for confirmation first.",
    ]},
    {"version": "Beta 1.6.0", "changes": [
        "Added player profile pages - click any name on the leaderboard.",
        "Added player search.",
        "Added this change log and the rating explanation page.",
    ]},
    {"version": "Beta 1.3.x", "changes": [
        "Blocked offensive names in several languages, not just English.",
        "Name filtering now applies only to names typed into the register box - names that starblast.io already allowed in-game are left alone, so nobody is silently kept off the board.",
    ]},
    {"version": "Beta 1.2.0", "changes": [
        "Rewrote how winners are decided. A damaged station no longer counts as a defeat - a team is only out when its station is destroyed AND it has no players left.",
        "When damage cannot separate two surviving teams, the higher team score now decides.",
        "Fixed matches occasionally being scored twice.",
    ]},
    {"version": "Beta 1.1.x", "changes": [
        "Fixed the tracker going blind after a reconnect, which had left it unable to read some lobbies at all.",
        "Stopped a lost connection being mistaken for a finished match, which had produced wrong results.",
        "Up to two names per network instead of one.",
        "Ability to remove a name you registered, as long as it has not played yet.",
    ]},
    {"version": "Beta 1.0.0", "changes": [
        "First public release: live leaderboard, registration, and automatic rating from tracked North American team matches.",
    ]},
]


def leaderboard_sort_key(row):
    """Ranking order for a (name, elo, wins, losses, ...) row.

    Elo alone leaves dozens of players tied at the same integer rating.
    Within a tie, rank by win rate then win count, so the order still
    means something instead of falling back to insertion order. Players
    with no matches yet sort last within their tier (rate -1 beats
    nothing real).
    """
    name, elo = row[0], row[1]
    wins = row[2] or 0
    losses = row[3] or 0
    played = wins + losses
    rate = (wins / played) if played else -1
    return (-elo, -rate, -wins, name.lower())


@app.route('/player/<name>')
def player_profile(name):
    """Public profile for one player. Lookup is case-insensitive so a
    search for "fede" finds "FEDE"; rank is derived from elo rather than
    stored, so it can never drift out of sync with the leaderboard."""
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, elo, wins, losses, clan, google_sub, "
              "COALESCE(strict_mode, 0) FROM players WHERE norm_name = ?",
              (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return render_template('player.html', player=None, query=name,
                               version=APP_VERSION, page='players'), 404

    stored_name, elo, wins, losses, clan, owner_sub, protected = row
    c.execute("SELECT COUNT(*) + 1 FROM players WHERE elo > ?", (elo,))
    rank = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM players")
    rank_of = c.fetchone()[0]

    # Where this player sits inside each region they have actually played
    # in, ranked the same way that region's own board ranks them - by the
    # rating earned there. A rank without its pool means nothing, so the
    # size of each pool is carried along with it.
    region_ranks = {}
    _key = normalize_name(name)
    for _rkey, _rlabel in REGIONS:
        _rows = board_rows(c, "all", _rkey)
        if not _rows:
            continue
        _rows.sort(key=leaderboard_sort_key)
        for _i, _r in enumerate(_rows, start=1):
            if normalize_name(_r[0]) == _key:
                region_ranks[_rkey] = {"rank": _i, "of": len(_rows)}
                break

    c.execute("SELECT COUNT(*) FROM claim_requests WHERE status = 'pending' "
              "AND name IN (SELECT name FROM players WHERE norm_name = ?)",
              (normalize_name(name),))
    pending_claim = c.fetchone()[0] > 0
    # Which clans this player's account runs. Shown on the profile so a
    # leader is identifiable away from the clan page itself.
    admin_of = clan_admin_tags(c, owner_sub) if owner_sub else []

    c.execute("SELECT m.played_at, mp.won, mp.delta, mp.half, mp.score, mp.played_as "
              "FROM match_players mp JOIN matches m ON m.id = mp.match_row "
              "WHERE mp.norm_name = ? ORDER BY m.id DESC LIMIT 15",
              (normalize_name(name),))
    history = [{"at": (r[0] or '')[5:16].replace('-', '/'),
                # Same instant, marked as UTC so the browser can localise
                # it. The plain "at" above stays as the fallback for
                # anyone without JavaScript.
                "at_utc": ((r[0] or '').replace(' ', 'T') + 'Z') if r[0] else '',
                "won": bool(r[1]),
                "delta": (f"{r[2]:+.1f}" if r[2] is not None else ""),
                "half": bool(r[3]),
                "score": (f"{r[4]:,}" if r[4] is not None else "-"),
                # Only worth showing when it differs from the name the
                # result was credited to; otherwise it is just noise.
                "played_as": (r[5] if len(r) > 5 and r[5] and r[5] != stored_name else "")}
               for r in c.fetchall()]

    c.execute("SELECT COALESCE(m.region, 'america'), "
              "SUM(CASE WHEN mp.won = 1 THEN 1 ELSE 0 END), "
              "SUM(CASE WHEN mp.won = 1 THEN 0 ELSE 1 END), "
              "SUM(COALESCE(mp.delta, 0)) "
              "FROM match_players mp JOIN matches m ON m.id = mp.match_row "
              "WHERE mp.norm_name = ? GROUP BY 1", (normalize_name(name),))
    split = {r[0]: (r[1] or 0, r[2] or 0, r[3] or 0) for r in c.fetchall()}
    # Every region is listed even when empty. "No matches in Europe" is a
    # real answer to the question, and a row appearing only once a player
    # has played there makes the three boards look like one.
    by_region = []
    for key, label in REGIONS:
        w, l, gained = split.get(key, (0, 0, 0))
        by_region.append({"key": key, "label": label, "wins": w, "losses": l,
                          "played": w + l, "gained": round(gained, 2),
                          "winrate": (f"{round(100 * w / (w + l))}%" if (w + l) else "-")})
    # Where this player actually plays. Most matches wins it, with wins as
    # the tie-break - someone splitting their time evenly is better
    # described by where they win than by whichever region sorts first.
    played_anywhere = [r for r in by_region if r["played"]]
    primary = None
    if played_anywhere:
        best = max(played_anywhere, key=lambda r: (r["played"], r["wins"]))
        rest = sum(r["played"] for r in played_anywhere) - best["played"]
        primary = {"label": best["label"],
                   "only": rest == 0,
                   "share": round(100 * best["played"] /
                                  sum(r["played"] for r in played_anywhere))}
    # Read while the connection is open - the dict below is built after
    # close, and a query there is exactly the 500 this line replaces.
    clan_shown = clan_display(c, clan) if clan else ""
    conn.close()

    played = (wins or 0) + (losses or 0)
    winrate = f"{round(100 * (wins or 0) / played)}%" if played else "-"
    player = {"name": stored_name,
              "display": display_name(stored_name, clan, clan_shown),
              "clan_display": clan_shown,
              "elo": f"{elo:.1f}", "wins": wins or 0,
              "losses": losses or 0, "rank": rank, "rank_of": rank_of,
              "winrate": winrate,
              "clan": clan, "pending_claim": pending_claim,
              "admin_of": admin_of,
              "owned": bool(owner_sub), "protected": bool(protected)}
    return render_template('player.html', player=player,
                           region_ranks=region_ranks, version=APP_VERSION,
                           contact=CONTACT_HANDLE, page='players', history=history,
                           by_region=by_region, primary=primary)


@app.route('/rename', methods=['POST'])
def rename_player():
    """Rename a name you registered, keeping its elo, wins and losses.

    Unlike /unregister this is allowed even after matches have been
    played: renaming carries your record with you, so it cannot be used
    to shed a bad rating. Same-network ownership is still required, and
    the new name faces the same checks a fresh registration would."""
    data = request.json
    if not data or 'old_name' not in data or 'new_name' not in data:
        return jsonify({"message": "Both the current and new name are required."}), 400

    old_name = data['old_name'].strip()
    new_name = data['new_name'].strip()
    if not is_valid_name_format(new_name):
        return jsonify({"message": "New name must be 1-16 letters or digits, and cannot end in a digit."}), 400
    if is_blocked_word(new_name):
        return jsonify({"message": "That name isn't allowed. Please choose another."}), 400

    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, reg_ip FROM players WHERE norm_name = ?", (normalize_name(old_name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{old_name}' is not registered."}), 404

    stored_name, reg_ip = row
    ok, err = owner_check(c, stored_name, reg_ip)
    if not ok:
        conn.close()
        return jsonify({"message": err}), 403

    c.execute("SELECT name FROM players WHERE norm_name = ? AND name != ?", (normalize_name(new_name), stored_name))
    if c.fetchone():
        conn.close()
        return jsonify({"message": f"'{new_name}' is already taken."}), 400

    c.execute("UPDATE players SET name = ?, norm_name = ? WHERE name = ?", (new_name, normalize_name(new_name), stored_name))
    conn.commit()
    conn.close()
    return jsonify({"message": f"'{stored_name}' is now '{new_name}'."}), 200


# A check-in is only honoured for this long. Comfortably covers the
# 45 minute cap a worker will watch a single match for, without letting a
# stale check-in vouch for a match hours later.
CHECKIN_VALID_SECONDS = 2 * 60 * 60

# How long after pressing Play a name may appear and still be taken as
# yours. Long enough to load the game and pick a side, short enough that
# somebody joining much later is not mistaken for you.
BINDING_WINDOW_SECONDS = 15 * 60

# The regions the tracker watches, and how they are labelled. Order is the
# order they appear in the interface.
REGIONS = [("america", "North America"), ("europe", "Europe"), ("asia", "Asia")]
REGION_KEYS = [r for r, _ in REGIONS]
REGION_LABELS = dict(REGIONS)
# "all" is a real, selectable view rather than a missing value, so it needs
# a label of its own. Kept out of REGION_KEYS: that list is what a region
# stored against a match is validated against, and no match is played in
# "all".
ALL_REGIONS = "all"
REGION_LABELS[ALL_REGIONS] = "All regions"
# What the leaderboard offers, combined view first.
REGION_CHOICES = [(ALL_REGIONS, REGION_LABELS[ALL_REGIONS])] + REGIONS

# Leaderboard windows. All time over every region is the live rating; each
# narrower view is computed from match history instead.
PERIODS = [("all", "All time"), ("month", "Monthly"),
           ("week", "Weekly"), ("day", "Daily")]
PERIOD_KEYS = [p for p, _ in PERIODS]
PERIOD_SQL = {"day": "-1 day", "week": "-7 days", "month": "-30 days"}

# How many rows of the leaderboard are sent at once. Every player on one
# page was 1.2 MB of HTML for 2,600 rows, and nobody scrolls that far -
# they search. Ranking is unaffected: the board is still sorted whole
# and then sliced, so a page boundary is only ever a display cut.
PER_PAGE = 50


def board_rows(c, period="all", region="all"):
    """Leaderboard rows for one window, as (name, elo, wins, losses, clan,
    protected) tuples, in no particular order.

    A running elo cannot be sliced - it is one number carried forward, not
    a series - so anything narrower than all-time-everywhere ranks by the
    rating a player GAINED inside the window. That is the only honest
    reading of "this week", and it is why the column changes its heading.
    """
    if period == "all" and region == "all":
        c.execute("SELECT name, elo, wins, losses, clan, COALESCE(strict_mode, 0) "
                  "FROM players")
        return [(name, elo, wins or 0, losses or 0, clan, bool(prot))
                for name, elo, wins, losses, clan, prot in c.fetchall()]

    where, args = [], []
    if region != "all":
        where.append("m.region = ?")
        args.append(region)
    if period in PERIOD_SQL:
        where.append("m.played_at >= datetime('now', ?)")
        args.append(PERIOD_SQL[period])
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    # Grouped on norm_name and joined back to players, never keyed on the
    # raw name. match_players keeps the name as it was played - decorated
    # with symbols and spacing - while players keeps the normalised form,
    # so grouping by name listed the same person twice under two spellings
    # and lost their clan and protection along the way. norm_name is what
    # the elo update, the profile history and the claim lookup all use.
    c.execute(
        "SELECT p.name, SUM(COALESCE(mp.delta, 0)), "
        "SUM(CASE WHEN mp.won = 1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN mp.won = 1 THEN 0 ELSE 1 END), "
        "p.clan, COALESCE(p.strict_mode, 0) "
        "FROM match_players mp "
        "JOIN matches m ON m.id = mp.match_row "
        "JOIN players p ON p.norm_name = mp.norm_name "
        + clause + " GROUP BY p.norm_name", args)
    return [(name, round(gained or 0, 2), wins or 0, losses or 0, clan, bool(prot))
            for name, gained, wins, losses, clan, prot in c.fetchall()]


# You may only check in during the opening minutes of a match. Without
# this you could simply wait, see how it is going, and check in only when
# winning - so a protected player's rating could rise but never fall.
# Requiring the declaration before the outcome is knowable is the whole
# point. Cost: someone joining a match already in progress cannot be
# rated for it.
CHECKIN_MAX_LOBBY_AGE = 10 * 60


def tracker_limits(c):
    """Capacity and pickup age as the tracker last reported them."""
    c.execute("SELECT key, value FROM tracker_state")
    state = {k: v for k, v in c.fetchall()}
    def num(key, default):
        try:
            return int(state.get(key, default))
        except (TypeError, ValueError):
            return default
    max_age = state.get('max_age_seconds')
    try:
        max_age = int(max_age) if max_age is not None else None
    except (TypeError, ValueError):
        max_age = None
    return (num('capacity', 3), num('min_age_seconds', 1200), max_age,
            num('min_players', 0))


def describe_lobbies(rows, capacity, min_age, max_age=None, min_players=0):
    """Turn raw lobby rows into what a player needs to see: whether it is
    being watched, when it will be, and whether they can still check in.

    Check-in closes exactly when the tracker starts watching. Those were two
    unrelated constants before - 10 minutes and 20 - which left a dead zone
    where a protected player could neither check in nor be picked up, so
    joining between minutes 10 and 20 meant the match could never count for
    them however it went."""
    watched_now = sum(1 for r in rows if r[3])
    free_slots = max(0, capacity - watched_now)
    out = []
    for name, players, age, watching in rows:
        age = age or 0
        if watching:
            status, tone = "Tracked", "on"
        elif max_age is not None and age > max_age:
            # Past the tracker's own cut-off, so no worker will ever take
            # it however many slots are free. Saying "starting shortly"
            # here sent players into a match that could not count.
            status, tone = "too old to track", "off"
        elif min_players and (players or 0) < min_players:
            # The tracker will not spend a worker on a lobby this small,
            # whatever its age or how many slots are free. Saying "waiting
            # for a free slot" implied it was queued - one 2-player lobby
            # claimed that for nearly two hours.
            status, tone = f"needs {min_players} players to be tracked", "off"
        elif age < min_age:
            mins = max(1, -(-(min_age - age) // 60))
            status, tone = f"eligible in {mins} min", "soon"
        elif free_slots > 0:
            status, tone = "starting shortly", "soon"
        else:
            status, tone = "waiting for a free slot", "off"
        out.append({"name": name, "players": players, "mins": int(age // 60),
                    "watching": bool(watching), "status": status, "tone": tone,
                    "can_checkin": not (max_age is not None and age > max_age)
                                   and not (min_players and (players or 0) < min_players)})
    return out, watched_now


@app.route('/api/lobbies', methods=['POST'])
def push_lobbies():
    """The tracker pushes the live NA lobby list here.

    PythonAnywhere's free tier cannot make outbound calls to starblast.io,
    so the site has no way to fetch this itself - the bot has to hand it
    over."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.json or {}
    lobbies = body.get('lobbies', [])
    conn = db(timeout=PUSH_TIMEOUT_SECONDS)
    c = conn.cursor()
    # Claim the write lock before doing anything, rather than discovering
    # halfway through that it is not available. The tracker re-sends the
    # complete state on the next sweep, so giving up here costs nothing,
    # whereas hanging on blocks a web worker long after the tracker has
    # stopped waiting for the reply.
    try:
        c.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError:
        conn.close()
        return jsonify({"status": "busy"}), 503
    for key in ('capacity', 'min_age_seconds', 'max_age_seconds'):
        if body.get(key) is not None:
            c.execute("INSERT OR REPLACE INTO tracker_state (key, value) VALUES (?, ?)",
                      (key, str(body[key])))
    # Pairs the tracker saw this cycle. Bounded and de-duplicated by the
    # primary key, so a noisy match cannot flood the table.
    now_ts = time.strftime('%Y-%m-%d %H:%M:%S')
    for pair in (body.get('name_fixes') or [])[:400]:
        try:
            ocr_name, real_name = str(pair[0])[:64], str(pair[1])[:64]
        except (TypeError, IndexError, ValueError):
            continue
        if not ocr_name or not real_name or ocr_name == real_name:
            continue
        c.execute("INSERT INTO name_map (ocr_name, real_name, seen, first_seen, last_seen) "
                  "VALUES (?, ?, 1, ?, ?) "
                  "ON CONFLICT(ocr_name, real_name) DO UPDATE SET "
                  "seen = seen + 1, last_seen = excluded.last_seen",
                  (ocr_name, real_name, now_ts, now_ts))

    c.execute("DELETE FROM live_lobbies")
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for lobby in lobbies[:40]:
        c.execute("INSERT OR REPLACE INTO live_lobbies (sys_id, name, players, age, updated_at, watching, region) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (lobby.get('id'), lobby.get('name'), lobby.get('players'), lobby.get('time'),
                   now, 1 if lobby.get('watching') else 0,
                   lobby.get('region') or 'america'))

    # Sightings of a ship id under a name. Kept for a short window - just
    # long enough for a check-in to be matched against one - then pruned.
    for ap in (body.get('appearances') or [])[:200]:
        try:
            c.execute("INSERT INTO appearances (sys_id, ship_id, name, region, at) "
                      "VALUES (?,?,?,?,?)",
                      (ap.get('sys_id'), ap.get('ship_id'), str(ap.get('name'))[:64],
                       ap.get('region'), ap.get('at') or now))
        except (TypeError, ValueError, sqlite3.Error):
            continue
    # Only prune occasionally. This is a full scan of a table that is
    # written several times a minute, and the rows it removes are ones
    # nothing has read for well over an hour - doing it every push spent
    # write-lock time on housekeeping that can wait.
    if random.randint(1, 20) == 1:
        c.execute("DELETE FROM appearances WHERE at < datetime('now', '-2 hours')")

    # Every push is a chance to match a fresh sighting to a waiting
    # check-in. Cheap - only unbound check-ins from the last few minutes
    # are considered.
    try:
        bind_appearances_to_checkins(c)
    except sqlite3.Error:
        pass
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "stored": len(lobbies[:40])}), 200


@app.route('/api/live_lobbies')
def live_lobbies():
    """Public list for the check-in picker. Deliberately exposes only the
    lobbies themselves - never who has checked in, since publishing that
    would tell an impersonator exactly which lobby to go and sit in."""
    conn = db()
    c = conn.cursor()
    capacity, min_age, max_age, min_players = tracker_limits(c)
    c.execute("SELECT sys_id, name, players, age, COALESCE(watching, 0), "
              "COALESCE(region, 'america') "
              "FROM live_lobbies WHERE updated_at > datetime('now', '-5 minutes') "
              "ORDER BY watching DESC, age DESC")
    rows = c.fetchall()
    conn.close()
    described, watched_now = describe_lobbies([(r[1], r[2], r[3], r[4]) for r in rows],
                                              capacity, min_age, max_age, min_players)
    for lobby, raw in zip(described, rows):
        lobby["id"] = raw[0]
        lobby["age"] = raw[3]
        # Callers group by this. Without it the bot could only ever show one
        # undifferentiated list, which is wrong now that three regions are
        # watched at once.
        lobby["region"] = raw[5]
        lobby["region_label"] = REGION_LABELS.get(raw[5], raw[5])
    return jsonify({"lobbies": described, "minutes_to_check_in": min_age // 60,
                    "capacity": capacity, "watching": watched_now,
                    "regions": [{"key": k, "label": l} for k, l in REGIONS]}), 200


@app.route('/protection', methods=['GET', 'POST'])
def protection():
    """Read or set a name's protection toggle.

    Protection ON means the name is only rated for matches it checked
    into, which is what stops someone else playing under it from moving
    the rating. It is deliberately opt-in: leaving it off keeps the
    ordinary automatic behaviour, so registering never silently costs a
    player their matches."""
    if request.method == 'GET':
        name = (request.args.get('name') or '').strip()
    else:
        name = str((request.json or {}).get('name', '')).strip()
    if not name:
        return jsonify({"message": "No name provided"}), 400

    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, reg_ip, COALESCE(strict_mode, 0), prot_changed_at "
              "FROM players WHERE norm_name = ?", (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{name}' is not on the leaderboard."}), 404
    stored_name, reg_ip, enabled, changed_at = row

    def hours_left():
        """Hours still to wait before protection can be flipped again."""
        if not changed_at:
            return 0.0
        c.execute("SELECT (julianday('now') - julianday(?)) * 24.0", (changed_at,))
        gone = c.fetchone()[0]
        if gone is None:
            return 0.0
        return max(0.0, PROTECTION_COOLDOWN_HOURS - gone)

    if request.method == 'GET':
        left = hours_left()
        # Ownership is the account, not the network. Reporting reg_ip here
        # left every account created since ratings moved to accounts - none
        # of which ever gets a reg_ip - looking like it owned nothing, so
        # the toggle was disabled for precisely the players it is meant for.
        owned, _ = owner_check(c, stored_name, reg_ip)
        conn.close()
        return jsonify({"name": stored_name, "owned": bool(owned),
                        "enabled": bool(enabled), "hours_left": round(left, 1)}), 200

    ok, err = owner_check(c, stored_name, reg_ip)
    if not ok:
        conn.close()
        return jsonify({"message": err}), 403

    want = 1 if (request.json or {}).get('enabled') else 0

    if not want:
        c.execute("SELECT COALESCE(game_name, '') FROM players WHERE name = ?",
                  (stored_name,))
        _gn = (c.fetchone() or [''])[0]
        if is_default_game_name(_gn):
            conn.close()
            return jsonify({"message": f"Your play name '{_gn}' is one of the game's "
                                       f"default names, so Protection stays on. Set a "
                                       f"play name of your own first.",
                            "enabled": True}), 400

    # No match history required. Protection is only useful BEFORE someone
    # else plays under your name, so demanding a tracked match first meant
    # your first match was always the exposed one - and after a board reset
    # that applied to everybody at once. The abuse it used to guard against
    # is much weaker now: an account name cannot be one already on the
    # board, results reach an account through the check-in binding, and a
    # misused name can be reported. Turning protection OFF is still always
    # allowed, so nobody can be stranded by it.

    if want != enabled:
        left = hours_left()
        if left > 0:
            conn.close()
            if left >= 1:
                wait = f"{int(left)} hour{'s' if int(left) != 1 else ''}"
            else:
                mins = max(1, int(left * 60))
                wait = f"{mins} minute{'s' if mins != 1 else ''}"
            return jsonify({"message": f"Protection can only be changed once a day. "
                                       f"Try again in {wait}.",
                            "enabled": bool(enabled)}), 429
        c.execute("UPDATE players SET strict_mode = ?, prot_changed_at = ? WHERE name = ?",
                  (want, time.strftime('%Y-%m-%d %H:%M:%S'), stored_name))
    conn.commit()
    conn.close()
    if want:
        return jsonify({"message": f"Protection is ON for '{stored_name}'. Only matches you check into will count.", "enabled": True}), 200
    return jsonify({"message": f"Protection is OFF for '{stored_name}'. All matches count, as normal.", "enabled": False}), 200


def perform_checkin(c, sub_id, sys_id):
    """Check an account into a lobby. Returns (http_status, payload).

    Shared by the website's /checkin and the bot's /api/bot/checkin. Two
    copies would drift the first time either was touched, and a check-in
    that means something different depending on where it was pressed is
    worse than one that lives in a single place.

    Does NOT commit - the caller owns the transaction.
    """
    if sys_id is None:
        return 400, {"ok": False, "message": "Which match? Pick one from the list."}
    try:
        sys_id = int(sys_id)
    except (TypeError, ValueError):
        return 400, {"ok": False, "message": "That lobby id is not valid."}

    # An account with no name has nowhere to put the result, so there is
    # nothing a check-in could achieve yet. Say so plainly rather than
    # accepting it and silently dropping the match later.
    who = account_name_for(c, sub_id)
    if not who:
        return 400, {"ok": False, "no_name": True,
                     "message": "Set your account name first - that is the name your "
                                "matches are recorded under."}

    c.execute("SELECT age FROM live_lobbies WHERE sys_id = ?", (sys_id,))
    lobby = c.fetchone()
    if not lobby:
        return 404, {"ok": False, "message": "That lobby is not in the current live list."}
    # No window. Half elo is what stops a latecomer collecting a full win
    # for arriving at the end, so refusing late check-ins only meant that
    # joining a match in progress could not be rated at all.
    lobby_age = lobby[0] or 0
    _, min_age, _max_age, _min_players = tracker_limits(c)

    # The name they will actually appear under, which is what has to be
    # said back to them. Falls back to the account name, which is what the
    # site assumes when no game name is set.
    c.execute("SELECT COALESCE(NULLIF(game_name, ''), name) FROM players WHERE name = ?",
              (who,))
    _row = c.fetchone()
    play_as = (_row[0] if _row else who) or who
    default_note = ""
    if is_default_game_name(play_as):
        c.execute("UPDATE players SET strict_mode = 1 WHERE name = ?", (who,))
        default_note = (" '%s' is one of the game's default names, so Protection "
                        "is on automatically - only matches you check into count."
                        % play_as)

    # One live check-in per account. Without this you could check into
    # every fresh lobby at once, watch which one is going well and join
    # only that one - keeping every option open would cost nothing.
    c.execute("DELETE FROM checkins WHERE sub = ? AND COALESCE(bound, 0) = 0 "
              "AND created_at > datetime('now', ?)",
              (sub_id, '-' + str(CHECKIN_VALID_SECONDS) + ' seconds'))
    c.execute("INSERT INTO checkins (player, sub, sys_id, created_at) VALUES (?,?,?,?)",
              (who, sub_id, sys_id, time.strftime('%Y-%m-%d %H:%M:%S')))
    late = lobby_age >= min_age
    note = (" This match is already under way, so your result counts at half value - "
            "and joining now only links to you if you have not already been playing."
            if late else
            " Play under any name you like - the first ship to appear is taken as yours.")
    return 200, {"ok": True,
                 "message": f"Checked in for this match as '{who}'.{note}"
                            f"{default_note} An earlier check-in you had not "
                            f"played yet is cancelled; one already tied to a "
                            f"match stays with it.",
                 "sys_id": sys_id, "late": late,
                 "account_name": who, "play_as": play_as}


@app.route('/checkin', methods=['POST'])
def check_in():
    """Declare that you are about to play a given lobby.

    You check in as an ACCOUNT, not as a name. That is the point: at the
    moment you press Play nobody knows yet which name you will appear
    under, and working that out is exactly what the check-in buys. The
    tracker reports every ship it sees; the first one to show up in this
    lobby after this row is written gets bound to you, and from then on
    that name's results are recorded against your account.
    """
    data = request.json or {}
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first, then press Play on the match "
                                   "you are about to join."}), 401
    conn = db()
    c = conn.cursor()
    status, payload = perform_checkin(c, sub_id, data.get('sys_id'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status




def perform_claim(c, me_sub, raw_name, raw_note, rate_src=None):
    """File a claim on an unowned leaderboard name.

    Shared by the website and the bot. Does NOT commit.
    """
    name = str(raw_name or '').strip()
    if not name:
        return 400, {"ok": False, "message": "No name provided."}
    note = str(raw_note or '').strip()[:200]

    # One name per account, the same rule registering follows. Without this
    # an account could register one name and then claim as many more as it
    # liked, which is the cap in name only.
    c.execute("SELECT name FROM players WHERE google_sub = ? "
              "AND (COALESCE(wins, 0) + COALESCE(losses, 0)) > 0", (me_sub,))
    held = [r[0] for r in c.fetchall()]
    if len(held) >= MAX_NAMES_PER_ACCOUNT:
        return 403, {"ok": False,
                     "message": f"Your account already has a name: '{held[0]}'. "
                                f"Remove it first if you want to claim a different one."}

    c.execute("SELECT name, google_sub FROM players WHERE norm_name = ?",
              (normalize_name(name),))
    row = c.fetchone()
    if not row:
        return 404, {"ok": False, "message": f"'{name}' is not on the leaderboard."}

    stored_name, owner_sub = row
    if owner_sub == me_sub:
        return 400, {"ok": False, "message": f"'{stored_name}' is already yours."}
    if owner_sub:
        return 400, {"ok": False,
                     "message": "That name already belongs to an account. If it is really "
                                "yours, report it and it will be looked at by hand."}

    c.execute("SELECT id FROM claim_requests WHERE name = ? AND google_sub = ? "
              "AND status = 'pending'", (stored_name, me_sub))
    if c.fetchone():
        return 400, {"ok": False,
                     "message": "You already have a pending claim for that name."}

    # Cap how many can be open at once. Each claim raises an alert, so an
    # unlimited supply is both a way to bury the genuine ones and a way to
    # flood the channel they are reported in.
    c.execute("SELECT COUNT(*) FROM claim_requests WHERE status = 'pending' "
              "AND google_sub = ?", (me_sub,))
    pending_mine = (c.fetchone() or [0])[0]
    if pending_mine >= MAX_PENDING_CLAIMS:
        return 429, {"ok": False,
                     "message": f"You already have {MAX_PENDING_CLAIMS} claims waiting. "
                                f"Wait for those to be looked at first."}
    if rate_hit(c, 'claim', MAX_PENDING_CLAIMS, '-1 day', src=rate_src):
        return 429, {"ok": False,
                     "message": f"You have started {MAX_PENDING_CLAIMS} claims in the "
                                f"last day, which is the limit - withdrawn ones "
                                f"included. Try again tomorrow."}

    c.execute("SELECT COALESCE(MAX(id), 0) FROM matches")
    from_match = c.fetchone()[0]
    c.execute("INSERT INTO claim_requests (name, ip, note, created_at, status, "
              "google_sub, verify_from) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
              (stored_name, None, note, time.strftime('%Y-%m-%d %H:%M:%S'),
               me_sub, from_match))
    n = CLAIM_WINS_REQUIRED
    return 200, {"ok": True, "name": stored_name,
                 "message": f"Claim started for '{stored_name}'. Prove it is yours "
                            f"with one ranked Deathmatch game - the Discord bot's "
                            f"/proveclaim walks you through it - or wait for the "
                            f"owner to review it. The claim is shown on that "
                            f"player's page while it is open, so the real owner "
                            f"can report it."}


def perform_claim_decide(c, claim_id, approve, decided_by=""):
    """The site owner granting a claim without waiting for the tracked win.

    Every check the automatic path makes is made here too - the name must
    be unheld, the account must be under its cap, and a placeholder row
    with no record is discarded so the claimed row can take its place.
    Skipping them here would let a hand-approval do what the automatic
    path is careful never to do: hand somebody a name that is already
    someone else's. Does NOT commit.
    """
    c.execute("SELECT name, google_sub, status FROM claim_requests WHERE id = ?",
              (claim_id,))
    row = c.fetchone()
    if not row:
        return 404, {"ok": False, "message": "No such claim."}
    name, claimant, status = row
    if status != 'pending':
        return 400, {"ok": False, "name": name,
                     "message": f"That claim was already {status}."}
    if not approve:
        c.execute("UPDATE claim_requests SET status = 'declined' WHERE id = ?",
                  (claim_id,))
        return 200, {"ok": True, "approved": False, "name": name,
                     "sub_id": claimant,
                     "message": f"Claim on '{name}' declined."}
    if not claimant:
        return 400, {"ok": False, "name": name,
                     "message": f"'{name}' was claimed without signing in, so there "
                                f"is no account to give it to. It can only complete "
                                f"the usual way."}
    key = normalize_name(name)
    c.execute("SELECT google_sub FROM players WHERE norm_name = ?", (key,))
    held = (c.fetchone() or [None])[0]
    if held and held != claimant:
        c.execute("UPDATE claim_requests SET status = 'declined' WHERE id = ?",
                  (claim_id,))
        return 200, {"ok": False, "name": name,
                     "message": f"'{name}' already belongs to another account, so "
                                f"the claim was declined instead."}
    c.execute("SELECT COUNT(*) FROM players WHERE google_sub = ?", (claimant,))
    if c.fetchone()[0] > MAX_NAMES_PER_ACCOUNT:
        return 400, {"ok": False, "name": name,
                     "message": f"That account already holds {MAX_NAMES_PER_ACCOUNT} "
                                f"names."}
    c.execute("SELECT name, COALESCE(wins, 0) + COALESCE(losses, 0) "
              "FROM players WHERE google_sub = ?", (claimant,))
    mine = c.fetchone()
    if mine and normalize_name(mine[0]) != key:
        if mine[1] > 0:
            return 400, {"ok": False, "name": name,
                         "message": f"That account already plays as '{mine[0]}', which "
                                    f"has a record of its own."}
        c.execute("DELETE FROM players WHERE name = ?", (mine[0],))
    c.execute("UPDATE players SET google_sub = ? WHERE norm_name = ?", (claimant, key))
    c.execute("UPDATE claim_requests SET status = 'approved' WHERE id = ?", (claim_id,))
    # Anyone else waiting on the same name is answered by the same decision.
    c.execute("UPDATE claim_requests SET status = 'declined' WHERE status = 'pending' "
              "AND id != ? AND name IN (SELECT name FROM players WHERE norm_name = ?)",
              (claim_id, key))
    return 200, {"ok": True, "approved": True, "name": name, "sub_id": claimant,
                 "message": f"'{name}' now belongs to that account."}


def refund_rate(c, kind, n, src=None):
    """Give back n rate events, newest first. The undo of rate_hit.

    Only called when the thing the event paid for was itself undone, so
    the limit still counts real, standing actions.
    """
    src = src or ip_source()
    c.execute("DELETE FROM rate_events WHERE rowid IN ("
              "SELECT rowid FROM rate_events WHERE kind = ? AND src = ? "
              "ORDER BY created_at DESC LIMIT ?)", (kind, src, int(n)))


def perform_claim_withdraw(c, sub_id, name=None, rate_src=None):
    """Take back a claim you have not had answered yet. Does NOT commit.

    Withdrawn rather than deleted: the row is what shows a name was asked
    for and by whom, and a claim that vanishes without trace is how the
    same argument gets had twice.
    """
    if not sub_id:
        return 401, {"ok": False, "message": "Sign in first."}
    want = str(name or '').strip()
    c.execute("SELECT id, name FROM claim_requests WHERE google_sub = ? "
              "AND status = 'pending' ORDER BY id", (sub_id,))
    rows = c.fetchall()
    if want:
        key = normalize_name(want)
        rows = [r for r in rows if normalize_name(r[1]) == key]
    if not rows:
        return 404, {"ok": False,
                     "message": f"You have no claim waiting on '{want}'." if want
                                else "You have no claim waiting."}
    c.executemany("UPDATE claim_requests SET status = 'withdrawn' WHERE id = ?",
                  [(r[0],) for r in rows])
    refund_rate(c, 'claim', len(rows), src=rate_src)
    names = ", ".join(r[1] for r in rows)
    return 200, {"ok": True, "withdrawn": [r[1] for r in rows],
                 "message": f"Claim on '{names}' withdrawn. You can claim it again "
                            f"whenever you like."}


@app.route('/claim/mine')
def claim_mine():
    """The claims this account is waiting on, so they can be taken back."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"claims": []}), 200
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, created_at FROM claim_requests WHERE google_sub = ? "
              "AND status = 'pending' ORDER BY id", (sub_id,))
    out = [{"name": r[0], "at": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"claims": out}), 200


@app.route('/claim/withdraw', methods=['POST'])
def claim_withdraw():
    """Take back a claim that has not been decided."""
    sub_id = current_user()
    conn = db()
    c = conn.cursor()
    status, payload = perform_claim_withdraw(c, sub_id,
                                             (request.json or {}).get('name'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/claim', methods=['POST'])
def claim_name():
    """Request ownership of a name that has no owner.

    Nothing is granted instantly - an instant claim would let anyone
    seize a top player's name and rename it. The claim completes on its
    own once the name wins a tracked match after filing, and while it is
    open it is shown publicly on that player's page so the real owner
    can see it and report it."""
    data = request.json or {}
    me_sub = current_user()
    if not me_sub:
        return jsonify({"message": "Sign in first - use the button at the top "
                                   "of the page."}), 401
    conn = db()
    c = conn.cursor()
    status, payload = perform_claim(c, me_sub, data.get('name'), data.get('note'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


def account_name_for(c, sub_id):
    """The name this account plays under on the leaderboard, or None."""
    if not sub_id:
        return None
    # Deterministic on purpose. A grandfathered account holds two rows and
    # a bare LIMIT 1 returned whichever the table felt like, so the Play
    # page could say one name and a check-in be recorded under the other.
    c.execute("SELECT name FROM players WHERE google_sub = ? "
              "ORDER BY (COALESCE(wins, 0) + COALESCE(losses, 0)) DESC, name LIMIT 1",
              (sub_id,))
    row = c.fetchone()
    return row[0] if row else None


def bind_appearances_to_checkins(c):
    """Turn 'someone checked in' plus 'a ship appeared' into 'that is them'.

    Only appearances AFTER a check-in in the SAME lobby count, and only
    within BINDING_WINDOW_SECONDS - a name that turns up half an hour later
    is somebody else. Each check-in binds once.
    """
    c.execute("SELECT rowid, sub, sys_id, created_at FROM checkins "
              "WHERE sub IS NOT NULL AND COALESCE(bound, 0) = 0 "
              "AND created_at > datetime('now', ?) ORDER BY created_at",
              (f'-{BINDING_WINDOW_SECONDS} seconds',))
    pending = c.fetchall()
    # A ship that has already been matched to somebody cannot also be
    # somebody else. Without this, two people pressing Play on the same
    # lobby both took the earliest join after their own click - which is
    # the same join - and one of them was credited with the other's game.
    c.execute("SELECT sys_id, ship_id FROM name_bindings")
    taken = {(r[0], r[1]) for r in c.fetchall()}
    for rowid, sub_id, sys_id, created_at in pending:
        # What this account says it plays as, falling back to the account
        # name - which is what the play name defaults to anyway.
        c.execute("SELECT game_name, name FROM players WHERE google_sub = ? "
                  "ORDER BY (COALESCE(wins, 0) + COALESCE(losses, 0)) DESC, name LIMIT 1",
                  (sub_id,))
        _row = c.fetchone()
        expect = normalize_name((_row[0] or _row[1]) if _row else '')
        if not expect:
            continue
        c.execute("SELECT name, ship_id, region FROM appearances "
                  "WHERE sys_id = ? AND at >= ? ORDER BY at",
                  (sys_id, created_at))
        hit = None
        for cand in c.fetchall():
            if (sys_id, cand[1]) in taken:
                continue
            if normalize_name(cand[0]) == expect:
                hit = cand
                break
        if not hit:
            continue
        name, ship_id, region = hit
        taken.add((sys_id, ship_id))
        who = account_name_for(c, sub_id)
        # Never bind an account to its own account name - that is already
        # the row results land on, and a self-binding would be a no-op that
        # only confuses the audit trail.
        if who and normalize_name(who) == normalize_name(name):
            c.execute("UPDATE checkins SET bound = 1 WHERE rowid = ?", (rowid,))
            continue
        c.execute("INSERT OR REPLACE INTO name_bindings "
                  "(sub, in_game_name, sys_id, ship_id, region, bound_at) "
                  "VALUES (?,?,?,?,?,?)",
                  (sub_id, name, sys_id, ship_id, region,
                   time.strftime('%Y-%m-%d %H:%M:%S')))
        c.execute("UPDATE checkins SET bound = 1 WHERE rowid = ?", (rowid,))


def account_for_ingame_name(c, name, sys_id=None):
    """The account this in-game name belongs to IN THIS MATCH, or None.

    Scoped to sys_id deliberately. A binding records that one ship in one
    lobby was one account - it is not a standing claim on the name. Looked
    up by name alone, a single check-in credited that account for every
    later match anyone played under the same name, which is the duplicate
    name problem turned around: instead of two players sharing a rating,
    one player quietly collects the other's results forever.
    """
    if not name or sys_id is None:
        return None
    c.execute("SELECT sub FROM name_bindings WHERE in_game_name = ? AND sys_id = ? "
              "LIMIT 1", (name, sys_id))
    row = c.fetchone()
    if not row:
        return None
    return account_name_for(c, row[0])


def current_user():
    """The signed-in Google account id, or None if nobody is signed in."""
    return session.get('google_sub')


def is_site_owner():
    """True when the REAL signed-in account is an owner. While the owner
    is impersonating the sandbox, current_user() is the sandbox - so the
    stashed real id is what counts."""
    real = session.get('dev_real_owner') or current_user()
    return real in OWNER_SUBS


def safe_next(raw):
    """A path on this site to return to after signing in, or None.

    Only our own paths. A value with a scheme, or a second leading slash,
    is a link to somebody else's site, and sending a freshly signed-in
    player there is how an invite link would be turned into a way of
    harvesting them. Anything that is not plainly local is dropped rather
    than repaired.
    """
    s = str(raw or '')
    if not s or len(s) > 200:
        return None
    if not s.startswith('/') or s.startswith('//'):
        return None
    if '\\' in s or any(ch < ' ' for ch in s):
        return None
    return s


def owner_check(c, stored_name, reg_ip):
    """May the current visitor act on this name? Returns (ok, error).

    Ownership is the signed-in account, and nothing else. The reg_ip
    parameter is historical - addresses are no longer recorded anywhere,
    and a network never proved identity to begin with. An unowned name
    is taken through a claim, which completes once the name wins a
    tracked match after filing.
    """
    me_sub = current_user()
    c.execute("SELECT google_sub FROM players WHERE name = ?", (stored_name,))
    row = c.fetchone()
    owner_sub = row[0] if row else None

    if owner_sub:
        if me_sub and me_sub == owner_sub:
            return True, None
        return False, ("That name belongs to another account. Sign in with the "
                       "account that owns it.")

    # No account on the name means nobody owns it - there is no network
    # fallback any more. Matching an address only ever proved somebody was
    # on the same wifi, which is why housemates, schools and mobile networks
    # could all edit each other's names. Claiming is the only route in, and
    # it is reviewed by a person.
    if not me_sub:
        return False, ("Sign in first, then use Claim to ask for this name.")
    return False, ("Nobody owns that name yet. Use Claim to ask for it - "
                   "prove a claim with one ranked Deathmatch game (the Discord bot walks you through it), or the owner reviews it by hand.")


@app.route('/auth/google', methods=['POST'])
def auth_google():
    """Sign in with the token Google's button hands to the browser.

    The signature is checked against Google's published keys and the
    token must have been issued for this site specifically, so a token
    minted for some other app cannot be replayed here. Only the opaque
    account id is kept - never the email or the name - which leaves the
    leaderboard holding no personal data about anyone.
    """
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except ImportError:
        return jsonify({"message": "Sign-in is temporarily unavailable."}), 503

    token = str((request.json or {}).get('credential', '')).strip()
    if not token:
        return jsonify({"message": "No sign-in token was received."}), 400

    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception:
        # Covers a bad signature, the wrong audience and an expired token.
        # The reason is deliberately not echoed back to the browser.
        return jsonify({"message": "That sign-in could not be verified. Please try again."}), 401

    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        return jsonify({"message": "That sign-in could not be verified."}), 401
    sub_id = str(claims.get('sub') or '')
    if not sub_id:
        return jsonify({"message": "That sign-in could not be verified."}), 401

    session.permanent = True
    session['google_sub'] = sub_id
    return jsonify({"message": "Signed in."}), 200


def remember_discord_user(sub_id, username, display):
    """Keep the handle behind a Discord identity current."""
    conn = db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO discord_users (sub, username, display, updated_at) "
              "VALUES (?, ?, ?, ?)",
              (sub_id, username or '', display or '',
               time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


def discord_handle(c, sub_id):
    """The Discord handle behind an identity, or None for a Google one."""
    if not sub_id or not str(sub_id).startswith('discord:'):
        return None
    c.execute("SELECT username, display FROM discord_users WHERE sub = ?", (sub_id,))
    row = c.fetchone()
    if not row:
        return None
    return row[1] or row[0] or None


@app.route('/auth/discord')
def auth_discord_start():
    """Send the player to Discord to approve the sign-in."""
    if not (DISCORD_CLIENT_ID and not DISCORD_CLIENT_ID.startswith('DISCORD_CLIENT_ID')
            and DISCORD_CLIENT_SECRET):
        return redirect('/?signin=unavailable')
    from urllib.parse import urlencode
    # The state is what stops someone handing you a link that quietly signs
    # you into *their* account: the value has to come back unchanged, and
    # only this browser's session knows what was sent.
    state = secrets.token_urlsafe(24)
    session.permanent = True
    session['discord_state'] = state
    # Where to go once Discord sends them back. An invite link needs this:
    # without it the player signs in and lands on the front page, with no
    # sign of the clan they were trying to join.
    session['discord_next'] = safe_next(request.args.get('next'))
    return redirect(DISCORD_AUTHORIZE_URL + '?' + urlencode({
        'client_id': DISCORD_CLIENT_ID,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'identify',
        'state': state,
        'prompt': 'none',
    }))


@app.route('/auth/discord/callback')
def auth_discord_callback():
    """Finish the sign-in Discord just sent back.

    Only `identify` is asked for, so what comes back is an account id and a
    handle - no email, and nothing that could be used to contact anyone.
    """
    expected = session.pop('discord_state', None)
    given = request.args.get('state', '')
    if not expected or not given or not secrets.compare_digest(str(given), str(expected)):
        return redirect('/?signin=expired')
    if request.args.get('error'):
        # The player pressed Cancel on Discord's screen. Nothing to say.
        return redirect('/')
    code = request.args.get('code', '')
    if not code:
        return redirect('/?signin=failed')

    try:
        import requests as _rq
    except ImportError:
        return redirect('/?signin=unavailable')

    try:
        tok = _rq.post(
            DISCORD_API + '/oauth2/token',
            data={
                'client_id': DISCORD_CLIENT_ID,
                'client_secret': DISCORD_CLIENT_SECRET,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': DISCORD_REDIRECT_URI,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10,
        )
        if tok.status_code != 200:
            return redirect('/?signin=failed')
        access = (tok.json() or {}).get('access_token')
        if not access:
            return redirect('/?signin=failed')
        who = _rq.get(DISCORD_API + '/users/@me',
                      headers={'Authorization': 'Bearer ' + access}, timeout=10)
        if who.status_code != 200:
            return redirect('/?signin=failed')
        info = who.json() or {}
    except Exception:
        # A network hiccup between here and Discord is not the player's
        # problem to read a stack trace about.
        return redirect('/?signin=failed')

    discord_id = str(info.get('id') or '')
    if not discord_id:
        return redirect('/?signin=failed')

    sub_id = 'discord:' + discord_id
    session.permanent = True
    session['google_sub'] = sub_id
    remember_discord_user(sub_id, info.get('username') or '',
                          info.get('global_name') or info.get('username') or '')
    back = safe_next(session.pop('discord_next', None))
    return redirect(back or '/?signin=ok')


# The game's own default commander names, extracted from the
# starblast.io client on 17 Aug 2026 (44 names). Half the ships in any
# lobby wear one, so an account playing under one can never be told
# apart from strangers by name alone - Protection is therefore forced
# on while a default name is the play name: only checked-in matches
# count, which shields the account AND every stranger sharing the name.
DEFAULT_GAME_NAMES = {normalize_name(_n) for _n in (
    'Arkady Darell', 'Bel Riose', 'Cleon I', 'Dors Venabili',
    'Ebling Mis', 'Gaal Dornick', 'Hari Seldon', 'Hober Mallow',
    'Janov Pelorat', 'The Mule', 'Preem Palver', 'R.D. Olivaw',
    'R.G. Reventlov', 'Raych Seldon', 'Salvor Hardin', 'Wanda Seldon',
    'Yugo Amaryl', 'James T. Kirk', 'Leonard McCoy', 'Hikaru Sulu',
    'Montgomery Scott', 'Spock', 'Picard', 'Christine Chapel',
    'Nyota Uhura', 'Pavel Chekov', 'Ford', 'Zaphod', 'Marvin',
    'Anakin', 'Luke', 'Leia', 'Ackbar', 'Tarkin', 'Jabba', 'Rey',
    'Kylo', 'Han', 'Vader', 'D.A.R.Y.L.', 'HAL 9000',
    'Lyta Alexander', 'Stephen Franklin', 'Lennier')}


def is_default_game_name(name):
    """Whether this is one of the names the game hands out for free."""
    return normalize_name(str(name or '')) in DEFAULT_GAME_NAMES


def perform_set_game_name(c, sub_id, raw_name):
    """Set (or clear) the name this account currently plays under.

    Shared by the website and the bot so both enforce the same rules.
    Does NOT commit - the caller owns the transaction.
    """
    name = str(raw_name or '').strip()[:32]
    who = account_name_for(c, sub_id)
    if not who:
        return 400, {"ok": False, "no_name": True,
                     "message": "Set your account name first - that is the name your "
                                "matches are recorded under."}
    if name and is_blocked_word(name):
        return 400, {"ok": False,
                     "message": "That name isn't allowed. Please choose another."}
    c.execute("UPDATE players SET game_name = ? WHERE name = ?", (name or None, who))
    if not name:
        return 200, {"ok": True, "game_name": "",
                     "message": "Cleared. Your profile no longer says what you play as."}
    if is_default_game_name(name):
        c.execute("UPDATE players SET strict_mode = 1 WHERE name = ?", (who,))
        return 200, {"ok": True, "game_name": name, "protection_forced": True,
                     "message": f"Noted - you play as '{name}'. That is one of the "
                                f"game's default names, which many players wear at "
                                f"once - so Protection is now ON automatically: only "
                                f"matches you check into count, and it stays on "
                                f"while you use a default name."}
    return 200, {"ok": True, "game_name": name,
                 "message": f"Noted - you play as '{name}'. Your results still appear "
                            f"under '{who}' whenever you press Play."}


@app.route('/account/gamename', methods=['POST'])
def set_game_name():
    """Set the name this account currently plays under in Starblast.

    Free to change as often as you like, because it is a statement about
    what to expect rather than a claim on anything: it never routes a
    result by itself. Pressing Play is what ties a match to you, and that
    works whatever you are called at the time. Sending an empty value
    clears it.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    conn = db()
    c = conn.cursor()
    status, payload = perform_set_game_name(c, sub_id, (request.json or {}).get('name', ''))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


def board_name_readings(name, clan):
    """Every plain-letter reading of a leaderboard row a person might type.

    The whole name, and the name without its clan tag - somebody wearing a
    tag types their own name, not the tag as well.
    """
    out = set()
    whole = clean_clan_tag(name)
    if whole:
        out.add(whole)
    if not clan:
        return out
    bare = clean_clan_tag(display_name(name, clan))
    if bare:
        out.add(bare)
    key = clean_clan_tag(clan)
    if key and len(whole) > len(key):
        if whole.startswith(key):
            out.add(whole[len(key):])
        if whole.endswith(key):
            out.add(whole[:-len(key)])
    return out


def similar_board_name(c, name, sub_id):
    """An unclaimed row that READS the same as this name, or None.

    The trap this closes, hit twice on 14 Aug: a player sets a plain
    account name while playing under a styled version of it. Their matches
    land on the styled row, which they do not own, and their own row sits
    at 0-0 for ever with nothing to say why. The fold is the one the search
    box already uses, so KASANE TETO and the styled form read alike.

    Only rows with a record and no owner are offered. An empty row is
    nothing to claim, and a row that belongs to somebody else is not theirs
    to take. Where several read the same, the busiest one wins.
    """
    want = clean_clan_tag(name)
    if len(want) < 2:
        return None
    mine = normalize_name(name)
    c.execute("SELECT name, clan, COALESCE(wins, 0), COALESCE(losses, 0), norm_name "
              "FROM players WHERE (google_sub IS NULL OR google_sub = '') "
              "AND COALESCE(wins, 0) + COALESCE(losses, 0) > 0")
    best = None
    for row_name, clan, wins, losses, norm in c.fetchall():
        if norm == mine:
            continue
        if want not in board_name_readings(row_name, clan):
            continue
        if best is None or wins + losses > best[1] + best[2]:
            best = (row_name, wins, losses)
    return best


@app.route('/account/name', methods=['POST'])
def set_account_name():
    """Set or change the name this account appears under.

    This replaces name registration. The name is a label for the account,
    not a claim on anyone else's results - taking over an existing row is
    what /claim is for, and that needs evidence you actually played as it.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    name = str((request.json or {}).get('name', '')).strip()
    anyway = bool((request.json or {}).get('anyway'))
    if not is_valid_name_format(name):
        return jsonify({"message": "That name cannot be used. Try another."}), 400
    if is_blocked_word(name):
        return jsonify({"message": "That name isn't allowed. Please choose another."}), 400
    if is_default_name(name):
        return jsonify({"message": "That is one of Starblast's default names - too many "
                                   "players share it. Pick a name of your own."}), 400

    conn = db()
    c = conn.cursor()
    c.execute("BEGIN IMMEDIATE")
    key = normalize_name(name)
    c.execute("SELECT google_sub FROM players WHERE norm_name = ?", (key,))
    taken = c.fetchone()
    if taken and taken[0] and taken[0] != sub_id:
        conn.close()
        return jsonify({"message": f"'{name}' already belongs to another account."}), 403
    if taken and not taken[0]:
        conn.close()
        return jsonify({"message": f"'{name}' is already on the leaderboard as an "
                                   f"unverified player. Use Claim to take it over.",
                        "claim_name": name}), 409

    # Already one of this account's own rows - including the case where it
    # is the name they are currently using. Nothing to move, and trying to
    # would rename some other row on top of it.
    if taken and taken[0] == sub_id:
        c.execute("SELECT name FROM players WHERE norm_name = ?", (key,))
        row = c.fetchone()
        conn.commit()
        conn.close()
        return jsonify({"message": f"Your account name is '{row[0] if row else name}'."}), 200

    # A row that READS like the name they typed. Their matches are landing
    # there and not here, and until now nothing said so - two players spent
    # the day at 0-0 while a styled version of their name collected the
    # record. Refusing outright would trap anyone whose name genuinely
    # reads like somebody else's, so this is a question, not a wall.
    if not anyway:
        near = similar_board_name(c, name, sub_id)
        if near:
            conn.close()
            return jsonify({
                "message": f"'{near[0]}' is already on the leaderboard and reads the same "
                           f"as '{name}' - it has a {near[1]}-{near[2]} record. If that is "
                           f"you, claim it: that row is where your matches are landing.",
                "claim_name": near[0],
                "suggest_claim": True,
            }), 409

    # An account is meant to hold one name, but the grandfathered ones hold
    # two, and updating on google_sub moved BOTH rows to the same
    # norm_name - which the unique index refused, failing every save. Pick
    # one row and rename that, keyed on its own primary key. The one with a
    # record is the one that matters, and the tie-break keeps it stable
    # rather than leaving it to whatever order the table returns.
    c.execute("SELECT name FROM players WHERE google_sub = ? "
              "ORDER BY (COALESCE(wins, 0) + COALESCE(losses, 0)) DESC, name LIMIT 1",
              (sub_id,))
    mine = c.fetchone()
    if mine:
        c.execute("SELECT COALESCE(name_changes, 0) FROM players WHERE name = ?", (mine[0],))
        used = (c.fetchone() or [0])[0]
        if used >= MAX_ACCOUNT_NAME_CHANGES:
            conn.close()
            return jsonify({"message": f"Your account name has already been changed "
                                       f"{used} time{'' if used == 1 else 's'}, which is the "
                                       f"limit - it is how other players recognise you on the "
                                       f"board. The name you PLAY under can still be changed "
                                       f"whenever you like."}), 403
        c.execute("UPDATE players SET name = ?, norm_name = ?, "
                  "name_changes = COALESCE(name_changes, 0) + 1 WHERE name = ?",
                  (name, key, mine[0]))
        # The play name defaults to the account name, and follows it while
        # it has never been set to anything else - most people play under
        # the name they signed up with, and making them type it twice to
        # say so is busywork.
        c.execute("UPDATE players SET game_name = ? WHERE name = ? AND "
                  "(game_name IS NULL OR game_name = '' OR game_name = ?)",
                  (name, name, mine[0]))
        left = MAX_ACCOUNT_NAME_CHANGES - (used + 1)
        msg = (f"Your account name is now '{name}'. "
               + (f"You can change it {left} more time." if left
                  else "That was your last change."))
    else:
        c.execute("INSERT INTO players (name, elo, wins, losses, norm_name, google_sub) "
                  "VALUES (?, ?, 0, 0, ?, ?)", (name, STARTING_ELO, key, sub_id))
        msg = f"Your account name is '{name}'."
    landed = join_own_clans(c, sub_id)
    if landed:
        msg += f" You are now on the {landed[0][0]} roster."
    conn.commit()
    conn.close()
    return jsonify({"message": msg}), 200


@app.route('/dev/actas', methods=['POST'])
def dev_actas():
    """Owner steps into the blank sandbox account. Verified against the
    REAL current user, and the real id is stashed so /dev/restore can
    only ever hand it back."""
    if current_user() not in OWNER_SUBS:
        return jsonify({"error": "Not allowed."}), 403
    conn = db()
    c = conn.cursor()
    # Fresh slate: the sandbox is never a real person, so wiping its
    # rows is safe and makes every test start as a nameless newcomer.
    c.execute("DELETE FROM players WHERE google_sub = ?", (SANDBOX_SUB,))
    c.execute("DELETE FROM claim_requests WHERE google_sub = ?", (SANDBOX_SUB,))
    conn.commit()
    conn.close()
    session['dev_real_owner'] = current_user()
    session['google_sub'] = SANDBOX_SUB
    return jsonify({"ok": True}), 200


@app.route('/dev/restore', methods=['POST'])
def dev_restore():
    """Return to the real owner account. Safe by construction: it only
    restores the id a prior owner-verified /dev/actas stashed."""
    real = session.pop('dev_real_owner', None)
    if real:
        session['google_sub'] = real
    return jsonify({"ok": True}), 200


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Signed out."}), 200


def current_lang():
    """The language for this request.

    ?lang= wins so a link can carry it, then the cookie, then whatever the
    browser asks for in Accept-Language. English if none of that fits.
    """
    asked = str(request.args.get('lang', '')).strip().lower()
    if asked in i18n.LANG_KEYS:
        return asked
    cookie = str(request.cookies.get('lang', '')).strip().lower()
    if cookie in i18n.LANG_KEYS:
        return cookie
    for chunk in str(request.headers.get('Accept-Language', '')).split(','):
        code = chunk.split(';')[0].strip().lower()[:2]
        if code in i18n.LANG_KEYS:
            return code
    return i18n.DEFAULT_LANG


@app.context_processor
def inject_lang():
    """t(), the language list, and whether to show the Your clan tab."""
    lang = current_lang()
    mine = None
    sub_id = current_user()
    if sub_id:
        # One indexed look-up per page for signed-in visitors. The nav is
        # rendered on every page, so this cannot be any heavier than that.
        try:
            conn = db()
            c = conn.cursor()
            tags = clan_admin_tags(c, sub_id)
            if tags:
                mine = {"tag": tags[0], "display": clan_display(c, tags[0]),
                        "role": clan_role(c, sub_id, tags[0]), "count": len(tags)}
            conn.close()
        except Exception:
            mine = None
    return {"t": lambda text: i18n.translate(text, lang),
            "lang": lang, "langs": i18n.LANGS, "my_clan": mine}


@app.route('/lang/<code>')
def set_lang(code):
    """Remember a language and go back where you were."""
    code = str(code or '').lower()
    if code not in i18n.LANG_KEYS:
        return redirect('/')
    back = request.referrer or '/'
    # Only ever back into this site: a referrer is attacker-controllable
    # and an open redirect is not worth a convenience.
    if not back.startswith(request.host_url):
        back = '/'
    resp = redirect(back)
    resp.set_cookie('lang', code, max_age=60 * 60 * 24 * 365,
                    samesite='Lax', path='/')
    return resp


def notice_invites(c, sub_id):
    """Clan invitations waiting on this account's names. Actionable,
    so they count on the badge until actually answered."""
    if not sub_id:
        return []
    c.execute("SELECT i.id, i.clan, i.name FROM clan_invites i "
              "JOIN players p ON p.name = i.name "
              "WHERE i.status = 'pending' AND i.direction = 'invite' "
              "AND p.google_sub = ? ORDER BY i.id", (sub_id,))
    return [{"id": r[0], "clan": r[1], "name": r[2]} for r in c.fetchall()]


def notice_updates(c, sub_id):
    """Decisions this account has not seen yet - claims, clan
    applications and leader requests, wherever they were decided.
    Withdrawn claims are the account's own doing and never listed."""
    if not sub_id:
        return []
    out = []
    c.execute("SELECT id, name, status FROM claim_requests "
              "WHERE google_sub = ? AND status IN ('approved', 'declined') "
              "AND COALESCE(seen, 0) = 0 ORDER BY id", (sub_id,))
    for r in c.fetchall():
        out.append({"kind": "claim", "id": r[0], "text":
                    ("Your claim on '%s' was approved - the name is yours." % r[1])
                    if r[2] == 'approved' else
                    ("Your claim on '%s' was declined." % r[1])})
    c.execute("SELECT id, clan, name, status FROM clan_invites "
              "WHERE invited_by = ? AND direction = 'application' "
              "AND status IN ('approved', 'declined') "
              "AND COALESCE(seen, 0) = 0 ORDER BY id", (sub_id,))
    for r in c.fetchall():
        out.append({"kind": "application", "id": r[0], "text":
                    ("%s accepted '%s' - you are in." % (r[1], r[2]))
                    if r[3] == 'approved' else
                    ("%s declined '%s'." % (r[1], r[2]))})
    c.execute("SELECT id, tag, status FROM clan_leader_requests "
              "WHERE google_sub = ? AND status IN ('approved', 'denied') "
              "AND COALESCE(seen, 0) = 0 ORDER BY id", (sub_id,))
    for r in c.fetchall():
        out.append({"kind": "leader", "id": r[0], "text":
                    "Your request to run a clan was approved - create it on the Clans page."
                    if r[2] == 'approved' else
                    "Your request to run a clan was denied."})
    return out


def notice_result_count(c, sub_id):
    """Match results recorded since this account last opened its page.
    Counts across every name the account owns, and the account page
    clears the same set, so the badge can never get stuck."""
    if not sub_id:
        return 0
    c.execute("SELECT COUNT(*) FROM match_players mp "
              "JOIN players p ON p.norm_name = mp.norm_name "
              "WHERE p.google_sub = ? AND COALESCE(mp.seen, 0) = 0", (sub_id,))
    return c.fetchone()[0]


@app.route('/me')
def me():
    """Who is signed in, and which names they own."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"logged_in": False, "names": []}), 200
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name FROM players WHERE google_sub = ? ORDER BY name", (sub_id,))
    names = [row[0] for row in c.fetchall()]
    # The name results are recorded under, and the clan it is in. The clan
    # page needs both to know whether to offer applying: you cannot apply
    # without a name, and you cannot apply while already in a clan.
    account_name = account_name_for(c, sub_id)
    my_clan = None
    if account_name:
        c.execute("SELECT clan FROM players WHERE name = ?", (account_name,))
        my_clan = (c.fetchone() or [None])[0]

    # Which provider signed you in, so the header can say so. The Google
    # flow labels itself from the browser; Discord has to be told from here
    # because nothing about that sign-in touches the page.
    provider = 'discord' if str(sub_id).startswith('discord:') else 'google'
    label = discord_handle(c, sub_id) if provider == 'discord' else None

    # Which match this account is currently checked into, if any. Without
    # this the Play page cannot show that you are already checked in - and
    # since checking into a second lobby silently cancels the first, an
    # invisible check-in is one you can lose by clicking again.
    checkin = None
    if names:
        c.execute("SELECT sys_id, created_at FROM checkins WHERE sub = ? "
                  "AND created_at > datetime('now', ?) ORDER BY id DESC LIMIT 1",
                  (sub_id, f'-{CHECKIN_VALID_SECONDS} seconds'))
        row = c.fetchone()
        if row:
            checkin = {"sys_id": row[0], "at": row[1]}
    conn.close()
    # Its own short-lived connection on purpose: the one above is already
    # closed by this point, and reaching for it threw
    # "Cannot operate on a closed database" on EVERY /me call - which the
    # pages read to decide whether you are signed in, so a working sign-in
    # looked like being signed out the moment you changed tab.
    _gn = None
    try:
        _c2 = db()
        _gn = _c2.execute("SELECT game_name FROM players WHERE google_sub = ? "
                          "AND game_name IS NOT NULL LIMIT 1", (sub_id,)).fetchone()
        _c2.close()
    except sqlite3.Error:
        pass
    stats = None
    if account_name:
        try:
            _c3 = db()
            _row = _c3.execute("SELECT elo, COALESCE(wins,0), COALESCE(losses,0) "
                               "FROM players WHERE norm_name = ?",
                               (normalize_name(account_name),)).fetchone()
            if _row:
                _rank = _c3.execute("SELECT COUNT(*) + 1 FROM players WHERE elo > ?",
                                    (_row[0],)).fetchone()[0]
                stats = {"elo": round(_row[0], 2), "rank": _rank,
                         "wins": _row[1], "losses": _row[2]}
            _c3.close()
        except sqlite3.Error:
            pass
    # Own short-lived connection, same as stats above - the main one
    # is long closed and reusing it is the recurring closed-DB trap.
    admin_of = []
    notices = {"invites": 0, "updates": 0, "results": 0, "total": 0}
    try:
        _c4 = db()
        _cc = _c4.cursor()
        admin_of = clan_admin_tags(_cc, sub_id)
        _inv = len(notice_invites(_cc, sub_id))
        _upd = len(notice_updates(_cc, sub_id))
        _res = notice_result_count(_cc, sub_id)
        _c4.close()
        notices = {"invites": _inv, "updates": _upd, "results": _res,
                   "total": _inv + _upd + _res}
    except sqlite3.Error:
        pass
    return jsonify({"logged_in": True, "account_name": account_name, "clan": my_clan, "names": names, "checkin": checkin, "stats": stats, "admin_of": admin_of, "notices": notices,
                    # Reveals the owner-only live win-probability tab in the menu.
                    "is_owner": is_site_owner(),
                    # Defaults to the account name: that is what most
                    # people are called in game, and a blank box on Play
                    # reads as "unknown" rather than "same as my name".
                    "game_name": (_gn[0] if _gn and _gn[0]
                                  else (names[0] if names else "")),
                    "provider": provider, "label": label}), 200


def join_date(stamp):
    """`2026-08-12 18:20:04` as `12 Aug 2026`.

    A day is as precise as this needs to be, and an empty string for the
    members who were already in a clan before dates were kept - showing
    them a made-up date would be worse than showing them none.
    """
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    try:
        year, month, day = str(stamp or "")[:10].split("-")
        return "%d %s %s" % (int(day), months[int(month) - 1], year)
    except (ValueError, IndexError):
        return ""


@app.route('/clan/<tag>')
def clan_page(tag):
    """Everyone currently carrying one clan tag, ranked as the leaderboard
    ranks them."""
    known = canonical_clan_tag(tag)
    if not known:
        return render_template('clan.html', clan=None, query=tag,
                               version=APP_VERSION, contact=CONTACT_HANDLE,
                               page='clans'), 404

    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, elo, wins, losses, google_sub, clan_joined_at "
              "FROM players WHERE clan = ?", (known,))
    rows = c.fetchall()
    c.execute("SELECT google_sub, COALESCE(role, 'leader') FROM clan_admins WHERE clan = ?",
              (known,))
    roles = {r[0]: r[1] for r in c.fetchall() if r[0]}
    admin_subs = set(roles)
    # Rank is the player's place on the WHOLE leaderboard, not within the
    # clan: a member shown as #12 has to mean the same thing on both pages.
    ranks = {}
    for row in rows:
        c.execute("SELECT COUNT(*) + 1 FROM players WHERE elo > ?", (row[1],))
        ranks[row[0]] = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(won), 0), COALESCE(SUM(1 - won), 0) "
              "FROM clan_results WHERE clan = ?", (known,))
    clan_wins, clan_losses = c.fetchone()
    apps = clan_applications(c, known)
    c.execute("SELECT region FROM clans WHERE tag = ?", (known,))
    region_key = (c.fetchone() or [None])[0] or ""
    shown_tag = clan_display(c, known)
    conn.close()

    rows.sort(key=leaderboard_sort_key)

    members = []
    total_wins = total_losses = total_elo = 0
    for name, elo, wins, losses, owner_sub, joined in rows:
        wins = wins or 0
        losses = losses or 0
        played = wins + losses
        total_wins += wins
        total_losses += losses
        total_elo += elo
        members.append({
            "name": name, "display": display_name(name, known, shown_tag),
            "admin": bool(owner_sub) and owner_sub in admin_subs,
            "role": roles.get(owner_sub, ""),
            "role_label": CLAN_ROLE_LABELS.get(roles.get(owner_sub), ""),
            "elo": f"{elo:.1f}", "wins": wins, "losses": losses,
            "winrate": f"{round(100 * wins / played)}%" if played else "-",
            "rank": ranks[name],
            "joined": join_date(joined),
        })

    # The sum of the members' own records, which is every match they have
    # ever played rather than only those since clan tracking began. The
    # per-match count in clan_results is still recorded and is the more
    # honest figure - a single match won by several clanmates counts once
    # there and once per member here - but with clans this small nobody has
    # yet won a match alongside a clanmate, so the totals agree and the
    # longer history is worth more. Switch back to clan_wins/clan_losses
    # once clans routinely play together.
    clan_wins, clan_losses = total_wins, total_losses
    played = clan_wins + clan_losses
    clan = {
        "tag": known,
        "members": members,
        "size": len(members),
        "avg_elo": f"{total_elo / len(members):.1f}" if members else "0.0",
        "wins": clan_wins,
        "losses": clan_losses,
        "winrate": f"{round(100 * clan_wins / played)}%" if played else "-",
        "played": played,
    }
    clan["applications"] = apps
    clan["region"] = region_key
    clan["region_label"] = REGION_LABELS.get(region_key, "")
    clan["regions"] = REGIONS
    # "run by" means the leader. Co-leaders and moderators are shown on
    # their own rows rather than in the heading, or a big clan's heading
    # would be a list of staff.
    clan["admins"] = [m["name"] for m in members if m["role"] == 'leader']
    conn2 = db()
    c2 = conn2.cursor()
    clan["display"] = clan_display(c2, known)
    clan["your_role"] = clan_role(c2, current_user(), known) or ""
    clan["can_manage"] = clan_rank(clan["your_role"]) >= clan_rank('coleader')
    clan["is_leader"] = clan["your_role"] == 'leader'
    conn2.close()
    return render_template('clan.html', clan=clan, version=APP_VERSION,
                           contact=CONTACT_HANDLE, page='clans',
                           client_id=GOOGLE_CLIENT_ID)


@app.route('/clan/leave', methods=['POST'])
def clan_leave():
    """Take yourself out of your own clan.

    Separate from /clan/remove so nobody has to name themselves correctly
    to leave, and so an admin leaving is an ordinary act rather than an
    admin action against a member. Admin rights are kept: running a clan
    and appearing on its roster are different things, and a leader who is
    between names should not lose the clan.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, clan FROM players WHERE google_sub = ? AND clan IS NOT NULL "
              "AND clan != ''", (sub_id,))
    rows = c.fetchall()
    if not rows:
        conn.close()
        return jsonify({"ok": False, "message": "You are not in a clan."}), 200
    # clan_locked = 1: this was a deliberate choice, so detection must not
    # quietly put them back next time they are seen wearing the tag.
    for name, _clan in rows:
        c.execute("UPDATE players SET clan = NULL, clan_locked = 1 WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    left = rows[0][1]
    return jsonify({"ok": True, "clan": left,
                    "message": f"You have left {left}."}), 200


@app.route('/clan/remove', methods=['POST'])
def clan_remove():
    """Take a clan tag off a name by hand, or let detection resume.

    A tag is inferred from the name the tracker read, so it is a guess that
    can be wrong: COVER starts with COV and SRSLY starts with SR, and
    neither player is in a clan. This is how that gets corrected.

    Two ways in. The name's owner can do it themselves. Most clan members
    were auto-registered from a win and have no owner at all, so the site's
    API key also works - that is the path for fixing someone else's tag.
    """
    data = request.json or {}
    name = str(data.get('name', '')).strip()
    undo = bool(data.get('undo'))
    if not name:
        return jsonify({"message": "A player name is required."}), 400

    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, reg_ip, clan FROM players WHERE norm_name = ?",
              (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{name}' is not on the leaderboard."}), 404

    stored_name, reg_ip, clan = row
    # Three ways in: the site's API key, an admin of the clan the player is
    # currently in, or the player themselves.
    by_admin = False
    if not api_key_ok(request.headers.get('X-API-Key')):
        actor = clan_role(c, current_user(), clan) if clan else None
        if actor and not may_kick(actor, player_clan_role(c, stored_name, clan)):
            conn.close()
            return jsonify({"message": "You cannot remove someone of your own rank or "
                                       "above in the clan."}), 403
        if actor:
            by_admin = True
        else:
            ok, err = owner_check(c, stored_name, reg_ip)
            if not ok:
                conn.close()
                return jsonify({"message": err}), 403

    if undo:
        # Removal is sticky by design, so this is the way back for a
        # removal that was a mistake. The tag is not restored here - it
        # comes back on its own the next time the player is seen with it.
        c.execute("UPDATE players SET clan_locked = 0 WHERE name = ?", (stored_name,))
        conn.commit()
        conn.close()
        return jsonify({"message": f"'{stored_name}' can be given a clan tag "
                                   f"again the next time one is seen."}), 200

    if not clan:
        conn.close()
        return jsonify({"message": f"'{stored_name}' has no clan tag."}), 400

    # The lock only exists to stop automatic detection undoing a correction.
    # An admin does not need it - their clan is curated, so detection already
    # skips it - and setting it would let one clan's admin permanently stop a
    # player being tagged into any clan at all, including a rival's.
    c.execute("UPDATE players SET clan = NULL, clan_locked = ? WHERE name = ?",
              (0 if by_admin else 1, stored_name))
    conn.commit()
    conn.close()
    return jsonify({"message": f"'{stored_name}' is no longer listed under {clan}."}), 200


@app.route('/clan/code', methods=['POST'])
def clan_code():
    """Mint a one-time code that makes whoever redeems it an admin of one clan.

    Site owner only. This is the handoff: the code goes to the clan's leader
    on Discord, and redeeming it is what ties their Google account to the
    clan. Nothing else grants admin, so a clan cannot be taken over by
    someone who simply signs in.
    """
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"message": "Unauthorized"}), 401
    raw = (request.json or {}).get('clan')
    known = canonical_clan_tag(raw)
    conn = db()
    c = conn.cursor()
    if not known:
        # A code for a clan that does not exist yet is the normal case:
        # this is how a leader who cannot pass the play-under-the-tag test
        # gets their clan at all. Mint it here, unowned, so the code is
        # what hands it over.
        tag = clean_clan_tag(raw)
        if (not CLAN_TAG_MIN_LEN <= len(tag) <= CLAN_TAG_MAX_LEN
                or not any(ch.isalpha() for ch in tag)):
            conn.close()
            return jsonify({"message": f"A clan tag is {CLAN_TAG_MIN_LEN} to "
                                       f"{CLAN_TAG_MAX_LEN} letters or numbers, "
                                       f"with at least one letter."}), 400
        if is_blocked_word(tag):
            conn.close()
            return jsonify({"message": "That tag isn't allowed."}), 400
        c.execute("INSERT OR IGNORE INTO clans (tag, created_by, created_at) VALUES (?, ?, ?)",
                  (tag, None, time.strftime('%Y-%m-%d %H:%M:%S')))
        known = tag

    code = known + "-" + secrets.token_hex(3).upper()
    c.execute("INSERT INTO clan_codes (code, clan, created_at) VALUES (?, ?, ?)",
              (code, known, time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({"code": code, "clan": known}), 200


@app.route('/clan/redeem', methods=['POST'])
def clan_redeem():
    """Turn a one-time code into admin rights over that clan."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in with Google first."}), 401

    code = str((request.json or {}).get('code', '')).strip().upper()
    if not code:
        return jsonify({"message": "Enter the code you were given."}), 400

    conn = db()
    c = conn.cursor()
    c.execute("SELECT clan, used_at FROM clan_codes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": "That code is not valid."}), 400
    clan, used_at = row
    if used_at:
        conn.close()
        return jsonify({"message": "That code has already been used."}), 400

    c.execute("INSERT OR IGNORE INTO clan_admins (clan, google_sub, created_at) VALUES (?, ?, ?)",
              (clan, sub_id, time.strftime('%Y-%m-%d %H:%M:%S')))
    c.execute("UPDATE clan_codes SET used_at = ?, used_by = ? WHERE code = ?",
              (time.strftime('%Y-%m-%d %H:%M:%S'), sub_id, code))
    joined, elsewhere = join_admin_names(c, sub_id, clan)
    conn.commit()
    conn.close()
    msg = f"You are now an admin of {clan}."
    if joined:
        msg += " Added " + ", ".join(joined) + " to the roster."
    if elsewhere:
        msg += (" " + ", ".join(elsewhere) + " stayed in their current clan - "
                "remove them from it first if they should be in " + clan + ".")
    return jsonify({"message": msg, "clan": clan}), 200


@app.route('/clan/admin/state')
def clan_admin_state():
    """Everything the clan admin page needs: which clans you run, who is in
    them, and which invitations are still waiting on a reply."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"logged_in": False, "clans": []}), 200

    conn = db()
    c = conn.cursor()
    out = []
    for tag in clan_admin_tags(c, sub_id):
        c.execute("SELECT name FROM players WHERE clan = ? ORDER BY name", (tag,))
        members = [{"name": r[0], "display": display_name(r[0], tag)} for r in c.fetchall()]
        c.execute("SELECT id, name FROM clan_invites WHERE clan = ? AND status = 'pending' "
                  "AND direction = 'invite' ORDER BY name", (tag,))
        pending = [{"id": r[0], "name": r[1]} for r in c.fetchall()]
        c.execute("SELECT id, name FROM clan_invites WHERE clan = ? AND status = 'pending' "
                  "AND direction = 'application' ORDER BY name", (tag,))
        applicants = [{"id": r[0], "name": r[1]} for r in c.fetchall()]
        out.append({"tag": tag, "members": members, "pending": pending,
                    "applicants": applicants})
    conn.close()
    return jsonify({"logged_in": True, "clans": out}), 200


@app.route('/clan/add', methods=['POST'])
def clan_add():
    """Put a player in a clan, as that clan's admin.

    A player who has an account is invited, never added: they get the
    request on their own page and it does nothing until they accept. Being
    put in a clan by somebody else is exactly what people are complaining
    about, so anyone with an account gets to say no.

    A player with no account has nobody to ask. For them the add is allowed
    only when the tag is genuinely in the name the tracker read, which is
    the same evidence automatic detection used to run on - so an admin can
    tidy up their own roster but cannot rope in unrelated players.
    """
    sub_id = current_user()
    data = request.json or {}
    known = canonical_clan_tag(data.get('clan'))
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({"message": "A player name is required."}), 400

    conn = db()
    c = conn.cursor()
    if not known or known not in clan_admin_tags(c, sub_id):
        conn.close()
        return jsonify({"message": "You are not an admin of that clan."}), 403

    c.execute("SELECT name, google_sub, clan FROM players WHERE norm_name = ?",
              (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{name}' is not on the leaderboard."}), 404

    stored_name, owner_sub, current_clan = row
    if current_clan == known:
        conn.close()
        return jsonify({"message": f"'{stored_name}' is already in {known}."}), 400
    if current_clan:
        # The owner's rule, restated 17 Aug: a player already in a clan
        # is never offered around. They leave first, then invitations.
        conn.close()
        return jsonify({"message": f"'{stored_name}' is in {current_clan}. They have to "
                                   f"leave that clan before joining {known}."}), 400

    if owner_sub:
        c.execute("SELECT id FROM clan_invites WHERE clan = ? AND name = ? AND status = 'pending' "
                  "AND direction = 'invite'", (known, stored_name))
        if c.fetchone():
            conn.close()
            return jsonify({"message": f"'{stored_name}' already has an invitation "
                                       f"from {known} waiting."}), 400
        c.execute("INSERT INTO clan_invites (clan, name, invited_by, created_at, status, direction) "
                  "VALUES (?, ?, ?, ?, 'pending', 'invite')",
                  (known, stored_name, sub_id, time.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        return jsonify({"message": f"Invitation sent to '{stored_name}'. They will see it "
                                   f"on Manage your name and have to accept it."}), 200

    if detect_clan(stored_name) != known:
        conn.close()
        return jsonify({"message": f"'{stored_name}' has no account to ask, and {known} is "
                                   f"not in their name, so they cannot be added. Ask them "
                                   f"to sign in and claim the name first."}), 400

    c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (known, stored_name))
    conn.commit()
    conn.close()
    return jsonify({"message": f"'{stored_name}' added to {known}."}), 200


@app.route('/me/clan_invites')
def my_clan_invites():
    """Clan invitations waiting on the signed-in player."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"invites": []}), 200
    conn = db()
    c = conn.cursor()
    c.execute("SELECT i.id, i.clan, i.name FROM clan_invites i "
              "JOIN players p ON p.name = i.name "
              "WHERE i.status = 'pending' AND i.direction = 'invite' "
              "AND p.google_sub = ? ORDER BY i.id", (sub_id,))
    invites = [{"id": r[0], "clan": r[1], "name": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify({"invites": invites}), 200


@app.route('/me/notices')
def my_notices():
    """The account page's inbox: invitations to answer and decisions
    not yet seen."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"invites": [], "updates": []}), 200
    conn = db()
    c = conn.cursor()
    invites = notice_invites(c, sub_id)
    updates = notice_updates(c, sub_id)
    conn.close()
    return jsonify({"invites": invites, "updates": updates}), 200


@app.route('/me/notices/seen', methods=['POST'])
def my_notices_seen():
    """Mark this account's decided items as read. Pending invitations
    are left alone - they stay on the badge until answered."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"ok": False}), 401
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE claim_requests SET seen = 1 WHERE google_sub = ? "
              "AND status IN ('approved', 'declined')", (sub_id,))
    c.execute("UPDATE clan_invites SET seen = 1 WHERE invited_by = ? "
              "AND direction = 'application' "
              "AND status IN ('approved', 'declined')", (sub_id,))
    c.execute("UPDATE clan_leader_requests SET seen = 1 WHERE google_sub = ? "
              "AND status IN ('approved', 'denied')", (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 200


@app.route('/clan/invite/respond', methods=['POST'])
def clan_invite_respond():
    """Accept or decline a clan invitation. Only the invited player can."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in with Google first."}), 401

    data = request.json or {}
    invite_id = data.get('id')
    accept = bool(data.get('accept'))

    conn = db()
    c = conn.cursor()
    c.execute("SELECT clan, name, status FROM clan_invites WHERE id = ? "
              "AND direction = 'invite'", (invite_id,))
    row = c.fetchone()
    if not row or row[2] != 'pending':
        conn.close()
        return jsonify({"message": "That invitation is no longer open."}), 404

    clan, stored_name, _ = row
    c.execute("SELECT google_sub FROM players WHERE name = ?", (stored_name,))
    owner = c.fetchone()
    if not owner or owner[0] != sub_id:
        conn.close()
        return jsonify({"message": "That invitation is not yours."}), 403

    if accept:
        c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (clan, stored_name))
    c.execute("UPDATE clan_invites SET status = ? WHERE id = ?",
              ('approved' if accept else 'declined', invite_id))
    conn.commit()
    conn.close()
    return jsonify({"message": f"You joined {clan}." if accept
                    else f"Invitation from {clan} declined."}), 200


@app.route('/clan/invite/cancel', methods=['POST'])
def clan_invite_cancel():
    """Take back a pending invitation, as staff of the clan that sent
    it. The player's inbox and badge only ever show pending rows, so a
    cancelled invitation vanishes from their side without a trace."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    c.execute("SELECT clan, name, status FROM clan_invites WHERE id = ? "
              "AND direction = 'invite'", (data.get('id'),))
    row = c.fetchone()
    if not row or row[2] != 'pending':
        conn.close()
        return jsonify({"message": "That invitation is no longer open."}), 404
    clan, name, _ = row
    if clan not in clan_admin_tags(c, sub_id):
        conn.close()
        return jsonify({"message": "You are not an admin of that clan."}), 403
    c.execute("UPDATE clan_invites SET status = 'cancelled' WHERE id = ?",
              (data.get('id'),))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Invitation to {name} taken back."}), 200


INVITE_LINK_DAYS = 7


def invite_link_row(c, token):
    """One invite link by its token, or None."""
    c.execute("SELECT token, clan, created_at, expires_at, revoked_at, "
              "COALESCE(uses, 0) FROM clan_invite_links WHERE token = ?",
              (str(token or ''),))
    return c.fetchone()


def invite_link_state(row):
    """Whether a link may still be used: ok, missing, revoked or expired."""
    if not row:
        return 'missing'
    if row[4]:
        return 'revoked'
    if row[3] and row[3] <= time.strftime('%Y-%m-%d %H:%M:%S'):
        return 'expired'
    return 'ok'


INVITE_DEAD_MESSAGE = {
    'missing': "That invite link is not valid.",
    'revoked': "That invite link has been withdrawn by the clan.",
    'expired': "That invite link has expired. Ask the clan for a new one.",
}


def active_invite_link(c, tag):
    """The clan's live link, or None. Expired and revoked rows stay in the
    table - they are what tells someone holding an old link why it stopped
    working, rather than that it never existed."""
    c.execute("SELECT token, clan, created_at, expires_at, revoked_at, "
              "COALESCE(uses, 0) FROM clan_invite_links "
              "WHERE clan = ? AND revoked_at IS NULL AND expires_at > ? "
              "ORDER BY created_at DESC LIMIT 1",
              (tag, time.strftime('%Y-%m-%d %H:%M:%S')))
    return c.fetchone()


def invite_link_json(row):
    return {
        "token": row[0],
        "url": request.url_root.rstrip('/') + '/clan/join/' + row[0],
        "created_at": row[2],
        "expires_at": row[3],
        "uses": row[5],
    }


@app.route('/clan/invite/link')
def clan_invite_link_get():
    """The clan's current invite link, for the manage card."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"can_manage": False, "link": None}), 200
    conn = db()
    c = conn.cursor()
    tag = canonical_clan_tag(request.args.get('clan'))
    if not tag:
        tags = clan_admin_tags(c, sub_id)
        tag = tags[0] if tags else None
    if not tag or not may_manage(c, sub_id, tag):
        conn.close()
        return jsonify({"can_manage": False, "link": None}), 200
    row = active_invite_link(c, tag)
    out = invite_link_json(row) if row else None
    conn.close()
    return jsonify({"can_manage": True, "clan": tag, "link": out,
                    "days": INVITE_LINK_DAYS}), 200


@app.route('/clan/invite/link', methods=['POST'])
def clan_invite_link_new():
    """Mint a link, retiring whatever the clan had before.

    Leaders and co-leaders, the same people who may already invite by
    name. A moderator is there to remove people, not to recruit.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    tag = canonical_clan_tag((request.json or {}).get('clan'))
    conn = db()
    c = conn.cursor()
    if not tag or not may_manage(c, sub_id, tag):
        conn.close()
        return jsonify({"message": "Only a leader or co-leader can do that."}), 403
    now = time.time()
    stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
    ends = time.strftime('%Y-%m-%d %H:%M:%S',
                         time.localtime(now + INVITE_LINK_DAYS * 86400))
    # Retiring the old link is the point: two live links would mean
    # revoking the one that leaked still left the clan open.
    c.execute("UPDATE clan_invite_links SET revoked_at = ? "
              "WHERE clan = ? AND revoked_at IS NULL", (stamp, tag))
    token = secrets.token_urlsafe(12)
    c.execute("INSERT INTO clan_invite_links "
              "(token, clan, created_by, created_at, expires_at, uses) "
              "VALUES (?, ?, ?, ?, ?, 0)", (token, tag, sub_id, stamp, ends))
    conn.commit()
    row = invite_link_row(c, token)
    out = invite_link_json(row)
    conn.close()
    out["message"] = "Link created. Anyone who opens it can join %s." % tag
    return jsonify(out), 200


@app.route('/clan/invite/revoke', methods=['POST'])
def clan_invite_link_revoke():
    """Withdraw the clan's live link."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    tag = canonical_clan_tag((request.json or {}).get('clan'))
    conn = db()
    c = conn.cursor()
    if not tag or not may_manage(c, sub_id, tag):
        conn.close()
        return jsonify({"message": "Only a leader or co-leader can do that."}), 403
    c.execute("UPDATE clan_invite_links SET revoked_at = ? "
              "WHERE clan = ? AND revoked_at IS NULL",
              (time.strftime('%Y-%m-%d %H:%M:%S'), tag))
    changed = c.rowcount
    conn.commit()
    conn.close()
    if not changed:
        return jsonify({"message": "There was no live link to withdraw."}), 400
    return jsonify({"message": "Link withdrawn. It no longer works."}), 200


def invite_join_state(c, sub_id, clan):
    """Why this visitor can or cannot take the invite. Returns
    (state, name). The states are what join.html renders."""
    if not sub_id:
        return 'signed_out', None
    who = account_name_for(c, sub_id)
    if not who:
        return 'no_name', None
    c.execute("SELECT clan FROM players WHERE name = ?", (who,))
    row = c.fetchone()
    current = row[0] if row else None
    if current == clan:
        return 'already_in', who
    if current:
        return 'other_clan', who
    return 'ready', who


@app.route('/clan/join/<token>')
def clan_join_page(token):
    """The page an invite link opens."""
    conn = db()
    c = conn.cursor()
    row = invite_link_row(c, token)
    state = invite_link_state(row)
    clan = row[1] if row else ''
    display = clan_display(c, clan) if clan else ''
    sub_id = current_user()
    join_state, who = ('dead', None)
    if state == 'ok':
        join_state, who = invite_join_state(c, sub_id, clan)
    # Straight to Discord rather than a page whose only purpose is a button
    # to Discord. back=1 is on the return path so that coming back still
    # signed out - cookies refused, or Cancel pressed on Discord's screen -
    # lands on the page with something to read instead of being bounced
    # round the same loop again.
    returned = bool(request.args.get('back'))
    if state == 'ok' and join_state == 'signed_out' and not returned:
        conn.close()
        return redirect('/auth/discord?next='
                        + quote('/clan/join/' + token + '?back=1', safe=''))
    c.execute("SELECT COUNT(*) FROM players WHERE clan = ?", (clan,))
    size = c.fetchone()[0] if clan else 0
    c.execute("SELECT clan FROM players WHERE google_sub = ? AND clan IS NOT NULL "
              "AND clan != '' LIMIT 1", (sub_id or '',))
    mine = c.fetchone()
    conn.close()
    return render_template(
        'join.html', version=APP_VERSION, contact=CONTACT_HANDLE,
        page='clans', client_id=GOOGLE_CLIENT_ID, token=token,
        clan=clan, display=display or clan, members=size,
        link_state=state, join_state=join_state, who=who or '',
        your_clan=(mine[0] if mine else ''), returned=returned,
        dead_message=INVITE_DEAD_MESSAGE.get(state, '')), (200 if state == 'ok' else 410)


@app.route('/clan/join/<token>', methods=['POST'])
def clan_join_accept(token):
    """Take the invite. The same rules as every other way into a clan."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    conn = db()
    c = conn.cursor()
    row = invite_link_row(c, token)
    state = invite_link_state(row)
    if state != 'ok':
        conn.close()
        return jsonify({"message": INVITE_DEAD_MESSAGE.get(state, "That link is not valid.")}), 410
    clan = row[1]
    join_state, who = invite_join_state(c, sub_id, clan)
    if join_state == 'no_name':
        conn.close()
        return jsonify({"message": "Claim your player name first, on Manage your name - "
                                   "a clan is a list of names, so there has to be one "
                                   "to add."}), 400
    if join_state == 'already_in':
        conn.close()
        return jsonify({"message": "You are already in %s." % clan}), 400
    if join_state == 'other_clan':
        c.execute("SELECT clan FROM players WHERE name = ?", (who,))
        cur = c.fetchone()
        conn.close()
        return jsonify({"message": "You are in %s. Leave it first, then open this "
                                   "link again." % (cur[0] if cur else 'another clan')}), 400
    c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (clan, who))
    c.execute("UPDATE clan_invite_links SET uses = COALESCE(uses, 0) + 1 "
              "WHERE token = ?", (row[0],))
    # Any invitation or application already open for this player is settled
    # by their walking in, or the clan's page would keep offering a decision
    # about somebody who is already a member.
    c.execute("UPDATE clan_invites SET status = 'approved' "
              "WHERE clan = ? AND name = ? AND status = 'pending'", (clan, who))
    conn.commit()
    conn.close()
    return jsonify({"message": "You joined %s." % clan, "clan": clan}), 200


@app.route('/api/notify_state')
def notify_state():
    """Everything the droplet's notifier needs in one call.

    The droplet polls this because PythonAnywhere's free tier cannot make
    outbound calls to arbitrary hosts, so the site cannot push to Discord
    itself. Keyed the same way as /api/game_end - pending claims are
    moderation data and are nobody else's business.
    """
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401

    conn = db()
    c = conn.cursor()
    # The handle is joined on here so a claim alert can say who filed it.
    # That is the one thing reviewing a claim always needed and the site
    # could never supply, because a Google account id says nothing a person
    # can act on.
    c.execute("SELECT cr.id, cr.name, cr.created_at, cr.google_sub IS NOT NULL, "
              "COALESCE(du.display, du.username) "
              "FROM claim_requests cr "
              "LEFT JOIN discord_users du ON du.sub = cr.google_sub "
              "WHERE cr.status = 'pending' ORDER BY cr.id")
    claims = [{"id": r[0], "name": r[1], "at": r[2], "has_account": bool(r[3]),
               "discord": r[4] or None}
              for r in c.fetchall()]
    c.execute("SELECT clan, COUNT(*) FROM clan_admins GROUP BY clan")
    admins = {r[0]: r[1] for r in c.fetchall()}
    conn.close()

    latest = CHANGELOG[0] if CHANGELOG else {"version": APP_VERSION, "changes": []}
    return jsonify({
        "version": APP_VERSION,
        "latest_changelog": latest,
        "pending_claims": claims,
        "clan_admins": admins,
    }), 200


# ----------------------------------------------------------------------
# Everything below serves the Discord bot. It runs on the droplet rather
# than here because a bot has to hold a connection open, which this host
# does not allow - so the same key that guards match reporting guards
# these too. The data is public either way; the key is there so the write
# endpoint below cannot be reached by anyone who merely knows the URL.
# ----------------------------------------------------------------------

def bot_authorised():
    return api_key_ok(request.headers.get('X-API-Key'))


def region_split(c, name):
    """A player's record broken down by region, every region listed.

    The same query the profile page runs. "No matches in Europe" is a real
    answer, so a region appears even when empty - otherwise the three
    boards look like one.
    """
    c.execute("SELECT COALESCE(m.region, 'america'), "
              "SUM(CASE WHEN mp.won = 1 THEN 1 ELSE 0 END), "
              "SUM(CASE WHEN mp.won = 1 THEN 0 ELSE 1 END), "
              "SUM(COALESCE(mp.delta, 0)) "
              "FROM match_players mp JOIN matches m ON m.id = mp.match_row "
              "WHERE mp.norm_name = ? GROUP BY 1", (normalize_name(name),))
    split = {r[0]: (r[1] or 0, r[2] or 0, r[3] or 0) for r in c.fetchall()}
    out = []
    for key, label in REGIONS:
        w, l, gained = split.get(key, (0, 0, 0))
        out.append({"key": key, "label": label, "wins": w, "losses": l,
                    "played": w + l, "gained": round(gained, 2)})
    return out


def bot_player(c, row, history=0, regions=0):
    """One player as the bot wants them: the same numbers the player page
    shows, formatted once here so the bot never recomputes a rank or a win
    rate and drifts away from the site."""
    stored_name, elo, wins, losses, clan, owner_sub = row
    wins = wins or 0
    losses = losses or 0
    played = wins + losses
    c.execute("SELECT COUNT(*) + 1 FROM players WHERE elo > ?", (elo,))
    rank = c.fetchone()[0]
    # "#4" means nothing without the size of the field it is out of.
    c.execute("SELECT COUNT(*) FROM players")
    rank_of = c.fetchone()[0]
    out = {
        "name": stored_name,
        "display": display_name(stored_name, clan),
        "elo": round(elo, 2),
        "wins": wins,
        "losses": losses,
        "played": played,
        "rank": rank,
        "rank_of": rank_of,
        "winrate": (round(100 * wins / played) if played else None),
        "clan": clan,
        "owned": bool(owner_sub),
    }
    if history:
        c.execute("SELECT m.played_at, mp.won, mp.delta, mp.half "
                  "FROM match_players mp JOIN matches m ON m.id = mp.match_row "
                  "WHERE mp.norm_name = ? ORDER BY m.id DESC LIMIT ?",
                  (normalize_name(stored_name), int(history)))
        out["history"] = [
            {"at": r[0], "won": bool(r[1]),
             "delta": (round(r[2], 2) if r[2] is not None else None),
             "half": bool(r[3])}
            for r in c.fetchall()
        ]
    if regions:
        out["by_region"] = region_split(c, stored_name)
    return out


def bot_lookup(c, name):
    c.execute("SELECT name, elo, wins, losses, clan, google_sub FROM players "
              "WHERE norm_name = ?", (normalize_name(name or ''),))
    return c.fetchone()


@app.route('/api/bot/player')
def bot_player_route():
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    name = request.args.get('name', '')
    try:
        history = min(15, max(0, int(request.args.get('history', 0))))
    except (TypeError, ValueError):
        history = 0
    conn = db()
    c = conn.cursor()
    row = bot_lookup(c, name)
    if not row:
        conn.close()
        return jsonify({"found": False, "query": name}), 200
    payload = bot_player(c, row, history=history,
                         regions=request.args.get('regions') in ('1', 'true', 'yes'))
    c.execute("SELECT COUNT(*) FROM claim_requests WHERE status = 'pending' AND name = ?",
              (row[0],))
    payload["pending_claim"] = c.fetchone()[0] > 0
    conn.close()
    return jsonify({"found": True, "player": payload}), 200


@app.route('/api/bot/top')
def bot_top_route():
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        n = min(25, max(1, int(request.args.get('n', 10))))
    except (TypeError, ValueError):
        n = 10
    # Paging. Without this the bot could only ever show the first page,
    # which on a board of a couple of thousand is most of it hidden.
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0
    region = str(request.args.get('region', ALL_REGIONS)).strip().lower()
    period = str(request.args.get('period', 'all')).strip().lower()
    if region not in REGION_KEYS and region != ALL_REGIONS:
        region = ALL_REGIONS
    if period not in PERIOD_KEYS:
        period = 'all'
    # Straight through board_rows, so the bot and the page can never show
    # different boards for the same question.
    gain = period != 'all'
    # board_rows returns two different kinds of number. All-regions
    # all-time comes off the players table and is ALREADY an absolute
    # rating; a single region's all-time is a SUM OF DELTAS that only
    # becomes a rating once STARTING_ELO is added. Adding it to both
    # showed a player on 6.0 as 11.0 on the combined board.
    relative = region != ALL_REGIONS or gain

    conn = db()
    c = conn.cursor()
    rows = board_rows(c, period, region)
    shown = clan_display_map(c)
    conn.close()
    rows.sort(key=leaderboard_sort_key)
    out = []
    for i, (name, elo, wins, losses, clan, protected) in enumerate(
            rows[offset:offset + n], start=offset + 1):
        played = wins + losses
        out.append({"place": i, "name": name, "display": display_name(name, clan),
                    "clan_display": shown.get(clan, clan),
                    # Over a window this is rating gained, not a standing -
                    # the bot labels the column from `gain`.
                    "elo": round(elo if gain
                                 else (STARTING_ELO + elo if relative else elo), 2),
                    "wins": wins, "losses": losses,
                    "winrate": (round(100 * wins / played) if played else None),
                    "clan": clan, "protected": protected})
    return jsonify({"players": out, "total": len(rows), "gain": gain,
                    "offset": offset, "count": n,
                    "region": region, "region_label": REGION_LABELS[region],
                    "period": period, "period_label": dict(PERIODS)[period]}), 200


@app.route('/api/bot/changelog')
def bot_changelog_route():
    """The most recent changelog entries, so players can read what moved
    without leaving Discord. Public information - it is on the site - but
    key-gated like the rest of the bot API for consistency."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        n = min(5, max(1, int(request.args.get('n', 3))))
    except (TypeError, ValueError):
        n = 3
    return jsonify({"version": APP_VERSION,
                    "entries": CHANGELOG[:n]}), 200


@app.route('/api/bot/clan')
def bot_clan_route():
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    known = canonical_clan_tag(request.args.get('tag', ''))
    if not known:
        return jsonify({"found": False}), 200
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, elo, wins, losses, google_sub FROM players WHERE clan = ?", (known,))
    rows = c.fetchall()
    c.execute("SELECT google_sub FROM clan_admins WHERE clan = ?", (known,))
    admin_subs = {r[0] for r in c.fetchall() if r[0]}
    conn.close()
    rows.sort(key=leaderboard_sort_key)
    members = []
    total_wins = total_losses = 0
    total_elo = 0.0
    for name, elo, wins, losses, owner_sub in rows:
        wins = wins or 0
        losses = losses or 0
        total_wins += wins
        total_losses += losses
        total_elo += elo
        members.append({"name": name, "display": display_name(name, known),
                        "elo": round(elo, 2), "wins": wins, "losses": losses,
                        "admin": bool(owner_sub) and owner_sub in admin_subs})
    played = total_wins + total_losses
    return jsonify({"found": True, "clan": {
        "tag": known,
        "size": len(members),
        "wins": total_wins,
        "losses": total_losses,
        "winrate": (round(100 * total_wins / played) if played else None),
        "avg_elo": (round(total_elo / len(members), 2) if members else None),
        "members": members,
    }}), 200


@app.route('/api/bot/compare')
def bot_compare_route():
    """Two players side by side, plus what a win would actually be worth.

    The projection is worked out here, with the site's own rating code,
    rather than reimplemented in the bot - a second copy of the formula is
    a second thing to forget to change.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    rows = [bot_lookup(c, request.args.get('a', '')),
            bot_lookup(c, request.args.get('b', ''))]
    if not rows[0] or not rows[1]:
        conn.close()
        return jsonify({"found": False,
                        "missing": [q for q, r in
                                    ((request.args.get('a', ''), rows[0]),
                                     (request.args.get('b', ''), rows[1])) if not r]}), 200
    a = bot_player(c, rows[0])
    b = bot_player(c, rows[1])
    conn.close()

    # Deliberately not team_rating() for the opposing side. That function
    # pads a short roster out to two with STARTING_ELO, which is right when
    # a real team is half unregistered but wrong here - it would drag a
    # single named opponent halfway back to average and quote a swing
    # neither player would ever see. One player's rating is their elo.
    exp_a = expected_score(rows[0][1], rows[1][1])
    return jsonify({"found": True, "a": a, "b": b, "projection": {
        "a_win_chance": round(100 * exp_a),
        "a_gain": round(ELO_K * (1 - exp_a), 2),
        "a_loss": round(ELO_K * exp_a, 2),
        "b_gain": round(ELO_K * exp_a, 2),
        "b_loss": round(ELO_K * (1 - exp_a), 2),
    }}), 200


@app.route('/api/bot/checkin', methods=['POST'])
def bot_checkin_route():
    """Press Play from Discord.

    The point of doing this from a bot: the player is already identified by
    their Discord account, so there is no sign-in - and no browser connects
    here at all, so the site never sees a player's address.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    discord_id = str(data.get('discord_id', '')).strip()
    if not discord_id:
        return jsonify({"error": "no discord_id"}), 400
    conn = db()
    c = conn.cursor()
    status, payload = perform_checkin(c, 'discord:' + discord_id, data.get('sys_id'))
    if status == 200:
        conn.commit()
    conn.close()
    # Always 200 to the bot: it shows payload["message"] either way, and a
    # 4xx would be swallowed as a generic transport error by its client.
    return jsonify(payload), 200


def _bot_sub():
    """The account behind a bot request, or None."""
    discord_id = str((request.json or {}).get('discord_id', '')).strip()
    return ('discord:' + discord_id) if discord_id else None


@app.route('/api/bot/clan/leader/request', methods=['POST'])
def bot_clan_leader_request_route():
    """Ask to be allowed to run a clan. The owner decides in Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    _status, payload = perform_leader_request(c, sub_id, data.get('handle'),
                                              data.get('tag'), data.get('note'))
    if payload.get("ok"):
        # Sent straight from Discord, so the bot is about to show the owner
        # itself and does not need to collect this one later.
        c.execute("UPDATE clan_leader_requests SET notified = 1 WHERE id = ?",
                  (payload["id"],))
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/clan/leader/undelivered')
def bot_leader_reqs_undelivered():
    """Leader requests the bot has not yet shown the owner.

    Requests made on the website land here; the bot collects them and DMs
    the owner, exactly as it does with clan applications.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, handle, tag, note FROM clan_leader_requests "
              "WHERE status = 'pending' AND COALESCE(notified, 0) = 0 "
              "ORDER BY id LIMIT 25")
    out = [{"id": r[0], "handle": r[1] or "someone", "tag": r[2] or "",
            "note": r[3] or ""} for r in c.fetchall()]
    conn.close()
    return jsonify({"requests": out}), 200


@app.route('/api/bot/clan/leader/delivered', methods=['POST'])
def bot_leader_reqs_delivered():
    """Mark leader requests as shown, so the owner is asked once."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    ids = [int(i) for i in (request.json or {}).get('ids', []) if str(i).isdigit()]
    if not ids:
        return jsonify({"ok": True, "marked": 0}), 200
    conn = db()
    c = conn.cursor()
    c.executemany("UPDATE clan_leader_requests SET notified = 1 WHERE id = ?",
                  [(i,) for i in ids])
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "marked": len(ids)}), 200


@app.route('/api/bot/clan/leader/decide', methods=['POST'])
def bot_clan_leader_decide_route():
    """Approve or deny a request. Only the bot calls this, and only after
    the owner has pressed a button in their DMs."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    try:
        rid = int(data.get('id'))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Which request?"}), 200
    decision = str(data.get('decision', '')).strip().lower()
    if decision not in ('approved', 'denied'):
        return jsonify({"ok": False, "message": "Unknown decision."}), 200
    conn = db()
    c = conn.cursor()
    c.execute("SELECT google_sub, handle, tag, status FROM clan_leader_requests WHERE id = ?",
              (rid,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "That request no longer exists."}), 200
    who, handle, tag, status = row
    if status != 'pending':
        conn.close()
        return jsonify({"ok": False, "already": status,
                        "message": f"That request was already {status}."}), 200
    c.execute("UPDATE clan_leader_requests SET status = ?, decided_at = ?, decided_by = ? "
              "WHERE id = ?", (decision, time.strftime('%Y-%m-%d %H:%M:%S'),
                               str(data.get('decided_by', ''))[:80], rid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "decision": decision, "google_sub": who,
                    "handle": handle, "tag": tag,
                    "discord_id": who.split(':', 1)[1] if who.startswith('discord:') else None,
                    "message": f"Request {decision}."}), 200


@app.route('/api/bot/clan/leader/state')
def bot_clan_leader_state_route():
    """Whether this account may run a clan, and any requests still waiting."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    discord_id = str(request.args.get('discord_id', '')).strip()
    conn = db()
    c = conn.cursor()
    state = clan_leader_state(c, 'discord:' + discord_id) if discord_id else 'none'
    c.execute("SELECT id, google_sub, handle, tag, note, created_at "
              "FROM clan_leader_requests WHERE status = 'pending' ORDER BY id")
    pending = [{"id": r[0],
                "discord_id": r[1].split(':', 1)[1] if r[1].startswith('discord:') else None,
                "handle": r[2], "tag": r[3], "note": r[4], "at": r[5]}
               for r in c.fetchall()]
    conn.close()
    return jsonify({"state": state, "pending": pending}), 200


@app.route('/api/bot/clan/claim', methods=['POST'])
def bot_clan_claim_route():
    """Claim a clan tag from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_create(c, sub_id, (request.json or {}).get('tag'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/clan/members', methods=['POST'])
def bot_clan_members_route():
    """Add or remove a player, as an admin of that clan.

    One endpoint for both so the admin check lives in a single place; the
    website's own routes enforce exactly the same rules.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    action = str(data.get('action', '')).strip().lower()
    name = str(data.get('name', '')).strip()
    if action not in ('add', 'remove'):
        return jsonify({"ok": False, "message": "Unknown action."}), 200
    if not name:
        return jsonify({"ok": False, "message": "A player name is required."}), 200

    conn = db()
    c = conn.cursor()
    mine = clan_admin_tags(c, sub_id)
    if not mine:
        conn.close()
        return jsonify({"ok": False, "no_clan": True,
                        "message": "You do not run a clan yet. Claim your tag first."}), 200
    # An admin of exactly one clan never has to name it; anyone running two
    # says which, and a wrong name is refused rather than guessed at.
    tag = clean_clan_tag(data.get('clan')) or (mine[0] if len(mine) == 1 else None)
    if not tag or tag not in mine:
        conn.close()
        return jsonify({"ok": False,
                        "message": ("Say which clan - you are an admin of "
                                    + ", ".join(mine) + ".") if len(mine) > 1
                                   else "You are not an admin of that clan."}), 200

    c.execute("SELECT name, google_sub, clan FROM players WHERE norm_name = ?",
              (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False,
                        "message": f"'{name}' is not on the leaderboard."}), 200
    stored_name, owner_sub, current_clan = row
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    if action == 'remove':
        if current_clan != tag:
            conn.close()
            return jsonify({"ok": False,
                            "message": f"'{stored_name}' is not in {tag}."}), 200
        # clan_locked stays 0: an admin's clan is curated, so detection
        # already skips it, and locking would stop the player ever being
        # tagged into another clan.
        c.execute("UPDATE players SET clan = NULL, clan_locked = 0 WHERE name = ?",
                  (stored_name,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True,
                        "message": f"'{stored_name}' removed from {tag}."}), 200

    if current_clan == tag:
        conn.close()
        return jsonify({"ok": False,
                        "message": f"'{stored_name}' is already in {tag}."}), 200
    if current_clan:
        conn.close()
        return jsonify({"ok": False,
                        "message": f"'{stored_name}' is in {current_clan} and has to leave "
                                   f"that first."}), 200

    # A player with an account is invited, never added. Being put in a clan
    # by somebody else is the complaint the whole system exists to avoid,
    # so anyone with an account gets to say no.
    if owner_sub:
        c.execute("SELECT id FROM clan_invites WHERE clan = ? AND name = ? "
                  "AND status = 'pending' AND direction = 'invite'", (tag, stored_name))
        if c.fetchone():
            conn.close()
            return jsonify({"ok": False,
                            "message": f"'{stored_name}' already has an invitation from "
                                       f"{tag} waiting."}), 200
        c.execute("INSERT INTO clan_invites (clan, name, invited_by, created_at, status, "
                  "direction) VALUES (?, ?, ?, ?, 'pending', 'invite')",
                  (tag, stored_name, sub_id, now))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "invited": True,
                        "message": f"Invitation sent to '{stored_name}'. It does nothing "
                                   f"until they accept it."}), 200

    # Nobody to ask. Allowed only when the tag really is in the name the
    # tracker read - the same evidence detection used - so an admin can
    # tidy their own roster but cannot rope in unrelated players.
    if not clean_clan_tag(stored_name).startswith(tag):
        conn.close()
        return jsonify({"ok": False,
                        "message": f"'{stored_name}' has no account to ask, and {tag} is not "
                                   f"in their name, so they cannot be added. Ask them to "
                                   f"sign in and claim the name first."}), 200
    c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (tag, stored_name))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": f"'{stored_name}' added to {tag}."}), 200


@app.route('/api/bot/clan/redeem', methods=['POST'])
def bot_clan_redeem_route():
    """Turn a one-time code into admin rights, from Discord.

    This is the way round the play-under-the-tag rule: the code is issued
    by the site owner, so the check it skips has already been made by a
    person.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    code = str((request.json or {}).get('code', '')).strip().upper()
    if not code:
        return jsonify({"ok": False, "message": "Enter the code you were given."}), 200
    conn = db()
    c = conn.cursor()
    c.execute("SELECT clan, used_at FROM clan_codes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "That code is not valid."}), 200
    clan, used_at = row
    if used_at:
        conn.close()
        return jsonify({"ok": False, "message": "That code has already been used."}), 200
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT OR IGNORE INTO clan_admins (clan, google_sub, created_at) "
              "VALUES (?, ?, ?)", (clan, sub_id, now))
    c.execute("UPDATE clan_codes SET used_at = ?, used_by = ? WHERE code = ?",
              (now, sub_id, code))
    joined, elsewhere = join_admin_names(c, sub_id, clan)
    conn.commit()
    conn.close()
    msg = f"You are now an admin of {clan}."
    if joined:
        msg += " Added " + ", ".join(joined) + " to the roster."
    if elsewhere:
        msg += " " + ", ".join(elsewhere) + " stayed in their current clan."
    return jsonify({"ok": True, "clan": clan, "message": msg}), 200


@app.route('/api/bot/clan/applications/undelivered')
def bot_clan_apps_undelivered():
    """Applications the bot has not yet put in front of a leader.

    Pulled by the bot rather than pushed by the site: an application can be
    made on the website, which has no way to reach Discord, and one made
    while the bot was restarting must not be lost.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, clan, name FROM clan_invites "
              "WHERE direction = 'application' AND status = 'pending' "
              "AND COALESCE(notified, 0) = 0 ORDER BY created_at LIMIT 25")
    pending = c.fetchall()
    out = []
    for app_id, clan, name in pending:
        row = applicant_stats(c, name)
        # Only leaders who signed in through Discord can be sent a DM.
        c.execute("SELECT google_sub FROM clan_admins WHERE clan = ?", (clan,))
        leaders = [r[0][8:] for r in c.fetchall()
                   if r[0] and r[0].startswith('discord:')]
        row.update({"id": app_id, "clan": clan, "leaders": leaders})
        out.append(row)
    conn.close()
    return jsonify({"applications": out}), 200


@app.route('/api/bot/clan/applications/delivered', methods=['POST'])
def bot_clan_apps_delivered():
    """Mark applications as sent, so a leader is asked once and not again."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    ids = [int(i) for i in (request.json or {}).get('ids', []) if str(i).isdigit()]
    if not ids:
        return jsonify({"ok": True, "marked": 0}), 200
    conn = db()
    c = conn.cursor()
    c.executemany("UPDATE clan_invites SET notified = 1 WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "marked": len(ids)}), 200


@app.route('/api/bot/clan/applications')
def bot_clan_apps_route():
    """Everyone waiting on the clans this Discord account runs."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    conn = db()
    c = conn.cursor()
    out = []
    for tag in clan_admin_tags(c, sub_id):
        out.extend(clan_applications(c, tag))
    conn.close()
    return jsonify({"applications": out}), 200


@app.route('/api/bot/clan/application/decide', methods=['POST'])
def bot_clan_app_decide_route():
    """A leader deciding an application from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_app_decide(c, sub_id, data.get('id'),
                                              data.get('decision') == 'accept')
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/playerrole/undelivered')
def bot_playerrole_undelivered():
    """Discord accounts that own a named row and have not yet been
    granted the server's Player role. The bot polls and grants."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    # A pending claim counts. A claim only completes on the claimed
    # name's next tracked win, which can be hours - and the people
    # claiming are exactly the established players the server most
    # wants talking, so making them wait as guests is backwards.
    c.execute("SELECT DISTINCT sub FROM ("
              "  SELECT google_sub AS sub FROM players "
              "  WHERE google_sub LIKE 'discord:%' AND name IS NOT NULL "
              "  UNION "
              "  SELECT google_sub AS sub FROM claim_requests "
              "  WHERE google_sub LIKE 'discord:%' AND status = 'pending'"
              ") WHERE sub NOT IN (SELECT sub FROM discord_role_grants)")
    subs = [r[0] for r in c.fetchall()]
    conn.close()
    return jsonify({"subs": subs}), 200


@app.route('/api/bot/playerrole/delivered', methods=['POST'])
def bot_playerrole_delivered():
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    subs = (request.json or {}).get('subs') or []
    conn = db()
    c = conn.cursor()
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for s in subs:
        c.execute("INSERT OR IGNORE INTO discord_role_grants (sub, granted_at) "
                  "VALUES (?, ?)", (str(s), now))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "count": len(subs)}), 200


@app.route('/api/bot/playerrole/check')
def bot_playerrole_check():
    """Does this Discord account own a named row? Asked when somebody
    joins the server, so signing up first still lands them as Player."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    sub = str(request.args.get('sub') or '')
    conn = db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM players WHERE google_sub = ? "
              "AND name IS NOT NULL LIMIT 1", (sub,))
    qualifies = bool(c.fetchone())
    if not qualifies:
        # Same rule as the queue above: a filed claim is joining.
        c.execute("SELECT 1 FROM claim_requests WHERE google_sub = ? "
                  "AND status = 'pending' LIMIT 1", (sub,))
        qualifies = bool(c.fetchone())
    conn.close()
    return jsonify({"player": qualifies}), 200


@app.route('/api/bot/matches/undelivered')
def bot_matches_undelivered():
    """Decided matches not yet posted to the Discord results feed, with
    their winners and losers. Oldest first so the feed reads in order."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, match_id, COALESCE(region, 'america'), played_at, "
              "lobby_name, COALESCE(tracked_reads, 0), sys_id "
              "FROM matches WHERE COALESCE(announced, 0) = 0 "
              "ORDER BY id LIMIT 15")
    rows = c.fetchall()
    out = []
    for mid, match_id, region, played_at, lobby_name, treads, sysid in rows:
        c.execute("SELECT name, won, COALESCE(delta, 0), COALESCE(team, '') "
                  "FROM match_players WHERE match_row = ? "
                  "ORDER BY won DESC, delta DESC", (mid,))
        winners, lose1, lose2 = [], [], []
        for name, won, delta, team in c.fetchall():
            e = {"name": name, "delta": round(delta, 2)}
            if won:
                winners.append(e)
            elif team == 'lose2':
                lose2.append(e)
            else:
                lose1.append(e)
        losing_teams = [t for t in (lose1, lose2) if t]
        # A team exempted by the flip rule is not rated (it led big and
        # lost to reinforcements), so it is absent from match_players -
        # which made a 3-team match look like 2. Surface it from
        # held_results so the feed accounts for every side.
        c.execute("SELECT name FROM held_results "
                  "WHERE match_id = ? AND reason = 'dominance-flip' "
                  "ORDER BY name", (match_id,))
        exempt = [r[0] for r in c.fetchall()]
        mins = int(round((treads or 0) * 10 / 60.0))
        out.append({"id": mid, "match_id": match_id, "region": region,
                    "played_at": played_at, "winners": winners,
                    "losing_teams": losing_teams, "exempt": exempt,
                    "lobby_name": lobby_name, "sys_id": sysid,
                    "tracked_minutes": mins})
    conn.close()
    return jsonify({"matches": out}), 200


@app.route('/api/bot/matches/delivered', methods=['POST'])
def bot_matches_delivered():
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    ids = [int(x) for x in ((request.json or {}).get('ids') or [])
           if str(x).lstrip('-').isdigit()]
    if not ids:
        return jsonify({"ok": True, "count": 0}), 200
    conn = db()
    c = conn.cursor()
    c.executemany("UPDATE matches SET announced = 1 WHERE id = ?",
                  [(i,) for i in ids])
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "count": len(ids)}), 200


@app.route('/api/bot/gamerank/push', methods=['POST'])
def bot_gamerank_push():
    """Today's ladder snapshot, pushed by the bot. Replaces today's
    rows so re-pushing is safe; older days accumulate as history."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    rows = data.get('rows') or []
    day = str(data.get('day') or time.strftime('%Y-%m-%d'))
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM game_ladder WHERE day = ?", (day,))
    kept = 0
    for r in rows[:2000]:
        try:
            c.execute("INSERT OR REPLACE INTO game_ladder "
                      "(day, region, position, account_id, name, norm_name, "
                      "official, live, custom) VALUES (?,?,?,?,?,?,?,?,?)",
                      (day, str(r.get('region') or ''), r.get('position'),
                       str(r.get('account_id') or ''), r.get('name'),
                       normalize_name(str(r.get('name') or '')) or None,
                       r.get('official'), r.get('live'),
                       json.dumps(r.get('custom')) if r.get('custom') else None))
            kept += 1
        except sqlite3.Error:
            continue
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "day": day, "rows": kept}), 200


@app.route('/api/bot/gamerank')
def bot_gamerank():
    """Ladder standing for a name: latest snapshot plus every name the
    matching account ids have worn across snapshots."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    name = str(request.args.get('name') or '').strip()
    if not name:
        return jsonify({"matches": []}), 200
    norm = normalize_name(name)
    conn = db()
    c = conn.cursor()
    latest = (c.execute("SELECT MAX(day) FROM game_ladder").fetchone()
              or [None])[0]
    out = []
    if latest and norm:
        rows = c.execute(
            "SELECT region, position, account_id, name, official, live, custom "
            "FROM game_ladder WHERE day = ? AND norm_name = ?",
            (latest, norm)).fetchall()
        for region, pos, aid, nm, official, live, custom in rows:
            history = [r[0] for r in c.execute(
                "SELECT DISTINCT name FROM game_ladder "
                "WHERE account_id = ? AND name IS NOT NULL", (aid,)).fetchall()]
            out.append({"region": region, "position": pos,
                        "account_id": aid, "name": nm,
                        "official": official, "live": live,
                        "custom": json.loads(custom) if custom else None,
                        "names_worn": history})
    conn.close()
    return jsonify({"day": latest, "matches": out}), 200


@app.route('/api/bot/claims/undelivered')
def bot_claims_undelivered():
    """Claims the bot has not yet told the owner about.

    There is nothing to approve: a claim completes on its own once the name
    wins a tracked match after it was filed. This is so the owner can see
    who is claiming what, and step in if it looks wrong.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, name, note, google_sub, created_at FROM claim_requests "
              "WHERE status = 'pending' AND COALESCE(notified, 0) = 0 "
              "ORDER BY id LIMIT 25")
    out = []
    for cid, name, note, claimant, created in c.fetchall():
        row = applicant_stats(c, name)
        c.execute("SELECT google_sub FROM players WHERE norm_name = ?",
                  (normalize_name(name),))
        owner = (c.fetchone() or [None])[0]
        row.update({"id": cid, "claim_name": name, "note": note or "",
                    "handle": discord_handle(c, claimant) or "",
                    "signed_in": bool(claimant), "taken": bool(owner),
                    "created_at": created})
        out.append(row)
    conn.close()
    return jsonify({"claims": out}), 200


@app.route('/api/bot/claims/delivered', methods=['POST'])
def bot_claims_delivered():
    """Mark claims as reported, so the owner hears about each one once."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    ids = [int(i) for i in (request.json or {}).get('ids', []) if str(i).isdigit()]
    if not ids:
        return jsonify({"ok": True, "marked": 0}), 200
    conn = db()
    c = conn.cursor()
    c.executemany("UPDATE claim_requests SET notified = 1 WHERE id = ?",
                  [(i,) for i in ids])
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "marked": len(ids)}), 200


@app.route('/api/bot/claim/pending')
def bot_claim_pending():
    """The pending claims filed by one account - the bot's /proveclaim
    needs to know what it is proving."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    sub = str(request.args.get('sub') or '')
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM claim_requests "
              "WHERE google_sub = ? AND status = 'pending' ORDER BY id",
              (sub,))
    out = [{"id": r[0], "name": r[1], "at": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify({"claims": out}), 200


@app.route('/api/bot/claim/decide', methods=['POST'])
def bot_claim_decide_route():
    """Grant or refuse a claim from Discord. The bot checks it is the owner
    pressing the button; the site trusts the bot's key, as everywhere else."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_claim_decide(c, data.get('id'),
                                           data.get('decision') == 'approve',
                                           str(data.get('decided_by', ''))[:80])
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/claim/withdraw', methods=['POST'])
def bot_claim_withdraw_route():
    """Take back a pending claim, from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    conn = db()
    c = conn.cursor()
    # rate_src mirrors how the bot's claim route CHARGES the limit: by
    # account tag, never by connection - every bot request shares the
    # droplet's address.
    status, payload = perform_claim_withdraw(c, sub_id,
                                             (request.json or {}).get('name'),
                                             rate_src=source_tag(sub_id))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/clan/role', methods=['POST'])
def bot_clan_role_route():
    """Appoint or unappoint a co-leader or moderator, from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_role(c, sub_id, data.get('clan'), data.get('name'),
                                        data.get('role'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/clan/region', methods=['POST'])
def bot_clan_region_route():
    """Set where a clan is based, from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_region(c, sub_id, data.get('clan'),
                                          data.get('region'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/clan/delete', methods=['POST'])
def bot_clan_delete_route():
    """Delete a clan you are an admin of, from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_delete(c, sub_id, (request.json or {}).get('clan'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/clan/mine')
def bot_clan_mine_route():
    """The clans this Discord account runs, with their rosters."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    discord_id = str(request.args.get('discord_id', '')).strip()
    if not discord_id:
        return jsonify({"error": "no discord_id"}), 400
    sub_id = 'discord:' + discord_id
    conn = db()
    c = conn.cursor()
    out = []
    for tag in clan_admin_tags(c, sub_id):
        c.execute("SELECT name, elo FROM players WHERE clan = ? ORDER BY elo DESC", (tag,))
        members = [{"name": r[0], "elo": round(r[1], 2)} for r in c.fetchall()]
        c.execute("SELECT name FROM clan_invites WHERE clan = ? AND status = 'pending' "
                  "AND direction = 'invite' ORDER BY id", (tag,))
        out.append({"tag": tag, "members": members,
                    "pending": [r[0] for r in c.fetchall()]})
    conn.close()
    return jsonify({"clans": out}), 200


@app.route('/api/bot/gamename', methods=['POST'])
def bot_gamename_route():
    """Set the name this account plays under, from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    conn = db()
    c = conn.cursor()
    status, payload = perform_set_game_name(c, sub_id, (request.json or {}).get('name', ''))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/claim', methods=['POST'])
def bot_claim_route():
    """File a claim from Discord, rate limited per account rather than per
    network - every bot request arrives from the same machine."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_claim(c, sub_id, data.get('name'), data.get('note'),
                                    rate_src=source_tag(sub_id))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/report', methods=['POST'])
def bot_report_route():
    """File a bug report from Discord."""
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    sub_id = _bot_sub()
    if not sub_id:
        return jsonify({"error": "no discord_id"}), 400
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_report(c, sub_id, data.get('kind'), data.get('body'),
                                     data.get('contact'), rate_src=source_tag(sub_id))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), 200


@app.route('/api/bot/me')
def bot_me_route():
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    discord_id = str(request.args.get('discord_id', '')).strip()
    if not discord_id:
        return jsonify({"error": "no discord_id"}), 400
    sub_id = 'discord:' + discord_id
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, elo, wins, losses, clan, google_sub FROM players "
              "WHERE google_sub = ? ORDER BY name", (sub_id,))
    rows = c.fetchall()
    players = [bot_player(c, r) for r in rows]
    c.execute("SELECT name, created_at FROM claim_requests "
              "WHERE google_sub = ? AND status = 'pending' ORDER BY id", (sub_id,))
    claims = [{"name": r[0], "at": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"players": players, "pending_claims": claims,
                    "cap": MAX_NAMES_PER_ACCOUNT}), 200


@app.route('/api/held')
def api_held_route():
    """Results withheld by protection. Never rendered on the site - showing
    them would undo the thing the player asked for - but kept so a wrong
    call can be found and put right."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    who = str(request.args.get('name', '')).strip()
    conn = db()
    c = conn.cursor()
    if who:
        c.execute("SELECT id, match_id, region, name, played_as, won, score, reason, played_at "
                  "FROM held_results WHERE norm_name = ? ORDER BY id DESC LIMIT 200",
                  (normalize_name(who),))
    else:
        c.execute("SELECT id, match_id, region, name, played_as, won, score, reason, played_at "
                  "FROM held_results ORDER BY id DESC LIMIT 200")
    out = [{"id": r[0], "match_id": r[1], "region": r[2], "name": r[3],
            "played_as": r[4], "won": bool(r[5]), "score": r[6],
            "reason": r[7], "at": r[8]} for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM held_results")
    total = (c.fetchone() or [0])[0]
    conn.close()
    return jsonify({"held": out, "shown": len(out), "total": total}), 200


@app.route('/api/bot/name', methods=['POST'])
def bot_set_name_route():
    """Set or change the account name from Discord.

    The same thing the Settings page does. /api/bot/register can only add a
    name to an account that has none, so someone who wanted to correct a
    typo had to come to the site - which is exactly the sort of errand a
    bot should save.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    discord_id = str(data.get('discord_id', '')).strip()
    name = str(data.get('name', '')).strip()
    if not discord_id:
        return jsonify({"error": "no discord_id"}), 400
    sub_id = 'discord:' + discord_id
    if not is_valid_name_format(name):
        return jsonify({"ok": False, "message": "That name cannot be used. Try another."}), 200
    if is_blocked_word(name):
        return jsonify({"ok": False, "message": "That name isn't allowed. Please choose another."}), 200
    if is_default_name(name):
        return jsonify({"ok": False, "message": "That is one of Starblast's default names - too "
                                                "many players share it. Pick a name of your own."}), 200

    conn = db()
    c = conn.cursor()
    c.execute("BEGIN IMMEDIATE")
    key = normalize_name(name)
    c.execute("SELECT google_sub FROM players WHERE norm_name = ?", (key,))
    taken = c.fetchone()
    if taken and taken[0] and taken[0] != sub_id:
        conn.close()
        return jsonify({"ok": False,
                        "message": f"'{name}' already belongs to another account."}), 200
    if taken and not taken[0]:
        conn.close()
        return jsonify({"ok": False, "claimable": True,
                        "message": f"'{name}' is already on the leaderboard as an unverified "
                                   f"player. Claim it on the site to take it over."}), 200
    if taken and taken[0] == sub_id:
        c.execute("SELECT name FROM players WHERE norm_name = ?", (key,))
        row = c.fetchone()
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "name": row[0] if row else name,
                        "message": f"Your name is already '{row[0] if row else name}'."}), 200

    # One row moves, chosen the same way the site chooses it - an account
    # holding two grandfathered names must not have both renamed at once.
    c.execute("SELECT name FROM players WHERE google_sub = ? "
              "ORDER BY (COALESCE(wins, 0) + COALESCE(losses, 0)) DESC, name LIMIT 1",
              (sub_id,))
    mine = c.fetchone()
    if mine:
        c.execute("UPDATE players SET name = ?, norm_name = ? WHERE name = ?",
                  (name, key, mine[0]))
        msg = f"Your name is now '{name}' (was '{mine[0]}')."
    else:
        c.execute("INSERT INTO players (name, elo, wins, losses, reg_ip, norm_name, google_sub) "
                  "VALUES (?, ?, 0, 0, ?, ?, ?)",
                  (name, STARTING_ELO, 'discord-bot', key, sub_id))
        msg = f"Your name is '{name}'."
    landed = join_own_clans(c, sub_id)
    if landed:
        msg += f" You are now on the {landed[0][0]} roster."
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "name": name, "message": msg}), 200


@app.route('/api/bot/protection', methods=['GET', 'POST'])
def bot_protection_route():
    """Read or set protection on the account's own name.

    Deliberately offers no way to name a target: from Discord you can only
    change your own. The rules are the site's - it needs match history to
    switch on, and it can only be changed once a day.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == 'GET':
        discord_id = str(request.args.get('discord_id', '')).strip()
        want = None
    else:
        data = request.json or {}
        discord_id = str(data.get('discord_id', '')).strip()
        want = 1 if data.get('enabled') else 0
    if not discord_id:
        return jsonify({"error": "no discord_id"}), 400
    sub_id = 'discord:' + discord_id

    conn = db()
    c = conn.cursor()
    name = account_name_for(c, sub_id)
    if not name:
        conn.close()
        return jsonify({"ok": False, "message": "You have no name on this account yet. "
                                                "Set one with /setname first."}), 200
    c.execute("SELECT COALESCE(strict_mode, 0), prot_changed_at, "
              "COALESCE(wins, 0) + COALESCE(losses, 0) FROM players WHERE name = ?", (name,))
    row = c.fetchone()
    enabled, changed_at, played = (row[0], row[1], row[2]) if row else (0, None, 0)

    def hours_left():
        if not changed_at:
            return 0.0
        c.execute("SELECT (julianday('now') - julianday(?)) * 24.0", (changed_at,))
        gone = (c.fetchone() or [None])[0]
        return 0.0 if gone is None else max(0.0, PROTECTION_COOLDOWN_HOURS - gone)

    if want is None:
        left = hours_left()
        conn.close()
        return jsonify({"ok": True, "name": name, "enabled": bool(enabled),
                        "hours_left": round(left, 1), "played": played}), 200

    # Same as the site: no match history needed. See the note there.
    if want != enabled:
        left = hours_left()
        if left > 0:
            conn.close()
            wait = (f"{int(left)} hours" if left >= 1
                    else f"{max(1, int(left * 60))} minutes")
            return jsonify({"ok": False, "name": name, "enabled": bool(enabled),
                            "message": f"Protection can only be changed once a day. "
                                       f"Try again in {wait}."}), 200
        c.execute("UPDATE players SET strict_mode = ?, prot_changed_at = ? WHERE name = ?",
                  (want, time.strftime('%Y-%m-%d %H:%M:%S'), name))
    conn.commit()
    conn.close()
    if want:
        return jsonify({"ok": True, "name": name, "enabled": True,
                        "message": f"Protection is ON for '{name}'. Only matches you press "
                                   f"Play on will count, and your rating shows as confirmed."}), 200
    return jsonify({"ok": True, "name": name, "enabled": False,
                    "message": f"Protection is OFF for '{name}'. Your rating is no longer "
                               f"marked as confirmed, and every match counts again."}), 200


@app.route('/api/bot/register', methods=['POST'])
def bot_register_route():
    """Register a name against a Discord account.

    Every rule /register applies is applied here too - shape, blocklist,
    default names, the one-name cap and the duplicate check - because this
    is the same act done from a different place. The account it lands on is
    the same identity Discord sign-in produces, so a name registered from
    the bot is simply there when the player signs into the site.
    """
    if not bot_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    discord_id = str(data.get('discord_id', '')).strip()
    name = str(data.get('name', '')).strip()
    if not discord_id:
        return jsonify({"ok": False, "message": "No Discord account was given."}), 400
    if not name:
        return jsonify({"ok": False, "message": "No name provided."}), 400

    if not is_valid_name_format(name):
        return jsonify({"ok": False, "message": "Name must be 1-16 letters or digits, and cannot end in a digit."}), 200
    if is_blocked_word(name):
        return jsonify({"ok": False, "message": "That name isn't allowed. Please choose another."}), 200
    if is_default_name(name):
        return jsonify({"ok": False, "message": "That is one of Starblast's default names, given to anyone who joins without typing one. Too many players share it for it to be tracked. Pick a name of your own in game."}), 200

    sub_id = 'discord:' + discord_id
    if data.get('username'):
        remember_discord_user(sub_id, data.get('username'),
                              data.get('display') or data.get('username'))

    conn = db()
    c = conn.cursor()
    c.execute("BEGIN IMMEDIATE")
    c.execute("SELECT name FROM players WHERE google_sub = ?", (sub_id,))
    already = [row[0] for row in c.fetchall()]
    if len(already) >= MAX_NAMES_PER_ACCOUNT:
        conn.close()
        return jsonify({"ok": False, "held": already[0],
                        "message": f"Your account already has a name: '{already[0]}'. Remove it on the site first if you want a different one."}), 200

    c.execute("SELECT name FROM players WHERE norm_name = ?", (normalize_name(name),))
    taken = c.fetchone()
    if taken:
        conn.close()
        return jsonify({"ok": False, "taken": taken[0],
                        "message": f"'{taken[0]}' is already registered. If it is yours, claim it on the site."}), 200

    c.execute("INSERT INTO players (name, elo, wins, losses, reg_ip, norm_name, google_sub) "
              "VALUES (?, ?, 0, 0, ?, ?, ?)",
              (name, STARTING_ELO, 'discord-bot', normalize_name(name), sub_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "name": name,
                    "message": f"'{name}' is registered to your Discord account."}), 200


@app.route('/report', methods=['POST'])
def report_name():
    """Report that somebody has taken, or is trying to take, your name.

    Claims complete automatically once the claimant wins as that name, which
    is a cost rather than a proof - nothing observed in game can tell a real
    owner from someone wearing their name. This is the recourse. It does not
    undo anything on its own; it raises an alert for a person to look at,
    because deciding who someone really is needs knowledge the site does not
    have.
    """
    data = request.json or {}
    name = str(data.get('name', '')).strip()
    note = str(data.get('note', '')).strip()[:300]
    if not name:
        return jsonify({"message": "Which name are you reporting?"}), 400

    conn = db()
    c = conn.cursor()
    c.execute("SELECT name FROM players WHERE norm_name = ?", (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{name}' is not on the leaderboard."}), 404
    stored_name = row[0]

    me_now = current_user()
    if me_now:
        c.execute("SELECT COUNT(*) FROM name_reports WHERE status = 'open' "
                  "AND reported_by = ?", (me_now,))
        if (c.fetchone() or [0])[0] >= MAX_PENDING_CLAIMS:
            conn.close()
            return jsonify({"message": "You already have several reports open. "
                                       "Wait for those to be looked at first."}), 429
    if rate_hit(c, 'name_report', MAX_PENDING_CLAIMS, '-1 day'):
        conn.close()
        return jsonify({"message": "You already have several reports open. "
                                   "Wait for those to be looked at first."}), 429

    c.execute("INSERT INTO name_reports (name, reported_by, ip, note, created_at, status) "
              "VALUES (?, ?, ?, ?, ?, 'open')",
              (stored_name, current_user(), None, note, time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Reported '{stored_name}'. {CONTACT_HANDLE} will look at it by "
                               f"hand - nothing changes automatically."}), 200


@app.route('/clan/leader/request', methods=['POST'])
def clan_leader_request():
    """Ask to run a clan, from the website. The owner still decides in Discord."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"ok": False, "message": "Sign in first."}), 401
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    handle = discord_handle(c, sub_id) or account_name_for(c, sub_id) or ''
    status, payload = perform_leader_request(c, sub_id, handle,
                                             data.get('tag'), data.get('note'))
    if payload.get("ok"):
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/clan/leader/state')
def clan_leader_state_route():
    """Where the signed-in account stands, so the page can show one thing."""
    sub_id = current_user()
    if not sub_id:
        return jsonify({"state": "none", "logged_in": False}), 200
    conn = db()
    c = conn.cursor()
    state = clan_leader_state(c, sub_id)
    conn.close()
    return jsonify({"state": state, "logged_in": True,
                    "contact": CONTACT_HANDLE}), 200


@app.route('/clan/apply', methods=['POST'])
def clan_apply():
    """Ask a clan to take you. Its admin decides.

    Mirrors clan_add() from the other side, and uses the same evidence test,
    so neither route is a way round the other. If the name has an owner, only
    that owner can apply with it - otherwise anyone could volunteer somebody
    else. If it has no owner there is nobody to check, so the clan's tag must
    genuinely be in the name, exactly as a direct add would require.
    """
    data = request.json or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({"message": "Enter your player name."}), 400

    conn = db()
    c = conn.cursor()
    known = canonical_clan_tag(data.get('clan'), all_clan_tags(c))
    if not known:
        conn.close()
        return jsonify({"message": "No clan has that tag."}), 404

    if known not in curated_clans(c):
        conn.close()
        return jsonify({"message": f"{known} has no admin yet, so it still picks up members "
                                   f"automatically from the tag in your name. There is "
                                   f"nothing to apply for."}), 400

    c.execute("SELECT name, google_sub, clan FROM players WHERE norm_name = ?",
              (normalize_name(name),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": f"'{name}' is not on the leaderboard yet. Win a tracked "
                                   f"match first, or register the name."}), 404

    stored_name, owner_sub, current_clan = row
    if current_clan == known:
        conn.close()
        return jsonify({"message": f"'{stored_name}' is already in {known}."}), 400
    if current_clan:
        conn.close()
        return jsonify({"message": f"'{stored_name}' is in {current_clan} and has to leave "
                                   f"that clan first."}), 400

    if owner_sub:
        if current_user() != owner_sub:
            conn.close()
            return jsonify({"message": "That name belongs to an account. Sign in with it on "
                                       "Settings before applying."}), 403
    elif detect_clan(stored_name, all_clan_tags(c)) != known:
        conn.close()
        return jsonify({"message": f"'{stored_name}' has no account and {known} is not in the "
                                   f"name, so there is no way to tell this is you. Claim the "
                                   f"name on Settings first."}), 400

    c.execute("SELECT id FROM clan_invites WHERE clan = ? AND name = ? AND status = 'pending'",
              (known, stored_name))
    if c.fetchone():
        conn.close()
        return jsonify({"message": f"'{stored_name}' already has something pending with {known}."}), 400

    c.execute("INSERT INTO clan_invites (clan, name, invited_by, created_at, status, direction) "
              "VALUES (?, ?, ?, ?, 'pending', 'application')",
              (known, stored_name, current_user(), time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Applied to {known}. Their admin has to accept it."}), 200


@app.route('/clan/application/respond', methods=['POST'])
def clan_application_respond():
    """Accept or decline someone applying to a clan you run.

    The decision itself lives in perform_clan_app_decide, shared with the
    bot, so accepting on the website and accepting in Discord cannot come
    to mean different things.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_app_decide(c, sub_id, data.get('id'),
                                              bool(data.get('accept')))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/clan/create', methods=['POST'])
def clan_create():
    """Start a new clan. Whoever creates it becomes its first admin.

    A new clan is curated from the moment it exists, because its creator is
    already an admin of it - so automatic tag detection never touches it.
    That is the point: a fresh two-letter tag would otherwise sweep in every
    player whose name happens to begin with those letters. The creator
    builds the roster by inviting people instead.
    """
    sub_id = current_user()
    if not sub_id:
        return jsonify({"message": "Sign in first."}), 401
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_create(
        c, sub_id, (request.json or {}).get('tag'),
        trusted=api_key_ok(request.headers.get('X-API-Key')))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


def perform_leader_request(c, sub_id, handle, tag, note):
    """Ask to be allowed to run a clan. Shared by the website and the bot.

    Does NOT commit. A denial is sticky, so this refuses rather than
    quietly stacking up a second request behind the first.
    """
    if not sub_id:
        return 401, {"ok": False, "state": "none", "message": "Sign in first."}
    state = clan_leader_state(c, sub_id)
    if state == 'approved':
        return 200, {"ok": False, "state": state,
                     "message": "You are already approved to run a clan."}
    if state == 'pending':
        return 200, {"ok": False, "state": state,
                     "message": "You already have a request waiting."}
    # A denial does not block a new request - the earlier row stays on
    # record and the page says the last one was turned down, so asking
    # again is a choice made knowingly rather than a locked door.
    # The tag is stored AS TYPED. It is informational - the owner reads
    # it off the approval card - and folding it here is how ꞨⱤ turned
    # into a card that said SR.
    c.execute("INSERT INTO clan_leader_requests (google_sub, handle, tag, note, "
              "created_at, status) VALUES (?, ?, ?, ?, ?, 'pending')",
              (sub_id, str(handle or '')[:80], ' '.join(str(tag or '').split())[:24],
               str(note or '')[:300], time.strftime('%Y-%m-%d %H:%M:%S')))
    return 200, {"ok": True, "id": c.lastrowid, "state": "pending",
                 "message": "Request sent. The site owner decides, and you will hear "
                            "either way - on Discord if your account is linked."}


def clan_leader_state(c, sub_id):
    """Where this account stands on being allowed to run a clan.

    Returns one of: 'approved', 'pending', 'denied', 'none'. A denial does
    not block a new request; it is reported so the page can say the last
    answer was no before offering the form again.
    """
    if not sub_id:
        return 'none'
    c.execute("SELECT status FROM clan_leader_requests WHERE google_sub = ? "
              "ORDER BY CASE status WHEN 'approved' THEN 0 WHEN 'pending' THEN 1 "
              "ELSE 2 END, id DESC LIMIT 1", (sub_id,))
    row = c.fetchone()
    return row[0] if row else 'none'


def search_key(*parts):
    """What a search box matches against: each part as written, plus its
    plain-letter reading. L7 finds Ⱡ7, DARKWARRIOR finds a name written
    in symbol letters, and a pasted Ⱡ7 still finds itself. Cyrillic and
    Chinese names keep their own letters."""
    out = []
    for part in parts:
        if not part:
            continue
        raw = normalize_name(str(part))
        folded = clean_clan_tag(part)
        out.append(raw)
        if folded and folded != raw:
            out.append(folded)
    return ''.join(out)


def worn_tags(name):
    """Every clan tag a name is WEARING, read across the whole name.

    A tag counts where it stands on its own: as any whitespace-separated
    word, inside brackets anywhere, or as the entire name. "OSAMA ꞨⱤ✧➛"
    wears SR just as "ꞨⱤ✧ OSAMA" does.

    A plain substring match is still refused, and always will be: COVID19
    starts with COV, GERRIT with GE, SRSLY with SR, and none of those
    players are in a clan. That mistake is what got clan detection
    switched off the first time.
    """
    raw = str(name or '')
    out = set()
    # Brackets anywhere: "OSAMA [SR]" and "[SR] OSAMA" alike.
    for m in re.finditer(r'[\[\(\{\u3010\u3016\u300c\u300e<]\s*'
                         r'([^\]\)\}\u3011\u3017\u300d\u300f>]{1,12})', raw):
        out.add(clean_clan_tag(m.group(1)))
    # Every word, wherever it sits.
    for token in raw.split():
        out.add(clean_clan_tag(token))
    out.add(clean_clan_tag(raw))          # the name IS the tag
    return {t for t in out if t}


def absorb_unowned(c, tag):
    """Give a new clan every unowned player already wearing its tag.

    An unowned name has no account behind it, so there is nobody to ask,
    and the tag is genuinely in the name the tracker read. Players WITH
    accounts are never swept in - they get an invitation and accept it.

    Two kinds of evidence. A tag standing alone as a word, in brackets or
    as the whole name, anywhere in the name. And - only for a clan that
    styles its tag - a name that opens with that exact styling, which is
    how a fused ꞨⱤ✧ʲᵃᶜᵏᶦᵉᵉ counts while COVID19 still does not.
    """
    c.execute("SELECT display_tag FROM clans WHERE tag = ?", (tag,))
    row = c.fetchone()
    styled = (row[0] if row else None) or ""
    # Distinctive styling only: if the shown tag is just the letters, this
    # would be a plain prefix match, which is what swept in COVID19.
    if styled == tag or clean_clan_tag(styled) != tag:
        styled = ""

    taken = []
    c.execute("SELECT name FROM players WHERE (google_sub IS NULL OR google_sub = '') "
              "AND (clan IS NULL OR clan = '') AND COALESCE(clan_locked, 0) = 0")
    for (nm,) in c.fetchall():
        if tag in worn_tags(nm) or (styled and nm.startswith(styled)):
            taken.append(nm)
    for nm in taken:
        c.execute("UPDATE players SET clan = ? WHERE name = ?", (tag, nm))
    return taken


# Length bounds for the FOLDED tag - the plain-letter reading, not what
# was typed. 16 because 6 turned out to be too tight for real clan names:
# FV HAWKS reads as FVHAWKS, which is seven, and was refused as too long.
# The floor stays at 2; a one-letter tag carries no more meaning than a
# smudge and would collide with far too much.
CLAN_TAG_MIN_LEN = 2
CLAN_TAG_MAX_LEN = 16


def perform_clan_create(c, sub_id, raw_tag, trusted=False):
    """Claim a clan tag. Shared by the website and the bot. Does NOT commit."""
    tag = clean_clan_tag(raw_tag)
    if not CLAN_TAG_MIN_LEN <= len(tag) <= CLAN_TAG_MAX_LEN:
        return 400, {"ok": False,
                     "message": f"A clan tag is {CLAN_TAG_MIN_LEN} to "
                                f"{CLAN_TAG_MAX_LEN} letters or numbers."}
    if not any(ch.isalpha() for ch in tag):
        return 400, {"ok": False, "message": "A clan tag needs at least one letter."}
    if is_blocked_word(tag):
        return 400, {"ok": False,
                     "message": "That tag isn't allowed. Please choose another."}

    c.execute("SELECT tag FROM clans WHERE tag = ?", (tag,))
    if c.fetchone():
        return 400, {"ok": False, "message": f"{tag} has already been claimed."}

    # Running a clan is a permission, granted once by the site owner, not
    # something a name can prove on its own. It is checked before anything
    # else because it is about the person rather than the tag.
    if not trusted:
        state = clan_leader_state(c, sub_id)
        if state != 'approved':
            return 403, {"ok": False, "leader_state": state,
                         "message": {
                             'pending': "Your request to run a clan is still waiting to be "
                                        "looked at. You will hear as soon as it is decided.",
                             'denied': f"Your request to run a clan was turned down. Ask "
                                       f"{CONTACT_HANDLE} on Discord if that was a mistake.",
                         }.get(state,
                               "You need to be approved to run a clan first. Ask for it "
                               "and the site owner decides.")}

    # A name before a clan. The clan page names its leader by their
    # leaderboard name; without one the clan reads as run by nobody, and
    # the leader wonders where their crown went.
    if not trusted and not account_name_for(c, sub_id):
        return 400, {"ok": False, "need_name": True,
                     "message": "Set your account name first - the clan page shows "
                                "who runs it by that name. Save it on Your account, "
                                "then claim your tag."}

    c.execute("SELECT COUNT(*) FROM clans WHERE created_by = ?", (sub_id,))
    if c.fetchone()[0] >= MAX_CLANS_PER_ACCOUNT:
        return 400, {"ok": False,
                     "message": f"You have already claimed {MAX_CLANS_PER_ACCOUNT} clans. "
                                f"Ask {CONTACT_HANDLE} on Discord if you need another."}

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    shown = ' '.join(str(raw_tag or '').split())[:32]
    c.execute("INSERT INTO clans (tag, display_tag, created_by, created_at) "
              "VALUES (?, ?, ?, ?)",
              (tag, shown if shown and shown != tag else None, sub_id, now))
    c.execute("INSERT OR IGNORE INTO clan_admins (clan, google_sub, created_at) VALUES (?, ?, ?)",
              (tag, sub_id, now))
    joined, elsewhere = join_admin_names(c, sub_id, tag)
    # Every unowned name already wearing the tag joins on creation - that
    # is the roster the clan actually has, and nobody has to add them one
    # at a time.
    absorbed = absorb_unowned(c, tag)
    c.execute("SELECT COUNT(*) FROM players WHERE google_sub = ?", (sub_id,))
    has_name = (c.fetchone() or [0])[0] > 0
    msg = f"{tag} is yours. You are its admin."
    if joined:
        msg += " You are on the roster."
    elif not has_name:
        msg += (" You have no name on this account yet, so you are not on the roster - "
                "set one and you will be added automatically.")
    if absorbed:
        msg += (f" {len(absorbed)} player{'' if len(absorbed) == 1 else 's'} already "
                f"playing under {tag} joined automatically.")
    if absorbed:
        msg += (f" {len(absorbed)} player{'' if len(absorbed) == 1 else 's'} already "
                f"playing under {tag} joined automatically.")
    if elsewhere:
        msg += " " + ", ".join(elsewhere) + " stayed in their current clan."
    return 200, {"ok": True, "message": msg, "clan": tag,
                 "admin_on_roster": bool(joined), "admin_has_name": has_name,
                 "absorbed": absorbed[:25], "absorbed_count": len(absorbed)}


def clan_tagged_name(base, tag):
    """`NAME` in clan `Ł7` reads `Ł7 NAME`.

    Any tag already on the front is taken off first, bracketed or bare, so
    changing your name while in a clan cannot end up as `Ł7 Ł7 NAME`. A
    bare leading token is what detect_clan already treats as wearing the
    tag, so this form is one the rest of the site already understands.
    """
    text = str(base or "").strip()
    if not tag:
        return text[:32]
    text = re.sub(r'^\s*[\[\(\{<]?\s*' + re.escape(tag) + r'\s*[\]\)\}>]?\s*',
                  '', text, flags=re.IGNORECASE).strip()
    return ("%s %s" % (tag, text)).strip()[:32]


def applicant_stats(c, name):
    """The few numbers a leader wants before saying yes."""
    c.execute("SELECT elo, COALESCE(wins, 0), COALESCE(losses, 0) FROM players WHERE name = ?",
              (name,))
    row = c.fetchone()
    if not row:
        return {"name": name, "elo": "0.0", "wins": 0, "losses": 0,
                "winrate": "-", "rank": 0, "played": 0}
    elo, wins, losses = row
    c.execute("SELECT COUNT(*) + 1 FROM players WHERE elo > ?", (elo,))
    rank = (c.fetchone() or [0])[0]
    played = wins + losses
    return {"name": name, "elo": "%.1f" % elo, "wins": wins, "losses": losses,
            "winrate": ("%d%%" % round(100 * wins / played)) if played else "-",
            "rank": rank, "played": played}


def clan_applications(c, tag):
    """Everyone waiting on this clan, with the numbers a leader wants."""
    c.execute("SELECT id, name, created_at FROM clan_invites "
              "WHERE clan = ? AND direction = 'application' AND status = 'pending' "
              "ORDER BY created_at", (tag,))
    out = []
    for app_id, name, created in c.fetchall():
        row = applicant_stats(c, name)
        row.update({"id": app_id, "clan": tag, "created_at": created,
                    "joined": join_date(created)})
        out.append(row)
    return out


def perform_clan_app_decide(c, sub_id, app_id, accept, trusted=False):
    """Accept or turn down an application. Shared by site and bot.

    Accepting stamps the clan tag on the front of the name the member says
    they play as, which is what being in the clan looks like from outside.
    Does NOT commit.
    """
    c.execute("SELECT clan, name, status FROM clan_invites WHERE id = ? "
              "AND direction = 'application'", (app_id,))
    row = c.fetchone()
    if not row:
        return 404, {"ok": False, "message": "No such application."}
    clan, name, status = row
    if status != 'pending':
        return 400, {"ok": False, "clan": clan, "name": name,
                     "message": f"That application was already {status}."}
    if not trusted and not may_manage(c, sub_id, clan):
        return 403, {"ok": False,
                     "message": "Only the leader or a co-leader can decide who joins."}
    c.execute("UPDATE clan_invites SET status = ? WHERE id = ?",
              ('approved' if accept else 'declined', app_id))
    if not accept:
        return 200, {"ok": True, "accepted": False, "clan": clan, "name": name,
                     "message": f"Application from '{name}' declined."}
    c.execute("SELECT clan FROM players WHERE name = ?", (name,))
    already = (c.fetchone() or [None])[0]
    if already:
        return 200, {"ok": True, "accepted": False, "clan": clan, "name": name,
                     "message": f"'{name}' joined {already} in the meantime, "
                                f"so nothing changed."}
    c.execute("UPDATE players SET clan = ?, clan_locked = 0 WHERE name = ?", (clan, name))
    return 200, {"ok": True, "accepted": True, "clan": clan, "name": name,
                 "message": f"'{name}' joined {clan}, and now shows as "
                            f"'{clan_tagged_name(name, clan)}' on the leaderboard."}


def perform_clan_role(c, sub_id, raw_tag, name, role, trusted=False):
    """Make someone a co-leader or moderator, or take it back.

    An empty role removes it. The target has to have an account: a role is
    held by an account, and most members have never signed in. Does NOT
    commit.
    """
    known = canonical_clan_tag(raw_tag, all_clan_tags(c))
    if not known:
        return 404, {"ok": False, "message": "No clan with that tag."}
    want = str(role or "").strip().lower()
    if want and want not in ('coleader', 'moderator'):
        return 400, {"ok": False,
                     "message": "A role is co-leader, moderator, or nothing."}
    actor = 'leader' if trusted else clan_role(c, sub_id, known)
    if not actor:
        return 403, {"ok": False, "message": "You have no role in that clan."}
    c.execute("SELECT name, google_sub, clan FROM players WHERE norm_name = ?",
              (normalize_name(str(name or '')),))
    row = c.fetchone()
    if not row:
        return 404, {"ok": False, "message": f"'{name}' is not on the leaderboard."}
    stored_name, target_sub, their_clan = row
    if not target_sub:
        return 400, {"ok": False,
                     "message": f"'{stored_name}' has no account, so there is nothing "
                                f"to give a role to. They have to sign in first."}
    if their_clan != known:
        return 400, {"ok": False,
                     "message": f"'{stored_name}' is not in {known}."}
    if target_sub == sub_id and not trusted:
        return 400, {"ok": False, "message": "You cannot change your own role."}
    current = clan_role(c, target_sub, known)
    if current == 'leader':
        return 403, {"ok": False, "message": "The clan's leader keeps their role."}
    # Co-leader is the leader's to give: a co-leader cannot kick one, so
    # letting them appoint one would create power they could not undo.
    if (want == 'coleader' or current == 'coleader') and actor != 'leader':
        return 403, {"ok": False,
                     "message": "Only the clan's leader can appoint or remove a co-leader."}
    if actor == 'moderator':
        return 403, {"ok": False, "message": "Moderators cannot hand out roles."}
    if not want:
        c.execute("DELETE FROM clan_admins WHERE clan = ? AND google_sub = ?",
                  (known, target_sub))
        return 200, {"ok": True, "clan": known, "name": stored_name, "role": "",
                     "message": f"'{stored_name}' is an ordinary member of {known} again."}
    c.execute("INSERT INTO clan_admins (clan, google_sub, role, created_at) "
              "VALUES (?, ?, ?, ?) ON CONFLICT(clan, google_sub) DO UPDATE SET role = ?",
              (known, target_sub, want, time.strftime('%Y-%m-%d %H:%M:%S'), want))
    return 200, {"ok": True, "clan": known, "name": stored_name, "role": want,
                 "message": f"'{stored_name}' is now a {CLAN_ROLE_LABELS[want].lower()} "
                            f"of {known}."}


def perform_clan_region(c, sub_id, raw_tag, region, trusted=False):
    """Set - or clear - where a clan is based. Shared by site and bot.

    An empty region clears it rather than failing, so a leader who set the
    wrong one can take it back off. Does NOT commit.
    """
    known = canonical_clan_tag(raw_tag, all_clan_tags(c))
    if not known:
        return 404, {"ok": False, "message": "No clan with that tag."}
    if not trusted and not may_manage(c, sub_id, known):
        return 403, {"ok": False,
                     "message": "Only the leader or a co-leader can set the region."}
    key = str(region or "").strip().lower()
    if key and key not in REGION_KEYS:
        return 400, {"ok": False,
                     "message": "Pick one of: " + ", ".join(REGION_LABELS[k]
                                                            for k in REGION_KEYS)}
    c.execute("UPDATE clans SET region = ? WHERE tag = ?", (key or None, known))
    label = REGION_LABELS.get(key)
    return 200, {"ok": True, "clan": known, "region": key or "",
                 "region_label": label or "",
                 "message": f"{known} is now based in {label}." if key else
                            f"{known} no longer says where it is based."}


def perform_clan_delete(c, sub_id, raw_tag, trusted=False):
    """Delete a clan outright. Shared by the website and the bot.

    Revoking admin leaves the clan sitting there with no one running it;
    this removes the thing itself - the tag, its admins, its codes, its
    outstanding invitations, and the tag on every member's name. Does NOT
    commit.
    """
    known = canonical_clan_tag(raw_tag, all_clan_tags(c))
    if not known:
        return 404, {"ok": False, "message": "No clan with that tag."}
    if not trusted and not is_clan_leader(c, sub_id, known):
        return 403, {"ok": False,
                     "message": "Only the clan's leader can delete it."}

    c.execute("SELECT COUNT(*) FROM players WHERE clan = ?", (known,))
    members = (c.fetchone() or [0])[0]
    # clan_locked stays 0 so a name can be tagged again later; the clan is
    # gone, not the players.
    c.execute("UPDATE players SET clan = NULL WHERE clan = ?", (known,))
    c.execute("DELETE FROM clan_admins WHERE clan = ?", (known,))
    c.execute("DELETE FROM clan_codes WHERE clan = ?", (known,))
    c.execute("DELETE FROM clan_invites WHERE clan = ?", (known,))
    c.execute("DELETE FROM clans WHERE tag = ?", (known,))
    return 200, {"ok": True, "clan": known,
                 "message": f"{known} deleted. {members} member"
                            f"{'' if members == 1 else 's'} released - their ratings and "
                            f"match history are untouched."}


@app.route('/clan/role', methods=['POST'])
def clan_role_route():
    """Appoint or unappoint a co-leader or moderator."""
    sub_id = current_user()
    trusted = api_key_ok(request.headers.get('X-API-Key'))
    if not sub_id and not trusted:
        return jsonify({"message": "Sign in first."}), 401
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_role(c, sub_id, data.get('clan'), data.get('name'),
                                        data.get('role'), trusted=trusted)
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/clan/region', methods=['POST'])
def clan_region():
    """A leader saying where their clan is based."""
    sub_id = current_user()
    trusted = api_key_ok(request.headers.get('X-API-Key'))
    if not sub_id and not trusted:
        return jsonify({"message": "Sign in first."}), 401
    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_region(c, sub_id, data.get('clan'),
                                          data.get('region'), trusted=trusted)
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/clan/delete', methods=['POST'])
def clan_delete():
    """Delete your own clan, or any clan with the site's API key."""
    sub_id = current_user()
    trusted = api_key_ok(request.headers.get('X-API-Key'))
    if not sub_id and not trusted:
        return jsonify({"message": "Sign in first."}), 401
    data = request.json or {}
    # Deleting is irreversible, so the tag has to be typed back rather than
    # arriving from a button alone.
    if clean_clan_tag(data.get('confirm')) != clean_clan_tag(data.get('clan')):
        return jsonify({"message": "Type the clan tag to confirm."}), 400
    conn = db()
    c = conn.cursor()
    status, payload = perform_clan_delete(c, sub_id, data.get('clan'), trusted=trusted)
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/clan/revoke', methods=['POST'])
def clan_revoke():
    """Take clan admin away again. Site owner only.

    Admin does not expire on its own. The code that granted it is one-time,
    but the rights it hands over last until they are taken back here - so
    this is the way to deal with an admin who leaves or misbehaves. Removing
    a clan's last admin puts it back on automatic tag detection, and a fresh
    code can be issued to whoever takes over.
    """
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"message": "Unauthorized"}), 401
    known = canonical_clan_tag((request.json or {}).get('clan'))
    if not known:
        return jsonify({"message": "Unknown clan tag. Known tags: "
                                   + ", ".join(sorted(all_clan_tags()))}), 400

    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM clan_admins WHERE clan = ?", (known,))
    removed = c.rowcount
    # Unused codes for this clan would otherwise still be redeemable by
    # whoever is holding them.
    c.execute("DELETE FROM clan_codes WHERE clan = ? AND used_at IS NULL", (known,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Removed {removed} admin(s) from {known}. "
                               f"{known} is back on automatic tag detection."}), 200


# Clans are off while the change-over settles. The tags were matched
# against names read off the screen, and those were often wrong, so every
# membership derived from them is suspect. Saying so beats showing a
# directory that quietly lies.
CLANS_NOTICE = ("Clans are under construction. Names are now read from the game "
                "itself rather than off the screen, and the old clan tags were matched "
                "against names that were often misread - so they have been cleared and "
                "will be rebuilt from real data.")


# A clan is ranked from this many members up. One person's "average" is
# just their own rating, so a single strong player would sit above every
# real clan forever and the table would mean nothing. Smaller clans are
# still listed, just not placed.
CLAN_RANK_MIN = 2


@app.route('/myclan')
def my_clan_page():
    """Everything one clan's staff can do, in one place."""
    sub_id = current_user()
    conn = db()
    c = conn.cursor()
    tags = clan_admin_tags(c, sub_id) if sub_id else []
    if not tags:
        conn.close()
        return render_template('myclan.html', clan=None, signed_in=bool(sub_id),
                               version=APP_VERSION, contact=CONTACT_HANDLE,
                               page='myclan', client_id=GOOGLE_CLIENT_ID)
    # More than one clan is rare, so a chooser rather than a whole page of
    # tabs: ?clan= picks, the first one is the default.
    asked = canonical_clan_tag(request.args.get('clan'))
    tag = asked if asked in tags else tags[0]
    role = clan_role(c, sub_id, tag)

    c.execute("SELECT name, elo, wins, losses, google_sub, clan_joined_at "
              "FROM players WHERE clan = ?", (tag,))
    rows = c.fetchall()
    c.execute("SELECT google_sub, COALESCE(role, 'leader') FROM clan_admins WHERE clan = ?",
              (tag,))
    roles = {r[0]: r[1] for r in c.fetchall() if r[0]}
    rows.sort(key=leaderboard_sort_key)
    members = []
    for name, elo, wins, losses, owner_sub, joined in rows:
        wins = wins or 0
        losses = losses or 0
        played = wins + losses
        members.append({
            "name": name, "display": display_name(name, tag, clan_display(c, tag)),
            "role": roles.get(owner_sub, ""),
            "role_label": CLAN_ROLE_LABELS.get(roles.get(owner_sub), ""),
            "elo": f"{elo:.1f}", "wins": wins, "losses": losses,
            "winrate": f"{round(100 * wins / played)}%" if played else "-",
            "joined": join_date(joined),
            "is_you": bool(owner_sub) and owner_sub == sub_id,
        })

    c.execute("SELECT region FROM clans WHERE tag = ?", (tag,))
    region = (c.fetchone() or [None])[0] or ""
    link_row = active_invite_link(c, tag)
    clan = {
        "tag": tag, "display": clan_display(c, tag), "members": members,
        "size": len(members), "region": region,
        "region_label": REGION_LABELS.get(region, ""), "regions": REGIONS,
        "applications": clan_applications(c, tag),
        "invited": [{"id": r[0], "name": r[1]} for r in c.execute(
            "SELECT id, name FROM clan_invites WHERE clan = ? "
            "AND status = 'pending' AND direction = 'invite' "
            "ORDER BY name", (tag,)).fetchall()],
        "role": role, "role_label": CLAN_ROLE_LABELS.get(role, ""),
        "can_manage": clan_rank(role) >= clan_rank('coleader'),
        "is_leader": role == 'leader',
        "others": [t for t in tags if t != tag],
        "link": invite_link_json(link_row) if link_row else None,
        "link_days": INVITE_LINK_DAYS,
        # Running a clan and being on its roster are different things, so
        # staff with no leaderboard name are not a bug - but they are
        # invisible on their own roster and their clan says nobody runs it,
        # and nothing on the page told them why. Two of five leaders.
        "you_named": bool(account_name_for(c, sub_id)),
    }
    conn.close()
    return render_template('myclan.html', clan=clan, signed_in=True,
                           version=APP_VERSION, contact=CONTACT_HANDLE,
                           page='myclan', client_id=GOOGLE_CLIENT_ID)


@app.route('/clans')
def clans_page():
    """Public directory of every clan, ranked by average skill."""
    conn = db()
    c = conn.cursor()
    curated = curated_clans(c)
    c.execute("SELECT tag, region FROM clans")
    regions = {r[0]: (r[1] or "") for r in c.fetchall()}
    shown = clan_display_map(c)
    rows = []
    for tag in sorted(all_clan_tags(c)):
        c.execute("SELECT elo, COALESCE(wins, 0), COALESCE(losses, 0) "
                  "FROM players WHERE clan = ?", (tag,))
        got = c.fetchall()
        elos = [r[0] for r in got]
        wins = sum(r[1] for r in got)
        losses = sum(r[2] for r in got)
        played = wins + losses
        avg = sum(elos) / len(elos) if elos else 0.0
        rows.append({
            "tag": tag,
            "size": len(elos),
            "avg": avg,
            "avg_elo": f"{avg:.1f}",
            "wins": wins,
            "losses": losses,
            "winrate": f"{round(100 * wins / played)}%" if played else "-",
            "display": shown.get(tag, tag),
            "region": regions.get(tag, ""),
            "region_label": REGION_LABELS.get(regions.get(tag, ""), ""),
            "curated": tag in curated,
        })
    conn.close()
    ranked = [r for r in rows if r["size"] >= CLAN_RANK_MIN]
    small = [r for r in rows if r["size"] < CLAN_RANK_MIN]
    # Highest average first. Size breaks a tie: holding an average across
    # more people is the harder thing to have done.
    ranked.sort(key=lambda r: (-r["avg"], -r["size"], r["tag"]))
    for place, row in enumerate(ranked, 1):
        row["place"] = place
    small.sort(key=lambda r: (-r["size"], r["tag"]))
    return render_template('clans.html', clans=ranked, small=small,
                           total=len(rows), rank_min=CLAN_RANK_MIN,
                           version=APP_VERSION, contact=CONTACT_HANDLE, page='clans',
                           notice=CLANS_NOTICE)


@app.route('/settings')
def settings_page():
    """Settings lives inside Your account now; old links keep working."""
    return redirect('/account', code=301)


@app.route('/account')
def account_page():
    """Your stats and your settings, one place - the page a game opens
    when you tap your own name."""
    sub_id = current_user()
    conn = db()
    c = conn.cursor()
    account_name = account_name_for(c, sub_id)
    acct = None
    if account_name:
        c.execute("SELECT name, elo, COALESCE(wins,0), COALESCE(losses,0), clan "
                  "FROM players WHERE norm_name = ?", (normalize_name(account_name),))
        row = c.fetchone()
        if row:
            name, elo, wins, losses, clan = row
            c.execute("SELECT COUNT(*) + 1 FROM players WHERE elo > ?", (elo,))
            rank = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM players")
            total = c.fetchone()[0]
            played = wins + losses
            by_region = [r for r in region_split(c, name) if r["played"]]
            c.execute("SELECT mp.won, mp.delta, COALESCE(mp.half,0), m.played_at, "
                      "COALESCE(mp.seen, 0) "
                      "FROM match_players mp JOIN matches m ON m.id = mp.match_row "
                      "WHERE mp.norm_name = ? ORDER BY m.played_at DESC LIMIT 10",
                      (normalize_name(name),))
            recent = [{"won": r[0], "delta": r[1] or 0, "half": r[2],
                       "when": str(r[3])[:16], "unseen": not r[4]}
                      for r in c.fetchall()]
            # This render IS the notification. Clear every owned name,
            # not just the shown ten, so the counter matches what the
            # badge promised and can never get stuck on an old match.
            c.execute("UPDATE match_players SET seen = 1 "
                      "WHERE COALESCE(seen, 0) = 0 AND norm_name IN "
                      "(SELECT norm_name FROM players WHERE google_sub = ?)",
                      (sub_id,))
            conn.commit()
            gained = sum(r["gained"] for r in region_split(c, name))
            acct = {
                "name": name, "display": display_name(name, clan, clan_display(c, clan)) if clan else name,
                "elo": f"{elo:.2f}".rstrip('0').rstrip('.'),
                "rank": rank, "total": total, "wins": wins, "losses": losses,
                "winrate": f"{round(100 * wins / played)}%" if played else "-",
                "gained": ("%+.2f" % gained) if played else "-",
                "clan": clan, "clan_display": clan_display(c, clan) if clan else None,
                "by_region": by_region, "recent": recent,
            }
    conn.close()
    return render_template('account.html', version=APP_VERSION,
                           contact=CONTACT_HANDLE, client_id=GOOGLE_CLIENT_ID,
                           account_name=account_name, signed_in=bool(sub_id),
                           acct=acct, page='account',
                           wins_required=CLAIM_WINS_REQUIRED)


@app.route('/manage')
def manage_page():
    # The old address, kept working for anyone who bookmarked it.
    return redirect('/settings', code=301)


@app.route('/play')
def play_page():
    """Live matches, checking in, and getting hold of your name.

    These were spread across the leaderboard and Settings, so the one thing
    a player actually does before a game - make sure it will count - took
    two pages and some guessing.
    """
    conn = db()
    c = conn.cursor()
    capacity, min_age, max_age, min_players = tracker_limits(c)
    c.execute("SELECT sys_id, name, players, age, COALESCE(watching, 0), "
              "COALESCE(region, 'america') FROM live_lobbies "
              "WHERE updated_at > datetime('now', '-5 minutes') ORDER BY watching DESC, age DESC")
    raw = c.fetchall()
    conn.close()
    lobbies, watched_now = describe_lobbies([(r[1], r[2], r[3], r[4]) for r in raw],
                                            capacity, min_age, max_age, min_players)
    for lobby, row in zip(lobbies, raw):
        lobby["id"] = row[0]
        lobby["region"] = row[5]

    # Grouped by region rather than one flat list. Three continents of
    # lobbies in one column is unreadable, and a player only ever cares
    # about the one they are about to play in.
    groups = []
    for key, label in REGIONS:
        here = [l for l in lobbies if l["region"] == key]
        if here:
            groups.append({"key": key, "label": label, "lobbies": here})
    # Every region gets a tab whether or not it has a match right now, so a
    # quiet hour does not look like the tracker has stopped covering it.
    all_regions = [{"key": k, "label": lbl} for k, lbl in REGIONS]
    group_keys = [g["key"] for g in groups]

    conn = db()
    c = conn.cursor()
    account_name = account_name_for(c, current_user())
    conn.close()

    return render_template('play.html', version=APP_VERSION, page='play',
                           lobbies=lobbies, groups=groups, all_regions=all_regions,
                           group_keys=group_keys, watched=watched_now,
                           capacity=capacity, account_name=account_name,
                           min_age_mins=min_age // 60, contact=CONTACT_HANDLE,
                           wins_required=CLAIM_WINS_REQUIRED)


@app.route('/players')
def players_page():
    # Search lives on the leaderboard now - one list of players, not two.
    return redirect('/', code=301)


def _players_page_unused():
    """Search every tracked player. Ordered like the leaderboard so the
    unfiltered view is still meaningful."""
    conn = db()
    c = conn.cursor()
    c.execute("SELECT name, elo, wins, losses, clan FROM players")
    rows = c.fetchall()
    conn.close()
    rows.sort(key=leaderboard_sort_key)

    players = []
    for name, elo, wins, losses, clan in rows:
        wins = wins or 0
        losses = losses or 0
        played = wins + losses
        players.append({
            "name": name, "display": display_name(name, clan), "clan": clan,
            "skill": f"{elo:.1f}", "wins": wins, "losses": losses,
            "winrate": f"{round(100 * wins / played)}%" if played else "-",
            # Matched against the search box, which strips punctuation too, so
            # "bel riose" finds BELRIOSE.
            "search": search_key(name, clan),
        })
    return render_template('players.html', players=players, total=len(players),
                           version=APP_VERSION, page='players')


def perform_report(c, sub_id, raw_kind, raw_body, raw_contact, rate_src=None):
    """File a bug report. Shared by the website and the bot. Does NOT commit."""
    body = str(raw_body or '').strip()
    kind = str(raw_kind or 'bug').strip()
    who = str(raw_contact or '').strip()[:120]
    if kind not in dict(REPORT_KINDS):
        kind = 'other'
    if len(body) < 10:
        return 400, {"ok": False,
                     "message": "Please say a little more about what happened - "
                                "a sentence or two is enough."}
    body = body[:4000]
    if rate_hit(c, 'bug_report', MAX_REPORTS_PER_DAY, '-1 day', src=rate_src):
        return 429, {"ok": False,
                     "message": f"That is {MAX_REPORTS_PER_DAY} reports from here today, "
                                f"which is the limit. If there is more to say, "
                                f"message {CONTACT_HANDLE} on Discord."}
    c.execute("INSERT INTO bug_reports (kind, body, contact, google_sub, ip, created_at) "
              "VALUES (?,?,?,?,?,?)",
              (kind, body, who or None, sub_id, None,
               time.strftime('%Y-%m-%d %H:%M:%S')))
    return 200, {"ok": True,
                 "message": "Thank you - that has been logged. If you left a way to "
                            "reach you, you may get a reply."}


@app.route('/reports', methods=['GET', 'POST'])
def reports_page():
    """File a bug report, or read what to include in one.

    Open to anyone. Requiring sign-in would filter out the reports most
    worth reading - somebody who cannot sign in has no other way to say
    so - so the account is recorded when there is one and the form asks
    for a contact when there is not.
    """
    if request.method == 'GET':
        return render_template('reports.html', version=APP_VERSION, page='reports',
                               kinds=REPORT_KINDS, contact=CONTACT_HANDLE,
                               client_id=GOOGLE_CLIENT_ID)

    data = request.json or {}
    conn = db()
    c = conn.cursor()
    status, payload = perform_report(c, current_user(), data.get('kind'),
                                     data.get('body'), data.get('contact'))
    if status == 200:
        conn.commit()
    conn.close()
    return jsonify(payload), status


@app.route('/api/reports')
def api_reports():
    """Read the reports. API key only - they can contain contact details."""
    if not api_key_ok(request.headers.get('X-API-Key')):
        return jsonify({"error": "Unauthorized"}), 401
    status = request.args.get('status', 'open')
    conn = db()
    c = conn.cursor()
    if status == 'all':
        c.execute("SELECT id, kind, body, contact, google_sub, created_at, status "
                  "FROM bug_reports ORDER BY id DESC LIMIT 200")
    else:
        c.execute("SELECT id, kind, body, contact, google_sub, created_at, status "
                  "FROM bug_reports WHERE status = ? ORDER BY id DESC LIMIT 200", (status,))
    out = [{"id": r[0], "kind": r[1], "body": r[2], "contact": r[3],
            "account": r[4], "at": r[5], "status": r[6]} for r in c.fetchall()]
    conn.close()
    return jsonify({"reports": out, "count": len(out)}), 200


@app.route('/changelog')
def changelog_page():
    return render_template('changelog.html', changelog=CHANGELOG,
                           version=APP_VERSION, page='changelog')


@app.route('/info')
def info_page():
    """Every explanation on the site, compiled onto one page.

    The prose lives in info_text_<lang>.py rather than in the template, so
    the page follows the language picker like the rest of the site. It
    reads nothing from the database.
    """
    return render_template('info.html', version=APP_VERSION, page='info',
                           contact=CONTACT_HANDLE,
                           info=info_i18n.page(current_lang(),
                                               elo=STARTING_ELO, k=ELO_K,
                                               contact=CONTACT_HANDLE))


@app.route('/how-it-works')
def how_it_works_page():
    # The old address, kept working for anyone who bookmarked it.
    return redirect('/info', code=301)


@app.route('/elo')
def elo_page():
    return redirect('/info', code=301)


@app.route('/')
def leaderboard():
    period = request.args.get('period', 'all')
    region = request.args.get('region', ALL_REGIONS)
    if period not in PERIOD_KEYS:
        period = 'all'
    # All regions is the default view: one rating per player, which is the
    # number every region has been feeding all along. The per-region boards
    # remain because they are separate competitions - a rating earned
    # against Europeans is not the same achievement as one earned against
    # North Americans - and the selector says which you are looking at.
    if region not in REGION_KEYS and region != ALL_REGIONS:
        region = ALL_REGIONS
    # Which slice to show, what to search the whole board for, and which
    # player to resolve to a page. `pnum`, not `page` - `page` is already
    # the template's name for which nav item is lit.
    try:
        pnum = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        pnum = 1
    q = (request.args.get('q') or '').strip()
    find = (request.args.get('find') or '').strip()
    # Over a window the number is what you gained in it. Over all time the
    # same sum IS the rating that region has given you, so it is shown as a
    # rating instead of a delta.
    gain = period != 'all'
    # board_rows returns two different kinds of number. All-regions
    # all-time comes off the players table and is ALREADY an absolute
    # rating; a single region's all-time is a SUM OF DELTAS that only
    # becomes a rating once STARTING_ELO is added. Adding it to both
    # showed a player on 6.0 as 11.0 on the combined board.
    relative = region != ALL_REGIONS or gain

    conn = db()
    c = conn.cursor()
    rows = board_rows(c, period, region)
    conn.close()

    rows.sort(key=leaderboard_sort_key)

    # Which region each player turns up in most, for the badge on the
    # combined board. A player who splits their time gets the one they
    # play most - the profile has the full breakdown.
    home_region = {}
    if region == ALL_REGIONS:
        conn2 = db()
        c2 = conn2.cursor()
        c2.execute("SELECT mp.norm_name, m.region, COUNT(*) FROM match_players mp "
                   "JOIN matches m ON m.id = mp.match_row GROUP BY 1, 2")
        best = {}
        for norm, reg, cnt in c2.fetchall():
            if cnt > best.get(norm, (0, None))[0]:
                best[norm] = (cnt, reg)
        conn2.close()
        home_region = {k: v[1] for k, v in best.items() if v[1] in REGION_KEYS}

    leaderboard_data = []
    for rank, (name, elo, wins, losses, clan, protected) in enumerate(
            rows, 1):
        wins = wins or 0
        losses = losses or 0
        played = wins + losses
        # Same formatting as the player profile page, so a win rate reads
        # identically wherever it is shown.
        winrate = f"{round(100 * wins / played)}%" if played else "-"
        # The region cell links through to that region's board, so it needs
        # the key for the URL as well as the full label for the text.
        home = home_region.get(normalize_name(name))
        leaderboard_data.append({
            "rank": rank,
            "name": name, "display": display_name(name, clan),
            "skill": (f"{elo:+.2f}" if gain
                      else (f"{STARTING_ELO + elo:.1f}" if relative else f"{elo:.1f}")),
            "search": search_key(name, clan),
            "wins": wins, "losses": losses, "winrate": winrate,
            "clan": clan, "protected": protected,
            "region": home, "region_label": REGION_LABELS.get(home),
        })
    conn = db()
    c = conn.cursor()
    # The tag exactly as its leader wrote it. The folded key is for URLs
    # and matching only; a key is a poor thing to show people. Folding the
    # shown form into the search key too means a pasted ₣ⱠⱤ⇝ finds the
    # clan's members even when their own names do not carry it.
    _shown = clan_display_map(c)
    for _row in leaderboard_data:
        if _row.get("clan"):
            _disp = _shown.get(_row["clan"], _row["clan"])
            _row["clan_display"] = _disp
            if _disp != _row["clan"]:
                _row["search"] += normalize_name(_disp)
                _row["display"] = display_name(_row["name"], _row["clan"], _disp)
    # Only trust a recent push. A stale row would claim a match is being
    # watched long after the tracker stopped, which is worse than saying
    # nothing at all.
    conn.close()

    # A region link names a player, not a page - which page they sit on
    # is a property of the board being opened, so only this route can
    # know it. Redirecting (rather than rendering) keeps #p-<name> in the
    # address bar, which is what the :target highlight matches on.
    if find:
        fkey = normalize_name(find)
        for p in leaderboard_data:
            if normalize_name(p['name']) == fkey:
                return redirect('/?period=%s&region=%s&page=%d#p-%s' % (
                    period, region, (p['rank'] - 1) // PER_PAGE + 1,
                    quote(p['name'], safe='')))
        # Not ranked on this board at all - show page one rather than
        # a dead end.

    # `total` stays the size of the whole board: it is the count the page
    # reports, and a search must not appear to shrink the leaderboard.
    total_ranked = len(leaderboard_data)
    if q:
        # Both readings of the query: as written, and folded to plain
        # letters - so typing L7 finds Ⱡ7 and pasting Ⱡ7 finds it too,
        # whichever symbol alphabet either side used.
        qkey = normalize_name(q)
        qfold = clean_clan_tag(q)
        leaderboard_data = [p for p in leaderboard_data
                            if qkey in p['search']
                            or (qfold and qfold in p['search'])]
    found = len(leaderboard_data)
    pages = max(1, (found + PER_PAGE - 1) // PER_PAGE)
    # Clamped, not 404'd: ?page=900 is a stale link, not an error.
    pnum = min(max(pnum, 1), pages)
    start = (pnum - 1) * PER_PAGE
    leaderboard_data = leaderboard_data[start:start + PER_PAGE]
    return render_template('index.html', leaderboard=leaderboard_data,
                           periods=PERIODS, regions=REGION_CHOICES,
                           period=period, region=region, gain=gain,
                           region_label=REGION_LABELS[region],
                           period_label=dict(PERIODS)[period],
                           version=APP_VERSION, page='leaderboard',
                           pnum=pnum, pages=pages, q=q, found=found,
                           total=total_ranked)


init_db()  # runs on import too, since WSGI hosts never execute __main__

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
