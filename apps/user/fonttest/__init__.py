# Font catalog - previews every font in /system/assets/fonts on the badge:
# .ppf "pixel perfect" bitmap fonts (fixed size) AND .af "Alright Fonts" vector
# fonts (scalable). Each row shows the font's name + a type/size tag (in a fixed
# label font) and a sample rendered IN that font - a km number + ticker words.
# Bitmaps draw at their baked size; vectors draw at a fixed preview size.
# UP/DOWN scroll, A jumps to the top.
APP_DIR = "/system/apps/user/fonttest"

import os
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES)
W, H = 320, 240

FONT_DIR = "/system/assets/fonts"
# bitmaps first, then vectors; each alphabetical (case-insensitive)
FONTS = sorted((f for f in os.listdir(FONT_DIR) if f.endswith((".ppf", ".af"))),
               key=lambda f: (f.endswith(".af"), f.lower()))

BG = color.rgb(18, 18, 14)
INK = color.rgb(242, 240, 230)
DIM = color.rgb(140, 138, 122)
YELLOW = color.rgb(255, 216, 0)

# Fixed label font so a font's name stays readable even when its own sample is
# illegible/tiny.
LABEL = pixel_font.load(FONT_DIR + "/absolute.ppf")

DIGITS = "148.2"
WORDS = " Van der Poel attacks"
SAMPLE = DIGITS + WORDS          # single-colour sample for vector fonts
VEC_PREVIEW = 20                 # px size vector (.af) fonts are drawn at

scroll = 0
_last = -1
_cache = {}


def _font(name):
    f = _cache.get(name)
    if f is None:
        path = FONT_DIR + "/" + name
        f = font.load(path) if name.endswith(".af") else pixel_font.load(path)
        _cache[name] = f
    return f


def _t(s, x, y, pen):
    screen.pen = pen
    screen.text(s, int(x), int(y))


def _rt(s, right, y, pen):
    _t(s, right - screen.measure_text(s)[0], y, pen)


def _draw_vector(f, y, size):
    """Preview an .af vector font in one colour via the PicoVector text API,
    guarded so an API mismatch just skips the sample instead of killing the
    catalog."""
    try:
        screen.font = f
        screen.pen = INK
        screen.antialias = image.X2
        tokens = text.tokenise(screen, SAMPLE, size=size)
        text.draw(screen, tokens, rect(6, y, W - 12, size + 6), size=size)
        screen.antialias = image.OFF
    except Exception:
        screen.antialias = image.OFF
        screen.font = LABEL
        _t("(vector preview unavailable)", 6, y, DIM)


def update():
    global scroll, _last
    if badge.pressed(BUTTON_UP) and scroll > 0:
        scroll -= 1
    elif badge.pressed(BUTTON_DOWN) and scroll < len(FONTS) - 1:
        scroll += 1
    elif badge.pressed(BUTTON_A):
        scroll = 0

    # only the visible window needs to be resident; drop the rest on a move
    if scroll != _last:
        _cache.clear()
        _last = scroll

    screen.pen = BG
    screen.clear()

    screen.font = LABEL
    lh = int(screen.measure_text("0")[1])
    _t("FONT CATALOG", 6, 4, YELLOW)
    _rt("%d/%d  A:top" % (scroll + 1, len(FONTS)), W - 6, 4, DIM)
    screen.pen = DIM
    screen.rectangle(0, 4 + lh + 2, W, 1)
    y = 4 + lh + 8

    i = scroll
    while i < len(FONTS) and y < H - 6:
        name = FONTS[i]
        vec = name.endswith(".af")
        f = _font(name)
        if vec:
            sh = VEC_PREVIEW
        else:
            screen.font = f
            sh = int(screen.measure_text("0")[1])
        if y + lh + sh > H - 2:
            break
        # label row: name + type/size tag, in the fixed label font
        screen.font = LABEL
        _t(name.rsplit(".", 1)[0].upper(), 6, y, DIM)
        _rt("VEC" if vec else "h%d" % sh, W - 6, y, DIM)
        y += lh + 1
        # the sample, in the font itself
        if vec:
            _draw_vector(f, y, sh)
        else:
            screen.font = f
            _t(DIGITS, 6, y, YELLOW)
            _t(WORDS, 6 + screen.measure_text(DIGITS)[0], y, INK)
        y += sh + 7
        i += 1


run(update)
