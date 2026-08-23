# Loading the art, and turning a rolled look into two finished canvases.
#
# The character creator keeps one wardrobe family resident at a time and
# composites live, because you are changing your mind sixty times a second.
# Nobody here changes clothes: a resident is dressed ONCE into a standing canvas
# and a mid-breath canvas, and from then on drawing them is a single blit.  That
# is what makes three of them on screen cost the same as one, and it is why the
# whole wardrobe can be let go the moment the world starts.
#
# Cells come off a device sheet with .sprite(u, v).  The desktop shim also
# answers to .cell(), which the badge does not - so this file never calls it.

import gc

import config as cfg
import parts
import world

FW, FH = parts.FIGURE
STAND, BREATH = 0, 1
POSES = 2

S = {}          # the sheets that outlive a single dressing


def init():
    """The two sheets every resident draws from, and the room they stand in."""
    S["rooms"] = SpriteSheet("assets/rooms.png", 3, len(parts.ROOM))
    open_wardrobe()


def open_wardrobe():
    """Skin and eyes, which every resident needs and which are small enough to
    keep between dressings."""
    if "skin" not in S:
        S["skin"] = SpriteSheet("assets/skin.png", parts.SKIN, POSES)
        S["eyes"] = SpriteSheet("assets/eyes.png", parts.EYES, POSES)


def close_wardrobe():
    """Let the piece art go. Everyone is a pair of canvases by now, and nothing
    reloads a piece until a new world is rolled."""
    S.pop("skin", None)
    S.pop("eyes", None)
    gc.collect()


def room(which):
    """which: 0 wallpaper, 1 floor, 2 baseboard."""
    return S["rooms"].sprite(which, cfg.ROOM)


def _layer_sheet(layer, option):
    """The sheet holding every shade of one piece, or None when nothing is worn.

    Skin and eyes are one resident sheet each, indexed by option. The other four
    slots get a sheet per piece, loaded here and dropped by the caller - index 0
    is "None" and has no file, so piece n lives in (n-1).png.
    """
    if layer == world.SKIN:
        return S["skin"], option
    if layer == world.EYES:
        return S["eyes"], option
    if not option:
        return None, 0
    shades = world.PIECES[layer][option][1]
    return SpriteSheet("assets/%s/%02d.png" % (world.FOLDER[layer], option - 1),
                       shades, POSES), None


def dress(who):
    """Composite a resident into their two poses, then let the pieces go.

    One piece sheet is loaded, used for both poses, and dropped BEFORE the next
    one arrives, so dressing somebody in the 33rd outfit never costs more than
    dressing them in the first.
    """
    open_wardrobe()
    canvas = [image(FW, FH) for _ in range(POSES)]
    for layer in world.LAYER_ORDER:
        option, tint = who.look[layer]
        sheet, column = _layer_sheet(layer, option)
        if sheet is None:
            continue
        if column is None:
            column = tint
        for pose in range(POSES):
            canvas[pose].blit(sheet.sprite(column, pose), vec2(0, 0))
        if layer in world.FOLDER:
            sheet = None            # drop it before the next one is allocated
            gc.collect()
    who.pose = canvas


def dress_everyone(people):
    for who in people:
        dress(who)
