# STAR GRID - fill the sky, and no two stars touch.
#
# A star-placement logic puzzle set in deep space.  The grid is cut into as
# many zones as it has rows.  Put the stated number of stars in every row,
# every column and every zone, and never let two stars touch, not even at a
# corner.  There is exactly one way to do it.
#
#   UP/DOWN rows, A/C columns, wrapping.  B places a star (again to lift it),
#   hold B dots a cell you have ruled out.  Hold C clears the board, hold A
#   goes back to the list.  C on the title opens HOW TO PLAY.  A star that
#   breaks a rule turns red, so a wrong step shows itself.
#
# The puzzles are baked by tools/gen_star_grid_puzzles.py, which keeps only
# grids with one solution that a person can reach without guessing.
APP_DIR = "/system/apps/user/star_grid"

import os
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import math

from badgeware import State
from puzzles import PUZZLES

badge.mode(HIRES)
W, H = 320, 240

BOARD_Y = 24
BOARD_H = 200
HOLD_MS = 400
STATE_KEY = "starbattle"          # the app's old name, so best times survive
LIST_ROWS = 5
RANKS = {"SMALL": "CADET", "MEDIUM": "PILOT", "LARGE": "ACE",
         "HUGE": "LEGEND"}

# ---- palette: deep space, jewel-toned zones, gold stars --------------------
BG = color.rgb(6, 8, 24)
PANEL = color.rgb(18, 22, 52)
INK = color.rgb(230, 234, 255)
DIM = color.rgb(110, 120, 172)
GOLD = color.rgb(255, 214, 70)
GLOW = color.rgb(255, 214, 70, 55)
WHITE = color.rgb(255, 255, 255)
CYAN = color.rgb(90, 220, 255)
RED = color.rgb(255, 70, 80)
GREEN = color.rgb(110, 236, 150)
BORDER = color.rgb(176, 186, 255)
THIN = color.rgb(255, 255, 255, 26)
DOTC = color.rgb(130, 140, 210)
LED_OFF = color.rgb(52, 42, 12)
SCAN = color.rgb(0, 0, 0, 60)
REGION = (color.rgb(56, 34, 98), color.rgb(24, 56, 104),
          color.rgb(26, 80, 62), color.rgb(94, 72, 22),
          color.rgb(88, 30, 74), color.rgb(18, 72, 88),
          color.rgb(100, 38, 42), color.rgb(58, 60, 90),
          color.rgb(36, 44, 118), color.rgb(76, 50, 102))
TWINKLE = (color.rgb(50, 58, 100), color.rgb(100, 110, 164),
           color.rgb(170, 180, 232), color.rgb(245, 248, 255))
LEVEL = (0, 1, 2, 3, 3, 2, 1, 0)

F_BODY = pixel_font.load("/system/assets/fonts/lookout.ppf")   # h16
F_SMALL = pixel_font.load("/system/assets/fonts/ark.ppf")      # h11

TITLE, PLAYING, SOLVED, HOWTO = 0, 1, 2, 3
UNKNOWN, ON, OFF = 0, 1, 2

done = {}                         # puzzle key -> best time in ms
State.load(STATE_KEY, done)

mode = TITLE
pick = 0
top = 0
puzzle = PUZZLES[0]
n = k = 0
cell = 20                         # pixel size, from n
bx = by = 0                       # board origin
region = []                       # flat: region index per cell
cells = []                        # flat: UNKNOWN / ON / OFF
bad = []                          # flat: True where a star breaks a rule
cur = [0, 0]
started_at = 0
elapsed = 0
new_best = False
star_pts = []                     # (dx, dy) of a star's ten corners

_hold = {}


def star_shape(outer, inner):
    """A five-pointed star's ten corners, as (dx, dy) about its centre.
    shape.custom is what the device has that the simulator also has;
    shape.star is not."""
    pts = []
    for p in range(10):
        a = -math.pi / 2 + p * math.pi / 5
        rad = outer if p % 2 == 0 else inner
        pts.append((math.cos(a) * rad, math.sin(a) * rad))
    return pts


TINY_STAR = star_shape(6, 2.5)    # the list's "how many stars" marks


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


