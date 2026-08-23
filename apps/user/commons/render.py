# All drawing for Commons - 320x240 HIRES.
#
# The screen is a lit stage inside a dark instrument. The room and the three
# residents are the only warm thing on it; the header, the event rail and every
# readout are alma's near-black panel, in alma's palette, because a mood colour
# has to mean the same thing in both apps.
#
# Reading a resident, in the order you notice it:
#   the cone of light they stand in   which octant, and how far from PAD zero
#   the word above their head         the same octant, spelled out
#   the pill on their chest           an emotion currently above baseline
#   how fast they breathe             arousal
#   a ring                            an event just reached them
#
# Device globals (screen, color, image, ...) are only touched inside functions,
# so this module imports cleanly off-device; init() runs once after badge.mode.

import affect
import config as cfg
import events
import occ
import parts
import sprites

P = {}          # theme pens
OP = {}         # per-octant pen bundles
F = {}          # fonts
M = {}          # font heights

FW, FH = parts.FIGURE
FIG_W, FIG_H = FW * cfg.FIG_SCALE, FH * cfg.FIG_SCALE
SET_W, SET_H = FW * cfg.ROOM_SCALE, FH * cfg.ROOM_SCALE

AURA_STEPS = 5
RING_STEPS = 4


def _shade(rgb, k):
    if k <= 1.0:
        return tuple(int(c * k) for c in rgb[:3])
    return tuple(min(255, int(c + (255 - c) * (k - 1.0))) for c in rgb[:3])


def _blend(fg, bg, a):
    """Composite fg over bg at alpha a (0-255), in software, once."""
    return tuple(int(bg[i] + (fg[i] - bg[i]) * a / 255.0) for i in range(3))


def _level(frac, n):
    i = int(frac * (n - 1) + 0.5)
    return 0 if i < 0 else (n - 1 if i > n - 1 else i)


def octant_pen(name):
    return OP[name]["body"]


def _bake_octant_pens():
    """Every pen the app can need, baked once.

    Nothing here is translucent. The cone of light behind a resident is
    76x134 pixels and there are three of them; asking the badge to alpha-
    composite that every frame buys nothing, because the colour behind each one
    is known and fixed - it is the wallpaper. So the blend is done in software,
    once, and the draw calls get flat opaque colours.
    """
    bg = cfg.THEME["BG"]
    panel = cfg.THEME["PANEL"]
    wall = parts.ROOM[cfg.ROOM][1]
    floor = parts.ROOM[cfg.ROOM][2]
    for name, rgb in cfg.OCTANT_COLORS.items():
        OP[name] = {
            "body": color.rgb(*rgb),
            "dark": color.rgb(*_shade(rgb, 0.58)),
            "tint": color.rgb(*_blend(rgb, panel, 26)),
            # the cone of light on the wall, outermost (faintest) first
            "aura": [color.rgb(*_blend(rgb, wall, 38 + 23 * i))
                     for i in range(AURA_STEPS)],
            # the same cone on the setup screen, where the ground is the
            # instrument's own black rather than wallpaper
            "glow": [color.rgb(*_blend(rgb, bg, 22 + 15 * i))
                     for i in range(AURA_STEPS)],
            # the pool at their feet
            "pool": [color.rgb(*_blend(rgb, floor, 62)),
                     color.rgb(*_blend(rgb, floor, 130))],
            # the ripple an event sends across the floor, brightest first
            "ring": [color.rgb(*_blend(rgb, floor, 210 - 58 * i))
                     for i in range(RING_STEPS)],
            "fade": [color.rgb(*_blend(rgb, panel, 60 + 48 * i))
                     for i in range(4)],
        }


