# Layout metrics and colours for the Character Creator.
#
# The screen is one room seen face on: wallpaper down to a baseboard, then
# floor. The character hangs on the wall full length in a frame, the part list
# leans on the wall beside it, and the line-up stands on the floor below.
#
#      0        36        116  152                          312  320
#    0 +---------------------------------------------------------------+
#      |  wallpaper                                                     |
#    2 |    +---------------+    +----------------------------+  6      |
#      |    |   the hero,   |    | part list, one row selected|         |
#      |    |  full length, |    |                            |         |
#      |    |   breathing   |    +----------------------------+  135    |
#  146 |    +---------------+                                           |
#  148 | ------------------- baseboard --------------------------------- |
#      |  floor                                                         |
#  148 |         A    A    A    A    A   <- the line-up, you in the      |
#  212 | ---- feet ------------------------- middle ------------------- |
#  216 | -------------------------------------------------------------- |
#      |  hint bar                                                      |
#  240 +---------------------------------------------------------------+
#
# Device globals (screen, color, ...) are never touched at import time, so this
# module loads off-device; render.init() bakes the pens once badge.mode is set.

import parts

DEBUG = False


def log(*args):
    if DEBUG:
        print("[creator]", *args)


# ---- the room --------------------------------------------------------------
TILE = 16
FLOOR_TOP = 164            # where the wallpaper gives way to the floor
BOARD_Y = FLOOR_TOP - TILE  # baseboard tiles are bare but for the foot that
                            # lands on that line
BAR_TOP = 216              # the hint bar closes the screen

# ---- the hero --------------------------------------------------------------
# The character, full length, in one of the pack's picture frames. Full length
# because half of what you can choose - the outfit, and two of the hats - does
# not exist above the neck.
HERO_W, HERO_H = parts.HERO
FRAME_W, FRAME_H = parts.FRAME_WH
MAT_X, MAT_Y = parts.MAT   # where the character stands, relative to the frame
MAT_BOX = parts.MAT_BOX    # the frame's whole opening

# ---- the part list ---------------------------------------------------------
# Six rows, always the same six, however much the character is wearing. Each is
# a fixed grid: what the part is, what colour it is, what it is called, and how
# far along the list you are.
PANEL_X, PANEL_Y = 152, 6
PANEL_W, PANEL_H = parts.PANEL_WH
ROW_H = 17
ROW_TOP = PANEL_Y + 6
PILL_X = PANEL_X + 2
LABEL_X = PANEL_X + 8
SWATCH_X = PANEL_X + 48    # clear of the longest label ("OUTFIT")
NAME_X = PANEL_X + 68
COUNT_R = PANEL_X + PANEL_W - 12   # counts are right-aligned to here
SWATCH_W, SWATCH_H = 14, 10

FRAME_X = (PANEL_X - FRAME_W) // 2      # centred in the wall beside the panel
FRAME_Y = 2

# ---- the line-up -----------------------------------------------------------
# Five of the character standing on the floor, you in the middle, each wearing
# a different value of the row being edited.
FIGURE_W, FIGURE_H = parts.FIGURE
TRY_SCALE = 2
TRY_W, TRY_H = FIGURE_W * TRY_SCALE, FIGURE_H * TRY_SCALE
TRY_PITCH = 52             # centre to centre
TRY_SPAN = 2               # this many either side of the current option
TRY_FEET = 212             # the floor line they stand on
ROOM_W = ROOM_H = 44       # the ROOM row shows rooms, not people
ARROW_Y = TRY_FEET - 46
ARROW_INSET = 6

# ---- the gallery -----------------------------------------------------------
# A second wall, hung with the characters you saved. Two rows of five picture
# frames; the room behind is whichever one you were standing in.
HUNG_W, HUNG_H = parts.HUNG
HUNG_FRAME_W, HUNG_FRAME_H = parts.HUNG_FRAME_WH
HUNG_MAT_X, HUNG_MAT_Y = parts.HUNG_MAT
HUNG_MAT_BOX = parts.HUNG_MAT_BOX
SLOTS = parts.GALLERY_SLOTS
GAL_COLS = 5
GAL_X, GAL_Y = 8, 16
GAL_GAP_X, GAL_GAP_Y = 16, 8
GAL_FLOOR_TOP = 200        # the gallery wall runs lower than the dressing room's

# ---- idle ------------------------------------------------------------------
# The layer sheets hold two poses: standing, and the frame a third of the way
# into the pack's walk cycle, which seen from the front lifts the body a pixel
# and leaves the legs alone. Alternated slowly that reads as a breath. Only the
# hero breathes - five people doing it in unison reads as a machine.
BREATH_MS = 2400           # one full breath
BREATH_UP_MS = 800         # of which this much is the top of it
BUMP_MS = 130              # the frame jogs on its nail when a part changes
BUMP_PX = 3
RGB = dict(parts.PALETTE)
