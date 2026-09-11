# CIRCUIT - one loop through the pads, and the board powers on.
#
# A loop-drawing logic puzzle on a printed circuit board.  Draw a single
# closed loop along the grid lines.  A number says how many of that cell's
# four sides the loop uses; a cell with no number is anyone's guess.  The
# loop never crosses or branches, and there is only one.
#
# THE CURSOR LIVES ON THE PADS, NOT THE CELLS.  The puzzle is played on
# edges, and an edge has no square to stand on - so the cursor stands on a
# pad and the pencil does the rest: hold B and move, and the edge you cross
# is drawn.  Let go of B to walk without drawing.  Tap B to swap between
# trace and cross (a cross says "not this edge").  UP/DOWN repeat while
# held; A/C repeat only while B is down, because with it up a long hold on
# them means the list or a clear.
#
# Hold A for the list, hold C to clear - both only while B is up.  C on the
# title opens HOW TO PLAY.
#
# The puzzles are baked by tools/gen_circuit_puzzles.py, which keeps only
# grids with one loop that a person can reach without guessing.
APP_DIR = "/system/apps/user/circuit"

import os
import sys

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State
from puzzles import PUZZLES

badge.mode(HIRES)
W, H = 320, 240

BOARD_Y = 24
BOARD_H = 200                     # the board, bar to hint
PAD = 6                           # board beyond the outer pads
HOLD_MS = 400
REPEAT_AFTER, REPEAT_EVERY = 320, 90
STATE_KEY = "slitherlink"         # the app's old name, so best times survive
LIST_ROWS = 5
MARKS = {"SMALL": "MK-I", "MEDIUM": "MK-II", "LARGE": "MK-III"}

# ---- palette: solder-mask green, copper, silkscreen -----------------------
BG = color.rgb(4, 16, 9)
PCB = color.rgb(14, 58, 34)
PCB_EDGE = color.rgb(40, 104, 64)
PANEL = color.rgb(8, 32, 19)
SILK = color.rgb(226, 240, 222)
DIM = color.rgb(112, 160, 124)
COPPER = color.rgb(150, 104, 44)
COPPER_DIM = color.rgb(96, 68, 30)
TRACE = color.rgb(255, 196, 86)
TRACE_HOT = color.rgb(255, 250, 222)
CUT = color.rgb(242, 92, 72)
RED = color.rgb(255, 64, 56)
GREEN = color.rgb(120, 255, 150)
MET = color.rgb(84, 132, 96)      # a number whose sides are all drawn
LED_OFF = color.rgb(20, 52, 30)
SCAN = color.rgb(0, 0, 0, 60)
HOT = (TRACE_HOT, color.rgb(255, 238, 180), color.rgb(255, 226, 150),
       color.rgb(255, 214, 124), color.rgb(255, 204, 104), TRACE)

F_BODY = pixel_font.load("/system/assets/fonts/compass.ppf")   # h16
F_CLUE = pixel_font.load("/system/assets/fonts/awesome.ppf")   # h14
F_SMALL = pixel_font.load("/system/assets/fonts/ark.ppf")      # h11

TITLE, PLAYING, SOLVED, HOWTO = 0, 1, 2, 3
UNKNOWN, LINE, X = 0, 1, 2

done = {}
State.load(STATE_KEY, done)

mode = TITLE
pick = 0
top = 0
puzzle = PUZZLES[0]
n = 0
cell = 18
bx = by = 0                       # the top-left pad
clue = []                         # flat cell -> 0..3 or -1
edges = []                        # flat edge -> UNKNOWN / LINE / X
HN = 0                            # horizontal edges come first
cur = [0, 0]                      # pad column, pad row
ink = LINE
pen = None                        # [pressed at, drew something] while B down
started_at = 0
elapsed = 0
new_best = False
loop = []                         # the solved loop's edges, in walking order

_hold = {}
_rep = {}


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


# ---- the lattice ------------------------------------------------------------
# Horizontal edge (r, c), r in 0..n, c in 0..n-1  ->  r * n + c
# Vertical edge (r, c),   r in 0..n-1, c in 0..n  ->  HN + r * (n+1) + c
def h_edge(r, c):
    return r * n + c


def v_edge(r, c):
    return HN + r * (n + 1) + c


def cell_edges(i):
    r, c = i // n, i % n
    return (h_edge(r, c), h_edge(r + 1, c), v_edge(r, c), v_edge(r, c + 1))