def init():
    for name, rgb in cfg.THEME.items():
        P[name] = color.rgb(*rgb)
    # The name tags sit on the wall, so they are baked against it: dark enough
    # to read white text on, light enough to still be part of the room.
    wall = parts.ROOM[cfg.ROOM][1]
    P["PLATE"] = color.rgb(*_blend(cfg.THEME["BG"], wall, 216))
    P["PLATE_SEL"] = color.rgb(*_blend(cfg.THEME["PANEL"], wall, 196))
    _bake_octant_pens()
    # Size hierarchy picked with the fonttest app (see the repo's font notes):
    #   small - ark   (~h10) : counts, hints, emotion payloads
    #   body  - nope  (~h13) : everything by default
    #   mid   - smart (~h16) : the residents' names
    F["small"] = pixel_font.load("/system/assets/fonts/ark.ppf")
    F["body"] = pixel_font.load("/system/assets/fonts/nope.ppf")
    F["mid"] = pixel_font.load("/system/assets/fonts/smart.ppf")
    for key in F:
        screen.font = F[key]
        M[key] = int(screen.measure_text("0")[1])   # floats on-device
    screen.font = F["body"]
    sprites.init()


# ---- text ------------------------------------------------------------------
def _t(s, x, y, pen, font="body"):
    screen.font = F[font]
    screen.pen = pen
    screen.text(s, int(x), int(y))


def _tw(s, font="body"):
    screen.font = F[font]
    return int(screen.measure_text(s)[0])


def _rt(s, right, y, pen, font="body"):
    _t(s, right - _tw(s, font), y, pen, font)


def _ct(s, cx, y, pen, font="body"):
    _t(s, cx - _tw(s, font) / 2, y, pen, font)


def _fit(s, wmax, font="body"):
    if _tw(s, font) <= wmax:
        return s
    while s and _tw(s + "..", font) > wmax:
        s = s[:-1]
    return s + ".."


def _sign(v):
    return "%+.2f" % v


# ---- primitives ------------------------------------------------------------
def _fill(x, y, w, h, pen):
    if w <= 0 or h <= 0:
        return
    screen.pen = pen
    screen.rectangle(int(x), int(y), int(w), int(h))


def _rule(x, y, w, pen=None):
    _fill(x, y, w, 1, pen or P["EDGE"])


def _panel(x, y, w, h, pen=None):
    screen.pen = pen or P["PANEL"]
    screen.shape(shape.rounded_rectangle(x, y, w, h, 3))


def _ring(cx, cy, r, thick, pen):
    screen.pen = pen
    screen.shape(shape.circle(cx, cy, max(1.0, r)).stroke(thick))


def _ellipse(cx, cy, w, h, pen):
    # radius kept strictly below half the short side; at exactly half the badge
    # intermittently draws a plain rectangle instead (see alma/render.py).
    w, h = max(1.0, w), max(1.0, h)
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(cx - w / 2, cy - h / 2, w, h,
                                         max(0.5, min(w, h) / 2 - 0.5)))


def _bar(x, y, w, h, frac, pen):
    _fill(x, y, w, h, P["TRACK"])
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    _fill(x, y, w * frac, h, pen)


def _bipolar(x, y, w, h, v, pen):
    _fill(x, y, w, h, P["TRACK"])
    cx = x + w / 2
    v = -1.0 if v < -1 else (1.0 if v > 1 else v)
    span = (w / 2) * abs(v)
    _fill(cx if v >= 0 else cx - span, y, span, h, pen)
    _fill(cx, y - 1, 1, h + 2, P["DIM"])


def _tri(cx, y, size, up, pen):
    for i in range(size):
        half = i if up else size - 1 - i
        _fill(cx - half, y + i, half * 2 + 1, 1, pen)


# ---- the room --------------------------------------------------------------
def _stage_wall():
    """The papered wall, down to the floor line. The generator builds the
    wallpaper as one flat row repeated, so a whole column is a single stretched
    blit rather than nine tiles - twenty blits instead of a hundred."""
    wall = sprites.room(0)
    for x in range(0, cfg.W, cfg.TILE):
        screen.blit(wall, rect(x, cfg.STAGE_TOP, cfg.TILE,
                               cfg.FLOOR_TOP - cfg.STAGE_TOP))


