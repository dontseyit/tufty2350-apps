APP_DIR = "/system/apps/user/taboo"

import sys
import os

# Standalone bootstrap for finding app assets (and cards.json lives here too)
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

# Credentials (wi-fi + Mistral key) come from /system/secrets.py - the file you
# can edit directly on the badge's USB drive. Put /system on the import path and
# drop any stale cached copy so agent.py's lazy `import secrets` reads THAT file,
# not /secrets.py on the internal flash.
sys.path.insert(0, "/system")
sys.modules.pop("secrets", None)

import config as cfg
import render
import cards
import agent
from game import Game
from badgeware import State

# The design is authored for the Tufty's native 320x240; switch to hi-res.
badge.mode(HIRES)

game = Game()
cards.load_cache()

# badgeware State persists a small dict to the writable internal flash (not the
# read-only /system app folder), keyed by name - like snarky_sciuridae / hydrate.
# It carries two things: the set of already-played cards and any interrupted match.
_saved = {}
State.load("taboo", _saved)
# Restore the used-card set ALWAYS (even for a brand-new match) so cards never
# repeat across boots while online; the cache is only recycled when offline.
cards.restore_used(_saved.get("used", {}))
_resume = bool(_saved.get("in_progress"))
if _resume:
    cfg.log("resuming saved match", _saved.get("scores"))
    game.restore(_saved)

# wi-fi / fetch bookkeeping owned by the loop (kept out of the pure game/cards)
_connect_start = 0
_load_armed = False


def _begin_connecting(now):
    global _connect_start
    _connect_start = now
    game.state = cfg.CONNECTING


def _finish_startup():
    # after the wi-fi attempt: resume the saved match, else go to setup
    game.state = cfg.HANDOFF if _resume else cfg.SETUP


def _persist():
    # always snapshot which cards were used (so they stay used across boots), plus
    # the in-progress match so it can resume later
    st = game.save_state()
    st["used"] = cards.snapshot_used()
    State.save("taboo", st)


# Only bother with wi-fi if we actually could go online (creds + API key).
if agent.online_possible():
    cfg.log("boot: have creds + key, connecting wi-fi")
    _begin_connecting(badge.ticks)
else:
    cfg.log("boot: offline (no creds or key)")
    game.online = False
    _finish_startup()


# hardware button -> logical name (A/B/C face row, UP/DOWN side buttons)
_BUTTONS = (
    (BUTTON_A, "A"),
    (BUTTON_B, "B"),
    (BUTTON_C, "C"),
    (BUTTON_UP, "UP"),
    (BUTTON_DOWN, "DOWN"),
)


def _first_press():
    for const, name in _BUTTONS:
        if badge.pressed(const):
            return name
    return None


def _handle_input(now):
    global _load_armed
    b = _first_press()
    if b is None:
        return
    st = game.state

    if st == cfg.CONNECTING:
        # impatient? skip straight to play (offline)
        game.online = False
        _finish_startup()

    elif st == cfg.SETUP:
        if b == "UP":
            game.deck_idx = (game.deck_idx - 1) % len(cfg.CATEGORIES)
        elif b == "DOWN":
            game.deck_idx = (game.deck_idx + 1) % len(cfg.CATEGORIES)
        elif b == "B":
            game.start_game()
            _persist()

    elif st == cfg.HANDOFF:
        if b == "B":
            game.request_turn(now)      # may enter LOADING (fetch happens in _tick)
            _load_armed = False
        elif b == "UP":
            game.to_setup()

    elif st == cfg.LOADING:
        pass  # locked while the agent is queried

    elif st == cfg.COUNTDOWN:
        pass  # locked while it ticks

    elif st == cfg.TURN:
        if b == "A":
            game.resolve("taboo", now)
        elif b == "B":
            game.resolve("skip", now)
        elif b == "C":
            game.resolve("got", now)
        elif b == "UP":
            game.undo()
        elif b == "DOWN":
            game.end_turn("ended")

    elif st == cfg.SUMMARY:
        if b == "B":
            game.after_summary()
            _persist()        # checkpoint after each turn so a crash can resume
        elif b == "UP":
            game.to_setup()

    elif st == cfg.WIN:
        if b == "B":
            game.to_setup()

    elif st == cfg.NOCARDS:
        if b == "B":
            game.to_setup()
        elif b == "UP" and agent.online_possible():
            _begin_connecting(now)


def _tick(now):
    global _load_armed
    st = game.state

    if st == cfg.CONNECTING:
        if agent.connect():
            cfg.log("wi-fi connected")
            game.online = True
            _finish_startup()
        else:
            agent.tick()
            if now - _connect_start >= cfg.WIFI_TIMEOUT_MS:
                cfg.log("wi-fi timeout -> offline")
                game.online = False
                _finish_startup()

    elif st == cfg.LOADING:
        # render the loading screen for one frame, THEN do the blocking fetch,
        # so the player sees feedback during the (multi-second) network call
        if _load_armed:
            # re-check the link first - wi-fi may have dropped since startup, so
            # don't attempt a doomed fetch (and refresh the offline indicator)
            game.online = agent.connect()
            cfg.log("loading: link=", game.online, "category=", game.category)
            if game.online:
                cards.ensure_supply(game.category, cfg.MIN_CARDS)
            # stamp the countdown from a FRESH clock read taken AFTER the fetch,
            # or the multi-second fetch would be counted against the 3-2-1 timer
            game.finish_loading(badge.ticks)
            _persist()
            _load_armed = False
        else:
            _load_armed = True

    elif st == cfg.REFILL:
        # mid-turn top-up: same render-one-frame-then-block pattern as LOADING,
        # but we resume the (paused) turn instead of starting a countdown
        if _load_armed:
            game.online = agent.connect()
            cfg.log("refill: link=", game.online, "category=", game.category)
            if game.online:
                cards.ensure_supply(game.category, cfg.MIN_CARDS)
            # fresh clock read AFTER the fetch so resume_turn can discount the
            # paused span and the turn timer continues where it left off
            game.resume_turn(badge.ticks)
            _persist()
            _load_armed = False
        else:
            _load_armed = True

    elif st == cfg.COUNTDOWN and game.countdown_done(now):
        game.begin_turn(now)

    elif st == cfg.TURN and game.time_up(now):
        game.end_turn("time")


def update():
    now = badge.ticks
    _handle_input(now)
    _tick(now)
    render.draw(game, now)


def on_exit():
    # the launcher calls this when the app exits - persist so the match resumes
    _persist()


run(update)
