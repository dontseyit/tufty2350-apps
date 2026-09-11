# MOSAIC - paint by numbers, pixel by pixel.
#
# A picture-logic puzzle in synthwave neon.  Every number counts the painted
# squares in the 3x3 block centred on it - itself and its eight neighbours -
# so a 0 means all nine are blank and a 9 means all nine are painted.  Paint
# every square right and the picture lights up.
#
#   UP/DOWN rows, A/C columns, wrapping.  B paints a square (again to clear
#   it), hold B marks it blank.  Hold C clears the board, hold A goes back to
#   the list.  C on the title opens HOW TO PLAY.
#
# The puzzles are baked by tools/gen_mosaic_puzzles.py, which checks each can
# be finished by the basic rule alone - no guessing, ever.
APP_DIR = "/system/apps/user/mosaic"

import os
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import math

from badgeware import State
from puzzles import COLS, ROWS, PUZZLES

badge.mode(HIRES)
W, H = 320, 240

CELL = 20
BOARD_Y = 24
BOARD_X = (W - COLS * CELL) // 2
HOLD_MS = 400
STATE_KEY = "fillapix"            # the app's old name, so best times survive
LIST_ROWS = 4                     # puzzles visible at once on the title
REVEAL_MS = 900                   # the solved picture wipes in over this


def _mix(a, b, f):
    return color.rgb(int(a[0] + (b[0] - a[0]) * f),
                     int(a[1] + (b[1] - a[1]) * f),
                     int(a[2] + (b[2] - a[2]) * f))


# ---- palette: night purple, hot magenta, neon cyan paint --------------------
BG = color.rgb(14, 8, 26)
PANEL = color.rgb(34, 16, 56)
INK = color.rgb(250, 228, 255)
DIM = color.rgb(132, 100, 164)
MAGENTA = color.rgb(255, 50, 190)
CYAN = color.rgb(0, 226, 255)
CYAN_HI = color.rgb(176, 250, 255)
GRIDC = color.rgb(62, 30, 90)
CELLC = color.rgb(36, 20, 60)     # unknown
BLANKC = color.rgb(20, 11, 36)    # marked blank
BLANK_DOT = color.rgb(150, 50, 140)
CLUE_ON_CELL = color.rgb(255, 222, 250)
CLUE_ON_PAINT = color.rgb(6, 30, 52)
CLUE_ON_BLANK = color.rgb(118, 68, 128)
GRID_LINE = color.rgb(150, 36, 140)
LED_OFF = color.rgb(16, 40, 60)
SCAN = color.rgb(0, 0, 0, 60)
ROW_GRAD = [_mix((255, 50, 190), (0, 226, 255), r / 6) for r in range(7)]
SUN = [_mix((255, 232, 90), (255, 40, 170), k / 7) for k in range(8)]

F_BODY = pixel_font.load("/system/assets/fonts/yesterday.ppf")  # h16
F_CLUE = pixel_font.load("/system/assets/fonts/awesome.ppf")    # h14
F_SMALL = pixel_font.load("/system/assets/fonts/ark.ppf")       # h11

TITLE, PLAYING, SOLVED, HOWTO = 0, 1, 2, 3
UNKNOWN, ON, OFF = 0, 1, 2
N = COLS * ROWS

done = {}                         # puzzle name -> best time in ms
State.load(STATE_KEY, done)

mode = TITLE
pick = 0
top = 0                           # first puzzle shown in the list
puzzle = PUZZLES[0]
picture = []                      # flat: True where painted
clue = []                         # flat: 0-9, or -1 for none
cells = []                        # flat: UNKNOWN / ON / OFF
cur = [0, 0]
started_at = 0
elapsed = 0
new_best = False

_hold = {}


def tap_or_hold(button):
    """'tap', 'hold' or None - built from pressed() and held() only, the
    idiom every app here shares, because nothing that demonstrably runs on
    the badge uses released()."""
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


