# ALMA - a real-time simulation of Patrick Gebhard's layered model of affect
# (DFKI, AAMAS'05) driving an idle game character.
#
# The character has a Big Five personality, which the Mehrabian regression
# turns into a default mood in PAD space. External stimuli are appraised into
# OCC emotions, those emotions form a virtual emotion center, and ALMA's pull
# and push function walks the mood towards (then past) that center before it
# drifts back to the personality baseline.
#
#   UP / DOWN  choose an external stimulus   (or adjust a trait)
#   C          apply it, hold to repeat       (or re-seed the mood)
#   A          next view
#   B          time scale                    (or pick a trait / parameter)

APP_DIR = "/system/apps/user/alma"

import os
import sys

# Standalone bootstrap for finding app assets and importing app modules
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import affect
import config as cfg
import render
import stimuli
from badgeware import State

# The whole design is authored for the Tufty's native 320x240; switch to hi-res.
#
# VSYNC matters here. Unlike the other user apps - which paint a mostly static
# screen and only really change on a button press - this one repaints all
# 320x240 every frame with large moving shapes. Without waiting for the
# display's scan-out the panel shows part of one frame and part of the next,
# which reads as a flashing background and a ghost trailing the character.
# The factory apps that animate a full screen (gallery, bee_amazed) do the same.
badge.mode(HIRES | VSYNC)
render.init()

model = affect.Affect()

# UI state. `trail` is the PAD map's breadcrumb of recent mood positions.
ui = {
    "view": cfg.V_CHARACTER,
    "stim": 0,
    "trait": 0,
    "param": 0,
    "guide": 0,
    "scale": cfg.DEFAULT_SCALE_INDEX,
    "trail": [],
}

# ---- persistence -----------------------------------------------------------
# Defined before the boot block below, which calls _restore_dynamics: this
# module is executed top to bottom at launch, so a definition further down is
# not in scope yet.
def _restore_dynamics(saved):
    """Put back tuned dynamics values, snapped to their ladder."""
    if not isinstance(saved, dict):
        return
    for name, label, unit, ladder, paper in cfg.DYNAMICS:
        v = saved.get(name)
        if v is not None:
            cfg.set_param(name, ladder[cfg.nearest_index(ladder, v)])


def _persist():
    st = model.save_state()
    st["dynamics"] = {e[0]: cfg.param_value(e[0]) for e in cfg.DYNAMICS}
    st["view"] = ui["view"]
    st["stim"] = ui["stim"]
    st["scale"] = ui["scale"]
    State.save("alma", st)


# badgeware State persists to the writable internal flash (the /system app
# folder is read-only at runtime), so a personality survives a reboot.
_saved = {}
if State.load("alma", _saved):
    model.restore(_saved)
    ui["view"] = _saved.get("view", ui["view"]) % len(cfg.VIEW_NAMES)
    ui["stim"] = _saved.get("stim", 0) % len(stimuli.STIMULI)
    ui["scale"] = _saved.get("scale", ui["scale"]) % len(cfg.TIME_SCALES)
    _restore_dynamics(_saved.get("dynamics"))
    cfg.log("restored", model.personality)

_last_ticks = badge.ticks
_trail_accum = 0.0

# A real frame longer than this is treated as a stall (app switch, a blocking
# call) rather than elapsed time, so the model never jumps on a hiccup.
MAX_FRAME_MS = 200

# Holding C keeps re-appraising the same stimulus. That is how you actually
# move a mood in ALMA: one emotion is gone in twenty seconds and barely dents a
# ten-minute mood change, whereas a run of them keeps the virtual emotion
# center alive long enough for the pull and then the push phase to bite.
#
# The cadence is measured in SIMULATED time, so a held button means the same
# rate of appraisals in the character's world whatever the time scale - at real
# time it is one every few seconds, and fast-forwarding does not thin it out
# into a flicker between a fresh emotion and an almost-decayed one.
REPEAT_DELAY_SIM_MS = 1500
REPEAT_EVERY_SIM_MS = 2500
_sim_ms = 0.0
_repeat_at = 0.0


# ---- input -----------------------------------------------------------------
def _apply_stimulus():
    """Appraisal result in: every emotion this stimulus elicits, at once."""
    label, pairs = stimuli.STIMULI[ui["stim"]]
    for name, intensity in pairs:
        model.elicit(name, intensity)
    cfg.log("stimulus", label, "->", pairs)