def key_of(which):
    return "%s%d" % (PUZZLES[which][0], which)


def load(which):
    global puzzle, n, k, cell, bx, by, region, cells, bad, cur, star_pts
    global started_at, elapsed, mode, new_best
    puzzle = PUZZLES[which]
    _label, n, k, rows = puzzle
    region = [ord(rows[r][c]) - 65 for r in range(n) for c in range(n)]
    cells = [UNKNOWN] * (n * n)
    bad = [False] * (n * n)
    cell = BOARD_H // n
    bx = (W - n * cell) // 2
    by = BOARD_Y + (BOARD_H - n * cell) // 2
    cur = [n // 2, n // 2]
    star_pts = star_shape(cell * 0.40, cell * 0.17)   # to fit the cell
    started_at = badge.ticks
    elapsed = 0
    new_best = False
    mode = PLAYING


def audit():
    """Mark every star that breaks a rule; report whether all is solved.

    Counts per row, column and region, and a look at the eight neighbours -
    the same three rules the generator solved by, so a board this calls
    clean with the right number of stars is the answer.
    """
    global mode, elapsed, new_best
    rowc = [0] * n
    colc = [0] * n
    regc = [0] * n
    total = 0
    for i in range(n * n):
        bad[i] = False
        if cells[i] == ON:
            rowc[i // n] += 1
            colc[i % n] += 1
            regc[region[i]] += 1
            total += 1
    for i in range(n * n):
        if cells[i] != ON:
            continue
        c, r = i % n, i // n
        if rowc[r] > k or colc[c] > k or regc[region[i]] > k:
            bad[i] = True
            continue
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cc, rr = c + dc, r + dr
                if ((dr or dc) and 0 <= cc < n and 0 <= rr < n
                        and cells[rr * n + cc] == ON):
                    bad[i] = True
    if total != n * k or True in bad:
        return
    for x in range(n):
        if rowc[x] != k or colc[x] != k or regc[x] != k:
            return
    elapsed = badge.ticks - started_at
    mode = SOLVED
    key = key_of(pick)
    prev = done.get(key)
    if prev is None or elapsed < prev:
        done[key] = elapsed
        new_best = True
        State.save(STATE_KEY, done)


def place():
    i = cur[1] * n + cur[0]
    cells[i] = UNKNOWN if cells[i] == ON else ON
    audit()


def mark():
    i = cur[1] * n + cur[0]
    cells[i] = UNKNOWN if cells[i] == OFF else OFF
    audit()


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
        cur[1] = (cur[1] - 1) % n
    elif badge.pressed(BUTTON_DOWN):
        cur[1] = (cur[1] + 1) % n
    if a == "tap":
        cur[0] = (cur[0] - 1) % n
    elif c == "tap":
        cur[0] = (cur[0] + 1) % n
    if b == "tap":
        place()
    elif b == "hold":
        mark()
    if mode == PLAYING:
        elapsed = badge.ticks - started_at


# ---- arcade kit: block letters, LED digits, scanlines ----------------------
GLYPHS = {
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
}


def block_title(text, x, y, s, cell):
    """Text in 5x7 block letters; every lit pixel is handed to cell().

    The badge's fonts are fixed-size bitmaps topping out near 28px, so a
    marquee-sized title is drawn rather than typed - and drawing it lets the
    letters be made of whatever the game is made of.
    """
    for j in range(len(text)):
        g = GLYPHS.get(text[j])
        if g:
            for row in range(7):
                for col in range(5):
                    if g[row][col] == "#":
                        cell(x + col * s, y + row * s, s, g, col, row,
                             j * 6 + col)
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
    for j in range(7):
        screen.pen = on if bits & (1 << j) else off
        px, py, pw, ph = parts[j]
        screen.rectangle(px, py, pw, ph)


def led_width(s, w, t):
    total = 0
    for ch in s:
        total += (t + 3) if ch == ":" else (w + 3)
    return total - 3


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
    for kk, a in parts:
        total += screen.measure_text(kk)[0] + gap
        if a:
            total += 4 + screen.measure_text(a)[0]
    x = (W - total) // 2
    for kk, a in parts:
        _text(kk, x, y, key)
        x += screen.measure_text(kk)[0]
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


# a fixed sky: positions from a little LCG, so no random state is spent
SKY = []
_seed = 20490
for _i in range(56):
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    _sx = (_seed >> 8) % W
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    _sy = (_seed >> 8) % H
    SKY.append((_sx, _sy, _i % 8))
EX_STAR = star_shape(7.2, 3.0)    # the how-to page's example star


def draw_sky():
    step = badge.ticks // 160
    for x, y, p in SKY:
        lvl = LEVEL[(step + p) % 8]
        screen.pen = TWINKLE[lvl]
        screen.rectangle(x, y, 2 if lvl == 3 else 1, 1)


def draw_star(cx, cy, pen, pts=None):
    screen.pen = pen
    screen.shape(shape.custom([vec2(cx + dx, cy + dy)
                               for dx, dy in (pts or star_pts)]))


def draw_board():
    # zone fills first, then the thin grid, then zone borders over both
    for i in range(n * n):
        x = bx + (i % n) * cell
        y = by + (i // n) * cell
        screen.pen = REGION[region[i] % len(REGION)]
        screen.rectangle(x, y, cell, cell)
    screen.pen = THIN
    for t in range(1, n):
        screen.rectangle(bx + t * cell, by, 1, n * cell)
        screen.rectangle(bx, by + t * cell, n * cell, 1)
    screen.pen = BORDER
    for i in range(n * n):
        c, r = i % n, i // n
        x, y = bx + c * cell, by + r * cell
        if c + 1 < n and region[i + 1] != region[i]:
            screen.rectangle(x + cell - 1, y, 2, cell)
        if r + 1 < n and region[i + n] != region[i]:
            screen.rectangle(x, y + cell - 1, cell, 2)
    screen.rectangle(bx - 2, by - 2, n * cell + 4, 2)
    screen.rectangle(bx - 2, by + n * cell, n * cell + 4, 2)
    screen.rectangle(bx - 2, by - 2, 2, n * cell + 4)
    screen.rectangle(bx + n * cell, by - 2, 2, n * cell + 4)

    half = cell // 2
    glow = int(cell * 0.42)
    step = badge.ticks // 110
    for i in range(n * n):
        x = bx + (i % n) * cell
        y = by + (i // n) * cell
        if cells[i] == ON:
            if bad[i]:
                draw_star(x + half, y + half, RED)
                continue
            screen.pen = GLOW
            screen.shape(shape.circle(x + half, y + half, glow))
            twinkle = mode == SOLVED and (step + i) % 7 == 0
            draw_star(x + half, y + half, WHITE if twinkle else GOLD)
        elif cells[i] == OFF and mode == PLAYING:
            screen.pen = DOTC
            screen.rectangle(x + half - 1, y + half - 1, 3, 3)
    if mode == PLAYING:
        x = bx + cur[0] * cell
        y = by + cur[1] * cell
        screen.pen = CYAN
        screen.shape(shape.rounded_rectangle(x, y, cell, cell, 3).stroke(2))


def draw_bar():
    screen.pen = PANEL
    screen.rectangle(0, 0, W, 20)
    screen.pen = BORDER
    screen.rectangle(0, 20, W, 1)
    screen.font = F_BODY
    _text("%s %d" % (RANKS.get(puzzle[0], puzzle[0]), pick % 6 + 1), 6, 2,
          INK)
    if mode == SOLVED:
        if blink(400):
            _ctext("STAGE CLEAR", W // 2, 2, GREEN)
    else:                         # how many stars each line wants
        for m in range(k):
            draw_star(W // 2 - (k - 1) * 8 + m * 16, 10, GOLD, TINY_STAR)
    s = _clock(elapsed)
    led_text(s, W - 6 - led_width(s, 8, 2), 3, 8, 14, 2, GOLD, LED_OFF)


def draw_hint():
    y = H - 13
    if mode == PLAYING:
        hints((("B", "STAR"), ("HOLD B", "DOT"), ("HOLD C", "CLEAR")),
              y, GOLD)
    elif new_best:
        hints((("NEW BEST!", ""), ("B", "BACK TO THE LIST")), y, GOLD)
    else:
        hints((("B", "BACK TO THE LIST"),), y, GOLD)


def title_cell(px, py, s, g, col, row, gc):
    """Every letter pixel is a star, with a glint running through them."""
    sweep = (badge.ticks // 70) % 64
    screen.pen = WHITE if gc == sweep or gc + row == sweep else GOLD
    screen.rectangle(px, py, s - 1, s - 1)


def draw_title():
    draw_sky()
    block_title("STAR GRID", (W - title_width("STAR GRID", 5)) // 2, 18, 5,
                title_cell)
    screen.font = F_SMALL
    _ctext("FILL THE SKY  -  NO TWO STARS TOUCH", W // 2, 62, DIM)

    first = 82
    for j in range(top, min(top + LIST_ROWS, len(PUZZLES))):
        label, nn, kk, _rows = PUZZLES[j]
        y = first + (j - top) * 20
        sel = j == pick
        if sel:
            screen.pen = PANEL
            screen.shape(shape.rounded_rectangle(24, y - 2, W - 48, 19, 3))
            screen.pen = GOLD
            screen.rectangle(24, y - 2, 3, 19)
        screen.font = F_BODY
        _text("%s %d" % (RANKS.get(label, label), j % 6 + 1), 36, y,
              INK if sel else DIM)
        screen.font = F_SMALL
        size = "%dx%d" % (nn, nn)
        _text(size, 150, y + 3, DIM)
        sx = 150 + screen.measure_text(size)[0] + 12
        for m in range(kk):               # one tiny star per star to place
            draw_star(sx + m * 13, y + 8, GOLD if sel else DIM, TINY_STAR)
        t = done.get(key_of(j))
        if t is not None:
            _rtext(_clock(t), W - 34, y + 3, GOLD if sel else GREEN)
    if top > 0:
        triangle(W - 14, 86, True, DIM)
    if top + LIST_ROWS < len(PUZZLES):
        triangle(W - 14, 176, False, DIM)

    if blink():
        screen.font = F_BODY
        _ctext("PRESS B TO START", W // 2, 188, GOLD)
    hints((("C", "HOW TO PLAY"), ("UP DOWN", "PICK")), 222, GOLD)
    scanlines()


def draw_howto():
    draw_sky()
    screen.font = F_BODY
    _ctext("HOW TO PLAY", W // 2, 6, GOLD)

    # one star and the eight cells it rules out
    ex, ey, c = 20, 38, 18
    screen.pen = REGION[1]
    screen.rectangle(ex, ey, 3 * c, 3 * c)
    screen.pen = THIN
    for t in (1, 2):
        screen.rectangle(ex + t * c, ey, 1, 3 * c)
        screen.rectangle(ex, ey + t * c, 3 * c, 1)
    screen.pen = BORDER
    screen.shape(shape.rounded_rectangle(ex - 1, ey - 1, 3 * c + 2, 3 * c + 2,
                                         1).stroke(1))
    for i in range(9):
        x = ex + (i % 3) * c + c // 2
        y = ey + (i // 3) * c + c // 2
        if i == 4:
            screen.pen = GLOW
            screen.shape(shape.circle(x, y, 8))
            draw_star(x, y, GOLD, EX_STAR)
        else:
            screen.pen = DOTC
            screen.rectangle(x - 1, y - 1, 3, 3)
    screen.font = F_SMALL
    _ctext("NO TOUCHING", ex + 27, ey + 60, DIM)

    y = 38
    for line in ("PLACE STARS SO EVERY ROW,", "EVERY COLUMN AND EVERY",
                 "OUTLINED ZONE HOLDS THE SAME", "COUNT - THE STARS AT THE TOP.",
                 "STARS NEVER TOUCH, NOT EVEN", "AT A CORNER.  A RED STAR",
                 "BREAKS ONE OF THESE RULES."):
        _text(line, 96, y, INK)
        y += 13

    y = 140
    for key, what in (("UP DOWN A C", "MOVE"), ("B", "PLACE / LIFT A STAR"),
                      ("HOLD B", "DOT A RULED-OUT CELL"),
                      ("HOLD C", "CLEAR THE BOARD"),
                      ("HOLD A", "BACK TO THE LIST")):
        _text(key, 36, y, GOLD)
        _text(what, 136, y, INK)
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
