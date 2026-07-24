# Tour de France live dashboard - constants shared across the app.
# Pure CPython-safe module: no device globals, importable in tests.

# The LAN proxy that scrapes procyclingstats (which sits behind a Cloudflare
# JS challenge the badge can't pass) and serves the flattened JSON contract.
PROXY_URL = "http://192.168.0.n:8321/live.json"

POLL_MS = 10000          # how often the badge polls the proxy
HTTP_TIMEOUT = 5         # seconds; bounds the GET so a dead proxy can't hang the UI
WIFI_TIMEOUT_MS = 20000  # per-network wi-fi window before trying the next /
                         # offline (association + DHCP can take a while on a
                         # busy or just-rebooted AP; hard failures like
                         # "AP not found" cut the window short anyway)

# History persisted to the writable internal flash root (the /system app folder
# is read-only at runtime, like taboo's /cards.json).
HISTORY_FILE = "/tdf.json"
HISTORY_POSTS = 150      # merged ticker posts kept, newest first

# pages (cycled with A / C on the badge)
(RACE, TICKER, GC, POINTS, ROUTE) = range(5)
NPAGES = 5

# wi-fi states shared between __init__ and render
(WIFI_CONNECTING, WIFI_UP, WIFI_OFF) = range(3)

# Tour-yellow on dark theme, (r, g, b)
BG = (18, 18, 14)         # near-black
YELLOW = (255, 216, 0)    # maillot jaune
INK = (242, 240, 230)     # off-white text
DIM = (140, 138, 122)     # grey secondary text
GREEN = (70, 180, 80)     # sprints / fresh-data ok
RED = (224, 51, 43)       # KOM climbs / alerts

THEME = {
    "BG": BG, "YELLOW": YELLOW, "INK": INK,
    "DIM": DIM, "GREEN": GREEN, "RED": RED,
}

# freshness thresholds for the data-age dot (seconds)
AGE_OK_S = 20
AGE_WARN_S = 60

# ---- debug logging -------------------------------------------------------
# With DEBUG on, the app prints to the USB serial REPL. Watch it with e.g.
#   screen /dev/cu.usbmodem1101 115200      (Ctrl-A K to quit)
#   mpremote connect /dev/cu.usbmodem1101 repl
DEBUG = True


def log(*args):
    if DEBUG:
        print("[tdf]", *args)