def dot_edges(c, r):
    out = []
    if c > 0:
        out.append(h_edge(r, c - 1))
    if c < n:
        out.append(h_edge(r, c))
    if r > 0:
        out.append(v_edge(r - 1, c))
    if r < n:
        out.append(v_edge(r, c))
    return out


def edge_between(c0, r0, c1, r1):
    if r0 == r1:
        return h_edge(r0, min(c0, c1))
    return v_edge(min(r0, r1), c0)


def key_of(which):
    return "%s%d" % (PUZZLES[which][0], which)


def load(which):
    global puzzle, n, cell, bx, by, clue, edges, HN, cur, ink, pen
    global started_at, elapsed, mode, new_best
    puzzle = PUZZLES[which]
    _label, n, rows = puzzle
    clue = [-1 if rows[r][c] == "." else int(rows[r][c])
            for r in range(n) for c in range(n)]
    HN = (n + 1) * n
    edges = [UNKNOWN] * (HN + n * (n + 1))
    cell = (BOARD_H - 2 * PAD) // n
    bx = (W - n * cell) // 2
    by = BOARD_Y + PAD + (BOARD_H - 2 * PAD - n * cell) // 2
    cur = [n // 2, n // 2]
    ink = LINE
    pen = None
    started_at = badge.ticks
    elapsed = 0
    new_best = False
    mode = PLAYING


def sides(i):
    k = 0
    for e in cell_edges(i):
        if edges[e] == LINE:
            k += 1
    return k


def degree(c, r):
    k = 0
    for e in dot_edges(c, r):
        if edges[e] == LINE:
            k += 1
    return k


def check():
    """One closed loop, every number met?  Then it is solved."""
    global mode, elapsed, new_best
    total = 0
    for e in edges:
        if e == LINE:
            total += 1
    if not total:
        return
    for r in range(n + 1):
        for c in range(n + 1):
            if degree(c, r) not in (0, 2):
                return
    for i in range(n * n):
        if clue[i] >= 0 and sides(i) != clue[i]:
            return
    # every dot is clean, so the lines are loops; is it one loop?
    first = 0
    while edges[first] != LINE:
        first += 1
    seen = {first}
    todo = [first]
    while todo:
        e = todo.pop()
        if e < HN:
            r, c = e // n, e % n
            dots = ((c, r), (c + 1, r))
        else:
            r, c = (e - HN) // (n + 1), (e - HN) % (n + 1)
            dots = ((c, r), (c, r + 1))
        for dc, dr in dots:
            for f in dot_edges(dc, dr):
                if edges[f] == LINE and f not in seen:
                    seen.add(f)
                    todo.append(f)
    if len(seen) != total:
        return
    elapsed = badge.ticks - started_at
    mode = SOLVED
    key = key_of(pick)
    prev = done.get(key)
    if prev is None or elapsed < prev:
        done[key] = elapsed
        new_best = True
        State.save(STATE_KEY, done)


# ---- input ------------------------------------------------------------------
DIRS = ((BUTTON_UP, 0, -1), (BUTTON_DOWN, 0, 1),
        (BUTTON_A, -1, 0), (BUTTON_C, 1, 0))


def steps(drawing):
    """Direction presses this frame, repeating while held.

    UP and DOWN always repeat.  A and C repeat only while the pencil is
    down: with it up, a long hold on them is the menu or the clear, and a
    cursor that ran off under a hold would be a cursor that never meant to.
    """
    now = badge.ticks
    out = []
    for btn, dc, dr in DIRS:
        repeat = drawing or dc == 0
        if badge.pressed(btn):
            _rep[btn] = now + REPEAT_AFTER
            out.append((dc, dr))
        elif badge.held(btn) and btn in _rep:
            if repeat and now >= _rep[btn]:
                _rep[btn] = now + REPEAT_EVERY
                out.append((dc, dr))
        elif btn in _rep:
            del _rep[btn]
    return out


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
    global mode, elapsed, ink, pen
    now = badge.ticks
    a, c = tap_or_hold(BUTTON_A), tap_or_hold(BUTTON_C)
    if badge.pressed(BUTTON_B):
        pen = [now, False]
    drawing = pen is not None and (badge.held(BUTTON_B)
                                   or badge.pressed(BUTTON_B))
    if pen is not None and not drawing:
        # B came up: a short press that drew nothing swaps the pencil
        if not pen[1] and now - pen[0] < HOLD_MS:
            ink = X if ink == LINE else LINE
        pen = None
    if not drawing:
        if a == "hold":
            mode = TITLE
            return
        if c == "hold":
            load(pick)
            return
    if mode == SOLVED:
        b = tap_or_hold(BUTTON_B)
        if b == "tap":
            mode = TITLE
        return
    changed = False
    for dc, dr in steps(drawing):
        nc, nr = cur[0] + dc, cur[1] + dr
        if nc < 0 or nc > n or nr < 0 or nr > n:
            continue
        if drawing:
            e = edge_between(cur[0], cur[1], nc, nr)
            edges[e] = UNKNOWN if edges[e] == ink else ink
            pen[1] = True
            changed = True
        cur[0], cur[1] = nc, nr
    if changed:
        check()
    if mode == PLAYING:
        elapsed = badge.ticks - started_at


# ---- arcade kit: block letters, LED digits, scanlines ----------------------
GLYPHS = {
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
}


def block_title(text, x, y, s, cell_fn):
    """Text in 5x7 block letters; every lit pixel is handed to cell_fn().

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
                        cell_fn(x + col * s, y + row * s, s, g, col, row,
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


def _text(s, x, y, pen_):
    screen.pen = pen_
    screen.text(s, int(x), int(y))


def _ctext(s, cx, y, pen_):
    _text(s, cx - screen.measure_text(s)[0] // 2, y, pen_)


def _rtext(s, right, y, pen_):
    _text(s, right - screen.measure_text(s)[0], y, pen_)


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


def triangle(x, y, up, pen_):
    screen.pen = pen_
    d = -1 if up else 1
    screen.shape(shape.custom([vec2(x - 4, y), vec2(x + 4, y),
                               vec2(x, y + 5 * d)]))


# ---- drawing ----------------------------------------------------------------
def _clock(ms):
    s = min(5999, ms // 1000)
    return "%d:%02d" % (s // 60, s % 60)


def edge_ends(e):
    """The two pads an edge joins, as (column, row) pairs."""
    if e < HN:
        r, c = e // n, e % n
        return (c, r), (c + 1, r)
    r, c = (e - HN) // (n + 1), (e - HN) % (n + 1)
    return (c, r), (c, r + 1)


def build_loop():
    """Walk the solved loop once, so the current can run round it."""
    global loop
    loop = []
    if LINE not in edges:
        return
    first = edges.index(LINE)
    here = edge_ends(first)[1]
    prev = first
    loop.append(first)
    for _ in range(len(edges)):
        nxt = -1
        for f in dot_edges(here[0], here[1]):
            if f != prev and edges[f] == LINE:
                nxt = f
                break
        if nxt < 0 or nxt == first:
            break
        loop.append(nxt)
        a, b = edge_ends(nxt)
        here = b if a == here else a
        prev = nxt


def draw_edge(e, pen_, thick):
    a, _b = edge_ends(e)
    x, y = bx + a[0] * cell, by + a[1] * cell
    screen.pen = pen_
    if e < HN:
        screen.rectangle(x, y - thick // 2, cell, thick)
    else:
        screen.rectangle(x - thick // 2, y, thick, cell)


def draw_cross(x, y, size):
    """A small x centred on (x, y): this edge is not on the loop."""
    screen.pen = CUT
    for j in range(-size, size + 1):
        screen.rectangle(x + j, y + j, 1, 1)
        screen.rectangle(x - j, y + j, 1, 1)
    screen.rectangle(x - size, y - size, 2, 2)
    screen.rectangle(x + size - 1, y - size, 2, 2)
    screen.rectangle(x - size, y + size - 1, 2, 2)
    screen.rectangle(x + size - 1, y + size - 1, 2, 2)


def draw_pad(x, y, size, pen_):
    screen.pen = pen_
    screen.rectangle(x - size // 2, y - size // 2, size, size)
    screen.pen = PCB
    screen.rectangle(x - 1, y - 1, 2, 2)       # the drill hole


def draw_board():
    thick = 4 if cell >= 30 else 3
    padsz = 6 if cell >= 30 else 4
    x0 = bx - PAD
    wide = n * cell + 2 * PAD
    screen.pen = PCB_EDGE
    screen.rectangle(x0 - 1, BOARD_Y - 1, wide + 2, BOARD_H + 2)
    screen.pen = PCB
    screen.rectangle(x0, BOARD_Y, wide, BOARD_H)
    # numbers, coloured by how they are doing
    screen.font = F_CLUE
    for i in range(n * n):
        if clue[i] < 0:
            continue
        got = sides(i)
        if mode == SOLVED or got == clue[i]:
            p = MET
        elif got > clue[i]:
            p = RED
        else:
            p = SILK
        _text(str(clue[i]), bx + (i % n) * cell + (cell - 8) // 2,
              by + (i // n) * cell + (cell - 14) // 2, p)
    # traces, crosses, and the current running round a finished loop
    for e in range(len(edges)):
        st = edges[e]
        if st == LINE:
            draw_edge(e, TRACE, thick)
        elif st == X and mode == PLAYING:
            a, b = edge_ends(e)
            draw_cross(bx + (a[0] + b[0]) * cell // 2,
                       by + (a[1] + b[1]) * cell // 2, 2)
    if mode == SOLVED and loop:
        size = len(loop)
        head = (badge.ticks // 40) % size
        for j in range(len(HOT)):
            draw_edge(loop[(head - j) % size], HOT[j], thick)
    # pads on top: lit where a trace meets them, red where three do
    for r in range(n + 1):
        for c in range(n + 1):
            d = degree(c, r)
            draw_pad(bx + c * cell, by + r * cell, padsz,
                     RED if d > 2 else (TRACE if d else COPPER))
    if mode == PLAYING:
        x, y = bx + cur[0] * cell, by + cur[1] * cell
        screen.pen = CUT if ink == X else SILK
        if pen is not None:
            screen.shape(shape.circle(x, y, 5))          # pencil down
        else:
            screen.shape(shape.circle(x, y, 6).stroke(2))


def draw_bar():
    screen.pen = PANEL
    screen.rectangle(0, 0, W, 20)
    screen.pen = PCB_EDGE
    screen.rectangle(0, 20, W, 1)
    screen.font = F_BODY
    _text("%s %d" % (MARKS.get(puzzle[0], puzzle[0]), pick % 6 + 1), 6, 2,
          SILK)
    if mode == SOLVED:
        if blink(400):
            _ctext("POWER ON", W // 2, 2, GREEN)
    elif ink == X:
        _ctext("CROSS", W // 2, 2, CUT)
    else:
        _ctext("TRACE", W // 2, 2, TRACE)
    s = _clock(elapsed)
    led_text(s, W - 6 - led_width(s, 8, 2), 3, 8, 14, 2, GREEN, LED_OFF)


def draw_hint():
    y = H - 13
    if mode == PLAYING:
        hints((("HOLD B", "DRAW"), ("TAP B", "TRACE/CROSS"),
               ("HOLD C", "CLEAR")), y, TRACE)
    elif new_best:
        hints((("NEW BEST!", ""), ("B", "BACK TO THE LIST")), y, TRACE)
    else:
        hints((("B", "BACK TO THE LIST"),), y, TRACE)


def title_trace(px, py, s, g, col, row, gc):
    """Letters etched as circuitry: copper between neighbouring pads..."""
    h = s // 2
    screen.pen = COPPER_DIM
    if col < 4 and g[row][col + 1] == "#":
        screen.rectangle(px + h, py + h - 1, s, 2)
    if row < 6 and g[row + 1][col] == "#":
        screen.rectangle(px + h - 1, py + h, 2, s)


def title_pad(px, py, s, g, col, row, gc):
    """...and a solid pad on every pixel, drilled through the middle, with
    a pulse sweeping across them."""
    sweep = (badge.ticks // 60) % 60
    screen.pen = TRACE_HOT if sweep - 1 <= gc <= sweep else TRACE
    screen.rectangle(px + 1, py + 1, s - 2, s - 2)
    screen.pen = PCB
    screen.rectangle(px + s // 2, py + s // 2, 1, 1)


def draw_frame():
    """The bare board every screen sits on: mask, edge, mounting holes."""
    screen.pen = PCB
    screen.shape(shape.rounded_rectangle(6, 6, W - 12, H - 12, 8))
    screen.pen = PCB_EDGE
    screen.shape(shape.rounded_rectangle(6, 6, W - 12, H - 12, 8).stroke(1))


def draw_title():
    draw_frame()
    for hx, hy in ((17, 17), (W - 17, 17), (17, H - 17), (W - 17, H - 17)):
        screen.pen = COPPER
        screen.shape(shape.circle(hx, hy, 5))
        screen.pen = BG
        screen.shape(shape.circle(hx, hy, 2))
    # s=7 is the widest that fits, and sits just under the mounting holes
    x = (W - title_width("CIRCUIT", 7)) // 2
    block_title("CIRCUIT", x, 22, 7, title_trace)
    block_title("CIRCUIT", x, 22, 7, title_pad)
    screen.font = F_SMALL
    _ctext("ONE LOOP  -  EVERY NUMBER SATISFIED", W // 2, 76, DIM)

    # a bus with current riding it
    screen.pen = COPPER_DIM
    screen.rectangle(30, 93, W - 60, 2)
    draw_pad(30, 94, 6, COPPER)
    draw_pad(W - 30, 94, 6, COPPER)
    head = 30 + (badge.ticks // 5) % (W - 60)
    for j in range(len(HOT)):
        x = head - j * 5
        if 30 <= x < W - 35:
            screen.pen = HOT[j]
            screen.rectangle(x, 93, 5, 2)

    first = 104
    for j in range(top, min(top + LIST_ROWS, len(PUZZLES))):
        label, nn, _rows = PUZZLES[j]
        y = first + (j - top) * 19
        sel = j == pick
        if sel:
            screen.pen = PANEL
            screen.shape(shape.rounded_rectangle(30, y - 2, W - 60, 19, 3))
            screen.pen = TRACE
            screen.rectangle(30, y - 2, 3, 19)
        screen.font = F_BODY
        _text("%s %d" % (MARKS.get(label, label), j % 6 + 1), 42, y,
              SILK if sel else DIM)
        screen.font = F_SMALL
        _text("%dx%d" % (nn, nn), 160, y + 3, DIM)
        t = done.get(key_of(j))
        if t is not None:
            _rtext(_clock(t), W - 40, y + 3, TRACE if sel else GREEN)
    if top > 0:
        triangle(W - 22, 108, True, DIM)
    if top + LIST_ROWS < len(PUZZLES):
        triangle(W - 22, 194, False, DIM)

    if blink():
        screen.font = F_BODY
        _ctext("PRESS B TO START", W // 2, 200, SILK)
    hints((("C", "HOW TO PLAY"), ("UP DOWN", "PICK")), 220, TRACE)
    scanlines()


def draw_howto():
    draw_frame()
    screen.font = F_BODY
    _ctext("HOW TO PLAY", W // 2, 12, SILK)

    # a 3 drawn on three sides, and the 0 beside it crossed on all four
    ex, ey, c = 26, 44, 26
    screen.pen = PANEL
    screen.rectangle(ex - 8, ey - 8, 2 * c + 16, c + 16)
    screen.font = F_CLUE
    _text("3", ex + 9, ey + 6, SILK)
    _text("0", ex + c + 9, ey + 6, SILK)
    screen.pen = TRACE
    screen.rectangle(ex, ey - 1, c, 3)
    screen.rectangle(ex - 1, ey, 3, c)
    screen.rectangle(ex, ey + c - 1, c, 3)
    for x, y in ((ex + c, ey + c // 2), (ex + c + c // 2, ey),
                 (ex + 2 * c, ey + c // 2), (ex + c + c // 2, ey + c)):
        draw_cross(x, y, 2)
    for i in range(3):
        draw_pad(ex + i * c, ey, 4, TRACE if i < 2 else COPPER)
        draw_pad(ex + i * c, ey + c, 4, TRACE if i < 2 else COPPER)

    screen.font = F_SMALL
    y = 40
    for line in ("DRAW ONE CLOSED LOOP", "ALONG THE PADS.  A NUMBER",
                 "SAYS HOW MANY OF ITS FOUR", "SIDES THE LOOP USES.",
                 "NO BRANCHES, NO CROSSINGS -", "AND ONLY ONE LOOP."):
        _text(line, 104, y, SILK)
        y += 13

    y = 128
    for key, what in (("UP DOWN A C", "WALK THE PADS"),
                      ("HOLD B + MOVE", "DRAW AS YOU GO"),
                      ("TAP B", "SWAP TRACE / CROSS"),
                      ("HOLD C", "CLEAR THE BOARD"),
                      ("HOLD A", "BACK TO THE LIST")):
        _text(key, 30, y, TRACE)
        _text(what, 136, y, SILK)
        y += 14

    if blink():
        _ctext("PRESS ANY BUTTON", W // 2, 212, DIM)
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
        if mode == SOLVED:
            build_loop()
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