def _stage_floor():
    """Baseboard and boards, laid over the bottom of the wall - the pack's
    baseboards are cut with transparency above the moulding, so they have to
    sit ON the wall rather than replace a strip of it."""
    board = sprites.room(2)
    floor = sprites.room(1)
    for x in range(0, cfg.W, cfg.TILE):
        screen.blit(board, vec2(x, cfg.FLOOR_TOP - cfg.TILE))
        screen.blit(floor, rect(x, cfg.FLOOR_TOP, cfg.TILE,
                                cfg.STAGE_BOT - cfg.FLOOR_TOP))


# ---- one resident ----------------------------------------------------------
def breath(who, index, now):
    """Standing, or the top of a breath. The rate is read off arousal, so a
    calm resident is visibly slower than an agitated one - and the three are
    offset from each other, because breathing in unison reads as a machine."""
    a = who.model.mood[1]
    period = cfg.BREATH_SLOW_MS + (cfg.BREATH_FAST_MS - cfg.BREATH_SLOW_MS) \
        * (a + 1.0) / 2.0
    phase = (now + index * 830) % period
    return sprites.BREATH if phase < period * cfg.BREATH_UP else sprites.STAND


def _cone(cx, base, full, pens, reach, width=None):
    """A stepped cone of light standing on `base`: each step in is narrower and
    taller than the last, so the stack reads as a beam rather than a stack of
    posters. How far up it reaches is the caller's business."""
    for i in range(AURA_STEPS):
        w = (width or cfg.AURA_W) * (1.0 - 0.155 * i)
        h = full * reach * (0.52 + 0.12 * i)
        _fill(cx - w / 2, base - h, w, h, pens[i])


def _aura(who, cx):
    """The light a resident stands in: their octant's colour, reaching further
    up the wall the further their mood is from the PAD zero point."""
    reach = cfg.AURA_MIN + (1.0 - cfg.AURA_MIN) * min(
        1.0, who.model.strength() / occ.SQRT3)
    _cone(cx, cfg.FLOOR_TOP, cfg.FLOOR_TOP - cfg.STAGE_TOP,
          OP[who.model.octant()]["aura"], reach)


def _pool(who, cx):
    pens = OP[who.model.octant()]["pool"]
    k = min(1.0, who.model.strength() / occ.SQRT3)
    w = cfg.POOL_W * (0.55 + 0.45 * k)
    _ellipse(cx, cfg.FEET_Y - 1, w, cfg.POOL_H, pens[0])
    _ellipse(cx, cfg.FEET_Y - 1, w * 0.55, cfg.POOL_H * 0.55, pens[1])


def _hit(who, cx, now):
    """A ripple across the floor, for the moment an event reaches somebody -
    drawn flat and in perspective rather than as a hoop around their body, so
    three of them at once read as something crossing the room.

    Whoever it happened TO gets the accent; everyone else gets their own mood
    colour, so you can see the difference between acting and noticing."""
    age = now - who.hit_at
    if age < 0 or age >= cfg.HIT_MS:
        return
    k = age / cfg.HIT_MS
    step = _level(k, RING_STEPS)
    pen = P["ACCENT"] if who.hit_actor and step < 2 \
        else OP[who.model.octant()]["ring"][step]
    w = 18 + 74 * k
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(cx - w / 2, cfg.FEET_Y - 3 - w / 6,
                                         w, w / 3,
                                         max(0.5, w / 6 - 0.5)).stroke(1))


# ALMA states a mood as two words - a strength ("moderate") and an octant
# ("Disdainful") - and on one line that is 95 pixels of text in a 106 pixel
# column, so the tag overflowed into its neighbours.  They go on their own rows
# instead, which is also truer to what they are: two separate readings, not a
# phrase.  Everything below is measured off that.
PLATE_H = 42
PLATE_Y = 18
PLATE_MIN_W = 52