def _nudge_trait(direction):
    trait = cfg.TRAITS[ui["trait"]]
    model.set_trait(trait, model.personality[trait]
                    + direction * cfg.TRAIT_STEP)


def _nudge_param(direction):
    """Step one dynamics parameter along its ladder. The model reads the new
    value on its next step - no restart, and active emotions re-scale mid-decay."""
    name, label, unit, ladder, paper = cfg.DYNAMICS[ui["param"]]
    i = cfg.nearest_index(ladder, cfg.param_value(name)) + direction
    if 0 <= i < len(ladder):
        cfg.set_param(name, ladder[i])


def _restore_paper_values():
    for name, label, unit, ladder, paper in cfg.DYNAMICS:
        cfg.set_param(name, paper)
    cfg.log("restored the paper's dynamics")


def _scroll_guide(direction):
    top = ui["guide"] + direction
    limit = render.guide_max_scroll()
    ui["guide"] = 0 if top < 0 else (limit if top > limit else top)


def _handle_input():
    global _repeat_at
    view = ui["view"]
    stimulus_view = view in cfg.STIMULUS_VIEWS

    if badge.pressed(BUTTON_A):
        ui["view"] = (ui["view"] + 1) % len(cfg.VIEW_NAMES)
        _persist()

    if badge.pressed(BUTTON_B):
        if view == cfg.V_PERSONALITY:
            ui["trait"] = (ui["trait"] + 1) % len(cfg.TRAITS)
        elif view == cfg.V_DYNAMICS:
            ui["param"] = (ui["param"] + 1) % len(cfg.DYNAMICS)
        else:
            ui["scale"] = (ui["scale"] + 1) % len(cfg.TIME_SCALES)
            _persist()

    if badge.pressed(BUTTON_C):
        if view == cfg.V_PERSONALITY:
            # Re-seed: clear the emotions and drop the mood onto the baseline
            # the traits now imply. This doubles as the simulation's reset.
            model.reseed()
            ui["trail"] = []
            _persist()
        elif view == cfg.V_DYNAMICS:
            _restore_paper_values()
            _persist()
        elif view == cfg.V_GUIDE:
            ui["guide"] = 0
        else:
            _apply_stimulus()
            _repeat_at = _sim_ms + REPEAT_DELAY_SIM_MS
    elif (stimulus_view and badge.held(BUTTON_C)
            and _sim_ms >= _repeat_at):
        _apply_stimulus()
        _repeat_at = _sim_ms + REPEAT_EVERY_SIM_MS

    # UP/DOWN don't persist - a flash write per step would be wasteful, and
    # the view change, scale change, re-seed and on_exit all snapshot anyway.
    if badge.pressed(BUTTON_UP):
        if view == cfg.V_PERSONALITY:
            _nudge_trait(1)
        elif view == cfg.V_DYNAMICS:
            _nudge_param(1)
        elif view == cfg.V_GUIDE:
            _scroll_guide(-1)
        else:
            ui["stim"] = (ui["stim"] - 1) % len(stimuli.STIMULI)

    if badge.pressed(BUTTON_DOWN):
        if view == cfg.V_PERSONALITY:
            _nudge_trait(-1)
        elif view == cfg.V_DYNAMICS:
            _nudge_param(-1)
        elif view == cfg.V_GUIDE:
            _scroll_guide(1)
        else:
            ui["stim"] = (ui["stim"] + 1) % len(stimuli.STIMULI)


# ---- simulation ------------------------------------------------------------
def _advance(now):
    """Step the model by however much SIMULATED time this frame is worth."""
    global _last_ticks, _trail_accum, _sim_ms
    real = now - _last_ticks
    _last_ticks = now
    if real <= 0:
        return
    if real > MAX_FRAME_MS:
        real = MAX_FRAME_MS

    dt = real * cfg.TIME_SCALES[ui["scale"]]
    _sim_ms += dt
    model.update(dt)

    _trail_accum += dt
    if _trail_accum >= cfg.TRAIL_PERIOD_MS:
        _trail_accum = 0.0
        trail = ui["trail"]
        trail.append((model.mood[0], model.mood[1], model.mood[2]))
        if len(trail) > cfg.TRAIL_LEN:
            del trail[0]


def update():
    now = badge.ticks
    _handle_input()
    _advance(now)
    # The idle animation runs off the REAL clock, not the simulated one, so
    # fast-forwarding the mood doesn't turn the character into a strobe.
    render.draw(model, ui, now)


def on_exit():
    _persist()


run(update)
