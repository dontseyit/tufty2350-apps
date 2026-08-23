# The gallery: characters you hung on the wall, and the only thing this app
# remembers.
#
# A character is fourteen small integers - an option and a shade per part - so
# ten of them is about a kilobyte of JSON. That goes to the badge's internal
# flash through badgeware State, because the app's own folder is the USB drive
# and is read-only while the app is running. It survives a reboot; it is not a
# file you can copy off over USB.
#
# Each hung character is also composed once into its own 16x32 canvas. Drawing
# ten of them live would mean loading ten characters' worth of hair, hat and
# outfit sheets every frame, and only one family of each is ever resident - so
# they are painted once, one per frame, and blitted thereafter.

import character as ch
import parts
from badgeware import State

KEY = "character_creator"
SLOTS = parts.GALLERY_SLOTS


class Gallery:
    def __init__(self):
        self.slots = [None] * SLOTS
        self.cursor = 0
        self._picture = [None] * SLOTS      # composed thumbnails, or None
        self._restore()

    # ---- what is on the wall ----------------------------------------------
    def filled(self, i=None):
        return self.slots[self.cursor if i is None else i] is not None

    def count(self):
        return sum(1 for s in self.slots if s is not None)

    def move(self, step):
        self.cursor = (self.cursor + step) % SLOTS

    def hang(self, char):
        """Put the character being built into the empty frame under the cursor."""
        self.slots[self.cursor] = list(char.option) + list(char.tint)
        self._picture[self.cursor] = None
        self._persist()

    def remove(self):
        self.slots[self.cursor] = None
        self._picture[self.cursor] = None
        self._persist()

    def wear(self, char):
        """Take the character under the cursor down off the wall and put it on."""
        saved = self.slots[self.cursor]
        if saved is None:
            return False
        n = len(ch.ORDER)
        for part in ch.ORDER:
            char.option[part] = min(saved[part], ch.option_count(part) - 1)
            tints = ch.tint_count(part, char.option[part])
            char.tint[part] = min(saved[n + part], tints - 1) if tints else 0
        char.cursor = 0
        return True

    # ---- the pictures ------------------------------------------------------
    def picture(self, i):
        return self._picture[i]

    def stale(self):
        """The first hung character with no picture painted yet, or None. The
        gallery paints one per frame, so walking in never blocks."""
        for i, saved in enumerate(self.slots):
            if saved is not None and self._picture[i] is None:
                return i
        return None

    def put_picture(self, i, img):
        self._picture[i] = img

    def worn(self, i):
        """(options, shades) of a hung character, for painting its picture."""
        saved = self.slots[i]
        n = len(ch.ORDER)
        return saved[:n], saved[n:]

    # ---- flash -------------------------------------------------------------
    def _persist(self):
        State.save(KEY, {"gallery": self.slots})

    def _restore(self):
        saved = {}
        if not State.load(KEY, saved):
            return
        hung = saved.get("gallery")
        if not isinstance(hung, list):
            return
        n = len(ch.ORDER)
        for i, entry in enumerate(hung[:SLOTS]):
            # Anything the flash hands back is checked before it is trusted -
            # a half-written file or an older build's layout must not crash the
            # app on launch, and the option counts can change under it.
            if not isinstance(entry, list) or len(entry) != n * 2:
                continue
            try:
                nums = [int(v) for v in entry]
            except (TypeError, ValueError):
                continue
            for part in ch.ORDER:
                nums[part] = min(max(nums[part], 0), ch.option_count(part) - 1)
                tints = ch.tint_count(part, nums[part])
                nums[n + part] = min(max(nums[n + part], 0), max(tints - 1, 0))
            self.slots[i] = nums
