# Character Creator - build a character out of the LimeZu piece art.
#
# One room, one framed character, one part list. Every part has an option axis
# (which hairstyle, which outfit) and, where the art has one, a shade axis; the
# five standing on the floor wear the options either side of yours so you can
# see a choice before you make it.
#
#   UP / DOWN  choose a part
#   A / C      previous / next value for it, held to run a long list
#   B          shuffle the character, held to open the gallery
#
# The gallery is a second wall hung with the characters you saved, and the only
# thing this app remembers. What you are building is not kept: leave mid-outfit
# and you come back to a fresh character.

APP_DIR = "/system/apps/user/character_creator"

import os
import sys

# Standalone bootstrap for finding app assets and importing app modules
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import config as cfg
import render
from character import Character
from gallery import Gallery

# The whole design is authored for the Tufty's native 320x240; switch to hi-res.
badge.mode(HIRES)
render.init()

char = Character()
gal = Gallery()
in_gallery = False
_bumped_at = -cfg.BUMP_MS       # when a value last changed, for the frame's nudge

# Holding A or C runs through a long list (33 outfits, 29 hairstyles) without
# thirty presses. The first repeat waits long enough that a single press is
# never mistaken for a hold.
REPEAT_DELAY_MS = 420
REPEAT_EVERY_MS = 110
_repeat_at = None       # armed by a press, so a button held at launch never runs

# B is the only spare button, so it carries two actions. The hold fires the
# moment it qualifies rather than on release - waiting for the release to find
# out whether it was a tap makes the badge feel unresponsive - and the release
# that follows is then swallowed.
HOLD_MS = 450
_b_at = None
_b_spent = False


def _b_action():
    """'tap', 'hold', or None."""
    global _b_at, _b_spent
    now = badge.ticks
    if badge.pressed(BUTTON_B):
        _b_at, _b_spent = now, False
    elif _b_at is not None and badge.held(BUTTON_B):
        if not _b_spent and now - _b_at >= HOLD_MS:
            _b_spent = True
            return "hold"
    elif _b_at is not None:
        spent, _b_at = _b_spent, None
        if not spent:
            return "tap"
    return None


def _room_input(now):
    global _repeat_at, _bumped_at, in_gallery
    if badge.pressed(BUTTON_UP):
        char.move(-1)
    if badge.pressed(BUTTON_DOWN):
        char.move(1)

    action = _b_action()
    if action == "hold":
        in_gallery = True
        return
    if action == "tap":
        char.shuffle()
        _bumped_at = now
        cfg.log("shuffled", char.option, char.tint)

    step = -1 if badge.pressed(BUTTON_A) else 1 if badge.pressed(BUTTON_C) else 0
    if step:
        _repeat_at = now + REPEAT_DELAY_MS
    elif _repeat_at is None:
        pass
    elif not (badge.held(BUTTON_A) or badge.held(BUTTON_C)):
        _repeat_at = None
    elif now >= _repeat_at:
        step = -1 if badge.held(BUTTON_A) else 1
        _repeat_at = now + REPEAT_EVERY_MS
    if step:
        char.change(step)
        _bumped_at = now


def _gallery_input(now):
    global in_gallery, _bumped_at
    if badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN):
        in_gallery = False
        return
    if badge.pressed(BUTTON_A):
        gal.move(-1)
    if badge.pressed(BUTTON_C):
        gal.move(1)

    action = _b_action()
    if action == "hold":
        if gal.filled():
            gal.remove()
            cfg.log("removed", gal.cursor)
    elif action == "tap":
        if gal.filled():
            gal.wear(char)
            in_gallery = False
            _bumped_at = now
        else:
            gal.hang(char)
            cfg.log("hung", gal.cursor)


def update():
    now = badge.ticks
    if in_gallery:
        _gallery_input(now)
    else:
        _room_input(now)
    # the mode can flip mid-frame; draw whichever we ended up in
    if in_gallery:
        render.draw_gallery(char, gal)
    else:
        render.draw(char, now, _bumped_at)


run(update)