def load(which):
    global puzzle, picture, clue, cells, cur, started_at, elapsed, mode
    global new_best
    puzzle = PUZZLES[which]
    _name, pic, clues = puzzle
    picture = [pic[r][c] == "#" for r in range(ROWS) for c in range(COLS)]
    clue = [-1 if clues[r][c] == "." else int(clues[r][c])
            for r in range(ROWS) for c in range(COLS)]
    cells = [UNKNOWN] * N
    cur = [COLS // 2, ROWS // 2]
    started_at = badge.ticks
    elapsed = 0
    new_best = False
    mode = PLAYING


def check():
    """Painted exactly where the picture is?  Blank marks do not count."""
    global mode, elapsed, new_best
    for i in range(N):
        if (cells[i] == ON) != picture[i]:
            return
    elapsed = badge.ticks - started_at
    mode = SOLVED
    prev = done.get(puzzle[0])
    if prev is None or elapsed < prev:
        done[puzzle[0]] = elapsed
        new_best = True
        State.save(STATE_KEY, done)


def paint():
    i = cur[1] * COLS + cur[0]
    cells[i] = UNKNOWN if cells[i] == ON else ON
    check()


def mark():
    i = cur[1] * COLS + cur[0]
    cells[i] = UNKNOWN if cells[i] == OFF else OFF
    check()


# ---- input ------------------------------------------------------------------
def update_title():
    global pick, top, mode
    if badge.pressed(BUTTON_UP):
        pick = (pick - 1) % len(PUZZLES)
    elif badge.pressed(BUTTON_DOWN):
        pick = (pick + 1) % len(PUZZLES)
    if pick < top:
        top = pick
    elif pick >= top + LIST_ROWS:
        top = pick - LIST_ROWS + 1
    b = tap_or_hold(BUTTON_B)
    tap_or_hold(BUTTON_A)
    c = tap_or_hold(BUTTON_C)
    if b == "tap":
        load(pick)
    elif c == "tap":
        mode = HOWTO


def update_howto():
    global mode
    a, b, c = (tap_or_hold(BUTTON_A), tap_or_hold(BUTTON_B),
               tap_or_hold(BUTTON_C))
    if a or b or c:
        mode = TITLE


def update_game():
    global mode, elapsed
    a, b, c = (tap_or_hold(BUTTON_A), tap_or_hold(BUTTON_B),
               tap_or_hold(BUTTON_C))
    if a == "hold":
        mode = TITLE
        return
    if c == "hold":
        load(pick)
        return
    if mode == SOLVED:
        if b == "tap":
            mode = TITLE
        return
    if badge.pressed(BUTTON_UP):
        cur[1] = (cur[1] - 1) % ROWS
    elif badge.pressed(BUTTON_DOWN):
        cur[1] = (cur[1] + 1) % ROWS
    if a == "tap":
        cur[0] = (cur[0] - 1) % COLS
    elif c == "tap":
        cur[0] = (cur[0] + 1) % COLS
    if b == "tap":
        paint()
    elif b == "hold":
        mark()
    if mode == PLAYING:
        elapsed = badge.ticks - started_at


# ---- arcade kit: block letters, LED digits, scanlines ----------------------
GLYPHS = {
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
}


def block_title(text, x, y, s, cell):
    """Text in 5x7 block letters; every lit pixel is handed to cell().

    The badge's fonts are fixed-size bitmaps topping out near 28px, so a
    marquee-sized title is drawn rather than typed - and drawing it lets the
    letters be made of whatever the game is made of.
    """
    for k in range(len(text)):
        g = GLYPHS.get(text[k])
        if g:
            for row in range(7):
                for col in range(5):
                    if g[row][col] == "#":
                        cell(x + col * s, y + row * s, s, g, col, row,
                             k * 6 + col)
        x += 6 * s


def title_width(text, s):
    return len(text) * 6 * s - s


SEGS = (0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F)


def led_char(x, y, bits, w, h, t, on, off):
    """One seven-segment digit; bit 0 is the top bar, bit 6 the middle."""
    m = y + (h - t) // 2
    hi = m - y - t
    lo = y + h - 2 * t - m
    parts = ((x + t, y, w - 2 * t, t), (x + w - t, y + t, t, hi),
             (x + w - t, m + t, t, lo), (x + t, y + h - t, w - 2 * t, t),
             (x, m + t, t, lo), (x, y + t, t, hi), (x + t, m, w - 2 * t, t))
    for k in range(7):
        screen.pen = on if bits & (1 << k) else off
        px, py, pw, ph = parts[k]
        screen.rectangle(px, py, pw, ph)


def led_width(s, w, t):
    n = 0
    for ch in s:
        n += (t + 3) if ch == ":" else (w + 3)
    return n - 3


def led_text(s, x, y, w, h, t, on, off):
    """Digits, '-' and ':' in seven segments, the unlit ones faintly shown."""
    for ch in s:
        if ch == ":":
            screen.pen = on
            screen.rectangle(x, y + h // 3 - 1, t, t)
            screen.rectangle(x, y + 2 * h // 3, t, t)
            x += t + 3
            continue
        if ch == "-":
            bits = 0x40
        elif ch == " ":
            bits = 0
        else:
            bits = SEGS[ord(ch) - 48]
        led_char(x, y, bits, w, h, t, on, off)
        x += w + 3


def _text(s, x, y, pen):
    screen.pen = pen
    screen.text(s, int(x), int(y))


def _ctext(s, cx, y, pen):
    _text(s, cx - screen.measure_text(s)[0] // 2, y, pen)


def _rtext(s, right, y, pen):
    _text(s, right - screen.measure_text(s)[0], y, pen)


def hints(parts, y, key):
    """A centred row of (key, action) pairs: keys lit, actions dim."""
    screen.font = F_SMALL
    gap = 12
    total = -gap
    for k, a in parts:
        total += screen.measure_text(k)[0] + gap
        if a:
            total += 4 + screen.measure_text(a)[0]
    x = (W - total) // 2
    for k, a in parts:
        _text(k, x, y, key)
        x += screen.measure_text(k)[0]
        if a:
            x += 4
            _text(a, x, y, DIM)
            x += screen.measure_text(a)[0]
        x += gap


def scanlines():
    screen.pen = SCAN
    for y in range(0, H, 3):
        screen.rectangle(0, y, W, 1)


def blink(ms=500):
    return (badge.ticks // ms) % 2 == 0


def triangle(x, y, up, pen):
    screen.pen = pen
    d = -1 if up else 1
    screen.shape(shape.custom([vec2(x - 4, y), vec2(x + 4, y),
                               vec2(x, y + 5 * d)]))


# ---- drawing ----------------------------------------------------------------
def _clock(ms):
    s = min(5999, ms // 1000)
    return "%d:%02d" % (s // 60, s % 60)


_runs = {}


def runs(which):
    """A puzzle's picture as horizontal runs, so a thumbnail is a few dozen
    rectangles rather than a hundred and fifty."""
    got = _runs.get(which)
    if got is None:
        got = []
        pic = PUZZLES[which][1]
        for r in range(ROWS):
            c = 0
            while c < COLS:
                if pic[r][c] == "#":
                    c0 = c
                    while c < COLS and pic[r][c] == "#":
                        c += 1
                    got.append((r, c0, c - c0))
                else:
                    c += 1
        _runs[which] = got
    return got


def draw_picture(which, x, y, px, pen):
    screen.pen = pen
    for r, c0, ln in runs(which):
        screen.rectangle(x + c0 * px, y + r * px, ln * px, px)


def draw_cell(x, y, state, dot=True):
    screen.pen = GRIDC
    screen.rectangle(x, y, CELL, CELL)
    if state == ON:
        screen.pen = CYAN
        screen.rectangle(x + 1, y + 1, CELL - 1, CELL - 1)
        screen.pen = CYAN_HI
        screen.rectangle(x + 1, y + 1, CELL - 1, 1)
    elif state == OFF:
        screen.pen = BLANKC
        screen.rectangle(x + 1, y + 1, CELL - 1, CELL - 1)
        if dot:                   # a clue in a dimmer ink says it instead
            screen.pen = BLANK_DOT
            screen.rectangle(x + 8, y + 8, 4, 4)
    else:
        screen.pen = CELLC
        screen.rectangle(x + 1, y + 1, CELL - 1, CELL - 1)


def draw_board():
    screen.font = F_CLUE
    reach = COLS + ROWS
    if mode == SOLVED:            # the picture wipes in from the top left
        reach = (badge.ticks - since) * (COLS + ROWS) // REVEAL_MS
    for i in range(N):
        c, r = i % COLS, i // COLS
        x = BOARD_X + c * CELL
        y = BOARD_Y + r * CELL
        if mode == SOLVED and c + r < reach:
            if picture[i]:
                screen.pen = CYAN
                screen.rectangle(x, y, CELL, CELL)
                screen.pen = CYAN_HI
                screen.rectangle(x, y, CELL, 1)
            else:
                screen.pen = BG
                screen.rectangle(x, y, CELL, CELL)
            continue
        draw_cell(x, y, cells[i], clue[i] < 0)
        if clue[i] >= 0:
            if cells[i] == ON:
                pen = CLUE_ON_PAINT
            elif cells[i] == OFF:
                pen = CLUE_ON_BLANK
            else:
                pen = CLUE_ON_CELL
            _text(str(clue[i]), x + 6, y + 3, pen)
    if mode == PLAYING:
        x = BOARD_X + cur[0] * CELL
        y = BOARD_Y + cur[1] * CELL
        screen.pen = MAGENTA
        screen.shape(shape.rounded_rectangle(x, y, CELL, CELL, 3).stroke(2))


def draw_bar():
    screen.pen = PANEL
    screen.rectangle(0, 0, W, 20)
    screen.pen = MAGENTA
    screen.rectangle(0, 20, W, 1)
    screen.font = F_BODY
    _text("No.%02d" % (pick + 1), 6, 2, MAGENTA)
    name = puzzle[0]
    if mode == SOLVED:
        if badge.ticks - since < REVEAL_MS or blink(400):
            _ctext(name, W // 2, 2, CYAN)
    else:
        _ctext("?" * len(name), W // 2, 2, DIM)
    s = _clock(elapsed)
    led_text(s, W - 6 - led_width(s, 8, 2), 3, 8, 14, 2, CYAN, LED_OFF)


def draw_hint():
    y = H - 13
    if mode == PLAYING:
        hints((("B", "PAINT"), ("HOLD B", "BLANK"), ("HOLD C", "CLEAR")),
              y, CYAN)
    elif new_best:
        hints((("NEW BEST!", ""), ("B", "BACK TO THE LIST")), y, CYAN)
    else:
        hints((("B", "BACK TO THE LIST"),), y, CYAN)


def draw_sun(cx, horizon, r):
    """The synthwave sun: slices that thin out towards the horizon."""
    y = horizon - r
    k = 0
    while y < horizon:
        dy = horizon - (y + 2)
        hw = int(math.sqrt(max(0, r * r - dy * dy)))
        screen.pen = SUN[min(len(SUN) - 1, k)]
        screen.rectangle(cx - hw, y, 2 * hw, 4 - k // 3)
        y += 4
        k += 1


def draw_grid(horizon, bottom):
    """A floor of neon lines running out of the horizon towards you."""
    screen.pen = GRID_LINE
    phase = (badge.ticks % 1400) / 1400
    for k in range(6):
        f = (k + phase) / 6
        screen.rectangle(0, horizon + int((bottom - horizon) * f * f), W, 1)
    for k in range(-7, 8):
        xt = W // 2 + k * 14
        xb = W // 2 + k * 56
        screen.shape(shape.custom([vec2(xt, horizon), vec2(xt + 1, horizon),
                                   vec2(xb + 1, bottom), vec2(xb, bottom)]))
    screen.pen = MAGENTA
    screen.rectangle(0, horizon, W, 1)


def title_outline(px, py, s, g, col, row, gc):
    screen.pen = BG
    screen.rectangle(px - 1, py - 1, s + 1, s + 1)


def title_face(px, py, s, g, col, row, gc):
    """Each letter pixel is a mosaic tile, magenta fading into cyan."""
    sweep = (badge.ticks // 50) % 70
    screen.pen = CYAN_HI if gc == sweep else ROW_GRAD[row]
    screen.rectangle(px, py, s - 1, s - 1)


def question_cell(px, py, s, g, col, row, gc):
    screen.pen = MAGENTA
    screen.rectangle(px, py, s - 1, s - 1)


def draw_title():
    # the title up top, the sun setting under it onto a neon floor
    x = (W - title_width("MOSAIC", 6)) // 2
    block_title("MOSAIC", x, 8, 6, title_outline)
    block_title("MOSAIC", x, 8, 6, title_face)
    draw_sun(W // 2, 86, 30)
    draw_grid(86, 106)
    screen.font = F_SMALL
    _ctext("PAINT BY NUMBERS, PIXEL BY PIXEL", W // 2, 110, DIM)

    first = 126
    screen.font = F_BODY
    for j in range(top, min(top + LIST_ROWS, len(PUZZLES))):
        name = PUZZLES[j][0]
        y = first + (j - top) * 20
        sel = j == pick
        solved = name in done
        if sel:
            screen.pen = PANEL
            screen.shape(shape.rounded_rectangle(16, y - 2, 180, 19, 3))
            screen.pen = MAGENTA
            screen.rectangle(16, y - 2, 3, 19)
        _text("%02d" % (j + 1), 26, y, MAGENTA if sel else DIM)
        if solved:
            _text(name, 58, y, CYAN)
        else:
            _text("?" * len(name), 58, y, INK if sel else DIM)
    if top > 0:
        triangle(8, 130, True, DIM)
    if top + LIST_ROWS < len(PUZZLES):
        triangle(8, 198, False, DIM)

    # the picture you are playing for - or the question mark it still is
    px, py = 212, 126
    screen.pen = MAGENTA
    screen.shape(shape.rounded_rectangle(px - 3, py - 3, 96, 66, 3).stroke(1))
    screen.pen = BLANKC
    screen.rectangle(px, py, 90, 60)
    name = PUZZLES[pick][0]
    screen.font = F_SMALL
    if name in done:
        draw_picture(pick, px, py, 6, CYAN)
        _ctext("BEST " + _clock(done[name]), px + 45, py + 66, CYAN)
    else:
        block_title("?", px + 30, py + 9, 6, question_cell)
        _ctext("UNSOLVED", px + 45, py + 66, DIM)

    if blink():
        screen.font = F_BODY
        _ctext("PRESS B TO START", W // 2, 207, CYAN)
    hints((("C", "HOW TO PLAY"), ("UP DOWN", "PICK")), 226, CYAN)
    scanlines()


def draw_howto():
    screen.font = F_BODY
    _ctext("HOW TO PLAY", W // 2, 6, MAGENTA)
    screen.pen = MAGENTA
    screen.rectangle(40, 25, W - 80, 1)

    # three blocks and their numbers: none painted, four, all nine
    ex = (W - (3 * 42 + 2 * 30)) // 2
    for k, num, lit, say in ((0, "0", (), "NONE"),
                             (1, "4", (0, 2, 4, 7), "FOUR"),
                             (2, "9", (0, 1, 2, 3, 4, 5, 6, 7, 8), "ALL NINE")):
        x0, y0 = ex + k * 72, 34
        for i in range(9):
            x = x0 + (i % 3) * 14
            y = y0 + (i // 3) * 14
            screen.pen = GRIDC
            screen.rectangle(x, y, 14, 14)
            screen.pen = CYAN if i in lit else BLANKC
            screen.rectangle(x + 1, y + 1, 13, 13)
        screen.font = F_SMALL
        _text(num, x0 + 18, y0 + 16, CLUE_ON_PAINT if 4 in lit else CLUE_ON_CELL)
        _ctext(say, x0 + 21, y0 + 47, DIM)

    y = 98
    for line in ("EACH NUMBER COUNTS THE PAINTED SQUARES",
                 "IN THE 3x3 BLOCK AROUND IT - ITSELF TOO.",
                 "PAINT EVERY ONE RIGHT TO REVEAL A PICTURE."):
        _ctext(line, W // 2, y, INK)
        y += 13

    y = 144
    for key, what in (("UP DOWN A C", "MOVE"), ("B", "PAINT / UNPAINT"),
                      ("HOLD B", "MARK AS BLANK"),
                      ("HOLD C", "CLEAR THE BOARD"),
                      ("HOLD A", "BACK TO THE LIST")):
        _text(key, 40, y, CYAN)
        _text(what, 140, y, INK)
        y += 14

    if blink():
        _ctext("PRESS ANY BUTTON", W // 2, 222, DIM)
    scanlines()


_seen = TITLE
since = 0                         # badge.ticks when the mode last changed


def update():
    global _seen, since
    if mode == TITLE:
        update_title()
    elif mode == HOWTO:
        update_howto()
    else:
        update_game()
    if mode != _seen:
        _seen = mode
        since = badge.ticks
    screen.pen = BG
    screen.clear()
    if mode == TITLE:
        draw_title()
    elif mode == HOWTO:
        draw_howto()
    else:
        draw_bar()
        draw_board()
        draw_hint()


run(update)
