APP_DIR = "/system/apps/user/notes"

import os
import sys

# Standalone bootstrap for finding app assets / importing app modules
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

# ---------------------------------------------------------------------------
# Notes to leave behind. Edit this list - one string per note. "\n" forces a
# line break; otherwise text wraps to fit the screen automatically.
# HEADER is the little annunciator label above the message.
# ---------------------------------------------------------------------------
HEADER = "TELGRAF"
NOTES = [
    "Bakkala  gittim, döneceğim.",
]

# The dashboard is authored for the Tufty's native 320x240; switch to hi-res.
badge.mode(HIRES)
screen.antialias = image.X2

W, H = 320, 240

# ---- palette: warm amber CRT (espresso glass, phosphor amber, one red LED) --
BEZEL = color.rgb(14, 11, 8)          # molded plastic frame
GLASS = color.rgb(32, 21, 10)         # espresso CRT glass
FRAME = color.rgb(154, 106, 46)       # thin amber bezel-to-glass edge
RIVET = color.rgb(46, 34, 20)         # panel screws in the bezel
AMBER = color.rgb(255, 180, 60)       # phosphor text
AMBER_HI = color.rgb(255, 224, 166)   # hero highlight
AMBER_DIM = color.rgb(154, 106, 46)   # labels / secondary
GLOW = color.rgb(206, 126, 40)        # amber halo behind hero text (emissive)
SIGNAL = color.rgb(255, 90, 77)       # "message waiting" LED
SCAN = color.rgb(0, 0, 0, 70)         # CRT scanline

# ---- fonts (size hierarchy the simulator + device both understand) --------
F_HERO = pixel_font.load("/system/assets/fonts/bacteria.ppf")   # ~20px
F_MID = pixel_font.load("/system/assets/fonts/smart.ppf")       # ~16px
F_LABEL = pixel_font.load("/system/assets/fonts/nope.ppf")      # ~13px

# glass geometry (the CRT screen inside the bezel)
GX, GY, GW, GH = 12, 12, W - 24, H - 24

index = 0


def _measure(s):
    return screen.measure_text(s)[0]


def _line_h():
    return int(screen.measure_text("Ay")[1]) + 6


def _wrap(text, max_w):
    """Wrap text to max_w px with the current font, honouring explicit \n."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else cur + " " + word
            if not cur or _measure(trial) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _fit(text, max_w, max_h):
    """Largest font whose wrapped text fits; returns (font, lines, line_h)."""
    for font in (F_HERO, F_MID, F_LABEL):
        screen.font = font
        lines = _wrap(text, max_w)
        lh = _line_h()
        if len(lines) * lh <= max_h:
            return font, lines, lh
    return F_LABEL, lines, lh


def _text(s, x, y, pen):
    screen.pen = pen
    screen.text(s, int(x), int(y))


def _ctext(s, cx, y, pen):
    _text(s, cx - _measure(s) / 2, y, pen)


def _bezel_and_glass():
    # molded frame, then a thin amber edge, then the espresso glass (rounded
    # like a CRT tube). Four corner "screws" sell the physical panel.
    screen.pen = BEZEL
    screen.clear()
    for cx, cy in ((7, 7), (W - 8, 7), (7, H - 8), (W - 8, H - 8)):
        screen.pen = RIVET
        screen.shape(shape.rounded_rectangle(cx - 2, cy - 2, 4, 4, 2))
    screen.pen = FRAME
    screen.shape(shape.rounded_rectangle(GX - 1, GY - 1, GW + 2, GH + 2, 9))
    screen.pen = GLASS
    screen.shape(shape.rounded_rectangle(GX, GY, GW, GH, 8))


def _scanlines():
    screen.pen = SCAN
    for y in range(GY + 3, GY + GH - 2, 3):
        screen.rectangle(GX + 4, y, GW - 8, 1)


def _annunciator(now):
    # blinking LED + label, then a hairline rule under the header
    lit = (now // 550) % 2 == 0
    screen.pen = SIGNAL if lit else RIVET
    screen.shape(shape.rounded_rectangle(GX + 16, GY + 17, 8, 8, 4))
    screen.font = F_LABEL
    _text(HEADER, GX + 30, GY + 15, AMBER)
    screen.pen = FRAME
    screen.rectangle(GX + 16, GY + 34, GW - 32, 1)


def _message():
    text = NOTES[index]
    # centre the message in the band between the header and footer rules
    pad_x, top, bottom = 30, GY + 40, GY + GH - 26
    font, lines, lh = _fit(text, GW - 2 * (pad_x - GX), bottom - top)
    screen.font = font
    block_h = len(lines) * lh
    y = top + max(0, (bottom - top - block_h) // 2)
    for line in lines:
        # amber halo around a bright core -> the glyphs read as emitting light
        _ctext(line, W / 2 + 1, y, GLOW)
        _ctext(line, W / 2 - 1, y, GLOW)
        _ctext(line, W / 2, y + 1, GLOW)
        _ctext(line, W / 2, y, AMBER_HI)
        y += lh


def _footer():
    screen.pen = FRAME
    screen.rectangle(GX + 16, GY + GH - 22, GW - 32, 1)
    screen.font = F_LABEL
    _ctext("< A      %d / %d      C >" % (index + 1, len(NOTES)),
           W / 2, GY + GH - 17, AMBER_DIM)


def draw(now):
    _bezel_and_glass()
    _annunciator(now)
    _message()
    _footer()
    _scanlines()


def update():
    global index
    # A steps back, C (or B) steps forward through the notes
    if badge.pressed(BUTTON_A):
        index = (index - 1) % len(NOTES)
    elif badge.pressed(BUTTON_C) or badge.pressed(BUTTON_B):
        index = (index + 1) % len(NOTES)

    draw(badge.ticks)


run(update)