def _plate(who, cx, selected):
    """The name tag over their head: who they are, the mood they are in, and how
    far that mood is from the PAD zero point.  Smoked glass rather than solid
    black, so three of them do not punch three holes in the wall."""
    word, octant = who.state()
    pen = octant_pen(octant)
    w = max(_tw(who.name, "mid"), _tw(word, "small"), _tw(octant, "small"),
            PLATE_MIN_W) + 14
    x, y = cx - w / 2, PLATE_Y
    _panel(x, y, w, PLATE_H, P["PLATE_SEL"] if selected else P["PLATE"])
    if selected:
        screen.pen = P["ACCENT"]
        screen.shape(shape.rounded_rectangle(x, y, w, PLATE_H, 3).stroke(1))
    _ct(who.name, cx, y - 1, P["INK"] if selected else P["DIM"], "mid")
    # the strength word stays quiet; the octant is the one that carries a colour
    _ct(word, cx, y + 15, P["DIM"], "small")
    _ct(octant, cx, y + 26, pen, "small")
    _bar(x + 5, y + PLATE_H - 6, w - 10, 3,
         who.model.strength() / occ.SQRT3, pen)


def _emotion_pill(who, cx):
    """What they are feeling right now, if anything is above ALMA's baseline.
    It sits on their chest rather than in the name tag: the mood is what they
    are, the emotion is what is happening to them."""
    hot = who.dominant()
    if hot is None:
        return
    pen = octant_pen(occ.octant_of(*hot.pad()))
    label = "%s %.0f%%" % (hot.name.upper(), hot.intensity * 100)
    w = _tw(label, "small") + 12
    y = cfg.FEET_Y - FIG_H + 44
    _panel(cx - w / 2, y, w, M["small"] + 6, P["BG"])
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(cx - w / 2, y, w, M["small"] + 6,
                                         3).stroke(1))
    _ct(label, cx, y + 3, pen, "small")


def _resident(who, i, cx, now, selected):
    _pool(who, cx)
    _hit(who, cx, now)
    # Pleasure lifts them and displeasure sinks them, by a couple of pixels -
    # not a pose, just posture.
    lift = int(who.model.mood[0] * 2.0)
    screen.blit(who.pose[breath(who, i, now)],
                rect(cx - FIG_W // 2, cfg.FEET_Y - FIG_H - lift,
                     FIG_W, FIG_H))
    _plate(who, cx, selected)
    _emotion_pill(who, cx)


