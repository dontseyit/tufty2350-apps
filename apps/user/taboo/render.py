# Retro Taboo - all drawing. A faithful port of the canvas renderer in
# taboo/Pixel Mockup.dc.html to the badge's `screen` API, driven by live state.
#
# Coordinates, scales and colours match the mockup 1:1 (320x240, SUNSET palette).
# The dithered background is pre-baked (assets/bg.png) and blitted each frame; the
# 5x7 font is drawn as filled pixel cells, exactly like the design's text().

import math

import config as cfg
import textutil
from font import FONT

PW = 292   # play-area width; the right 28px hold the floating side buttons

# SUNSET palette (rgb tuples + ready-made pen objects)
RGB = {
    "INK": (255, 243, 230), "PANEL": (39, 16, 42), "FRAME": (255, 138, 92),
    "ACCENT": (255, 164, 92), "TABOO": (255, 111, 111), "GREEN": (116, 217, 159),
    "AMBER": (255, 194, 75), "DIM": (201, 138, 160), "DARK": (22, 8, 18),
    "BLUE": (159, 217, 255),
}
RGB["TEAMA"] = RGB["AMBER"]
RGB["TEAMB"] = RGB["GREEN"]
C = {k: color.rgb(*v) for k, v in RGB.items()}

_bg = image.load("assets/bg.png")


def _acolor(name, a):
    r, g, b = RGB[name]
    return color.rgb(r, g, b, a)


def _team_color(i):
    return C["TEAMA"] if i == 0 else C["TEAMB"]


# ---- primitives (mirror the mockup's rect / measure / text / ctext / box) ----
def rect(x, y, w, h, col):
    screen.pen = col
    screen.rectangle(int(x), int(y), int(w), int(h))


def measure(t, s):
    return len(t) * 6 * s - s


def text(t, x, y, s, col):
    screen.pen = col
    cx = int(x)
    y = int(y)
    for ch in t:
        g = FONT.get(ch, FONT[" "])
        for r in range(7):
            row = g[r]
            c = 0
            # batch each contiguous run of lit cells into one rectangle
            while c < 5:
                if row[c] == "1":
                    run = 1
                    while c + run < 5 and row[c + run] == "1":
                        run += 1
                    screen.rectangle(cx + c * s, y + r * s, run * s, s)
                    c += run
                else:
                    c += 1
        cx += 6 * s


def ctext(t, left, w, y, s, col):
    text(t, left + (w - measure(t, s)) / 2, y, s, col)


def box(x, y, w, h, fill, bd=None, bt=2, sh=0):
    if sh:
        rect(x + sh, y + sh, w, h, C["DARK"])
    rect(x, y, w, h, fill)
    if bd:
        rect(x, y, w, bt, bd)
        rect(x, y + h - bt, w, bt, bd)
        rect(x, y, bt, h, bd)
        rect(x + w - bt, y, bt, h, bd)


def draw_bg():
    screen.blit(_bg, vec2(0, 0))


# ---- floating bottom action buttons (no panel / divider) ----
def draw_actions(btns):
    gap = 18
    total = 0
    for b in btns:
        total += 16 + 4 + measure(b["lab"], 1)
    total += gap * (len(btns) - 1)
    bx = int((PW - total) / 2)
    by = 216
    for b in btns:
        rect(bx, by, 16, 16, b["c"])
        rect(bx, by, 16, 2, C["DARK"])
        rect(bx, by + 14, 16, 2, C["DARK"])
        rect(bx, by, 2, 16, C["DARK"])
        rect(bx + 14, by, 2, 16, C["DARK"])
        text(b["l"], bx + 6, by + 5, 1, C["DARK"])
        text(b["lab"], bx + 20, by + 5, 1, C["INK"])
        bx += 16 + 4 + measure(b["lab"], 1) + gap


