# SAPPER - clear the field, mind the mines.
#
# The classic mine-clearing game, rebuilt as an arcade cabinet: hazard
# stripes, steel tiles and red LED counters.  A number is how many mines
# touch that tile, diagonals included.
#
#   UP/DOWN rows, A/C columns (the badge has no left/right), wrapping.
#   B digs; on an open number whose flags are all planted, B digs the rest
#   around it.  Hold B to plant or pull a flag.  Hold C restarts the same
#   field, hold A goes back to the title.  C on the title opens HOW TO PLAY.
#
# The first dig is always safe: mines are laid AFTER it, clear of the tile
# and its eight neighbours, so every game opens with something to reason from.
APP_DIR = "/system/apps/user/sapper"

import os
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import random

from badgeware import State

badge.mode(HIRES)
W, H = 320, 240

# name, columns, rows, mines
BOARDS = (("EASY", 9, 9, 10), ("HARD", 14, 9, 26))
CELL = 22
BOARD_Y = 26                      # under the LED bar
HOLD_MS = 400
STATE_KEY = "minesweeper"         # the app's old name, so best times survive

# ---- palette: black cabinet, hazard yellow, steel tiles, red LEDs ----------
BG = color.rgb(10, 10, 12)
PANEL = color.rgb(30, 30, 32)
INK = color.rgb(236, 236, 228)
DIM = color.rgb(128, 128, 120)
HAZ_Y = color.rgb(255, 196, 0)
HAZ_HI = color.rgb(255, 234, 140)
HAZ_LO = color.rgb(196, 128, 0)
HAZ_K = color.rgb(16, 16, 16)
SHADOW = color.rgb(150, 20, 10)
RED = color.rgb(255, 56, 40)
GREEN = color.rgb(90, 230, 110)
LED_ON = color.rgb(255, 40, 24)
LED_OFF = color.rgb(62, 12, 8)
LED_BG = color.rgb(20, 4, 2)
STEEL = color.rgb(84, 88, 96)
STEEL_HI = color.rgb(150, 156, 166)
STEEL_LO = color.rgb(38, 40, 46)
FLOOR = color.rgb(20, 22, 26)
FLOOR_LINE = color.rgb(46, 50, 56)
POLE = color.rgb(230, 230, 222)
MINE = color.rgb(14, 14, 14)
GLINT = color.rgb(240, 240, 240)
FLASH = color.rgb(255, 60, 20, 110)
SCAN = color.rgb(0, 0, 0, 60)
NUMBER = (None,
          color.rgb(70, 170, 255),    # 1
          color.rgb(80, 230, 100),    # 2
          color.rgb(255, 80, 64),     # 3
          color.rgb(210, 100, 255),   # 4
          color.rgb(255, 160, 40),    # 5
          color.rgb(40, 226, 210),    # 6
          color.rgb(245, 245, 245),   # 7
          color.rgb(160, 160, 160))   # 8

F_BODY = pixel_font.load("/system/assets/fonts/hungry.ppf")    # h15
F_CLUE = pixel_font.load("/system/assets/fonts/awesome.ppf")   # h14
F_SMALL = pixel_font.load("/system/assets/fonts/ark.ppf")      # h11

TITLE, PLAYING, WON, LOST, HOWTO = 0, 1, 2, 3, 4

best = {}                         # board name -> best time in ms
State.load(STATE_KEY, best)

# ---- the game ---------------------------------------------------------------
mode = TITLE
pick = 0                          # field highlighted on the title
board = BOARDS[0]
cols = rows = nmines = 0
mine = []                         # flat, row-major: True where a mine is
near = []                         # flat: mines among the eight neighbours
opened = []                       # flat: dug
flagged = []                      # flat: flagged
cur = [0, 0]                      # column, row
laid = False                      # mines exist (they are laid on first dig)
opened_n = 0
started_at = 0                    # badge.ticks at first dig
elapsed = 0                       # ms, frozen when the game ends
hit = -1                          # the mine that ended the game
new_best = False

_hold = {}


def tap_or_hold(button):
    """'tap', 'hold' or None - one button carrying a rarer second action.

    Built out of pressed() and held() only, the way keep and dwell do it: no
    app that demonstrably runs on the badge uses released(), so this does not
    either.  The hold fires as soon as the threshold passes, so planting a
    flag feels like a switch rather than a wait.
    """
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