# ---- header ----------------------------------------------------------------
def _header(w, ui, title):
    _fill(0, 0, cfg.W, cfg.HEADER_H, P["PANEL"])
    _rule(0, cfg.HEADER_H, cfg.W)
    _t(title, 6, 1, P["INK"])
    _ct(w.clock(), cfg.W // 2, 1, P["DIM"], "small")
    x = cfg.W - 6
    if w.auto:
        _rt("AUTO", x, 1, P["ACCENT"], "small")
        x -= _tw("AUTO", "small") + 8
    _rt("x%d" % w.speed(), x, 1, P["INK"], "small")


# ---- the event rail --------------------------------------------------------
def _payload(label, pairs, x, y, wmax):
    _t(label, x, y, P["FAINT"], "small")
    x += _tw("ROOM ", "small")
    for n, (name, intensity) in enumerate(pairs):
        s = "%s %.2f" % (name, intensity)
        if x + _tw(s, "small") > wmax:
            _t("+%d" % (len(pairs) - n), x, y, P["FAINT"], "small")
            return
        _t(s, x, y, octant_pen(occ.octant_of(*occ.EMOTIONS[name])), "small")
        x += _tw(s, "small") + 6


def _rail(w, ui):
    """What will happen, to whom, and to everyone else - the OCC payload spelled
    out, because the whole claim of the app is that those two are different."""
    y0 = cfg.RAIL_TOP
    _fill(0, y0, cfg.W, cfg.RAIL_H, P["PANEL"])
    _rule(0, y0, cfg.W)

    i = ui["event"]
    label, mine, theirs = events.EVENTS[i]
    who = w.people[ui["who"]]

    _tri(9, y0 + 6, 4, True, P["DIM"])
    _tri(9, y0 + 13, 4, False, P["DIM"])

    count = "%d/%d" % (i + 1, len(events.EVENTS))
    _rt(count, cfg.W - 6, y0 + 4, P["DIM"], "small")
    _t(who.name, 20, y0 + 3, P["ACCENT"])
    x = 20 + _tw(who.name) + 6
    _t(_fit(label, cfg.W - 30 - _tw(count, "small") - x), x, y0 + 3, P["INK"])

    _payload("THEM", mine, 20, y0 + 20, cfg.W - 8)
    _payload("ROOM", theirs, 20, y0 + 32, cfg.W - 8)


# ---- the hint bar ----------------------------------------------------------
def _hints(pairs):
    """What each button does right now. Spread evenly, key in accent."""
    _fill(0, cfg.HINT_TOP, cfg.W, cfg.H - cfg.HINT_TOP, P["BG"])
    _rule(0, cfg.HINT_TOP, cfg.W)
    widths = [_tw(k, "small") + 4 + _tw(v, "small") for k, v in pairs]
    gap = max(3, (cfg.W - sum(widths)) // (len(pairs) + 1))
    y = cfg.HINT_TOP + (cfg.H - cfg.HINT_TOP - M["small"]) // 2
    x = gap
    for key, what in pairs:
        _t(key, x, y, P["ACCENT"], "small")
        x += _tw(key, "small") + 4
        _t(what, x, y, P["DIM"], "small")
        x += _tw(what, "small") + gap


WORLD_HINTS = (("UP/DN", "EVENT"), ("B", "WHO"), ("C", "DO IT"),
               ("A", "VIEW"), ("HOLD B", "SPEED"))
LOG_HINTS = (("UP/DN", "SCROLL"), ("C", "AUTO"), ("B", "WHO"),
             ("A", "VIEW"), ("HOLD A", "NEW WORLD"))
GUIDE_HINTS = (("UP/DN", "SCROLL"), ("C", "TOP"), ("A", "BACK"),
               ("HOLD A", "NEW WORLD"))
SETUP_HINTS = (("UP/DN", "ROW"), ("A/C", "VALUE"), ("B", "NEW BODY"),
               ("HOLD B", "BEGIN"))


# ---- the world view --------------------------------------------------------
def _view_world(w, ui, now):
    _stage_wall()
    for i, who in enumerate(w.people):
        _aura(who, cfg.COLUMN[i])
    _stage_floor()
    for i, who in enumerate(w.people):
        _resident(who, i, cfg.COLUMN[i], now, i == ui["who"])
    _rail(w, ui)
    _hints(WORLD_HINTS)


# ---- one resident, in detail ----------------------------------------------
_range = 1.0


def _plot(p, a):
    return (cfg.PLOT_X + (p / _range + 1.0) * 0.5 * cfg.PLOT_S,
            cfg.PLOT_Y + (1.0 - a / _range) * 0.5 * cfg.PLOT_S)


def _pad_map(who):
    """Pleasure across, arousal up; dominance is the size of the mood dot, so
    all three axes are on one square.

    The hollow ring is where their personality parks them, the cross is where
    the active emotions are pulling, the fading dots are the path they took.
    None of it is labelled on the plot - at 140 pixels square there is no room,
    and the guide says which is which."""
    p, a, d = who.model.mood
    cx, cy = _plot(0.0, 0.0)
    _panel(cfg.PLOT_X, cfg.PLOT_Y, cfg.PLOT_S, cfg.PLOT_S)

    # wash the quadrant the mood is in, so the octant reads before the numbers
    _fill(cx if p >= 0 else cfg.PLOT_X, cfg.PLOT_Y if a >= 0 else cy,
          cfg.PLOT_S / 2, cfg.PLOT_S / 2, OP[who.model.octant()]["tint"])
    _fill(cfg.PLOT_X, cy, cfg.PLOT_S, 1, P["EDGE"])
    _fill(cx, cfg.PLOT_Y, 1, cfg.PLOT_S, P["EDGE"])
    screen.pen = P["EDGE"]
    screen.shape(shape.rounded_rectangle(cfg.PLOT_X, cfg.PLOT_Y, cfg.PLOT_S,
                                         cfg.PLOT_S, 3).stroke(1))
    _t("+A", cx + 3, cfg.PLOT_Y + 2, P["FAINT"], "small")
    _rt("+P", cfg.PLOT_X + cfg.PLOT_S - 3, cy + 2, P["FAINT"], "small")

    pens = OP[who.model.octant()]
    # where they always end up
    bx, by = _plot(who.model.default_mood[0], who.model.default_mood[1])
    _ring(bx, by, 5, 1, P["DIM"])

    # where the active emotions are pulling them
    if who.model.vec is not None:
        vx, vy = _plot(who.model.vec[0], who.model.vec[1])
        _fill(vx - 4, vy, 9, 1, P["VEC"])
        _fill(vx, vy - 4, 1, 9, P["VEC"])

    # the path they took to get here
    trail = who.trail
    for n, (tp, ta, _ms) in enumerate(trail):
        tx, ty = _plot(tp, ta)
        _fill(tx, ty, 1, 1, pens["fade"][_level(1.0 - n / max(1, len(trail)), 4)])

    # the mood itself: dominance is its size
    mx, my = _plot(p, a)
    _ellipse(mx, my, 6 + 5 * (d + 1.0), 6 + 5 * (d + 1.0), pens["body"])


def _view_detail(w, ui, now):
    who = w.people[ui["who"]]
    _fill(0, cfg.HEADER_H + 1, cfg.W, cfg.RAIL_TOP - cfg.HEADER_H - 1, P["BG"])
    _pad_map(who)

    x, y = cfg.COL2_X, cfg.PLOT_Y
    wide = cfg.W - 6 - x
    _t(who.archetype_name(), x, y - 2, P["ACCENT"])
    _rt(affect.PHASE_NAMES[who.model.phase], cfg.W - 6, y, P["VEC"], "small")
    y += 16
    for trait in cfg.TRAITS:
        _t(cfg.TRAIT_SHORT[trait], x, y, P["DIM"], "small")
        _bipolar(x + 36, y + 2, wide - 36 - 32, 5,
                 who.model.personality[trait], P["VEC"])
        _rt(_sign(who.model.personality[trait]), cfg.W - 6, y, P["DIM"], "small")
        y += 11
    y += 1
    _rule(x, y, wide)
    y += 3

    word, octant = who.state()
    _t(word, x, y, P["DIM"], "small")
    _rt(octant, cfg.W - 6, y, octant_pen(octant), "small")
    y += 13
    for n, letter in enumerate("PAD"):
        _t(letter, x, y, P["FAINT"], "small")
        _bipolar(x + 12, y + 2, wide - 12 - 34, 5, who.model.mood[n],
                 octant_pen(octant))
        _rt(_sign(who.model.mood[n]), cfg.W - 6, y, P["INK"], "small")
        y += 11
    _rule(x, y, wide)
    y += 3

    # What they are feeling, strongest first. Two rows is what fits, and two is
    # enough: a third emotion is already folded into the cross on the plot.
    hot = who.model.by_intensity()
    if not hot:
        _t("no emotion active", x, y, P["FAINT"], "small")
    for e in hot[:2]:
        pen = octant_pen(occ.octant_of(*e.pad()))
        _t(_fit(e.name, wide - 44, "small"), x, y, pen, "small")
        _bar(cfg.W - 6 - 38, y + 3, 38, 4, e.intensity, pen)
        y += 11

    _rail(w, ui)
    _hints(WORLD_HINTS)


# ---- the log ---------------------------------------------------------------
def log_rows_visible():
    return (cfg.HINT_TOP - cfg.LOG_Y) // cfg.LOG_ROW_H


def log_max_scroll(w):
    return max(0, len(w.log) - log_rows_visible())


def _view_log(w, ui, now):
    _fill(0, cfg.HEADER_H + 1, cfg.W, cfg.HINT_TOP - cfg.HEADER_H - 1, P["BG"])
    if not w.log:
        _ct("nothing has happened yet", cfg.W // 2, 80, P["FAINT"])
        _ct("C lets the room run itself", cfg.W // 2, 98, P["DIM"], "small")
    top = min(ui["log"], log_max_scroll(w))
    for n in range(log_rows_visible()):
        i = top + n
        if i >= len(w.log):
            break
        sim_ms, actor, event, scheduled = w.log[i]
        y = cfg.LOG_Y + n * cfg.LOG_ROW_H
        if n % 2 == 0:
            _fill(0, y - 2, cfg.W, cfg.LOG_ROW_H, P["PANEL"])
        s = int(sim_ms // 1000)
        _t("%d:%02d:%02d" % (s // 3600, (s // 60) % 60, s % 60), 6, y + 1,
           P["FAINT"], "small")
        who = w.people[actor]
        _t(who.name, 58, y, P["ACCENT"] if not scheduled else P["VEC"])
        _t(_fit(events.label(event), cfg.W - 116), 106, y,
           P["INK"] if not scheduled else P["DIM"])
        if scheduled:
            _rt("auto", cfg.W - 6, y + 1, P["FAINT"], "small")
    _hints(LOG_HINTS)


# ---- the guide -------------------------------------------------------------
GUIDE_ROW_H = 13


def guide_rows_visible():
    return (cfg.HINT_TOP - cfg.LOG_Y) // GUIDE_ROW_H


def guide_max_scroll():
    return max(0, len(cfg.GUIDE) - guide_rows_visible())


def _view_guide(w, ui, now):
    _fill(0, cfg.HEADER_H + 1, cfg.W, cfg.HINT_TOP - cfg.HEADER_H - 1, P["BG"])
    top = min(ui["guide"], guide_max_scroll())
    for n in range(guide_rows_visible()):
        i = top + n
        if i >= len(cfg.GUIDE):
            break
        kind, left, right = cfg.GUIDE[i]
        y = cfg.LOG_Y + n * GUIDE_ROW_H
        if kind == "h":
            _t(left, 6, y, P["ACCENT"], "small")
            _rule(6 + _tw(left, "small") + 6, y + 5, cfg.W - 12
                  - _tw(left, "small") - 6)
        elif kind == "o":
            _fill(8, y + 2, 9, 7, octant_pen(left))
            _t(left, 22, y, P["INK"], "small")
            _rt(right, cfg.W - 8, y, P["DIM"], "small")
        elif kind == "t":
            _t(left, 8, y, P["DIM"], "small")
            _t(right, 130, y, P["INK"], "small")
    _hints(GUIDE_HINTS)


# ---- setup -----------------------------------------------------------------
SETUP_ROWS = 1 + len(cfg.TRAITS)          # archetype, then the five traits
SET_COLUMN = (28, 78, 128)
SET_FEET = 148


def _setup_trio(w, ui, now):
    """The three of them, small, each already standing in the light their
    personality implies - which is the whole reason to choose one."""
    for i, who in enumerate(w.people):
        cx = SET_COLUMN[i]
        here = i == ui["who"]
        _cone(cx, SET_FEET, SET_FEET - cfg.HEADER_H - 8,
              OP[who.model.octant()]["glow"],
              cfg.AURA_MIN + (1.0 - cfg.AURA_MIN)
              * min(1.0, who.model.strength() / occ.SQRT3), 46)
        if who.pose:
            screen.blit(who.pose[sprites.STAND],
                        rect(cx - SET_W // 2, SET_FEET - SET_H, SET_W, SET_H))
        _fill(cx - 22, SET_FEET, 44, 2,
              P["ACCENT"] if here else OP[who.model.octant()]["dark"])
        _ct(who.name, cx, SET_FEET + 5, P["INK"] if here else P["DIM"])
        _ct(who.archetype_name(), cx, SET_FEET + 20,
            octant_pen(who.model.octant()) if here else P["DIM"], "small")


def _setup_sheet(w, ui):
    """The selected resident's personality, and the baseline it implies."""
    who = w.people[ui["who"]]
    x, y = 164, 22
    wide = cfg.W - 6 - x
    _panel(x - 6, y - 4, wide + 12, 186)

    rows = [("ARCHETYPE", who.archetype_name(), None)]
    rows += [(cfg.TRAIT_SHORT[t], _sign(who.model.personality[t]),
              who.model.personality[t]) for t in cfg.TRAITS]
    for n, (label, value, bipolar) in enumerate(rows):
        ry = y + n * 17
        here = n == ui["row"]
        if here:
            _fill(x - 3, ry - 2, wide + 6, 16, P["EDGE"])
        _t(label, x, ry, P["INK"] if here else P["DIM"], "small")
        if bipolar is None:
            _rt(value, cfg.W - 8, ry - 1, P["ACCENT"] if here else P["INK"])
        else:
            _bipolar(x + 46, ry + 3, 54, 5, bipolar,
                     P["ACCENT"] if here else P["VEC"])
            _rt(value, cfg.W - 8, ry, P["INK"] if here else P["DIM"], "small")

    ry = y + SETUP_ROWS * 17 + 6
    _rule(x, ry, wide)
    ry += 6
    word, octant = who.state()
    _t("BASELINE", x, ry, P["FAINT"], "small")
    ry += 12
    _t("%s" % word, x, ry, P["DIM"], "small")
    _t(octant, x, ry + 11, octant_pen(octant))
    ry += 26
    for n, letter in enumerate("PAD"):
        _t(letter, x, ry, P["FAINT"], "small")
        _bipolar(x + 12, ry + 2, wide - 46, 5, who.model.default_mood[n],
                 octant_pen(octant))
        _rt(_sign(who.model.default_mood[n]), cfg.W - 8, ry, P["DIM"], "small")
        ry += 11


def draw_setup(w, ui, now):
    _fill(0, 0, cfg.W, cfg.H, P["BG"])
    _fill(0, 0, cfg.W, cfg.HEADER_H, P["PANEL"])
    _rule(0, cfg.HEADER_H, cfg.W)
    _t("A NEW WORLD", 6, 1, P["INK"])
    _rt("three people who have not met", cfg.W - 6, 1, P["DIM"], "small")
    _setup_trio(w, ui, now)
    # The one thing that is worth knowing before you press it.
    _ct("A PERSONALITY IS FIXED", 78, 188, P["FAINT"], "small")
    _ct("ONCE THE WORLD BEGINS", 78, 200, P["FAINT"], "small")
    _setup_sheet(w, ui)
    _hints(SETUP_HINTS)


# ---- entry point -----------------------------------------------------------
VIEWS = (_view_world, _view_detail, _view_log, _view_guide)


def draw(w, ui, now):
    view = ui["view"]
    title = cfg.VIEW_NAMES[view]
    if view == cfg.V_DETAIL:
        title = w.people[ui["who"]].name
    _header(w, ui, title)
    VIEWS[view](w, ui, now)