# ---- floating side buttons up/down (no rail; dimmed when inactive) ----
def draw_side(up, down, up_on, down_on):
    def cell(y, glyph, label, on):
        a = 255 if on else 82
        x = 298
        d = _acolor("DARK", a)
        rect(x, y, 16, 16, _acolor("BLUE", a))
        rect(x, y, 16, 2, d)
        rect(x, y + 14, 16, 2, d)
        rect(x, y, 2, 16, d)
        rect(x + 14, y, 2, 16, d)
        text(glyph, x + 5, y + 5, 1, d)
        if label:
            ctext(label, 292, 28, y + 22, 1, _acolor("INK", a))
    cell(40, "▲", up, up_on)
    cell(160, "▼", down, down_on)


def _edge_pulse(now):
    a = int(130 + 100 * abs(math.sin(now / 200.0)))
    p = color.rgb(255, 111, 111, a)
    screen.pen = p
    screen.rectangle(0, 0, 320, 4)
    screen.rectangle(0, 236, 320, 4)
    screen.rectangle(0, 0, 4, 240)
    screen.rectangle(316, 0, 4, 240)


# ---- per-screen renderers (all read live state from `g`) ----
def _dots(now):
    # fixed width (3) so centred text doesn't jitter as the count changes
    n = 1 + (now // 400) % 3
    return "." * n + " " * (3 - n)


def draw_setup(g, now):
    draw_bg()
    ctext("TABOO", 0, PW, 12, 3, C["INK"])
    ctext("PASS AND PLAY", 0, PW, 44, 1, C["ACCENT"])
    # single highlighted category, cycled with the ▲▼ side buttons (fits any count)
    ctext("SELECT A CATEGORY", 0, PW, 66, 1, C["DIM"])
    cat = textutil.tr_upper(cfg.CATEGORIES[g.deck_idx])
    cw = measure(cat, 2) + 20
    cx = (PW - cw) / 2
    box(cx, 82, cw, 24, C["PANEL"], C["FRAME"], 2, 2)
    ctext(cat, 0, PW, 89, 2, C["ACCENT"])
    ctext("%d / %d" % (g.deck_idx + 1, len(cfg.CATEGORIES)), 0, PW, 112, 1, C["DIM"])
    # connection status
    if not g.online:
        ctext("OFFLINE - PLAYING FROM CACHE", 0, PW, 132, 1, C["TABOO"])
    # house rules
    ctext("TEAM A VS TEAM B", 0, PW, 152, 1, C["DIM"])
    ctext(cfg.turn_label() + " TURN - FIRST TO " + str(cfg.TARGET_SCORE), 0, PW, 168, 1, C["INK"])
    draw_actions([{"l": "B", "lab": "START GAME", "c": C["GREEN"]}])
    draw_side("DECK", "DECK", True, True)


def draw_connecting(g, now):
    draw_bg()
    ctext("CONNECTING", 0, PW, 92, 2, C["BLUE"])
    ctext("TO WI-FI " + _dots(now), 0, PW, 120, 1, C["DIM"])
    ctext("ANY BUTTON - PLAY OFFLINE", 0, PW, 200, 1, C["DIM"])
    draw_side("", "", False, False)


def draw_loading(g, now):
    draw_bg()
    ctext("GENERATING CARDS" + _dots(now), 0, PW, 92, 2, C["ACCENT"])
    ctext(textutil.tr_upper(g.category), 0, PW, 120, 1, C["INK"])
    ctext("ASKING THE AGENT", 0, PW, 200, 1, C["DIM"])
    draw_side("", "", False, False)


def draw_refill(g, now):
    # mid-turn top-up: the turn timer is paused while we fetch more cards
    draw_bg()
    ctext("MORE CARDS" + _dots(now), 0, PW, 92, 2, C["ACCENT"])
    ctext(textutil.tr_upper(g.category), 0, PW, 120, 1, C["INK"])
    ctext("TIMER PAUSED", 0, PW, 148, 1, C["GREEN"])
    ctext("FETCHING NEW CARDS", 0, PW, 200, 1, C["DIM"])
    draw_side("", "", False, False)


def draw_nocards(g, now):
    draw_bg()
    ctext("NO CARDS", 0, PW, 78, 3, C["TABOO"])
    ctext("CONNECT TO WI-FI", 0, PW, 124, 1, C["DIM"])
    ctext("TO GENERATE NEW CARDS", 0, PW, 140, 1, C["DIM"])
    draw_actions([{"l": "B", "lab": "BACK", "c": C["GREEN"]}])
    draw_side("RETRY", "", True, False)


def draw_handoff(g, now):
    draw_bg()
    ctext("PASS THE DEVICE TO", 0, PW, 44, 1, C["DIM"])
    ctext(cfg.team_name(g.current), 0, PW, 60, 2, _team_color(g.current))
    bw = 150
    bxx = (PW - bw) / 2
    box(bxx, 94, bw, 46, C["PANEL"], C["FRAME"], 2, 2)
    ctext("A", bxx, bw / 2, 102, 1, C["TEAMA"])
    ctext(str(g.scores[0]), bxx, bw / 2, 114, 2, C["INK"])
    ctext("B", bxx + bw / 2, bw / 2, 102, 1, C["TEAMB"])
    ctext(str(g.scores[1]), bxx + bw / 2, bw / 2, 114, 2, C["INK"])
    ctext("NO PEEKING - CARD HIDDEN", 0, PW, 158, 1, C["TABOO"])
    draw_actions([{"l": "B", "lab": "READY - START TURN", "c": C["GREEN"]}])
    draw_side("BACK", "", True, False)


def draw_countdown(g, now):
    draw_bg()
    ctext(cfg.team_name(g.current) + " - GET READY", 0, PW, 70, 1, _team_color(g.current))
    v = g.countdown_value(now)
    if v == "GO":
        s = 5
        x = (PW - measure(v, s)) / 2
        text(v, x + 2, 118 + 2, s, C["DARK"])
        text(v, x, 118, s, _team_color(g.current))
    else:
        s = 9
        x = (PW - measure(v, s)) / 2
        text(v, x + 4, 98 + 4, s, C["DARK"])
        text(v, x, 98, s, _team_color(g.current))
    draw_side("", "", False, False)


def draw_turn(g, now):
    draw_bg()
    # timer chip
    box(6, 6, 58, 26, C["PANEL"], C["FRAME"], 2, 2)
    rem = g.remaining_seconds(now)
    ctext("%d:%02d" % (rem // 60, rem % 60), 6, 58, 12, 2, C["INK"])
    # theme + score
    ctext(textutil.tr_upper(g.category), 0, PW, 9, 1, C["ACCENT"])
    sa = str(g.scores[0])
    sb = str(g.scores[1])
    x0 = 286 - measure(sa + "-" + sb, 2)
    text(sa, x0, 9, 2, C["TEAMA"])
    text("-", x0 + len(sa) * 12, 9, 2, C["DIM"])
    text(sb, x0 + (len(sa) + 1) * 12, 9, 2, C["TEAMB"])
    # target word (hero), 3x with a 1px drop-shadow; shrink so any agent-supplied
    # word fits the 292px play area (3x -> 2x -> 1x), never drawing off-edge
    word = g.current_card["word"]
    if measure(word, 3) <= PW - 8:
        s, yw = 3, 58
    elif measure(word, 2) <= PW - 8:
        s, yw = 2, 64
    else:
        s, yw = 1, 68
    wx = max(0, (PW - measure(word, s)) / 2)
    text(word, wx + s, yw + s, s, C["DARK"])
    text(word, wx, yw, s, C["INK"])
    # taboo panel (cap at 5 so nothing spills past the panel onto the buttons)
    box(30, 96, 232, 112, C["PANEL"], C["FRAME"], 2, 3)
    ctext("DON'T SAY", 30, 232, 104, 1, C["TABOO"])
    rect(113, 113, 67, 1, C["TABOO"])
    for i, w in enumerate(g.current_card["taboo"][:5]):
        ctext(w, 30, 232, 120 + i * 16, 2, C["INK"])
    # actions (HANDOVER map: A=TABOO -1, B=SKIP, C=GOT IT +1)
    draw_actions([
        {"l": "A", "lab": "TABOO", "c": C["TABOO"]},
        {"l": "B", "lab": "SKIP", "c": C["AMBER"]},
        {"l": "C", "lab": "GOT IT", "c": C["GREEN"]},
    ])
    draw_side("UNDO", "END", True, True)
    if rem <= cfg.LOW_TIME_SECONDS:
        _edge_pulse(now)


def draw_summary(g, now):
    draw_bg()
    head = "TIME UP" if g.summary_reason == "time" else "TURN OVER"
    ctext(head, 0, PW, 16, 2, _team_color(g.current))
    ctext(cfg.team_name(g.current) + " - THIS TURN", 0, PW, 40, 1, C["DIM"])
    stats = [
        (str(g.turn_got), "GOT", C["GREEN"]),
        (str(g.turn_skip), "SKIP", C["AMBER"]),
        (str(g.turn_taboo), "TABOO", C["TABOO"]),
    ]
    bw, bh, gap = 72, 44, 10
    sx = (PW - (3 * bw + 2 * gap)) / 2
    sy = 56
    for v, lab, col in stats:
        box(sx, sy, bw, bh, C["PANEL"], C["FRAME"], 2, 2)
        ctext(v, sx, bw, sy + 8, 2, col)
        ctext(lab, sx, bw, sy + 30, 1, C["DIM"])
        sx += bw + gap
    ctext(cfg.team_name(0) + " " + str(g.scores[0]) + " - " + str(g.scores[1]) + " " + cfg.team_name(1),
          0, PW, 118, 1, C["INK"])
    net = g.turn_net
    ctext("NET " + ("+" if net >= 0 else "") + str(net), 0, PW, 134, 1,
          C["GREEN"] if net >= 0 else C["TABOO"])
    lab = "RESULTS" if g.target_reached() else "NEXT TEAM"
    draw_actions([{"l": "B", "lab": lab, "c": C["GREEN"]}])
    draw_side("BACK", "", True, False)


def draw_win(g, now):
    draw_bg()
    ctext("- WINNER -", 0, PW, 38, 1, C["ACCENT"])
    t = cfg.team_name(g.winner)
    x = (PW - measure(t, 2)) / 2
    text(t, x + 3, 66 + 3, 2, C["DARK"])
    text(t, x, 66, 2, _team_color(g.winner))
    bw = 150
    bxx = (PW - bw) / 2
    box(bxx, 104, bw, 42, C["PANEL"], C["FRAME"], 2, 2)
    ctext(str(g.scores[0]), bxx, bw / 3, 114, 2, C["TEAMA"])
    ctext("FINAL", bxx + bw / 3, bw / 3, 118, 1, C["DIM"])
    ctext(str(g.scores[1]), bxx + 2 * bw / 3, bw / 3, 114, 2, C["TEAMB"])
    draw_actions([{"l": "B", "lab": "PLAY AGAIN", "c": C["GREEN"]}])
    draw_side("", "", False, False)


_DRAWERS = {
    cfg.SETUP: draw_setup,
    cfg.HANDOFF: draw_handoff,
    cfg.COUNTDOWN: draw_countdown,
    cfg.TURN: draw_turn,
    cfg.SUMMARY: draw_summary,
    cfg.WIN: draw_win,
    cfg.CONNECTING: draw_connecting,
    cfg.LOADING: draw_loading,
    cfg.NOCARDS: draw_nocards,
    cfg.REFILL: draw_refill,
}


def draw(g, now):
    _DRAWERS[g.state](g, now)