def new_game(which):
    global board, cols, rows, nmines, mine, near, opened, flagged, cur
    global laid, opened_n, started_at, elapsed, hit, mode, new_best
    board = BOARDS[which]
    _n, cols, rows, nmines = board
    n = cols * rows
    mine = [False] * n
    near = [0] * n
    opened = [False] * n
    flagged = [False] * n
    cur = [cols // 2, rows // 2]
    laid = False
    opened_n = 0
    started_at = elapsed = 0
    hit = -1
    new_best = False
    mode = PLAYING


def neighbours(i):
    c, r = i % cols, i // cols
    out = []
    for dr in (-1, 0, 1):
        rr = r + dr
        if rr < 0 or rr >= rows:
            continue
        for dc in (-1, 0, 1):
            cc = c + dc
            if (dr or dc) and 0 <= cc < cols:
                out.append(rr * cols + cc)
    return out


def lay_mines(safe):
    """Everything except the first dig and the ring around it is fair game."""
    global laid
    keep = set(neighbours(safe))
    keep.add(safe)
    n = cols * rows
    placed = 0
    while placed < nmines:
        i = random.randrange(n)
        if mine[i] or i in keep:
            continue
        mine[i] = True
        placed += 1
    for i in range(n):
        if not mine[i]:
            k = 0
            for j in neighbours(i):
                if mine[j]:
                    k += 1
            near[i] = k
    laid = True


def dig(i):
    """Open a cell; a zero floods outward.  Returns False on a mine."""
    global opened_n, hit
    if opened[i] or flagged[i]:
        return True
    if mine[i]:
        hit = i
        return False
    stack = [i]
    while stack:
        j = stack.pop()
        if opened[j]:
            continue
        opened[j] = True
        opened_n += 1
        if near[j] == 0:
            for k in neighbours(j):
                if not opened[k] and not flagged[k]:
                    stack.append(k)
    return True


def chord(i):
    """On an open number: if the flags around it add up, dig the rest."""
    around = neighbours(i)
    flags = 0
    for j in around:
        if flagged[j]:
            flags += 1
    if flags != near[i]:
        return True
    for j in around:
        if not flagged[j] and not opened[j]:
            if not dig(j):
                return False
    return True


def finish(won):
    global mode, elapsed, new_best
    elapsed = badge.ticks - started_at if started_at else 0
    if won:
        mode = WON
        for i in range(cols * rows):
            if mine[i]:
                flagged[i] = True
        prev = best.get(board[0])
        if prev is None or elapsed < prev:
            best[board[0]] = elapsed
            new_best = True
            State.save(STATE_KEY, best)
    else:
        mode = LOST


def act():
    """The B button, on whatever the cursor is over."""
    global started_at
    i = cur[1] * cols + cur[0]
    if flagged[i]:
        return                    # a flag is a promise; digging it is a hold away
    if not laid:
        lay_mines(i)
        started_at = badge.ticks
    if opened[i]:
        ok = chord(i) if near[i] else True
    else:
        ok = dig(i)
    if not ok:
        finish(False)
    elif opened_n == cols * rows - nmines:
        finish(True)


def flag():
    i = cur[1] * cols + cur[0]
    if not opened[i]:
        flagged[i] = not flagged[i]


# ---- input ------------------------------------------------------------------
def update_title():
    global pick, mode
    if badge.pressed(BUTTON_UP):
        pick = (pick - 1) % len(BOARDS)
    elif badge.pressed(BUTTON_DOWN):
        pick = (pick + 1) % len(BOARDS)
    b = tap_or_hold(BUTTON_B)
    tap_or_hold(BUTTON_A)
    c = tap_or_hold(BUTTON_C)
    if b == "tap":
        new_game(pick)
    elif c == "tap":
        mode = HOWTO


def update_howto():
    global mode
    a, b, c = (tap_or_hold(BUTTON_A), tap_or_hold(BUTTON_B),
               tap_or_hold(BUTTON_C))
    if a or b or c:
        mode = TITLE


def update_game():
    global mode, pick, elapsed
    a, b, c = (tap_or_hold(BUTTON_A), tap_or_hold(BUTTON_B),
               tap_or_hold(BUTTON_C))
    if a == "hold":
        mode = TITLE
        return
    if c == "hold":
        new_game(pick)
        return
    if mode != PLAYING:
        if b == "tap":
            new_game(pick)
        return
    if badge.pressed(BUTTON_UP):
        cur[1] = (cur[1] - 1) % rows
    elif badge.pressed(BUTTON_DOWN):
        cur[1] = (cur[1] + 1) % rows
    if a == "tap":
        cur[0] = (cur[0] - 1) % cols
    elif c == "tap":
        cur[0] = (cur[0] + 1) % cols
    if b == "tap":
        act()
    elif b == "hold":
        flag()
    if mode == PLAYING and started_at:
        elapsed = badge.ticks - started_at


# ---- arcade kit: block letters, LED digits, stripes, scanlines -------------
GLYPHS = {
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
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


# ---- drawing ----------------------------------------------------------------
def seconds(ms):
    return min(999, ms // 1000)


def led_box_width(s):
    return led_width(s, 9, 2) + 8


def led_box(s, x, y):
    """A recessed red LED counter, the way the original had them."""
    bw = led_box_width(s)
    screen.pen = LED_BG
    screen.rectangle(x, y, bw, 20)
    screen.pen = LED_OFF
    screen.shape(shape.rounded_rectangle(x, y, bw, 20, 2).stroke(1))
    led_text(s, x + 4, y + 2, 9, 16, 2, LED_ON, LED_OFF)


def hazard(y, h, shift):
    """A strip of yellow-and-black warning stripes; shift scrolls it."""
    screen.pen = HAZ_Y
    screen.rectangle(0, y, W, h)
    screen.pen = HAZ_K
    x = shift % 16 - 2 * h - 16
    while x < W + h:
        screen.shape(shape.custom([vec2(x, y + h), vec2(x + 8, y + h),
                                   vec2(x + 8 + h, y), vec2(x + h, y)]))
        x += 16


def draw_tile(x, y, raised):
    if raised:
        screen.pen = STEEL
        screen.rectangle(x, y, CELL, CELL)
        screen.pen = STEEL_HI
        screen.rectangle(x, y, CELL - 1, 2)
        screen.rectangle(x, y, 2, CELL - 1)
        screen.pen = STEEL_LO
        screen.rectangle(x + 1, y + CELL - 2, CELL - 1, 2)
        screen.rectangle(x + CELL - 2, y + 1, 2, CELL - 1)
    else:
        screen.pen = FLOOR_LINE
        screen.rectangle(x, y, CELL, CELL)
        screen.pen = FLOOR
        screen.rectangle(x + 1, y + 1, CELL - 1, CELL - 1)


def draw_flag(x, y):
    screen.pen = POLE
    screen.rectangle(x + 11, y + 4, 2, 13)
    screen.rectangle(x + 7, y + 16, 10, 2)
    screen.pen = RED
    screen.shape(shape.custom([vec2(x + 11, y + 4), vec2(x + 11, y + 12),
                               vec2(x + 4, y + 8)]))


def draw_mine(x, y, boom):
    if boom:
        screen.pen = RED
        screen.rectangle(x + 1, y + 1, CELL - 2, CELL - 2)
    cx, cy = x + CELL // 2, y + CELL // 2
    screen.pen = MINE
    screen.rectangle(cx - 8, cy - 1, 16, 2)
    screen.rectangle(cx - 1, cy - 8, 2, 16)
    for dx, dy in ((-6, -6), (4, -6), (-6, 4), (4, 4)):
        screen.rectangle(cx + dx, cy + dy, 2, 2)
    screen.shape(shape.circle(cx, cy, 5))
    screen.pen = GLINT
    screen.rectangle(cx - 3, cy - 3, 2, 2)


def draw_cross(x, y):
    """A flag on a tile that was not a mine, shown at the end."""
    screen.pen = HAZ_Y
    for k in range(4, CELL - 4):
        screen.rectangle(x + k, y + k, 2, 2)
        screen.rectangle(x + CELL - 2 - k, y + k, 2, 2)


def draw_board():
    ox = oy = 0
    shaking = mode == LOST and badge.ticks - since < 450
    if shaking:                              # the blast rattles the cabinet
        ox = (badge.ticks // 30) % 5 - 2
        oy = (badge.ticks // 40) % 3 - 1
    x0 = (W - cols * CELL) // 2 + ox
    y0 = BOARD_Y + oy
    screen.font = F_CLUE
    for i in range(cols * rows):
        x = x0 + (i % cols) * CELL
        y = y0 + (i // cols) * CELL
        if opened[i]:
            draw_tile(x, y, False)
            if near[i]:
                _text(str(near[i]), x + 7, y + 4, NUMBER[near[i]])
        elif flagged[i]:
            draw_tile(x, y, True)
            draw_flag(x, y)
            if mode == LOST and not mine[i]:
                draw_cross(x, y)
        elif mode == LOST and mine[i]:
            draw_tile(x, y, i != hit)
            draw_mine(x, y, i == hit)
        else:
            draw_tile(x, y, True)
    if mode == PLAYING:
        x = x0 + cur[0] * CELL
        y = y0 + cur[1] * CELL
        screen.pen = HAZ_Y
        screen.shape(shape.rounded_rectangle(x - 1, y - 1, CELL + 2, CELL + 2,
                                             3).stroke(2))
    if shaking and badge.ticks - since < 150:
        screen.pen = FLASH
        screen.rectangle(0, BOARD_Y, W, rows * CELL)


def draw_bar():
    screen.pen = PANEL
    screen.rectangle(0, 0, W, 22)
    screen.pen = HAZ_Y
    screen.rectangle(0, 22, W, 1)
    flags = 0
    for f in flagged:
        if f:
            flags += 1
    left = nmines - flags
    led_box("%03d" % left if left >= 0 else "-%02d" % min(99, -left), 4, 1)
    s = "%03d" % seconds(elapsed)
    led_box(s, W - 4 - led_box_width(s), 1)
    screen.font = F_BODY
    if mode == WON:
        if blink(400):
            _ctext("ALL CLEAR", W // 2, 4, GREEN)
    elif mode == LOST:
        if blink(250) or badge.ticks - since > 2000:
            _ctext("BOOM", W // 2, 4, RED)
    else:
        _ctext(board[0] + " FIELD", W // 2, 4, HAZ_Y)


def draw_hint():
    y = H - 13
    if mode == PLAYING:
        hints((("B", "DIG"), ("HOLD B", "FLAG"), ("HOLD C", "RESTART")),
              y, HAZ_Y)
    elif mode == WON and new_best:
        hints((("NEW BEST!", ""), ("B", "PLAY AGAIN"), ("HOLD A", "TITLE")),
              y, HAZ_Y)
    else:
        hints((("B", "PLAY AGAIN"), ("HOLD A", "TITLE")), y, HAZ_Y)


def title_cell(px, py, s, g, col, row, gc):
    """A chunky yellow block with a red drop shadow, and a shine that runs
    across the letters now and then."""
    screen.pen = SHADOW
    screen.rectangle(px + 2, py + 2, s - 1, s - 1)
    screen.pen = HAZ_HI if gc == (badge.ticks // 45) % 70 else HAZ_Y
    screen.rectangle(px, py, s - 1, s - 1)
    screen.pen = HAZ_HI
    screen.rectangle(px, py, s - 1, 1)
    screen.pen = HAZ_LO
    screen.rectangle(px, py + s - 2, s - 1, 1)


def draw_title():
    shift = badge.ticks // 50
    hazard(0, 12, shift)
    block_title("SAPPER", (W - title_width("SAPPER", 7)) // 2, 24, 7,
                title_cell)
    screen.font = F_SMALL
    _ctext("CLEAR THE FIELD  -  MIND THE MINES", W // 2, 84, DIM)

    for k in range(len(BOARDS)):
        name, c, r, m = BOARDS[k]
        y = 106 + k * 32
        sel = k == pick
        if sel:
            screen.pen = PANEL
            screen.shape(shape.rounded_rectangle(20, y - 5, W - 40, 26, 3))
            screen.pen = HAZ_Y
            screen.shape(shape.custom([vec2(28, y + 1), vec2(28, y + 13),
                                       vec2(35, y + 7)]))
        screen.font = F_BODY
        _text(name, 42, y, HAZ_Y if sel else DIM)
        screen.font = F_SMALL
        _text("%dx%d  %d MINES" % (c, r, m), 100, y + 3, INK if sel else DIM)
        _text("BEST", 208, y + 3, DIM)
        t = best.get(name)
        s = "%03d" % seconds(t) if t is not None else "---"
        led_box(s, W - 26 - led_box_width(s), y - 3)

    if blink():
        screen.font = F_BODY
        _ctext("PRESS B TO START", W // 2, 176, HAZ_Y)
    hints((("C", "HOW TO PLAY"), ("UP DOWN", "FIELD")), 204, HAZ_Y)
    hazard(228, 12, -shift)
    scanlines()


def draw_howto():
    hazard(0, 10, 0)
    screen.font = F_BODY
    _ctext("HOW TO PLAY", W // 2, 16, HAZ_Y)

    # a corner of a field: a column of 1s beside the mine they point at
    ex, ey = 20, 42
    screen.font = F_CLUE
    for r in range(3):
        for c in range(3):
            x, y = ex + c * CELL, ey + r * CELL
            if c < 2:
                draw_tile(x, y, False)
                if c == 1:
                    _text("1", x + 7, y + 4, NUMBER[1])
            else:
                draw_tile(x, y, True)
                if r == 1:
                    draw_flag(x, y)

    screen.font = F_SMALL
    y = 44
    for line in ("A NUMBER IS HOW MANY MINES", "TOUCH THAT TILE, DIAGONALS",
                 "INCLUDED.  DIG EVERY SAFE", "TILE TO CLEAR THE FIELD.",
                 "YOUR FIRST DIG IS ALWAYS SAFE."):
        _text(line, 102, y, INK)
        y += 13

    y = 120
    for key, what in (("UP DOWN A C", "MOVE"), ("B", "DIG"),
                      ("HOLD B", "PLANT / PULL A FLAG"),
                      ("B ON A NUMBER", "DIG AROUND IT"),
                      ("HOLD C", "RESTART THE FIELD"),
                      ("HOLD A", "BACK TO THE TITLE")):
        _text(key, 24, y, HAZ_Y)
        _text(what, 124, y, INK)
        y += 14

    if blink():
        _ctext("PRESS ANY BUTTON", W // 2, 213, DIM)
    hazard(230, 10, 0)
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
