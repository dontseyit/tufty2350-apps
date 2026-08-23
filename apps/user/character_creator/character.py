# The character being built, and the rows the part list offers.
#
# Two axes, because the art has two: an option (which hairstyle, which hat) and
# a tint (which colour that piece comes in). Skin, eyes and the room have only
# the first - for them the option axis IS the colour axis - so a shade row only
# appears under a part that is actually wearing something.
#
# Nothing here is saved. Leaving the app forgets the face, which is the point:
# it is a booth, not a wardrobe.

import random

import parts

SKIN, EYES, HAIR, FACE, HEAD, OUTFIT, ROOM = range(7)
LABEL = ("SKIN", "EYES", "HAIR", "FACE", "HAT", "OUTFIT", "ROOM")
ORDER = (SKIN, EYES, HAIR, FACE, HEAD, OUTFIT, ROOM)

# Parts whose options are drawn from a family table: index 0 is always "None",
# and every other entry carries its own count of tints.
TABLE = {HAIR: parts.HAIR, FACE: parts.FACE, HEAD: parts.HEAD,
         OUTFIT: parts.OUTFIT}
# Parts a shade row can appear under.
TINTED = (HAIR, FACE, HEAD, OUTFIT)
# Parts whose value is a colour rather than a name.
COLOUR_ONLY = {SKIN: parts.SKIN_SWATCH, EYES: parts.EYE_SWATCH}

# The character the booth opens on: plainly dressed, so the first press on any
# row visibly changes something.
OPENING = (2, 3, 1, 0, 0, 4, 0)


def option_count(part):
    if part in TABLE:
        return len(TABLE[part])
    if part in COLOUR_ONLY:
        return len(COLOUR_ONLY[part])
    return len(parts.ROOM)


def tint_count(part, option):
    return TABLE[part][option][1] if part in TABLE else 0


def name(part, option):
    """The value's name, or None when the value is a colour."""
    if part in TABLE:
        return TABLE[part][option][0]
    if part == ROOM:
        return parts.ROOM[option][0]
    return None


def swatch(part, option, tint):
    """The colour a row shows instead of a name, or None."""
    if part in COLOUR_ONLY:
        return COLOUR_ONLY[part][option]
    if part in TABLE:
        shades = TABLE[part][option][2]
        return shades[tint] if shades else None
    return parts.ROOM[option][1] if part == ROOM else None


class Character:
    def __init__(self):
        self.option = list(OPENING)
        self.tint = [0] * len(ORDER)
        self.cursor = 0

    def stops(self):
        """Everywhere the cursor can rest, top to bottom: (part, is_shade).

        The panel always shows the same six rows; a row whose part is wearing
        something has a second stop on its colour. So the layout never jumps
        under you, and the cursor never lands on a control with nothing to do."""
        out = []
        for part in ORDER:
            out.append((part, False))
            if part in TINTED and self.option[part]:
                out.append((part, True))
        return out

    @property
    def stop(self):
        return self.stops()[self.cursor]

    def move(self, step):
        self.cursor = (self.cursor + step) % len(self.stops())

    def span(self):
        """How many values the selected stop can take - what the try-on row walks."""
        part, shade = self.stop
        return tint_count(part, self.option[part]) if shade else option_count(part)

    def index(self):
        part, shade = self.stop
        return self.tint[part] if shade else self.option[part]

    def at(self, offset):
        """The value `offset` steps along the selected stop, wrapped."""
        return (self.index() + offset) % self.span()

    def change(self, step):
        part, shade = self.stop
        if shade:
            self.tint[part] = self.at(step)
        else:
            self.option[part] = self.at(step)
            self._clamp_tint(part)

    def shuffle(self):
        """Reroll the character - but not the room. The room is where you are,
        not who you are, and re-rolling it makes the whole screen flinch."""
        for part in ORDER:
            if part == ROOM:
                continue
            self.option[part] = random.randrange(option_count(part))
            self._clamp_tint(part)
            tints = tint_count(part, self.option[part])
            self.tint[part] = random.randrange(tints) if tints else 0
        self.cursor = min(self.cursor, len(self.stops()) - 1)

    def _clamp_tint(self, part):
        """Families come in different numbers of shades; keep the same shade
        where the new family has one, so cycling hair does not reset its colour."""
        tints = tint_count(part, self.option[part])
        self.tint[part] = min(self.tint[part], tints - 1) if tints else 0
