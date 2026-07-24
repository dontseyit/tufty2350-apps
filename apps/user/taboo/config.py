# Game-wide constants and tiny helpers shared across the app.
# Button map = HANDOVER.md spec: B is the primary "proceed" button everywhere;
# on the turn screen A=TABOO -1, B=SKIP, C=GOT IT +1.

# screen states. REFILL is a mid-turn fetch: the timer is paused while we top the
# pool back up (distinct from LOADING, the pre-turn fetch that leads to COUNTDOWN).
(SETUP, HANDOFF, COUNTDOWN, TURN, SUMMARY, WIN,
 CONNECTING, LOADING, NOCARDS, REFILL) = range(10)

TURN_SECONDS = 120       # live turn length (2 minutes)
TARGET_SCORE = 7         # first team to reach this wins
COUNTDOWN_MS = 3500      # 3 - 2 - 1 - GO before a turn (~1s each, ~0.5s on GO)
LOW_TIME_SECONDS = 10    # screen edge pulses red at/under this many seconds
WIFI_TIMEOUT_MS = 9000   # how long to wait for wi-fi at startup before going offline
HTTP_TIMEOUT = 12        # seconds; bounds the agent request so a dropped link can't hang the UI
MIN_CARDS = 10           # online: ensure at least this many unused cards before/within a turn
MAX_FETCH_TRIES = 3      # cap on agent calls per top-up (the agent may repeat words we already have)

# Card categories, in Turkish. The Title-case form is what we send to the agent
# as the user message; the UI shows the uppercased form (textutil.tr_upper).
CATEGORIES = [
    "Yemekler", "Hayvanlar", "Filmler", "Teknoloji", "Spor",
    "Şehirler", "Meslekler", "Müzik", "Doğa", "Eşyalar",
]

# Mistral Agent (card generator). The agent id/version are not secret; the API
# key lives in secrets.py. The agent takes one Turkish category word and returns
# JSON: { "cards": [ { "main_word": str, "taboo_words": [str, ...] }, ... ] }.
API_URL = "https://api.mistral.ai/v1/conversations"
AGENT_ID = "ag_019e98852d1372c099cc8ff7a3c428fe"
AGENT_VERSION = 2

# Persisted card library, on the writable internal flash root (the read-only
# /system app folder shown in USB disk mode can't be written at runtime).
# Pull it off the device with tools/pull_cards.sh.
CACHE_FILE = "/cards.json"


def team_name(i):
    return "TEAM A" if i == 0 else "TEAM B"


def turn_label():
    return "%d:%02d" % (TURN_SECONDS // 60, TURN_SECONDS % 60)


# ---- debug logging -------------------------------------------------------
# With DEBUG on, the app prints to the USB serial REPL. Watch it with e.g.
#   screen /dev/cu.usbmodem1101 115200      (Ctrl-A K to quit)
#   mpremote connect /dev/cu.usbmodem1101 repl
# Open the Taboo app and you'll see lines like "[taboo] POST ... / HTTP 200".
DEBUG = True


def log(*args):
    if DEBUG:
        print("[taboo]", *args)
