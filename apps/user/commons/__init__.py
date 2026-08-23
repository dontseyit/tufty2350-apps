# Commons - three residents sharing a room, each running the ALMA affect model.
#
# The alma app proved the engine on one character; the character creator gave
# that engine a body to wear.  This is the two of them in the same room: three
# people with different Big Five personalities, one shared clock, and a list of
# things one of them can do that everybody else has to live with.
#
# An event carries two payloads - what it does to the person it happened to, and
# what it does to everyone watching - and both are appraisal results in the OCC
# sense, exactly as alma's stimuli were.  Nobody reacts "because they are
# grumpy": they react to identical input and end up somewhere different because
# ALMA pulls each mood away from a different personality baseline.
#
#   SETUP     UP/DOWN pick a row   A/C change it   B new body   HOLD B begin
#   RUNNING   UP/DOWN pick an event      C make it happen (hold to repeat)
#             B who it happens to        HOLD B time scale
#             A next view                HOLD A start over
#
# Nothing is saved. Leaving the app ends the world.

APP_DIR = "/system/apps/user/commons"

import os
import sys

# Standalone bootstrap for finding app assets and importing app modules
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import config as cfg
import events
import render
import sprites
from world import World

# The whole design is authored for the Tufty's native 320x240; switch to hi-res.
#
# VSYNC for the same reason alma needs it: this repaints all 320x240 every frame
# with three moving figures, and without waiting for scan-out the panel shows
# part of one frame and part of the next.
badge.mode(HIRES | VSYNC)
render.init()

world = World()
sprites.dress_everyone(world.people)

ui = {
    "view": cfg.V_WORLD,
    "who": 0,       # whose turn it is to have something happen to them
    "event": 0,
    "row": 0,       # setup: which row of the selected resident's sheet
    "log": 0,
    "guide": 0,
}
setup = True

_last_ticks = badge.ticks

# Holding C keeps re-appraising the same event, and the cadence is measured in
# SIMULATED time - so a held button means the same rate of appraisals in the
# residents' world whatever the time scale.  It is also the only way to actually
# shift a mood: one emotion is gone in a minute and barely dents a two-minute
# mood change, whereas a run of them keeps the virtual emotion center alive long
# enough for the pull and then the push phase to bite.
REPEAT_DELAY_SIM_MS = 1500
REPEAT_EVERY_SIM_MS = 2500
_repeat_at = None

# A and B each carry a second, rarer action.  The hold fires the moment it
# qualifies rather than on release - waiting for the release to find out whether
# it was a tap makes the badge feel unresponsive - and the release is swallowed.
HOLD_MS = 450
_hold = {}


def _action(button):
    """'tap', 'hold' or None, for a button that does two things."""
    now = badge.ticks
    if badge.pressed(button):
        _hold[button] = [now, False]
        return None
    state = _hold.get(button)
    if state is None:
        return None
    if badge.held(button):
        if not state[1] and now - state[0] >= HOLD_MS:
            state[1] = True
            return "hold"
        return None
    spent = state[1]
    del _hold[button]
    return None if spent else "tap"


# ---- setup -----------------------------------------------------------------
def _begin():
    """Lock the personalities in and start the clock."""
    global setup
    setup = False
    world.reset_clock()
    # Everyone is a pair of canvases by now; the wardrobe is dead weight until
    # somebody rolls a new world.
    sprites.close_wardrobe()
    cfg.log("world begins", [p.name for p in world.people])


def _new_world():
    global setup, ui
    sprites.open_wardrobe()
    world.roll()
    sprites.dress_everyone(world.people)
    ui["who"] = ui["row"] = ui["log"] = ui["guide"] = 0
    ui["view"] = cfg.V_WORLD
    setup = True


def _setup_move(step):
    """One cursor over three sheets: falling off the bottom of one resident's
    rows lands on the top of the next, so the whole cast is one list."""
    stop = (ui["who"] * render.SETUP_ROWS + ui["row"] + step) \
        % (cfg.SLOTS * render.SETUP_ROWS)
    ui["who"], ui["row"] = divmod(stop, render.SETUP_ROWS)


def _setup_change(step):
    who = world.people[ui["who"]]
    if ui["row"] == 0:
        who.cycle_archetype(step)
    else:
        who.nudge(cfg.TRAITS[ui["row"] - 1], step)


def _setup_input():
    if badge.pressed(BUTTON_UP):
        _setup_move(-1)
    if badge.pressed(BUTTON_DOWN):
        _setup_move(1)
    if badge.pressed(BUTTON_A):
        _setup_change(-1)
    if badge.pressed(BUTTON_C):
        _setup_change(1)

    action = _action(BUTTON_B)
    if action == "hold":
        _begin()
    elif action == "tap":
        world.reroll(ui["who"])
        sprites.dress(world.people[ui["who"]])


# ---- running ---------------------------------------------------------------
def _fire(now):
    world.fire(ui["who"], ui["event"], now)


def _scroll(key, limit, step):
    ui[key] = min(max(ui[key] + step, 0), limit)


def _run_input(now):
    global _repeat_at
    view = ui["view"]
    firing = view in cfg.FIRING_VIEWS

    action = _action(BUTTON_A)
    if action == "hold":
        _new_world()
        return
    if action == "tap":
        ui["view"] = (ui["view"] + 1) % len(cfg.VIEW_NAMES)

    action = _action(BUTTON_B)
    if action == "hold":
        world.cycle_speed()
    elif action == "tap":
        ui["who"] = (ui["who"] + 1) % cfg.SLOTS

    if badge.pressed(BUTTON_C):
        if firing:
            _fire(now)
            _repeat_at = world.sim_ms + REPEAT_DELAY_SIM_MS
        elif view == cfg.V_LOG:
            world.toggle_auto()
        else:
            ui["guide"] = 0
    elif firing and badge.held(BUTTON_C) and _repeat_at is not None \
            and world.sim_ms >= _repeat_at:
        _fire(now)
        _repeat_at = world.sim_ms + REPEAT_EVERY_SIM_MS
    elif not badge.held(BUTTON_C):
        _repeat_at = None

    step = -1 if badge.pressed(BUTTON_UP) else 1 if badge.pressed(BUTTON_DOWN) \
        else 0
    if step:
        if firing:
            ui["event"] = (ui["event"] + step) % len(events.EVENTS)
        elif view == cfg.V_LOG:
            _scroll("log", render.log_max_scroll(world), step)
        else:
            _scroll("guide", render.guide_max_scroll(), step)


# ---- the loop --------------------------------------------------------------
def _advance(now):
    """Step the world by however much simulated time this frame is worth."""
    global _last_ticks
    real = now - _last_ticks
    _last_ticks = now
    if real <= 0:
        return
    if real > cfg.MAX_FRAME_MS:
        real = cfg.MAX_FRAME_MS
    world.update(real * world.speed(), now)


def update():
    global _last_ticks
    now = badge.ticks
    if setup:
        _setup_input()
        _last_ticks = now          # the clock does not run until it begins
        render.draw_setup(world, ui, now)
        return
    _run_input(now)
    if setup:                      # HOLD A rolled a new world mid-frame
        render.draw_setup(world, ui, now)
        return
    _advance(now)
    # The breathing runs off the REAL clock, not the simulated one, so
    # fast-forwarding the moods does not turn three people into a strobe.
    render.draw(world, ui, now)


run(update)
