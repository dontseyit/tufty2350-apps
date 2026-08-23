# Sprite loading, and the one place that knows how the baked sheets are cut.
#
# Every layer is one cell of a sheet laid out (variant, pose): column = the
# skin/shade variant, row = standing or mid-breath. So a whole character is six
# blits at a single position, whatever it is wearing.
#
# What stays loaded does not grow with how much of the pack is on offer: skin,
# eyes, the four catalogue sheets and the chrome are always in; the hair, face,
# hat and outfit FAMILIES arrive one at a time as they are selected, and the
# one before is dropped. Choosing an outfit costs its own handful of shades,
# not all 33.

import gc

import character as ch
import parts

STAND, BREATH = 0, 1

FOLDER = {ch.HAIR: "hair", ch.FACE: "face", ch.HEAD: "head",
          ch.OUTFIT: "outfit"}

S = {}          # sheets that are always resident
_worn = {}      # part -> (option, Sheet) for the family currently selected


class Sheet:
    """A SpriteSheet that cuts each cell once and keeps it - the draw loop asks
    for the same handful of cells every frame.

    Cells come off the device sheet with .sprite(u, v); the desktop shim also
    answers to .cell(), which the badge does not."""

    def __init__(self, path, cols, rows):
        self._sheet = SpriteSheet(path, cols, rows)
        self.cols = cols
        self._cells = {}

    def cell(self, u, v=0):
        key = v * self.cols + u
        img = self._cells.get(key)
        if img is None:
            img = self._cells[key] = self._sheet.sprite(u, v)
        return img

    def flat(self, i):
        return self.cell(i % self.cols, i // self.cols)


GRID = {ch.HAIR: parts.HAIR_GRID, ch.FACE: parts.FACE_GRID,
        ch.HEAD: parts.HEAD_GRID, ch.OUTFIT: parts.OUTFIT_GRID}


def init():
    S["skin"] = Sheet("assets/skin.png", ch.option_count(ch.SKIN), 2)
    S["eyes"] = Sheet("assets/eyes.png", ch.option_count(ch.EYES), 2)
    # One thumbnail per option, which is what the line-up draws for the options
    # either side of yours.
    for part, grid in GRID.items():
        S["cat_" + FOLDER[part]] = Sheet(f"assets/cat_{FOLDER[part]}.png", *grid)
    S["rooms"] = Sheet("assets/rooms.png", 3, ch.option_count(ch.ROOM))
    S["glyphs"] = Sheet("assets/glyphs.png", 4, 1)
    for name in ("frame", "frame_small", "panel", "pill"):
        S[name] = image.load(f"assets/{name}.png")


def _family(part, option):
    """The sheet holding every shade of one hairstyle / hat / outfit."""
    worn = _worn.get(part)
    if worn is None or worn[0] != option:
        # Let go of the family we were wearing and reclaim it BEFORE loading the
        # next one, so holding A through 33 outfits never has two resident.
        worn = None
        _worn.pop(part, None)
        gc.collect()
        path = f"assets/{FOLDER[part]}/{option - 1:02d}.png"
        worn = (option, Sheet(path, ch.tint_count(part, option), 2))
        _worn[part] = worn
    return worn[1]


def layer(part, option, tint, pose):
    """One cell of a character layer, or None when nothing is worn."""
    if part == ch.SKIN:
        return S["skin"].cell(option, pose)
    if part == ch.EYES:
        return S["eyes"].cell(option, pose)
    if not option:
        return None
    return _family(part, option).cell(tint, pose)


def preview(part, option):
    """The catalogue cell for an option - its first shade, standing. This is
    what the line-up shows for options that are not the one being worn."""
    return S["cat_" + FOLDER[part]].flat(option) if option else None


def room(option, which):
    """which: 0 wallpaper, 1 floor, 2 baseboard."""
    return S["rooms"].cell(which, option)
