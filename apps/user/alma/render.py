# All drawing for the ALMA affect simulation - 320x240 HIRES.
#
# Device globals (screen, color, shape, pixel_font, ...) are only touched
# inside functions, so this module imports cleanly off-device; __init__ calls
# init() once after badge.mode(HIRES) to bake pens, fonts and metrics.
#
# Everything is built from screen.rectangle / shape.rounded_rectangle /
# shape.line, which means the mood orb squashes and stretches without needing
# transforms, and the desktop simulator draws it exactly as the badge does.

import math

import affect
import config as cfg
import occ
import stimuli

P = {}    # pens by theme name
OP = {}   # octant name -> its baked pen set (see _bake_octant_pens)
F = {}    # fonts
M = {}    # metrics

# Blink timing for the character's single lens-eye: a deterministic pseudo
# sequence so the badge needs no RNG and the idle loop stays reproducible.
BLINK_MIN_MS = 2200
BLINK_JITTER_MS = 2600
BLINK_LEN_MS = 130

# The stimulus strength the DYNAMICS view quotes its impact figure against -
# about what the stimulus table actually elicits.
SAMPLE_INTENSITY = 0.80


def init():
    for name, rgb in cfg.THEME.items():
        P[name] = color.rgb(*rgb)
    _bake_octant_pens()
    # Size hierarchy chosen with the fonttest app (see the repo's font notes):
    #   body - nope     (~h13) : everything by default
    #   mid  - smart    (~h16) : the dominant emotion, trait names
    #   big  - bacteria (~h20) : the mood word on the character screen
    F["body"] = pixel_font.load("/system/assets/fonts/nope.ppf")
    F["mid"] = pixel_font.load("/system/assets/fonts/smart.ppf")
    F["big"] = pixel_font.load("/system/assets/fonts/bacteria.ppf")
    # measure_text returns FLOATS on-device; keep the metrics int.
    for key in ("body", "mid", "big"):
        screen.font = F[key]
        M[key + "_h"] = int(screen.measure_text("0")[1])
    screen.font = F["body"]


def _shade(rgb, k):
    """Scale an RGB triple towards black (k<1) or white (k>1)."""
    if k <= 1.0:
        return tuple(int(c * k) for c in rgb[:3])
    return tuple(min(255, int(c + (255 - c) * (k - 1.0))) for c in rgb[:3])


def _blend(fg, bg, a):
    """Composite fg over bg at alpha a (0-255), in software, once."""
    return tuple(int(bg[i] + (fg[i] - bg[i]) * a / 255.0) for i in range(3))


def _level(frac, n):
    """Quantise 0..1 onto one of n baked steps."""
    i = int(frac * (n - 1) + 0.5)
    return 0 if i < 0 else (n - 1 if i > n - 1 else i)


def octant_pen(name):
    """The solid body colour for a mood octant."""
    return OP[name]["body"]


# Every pen the app can ever need, baked once at startup.
#
# Nothing here is translucent. The badge would have to alpha-composite a
# translucent pen per pixel, every frame, over shapes as large as the
# character's halo - and the faded trail dots used to mint a new pen per fade
# step per octant at draw time, which on a microcontroller is an allocation
# storm and a GC pause in the middle of a frame. Since the background behind
# every faded element is known and fixed, the blend is done here in software,
# once, and the draw calls get flat opaque colours.
FADE_STEPS = 6      # trail / active-emotion dot fades, faintest first
HALO_STEPS = 5      # the character's halo, by mood strength


def _bake_octant_pens():
    bg = cfg.THEME["BG"]
    panel = cfg.THEME["PANEL"]
    for name, rgb in cfg.OCTANT_COLORS.items():
        body = tuple(rgb)
        OP[name] = {
            "body": color.rgb(*body),
            "dark": color.rgb(*_shade(rgb, 0.58)),
            "lit": color.rgb(*_shade(rgb, 1.75)),
            # the orb's specular sits on the body, so blend against that
            "hi": color.rgb(*_blend(_shade(rgb, 1.35), body, 105)),
            # the PAD map's octant wash sits on the plot panel
            "tint": color.rgb(*_blend(rgb, panel, 26)),
            "halo": [color.rgb(*_blend(rgb, bg, 55 + int(120 * i
                                                         / (HALO_STEPS - 1))))
                     for i in range(HALO_STEPS)],
            "fade": [color.rgb(*_blend(rgb, panel, 40 + int(215 * i
                                                            / (FADE_STEPS - 1))))
                     for i in range(FADE_STEPS)],
        }


# ---- text helpers ----------------------------------------------------------
def _t(s, x, y, pen):
    screen.pen = pen
    screen.text(s, int(x), int(y))


def _tw(s):
    return int(screen.measure_text(s)[0])


def _rt(s, right, y, pen):
    _t(s, right - _tw(s), y, pen)


def _ct(s, cx, y, pen):
    _t(s, cx - _tw(s) / 2, y, pen)


def _fit(s, wmax):
    """Trim s to wmax pixels; a trailing '.' marks the cut."""
    if _tw(s) <= wmax:
        return s
    while s and _tw(s + ".") > wmax:
        s = s[:-1]
    return s + "." if s else ""


def _sign(v):
    return "%+.2f" % v


def _secs(ms):
    """A duration as 45s / 2m / 6m30 - short enough for a right-aligned cell."""
    total = int(ms / 1000 + 0.5)
    if total < 60:
        return "%ds" % total
    m, sec = total // 60, total % 60
    return "%dm" % m if sec == 0 else "%dm%02d" % (m, sec)


def _param_text(entry):
    name, label, unit, ladder, paper = entry
    v = cfg.param_value(name)
    return _secs(v) if unit == cfg.SECONDS else "%.2f" % v


# ---- primitives ------------------------------------------------------------
def _ellipse(cx, cy, w, h, pen):
    """A filled ellipse, approximated by a fully-rounded rectangle.

    The corner radius is kept strictly BELOW half the short side. At exactly
    half, the rounded rectangle is degenerate - the corners meet - and the
    badge intermittently gives up and draws a plain rectangle instead. Since
    the character breathes, w and h change every frame, so sitting on that
    boundary meant landing a hair over it on some frames and flashing a hard
    rectangle around the orb. Half a pixel of slack is invisible and stable.
    """
    w, h = max(1.0, w), max(1.0, h)
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(cx - w / 2, cy - h / 2, w, h,
                                         max(0.5, min(w, h) / 2 - 0.5)))


def _ring(cx, cy, r, thick, pen):
    """A hollow circle. Uses shape.circle rather than a stroked rounded
    rectangle - the same reason as above, and it is what the factory apps do."""
    screen.pen = pen
    screen.shape(shape.circle(cx, cy, max(1.0, r)).stroke(thick))


def _dot(cx, cy, r, pen):
    _ellipse(cx, cy, r * 2, r * 2, pen)


def _fill(x, y, w, h, pen):
    if w <= 0 or h <= 0:
        return
    screen.pen = pen
    screen.rectangle(int(x), int(y), int(w), int(h))


def _rule(x, y, w, pen=None):
    _fill(x, y, w, 1, pen or P["EDGE"])


def _panel(x, y, w, h):
    screen.pen = P["PANEL"]
    screen.shape(shape.rounded_rectangle(x, y, w, h, 3))


def _bar(x, y, w, h, frac, pen):
    """Left-anchored fill, for quantities that run 0..1."""
    _fill(x, y, w, h, P["TRACK"])
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    _fill(x, y, w * frac, h, pen)


def _bipolar(x, y, w, h, v, pen):
    """Centre-anchored fill, for PAD axes and traits that run -1..+1."""
    _fill(x, y, w, h, P["TRACK"])
    cx = x + w / 2
    v = -1.0 if v < -1 else (1.0 if v > 1 else v)
    span = (w / 2) * abs(v)
    if v >= 0:
        _fill(cx, y, span, h, pen)
    else:
        _fill(cx - span, y, span, h, pen)
    _fill(cx, y - 1, 1, h + 2, P["DIM"])   # the zero point


def _tri(cx, y, size, up, pen):
    """A small solid triangle, stacked from rows (no polygon primitive needed)."""
    screen.pen = pen
    for i in range(size):
        half = i if up else size - 1 - i
        _fill(cx - half, y + i, half * 2 + 1, 1, pen)


# ---- header ----------------------------------------------------------------
def _header(model, ui):
    _fill(0, 0, cfg.W, cfg.HEADER_H, P["PANEL"])
    _rule(0, cfg.HEADER_H, cfg.W)
    screen.font = F["body"]
    y = (cfg.HEADER_H - M["body_h"]) // 2

    _t("ALMA", 4, y, P["ACCENT"])

    word, oct_name = model.mood_words()
    pen = octant_pen(oct_name)
    _dot(40, cfg.HEADER_H / 2, 3.5, pen)
    _t("%s %s" % (word.upper(), oct_name.upper()), 48, y, pen)

    scale = cfg.TIME_SCALES[ui["scale"]]
    label = "x%d" % scale
    _rt(label, cfg.W - 4, y, P["ACCENT"] if scale > 1 else P["DIM"])
    _rt(cfg.VIEW_NAMES[ui["view"]], cfg.W - 9 - _tw(label), y, P["DIM"])


# ---- bottom rail -----------------------------------------------------------
def _rail(model, ui):
    y0 = cfg.RAIL_Y
    _fill(0, y0, cfg.W, cfg.RAIL_H, P["PANEL"])
    _rule(0, y0, cfg.W)
    screen.font = F["body"]

    if ui["view"] == cfg.V_GUIDE:
        _t("LEGEND & CONTROLS", 6, y0 + 5, P["DIM"])
        _rt("%d/%d" % (ui["guide"] + 1, guide_max_scroll() + 1),
            cfg.W - 6, y0 + 5, P["DIM"])
        _t("UP/DN SCROLL", 6, y0 + 21, P["DIM"])
        _rt("C:TOP  A:BACK TO CHARACTER", cfg.W - 6, y0 + 21, P["ACCENT"])
        return

    if ui["view"] in cfg.EDIT_VIEWS:
        if ui["view"] == cfg.V_PERSONALITY:
            what = cfg.TRAIT_LABELS[cfg.TRAITS[ui["trait"]]]
            keys = "B:TRAIT  C:RESEED"
        else:
            what = cfg.DYNAMICS[ui["param"]][1]
            keys = "B:PARAM  C:PAPER"
        _t("EDITING", 6, y0 + 5, P["DIM"])
        _t(what, 6 + _tw("EDITING "), y0 + 5, P["ACCENT"])
        _t("UP/DN ADJUST", 6, y0 + 21, P["DIM"])
        _rt(keys, cfg.W - 6, y0 + 21, P["ACCENT"])
        return

    i = ui["stim"]
    label, pairs = stimuli.STIMULI[i]

    # cursor chevrons on the left, mirroring the UP/DOWN buttons
    _tri(9, y0 + 7, 5, True, P["DIM"])
    _tri(9, y0 + 24, 5, False, P["DIM"])

    count = "%d/%d" % (i + 1, len(stimuli.STIMULI))
    _rt(count, cfg.W - 6, y0 + 5, P["DIM"])
    _t(_fit(label, cfg.W - 30 - _tw(count)), 20, y0 + 5, P["INK"])

    # the emotions this stimulus would elicit, tinted by where each one sits
    x = 20
    for n, (name, intensity) in enumerate(pairs):
        if n:
            _t("+", x, y0 + 21, P["FAINT"])
            x += _tw("+ ")
        pen = octant_pen(occ.octant_of(*occ.EMOTIONS[name]))
        s = "%s %.2f" % (name, intensity)
        _t(s, x, y0 + 21, pen)
        x += _tw(s) + 4
    _rt("C:APPLY (HOLD)", cfg.W - 6, y0 + 21, P["ACCENT"])


# ---- the character ---------------------------------------------------------
# Blink schedule: the moment the next blink starts, advanced in place. An LCG
# keeps the rhythm irregular without importing a random module, and keeps this
# O(1) per frame however long the badge has been running.
_blink_at = BLINK_MIN_MS
_blink_seed = 0x2545F491


def _blink_scale(now):
    """1.0 with the eye open, closing to 0 and back through a blink."""
    global _blink_at, _blink_seed
    if now >= _blink_at + BLINK_LEN_MS:
        _blink_seed = (1103515245 * _blink_seed + 12345) & 0x7FFFFFFF
        _blink_at = now + BLINK_MIN_MS + (_blink_seed % BLINK_JITTER_MS)
        return 1.0
    if now < _blink_at:
        return 1.0
    k = (now - _blink_at) / BLINK_LEN_MS       # 0..1 through the blink
    return abs(math.cos(k * math.pi))


def draw_character_orb(model, cx, cy, now, max_r=42):
    """The character: an idling orb whose whole look is read off its mood.

    colour  <- the mood octant           size    <- dominance
    stretch <- pleasure (droop vs lift)  breath  <- arousal (rate + sway)
    """
    p, a, d = model.mood
    oct_name = model.octant()
    pens = OP[oct_name]
    body, dark, lit = pens["body"], pens["dark"], pens["lit"]

    t = now / 1000.0
    # Arousal sets the metabolism: an aroused character breathes fast and sways.
    freq = 0.45 + 0.95 * (a + 1.0) / 2.0
    breath = math.sin(2.0 * math.pi * freq * t)
    sway = math.sin(2.0 * math.pi * freq * 0.37 * t)
    # A jitter that only appears on the aroused half of the axis.
    jitter = max(0.0, a) * 1.6 * math.sin(2.0 * math.pi * 3.1 * t)

    # Dominance sets how much space the character takes up.
    r = max_r * (0.58 + 0.42 * (d + 1.0) / 2.0)
    # Pleasure lifts and narrows; displeasure squats and spreads.
    sy = 1.0 + 0.20 * p + 0.055 * breath
    sx = 1.0 - 0.11 * p - 0.055 * breath
    w, h = 2 * r * sx, 2 * r * sy

    ox = sway * (1.5 + 2.5 * (a + 1.0) / 2.0) + jitter
    oy = -2.2 * breath - 3.0 * p          # low pleasure sinks towards the floor
    bx, by = cx + ox, cy + oy

    floor = cy + max_r + 6

    # The character stands on a faint pad, so its contact shadow has something
    # to darken - a black shadow on a near-black panel would be invisible.
    _ellipse(cx, floor, w * 0.98, 9, P["PANEL"])
    _ellipse(cx + ox * 0.35, floor, w * 0.66, 6, P["SHADOW"])

    # Halo: how far the mood is from the PAD zero point, i.e. its strength.
    # Drawn as a FILLED ellipse slightly larger than the body - the body is
    # painted over it a moment later, so what survives is a ring. That avoids
    # stroking a shape whose size changes every frame, which is what produced
    # the rectangular flash on the badge.
    strength = model.strength() / occ.SQRT3
    halo = 5 + 9 * strength
    _ellipse(bx, by, w + halo, h + halo,
             pens["halo"][_level(strength, HALO_STEPS)])

    # Lit from above: the shadowed body first, then the main colour offset up
    # so a crescent of shade survives along the bottom, then a soft highlight.
    _ellipse(bx, by, w, h, dark)
    _ellipse(bx, by - h * 0.075, w * 0.90, h * 0.85, body)
    _ellipse(bx - w * 0.23, by - h * 0.29, w * 0.28, h * 0.17, pens["hi"])

    # A single lens-eye: no face, but unmistakably somebody home. Pleasure
    # opens it, displeasure narrows it to a wary slit.
    ew = w * 0.42
    eh = h * 0.30 * (0.34 + 0.52 * (p + 1.0) / 2.0) * _blink_scale(now)
    ey = by - h * 0.07
    _ellipse(bx, ey, ew, max(1.5, eh), lit)
    if eh > 3.0:
        # the pupil drifts towards wherever the mood is heading
        px = bx + (0.16 * ew) * (1.0 if p >= 0 else -1.0)
        _ellipse(px, ey, ew * 0.34, min(eh * 0.8, ew * 0.34), P["BG"])


def _view_character(model, ui, now):
    y0 = cfg.BODY_Y
    split = 160

    draw_character_orb(model, 80, y0 + 74, now)

    screen.font = F["body"]
    phase = affect.PHASE_NAMES[model.phase]
    _ct("IDLE", 80, y0 + 132, P["DIM"])
    _ct("MOOD " + phase, 80, y0 + 148,
        P["ACCENT"] if model.phase != affect.IDLE else P["FAINT"])
    _ct("A VIEW   B SPEED", 80, y0 + 166, P["FAINT"])

    _fill(split, y0, 1, cfg.BODY_H, P["EDGE"])

    # --- PAD readouts
    px = split + 8
    pw = cfg.W - px - 6
    oct_pen = octant_pen(model.octant())
    for n, (letter, name) in enumerate((("P", "PLEASURE"),
                                        ("A", "AROUSAL"),
                                        ("D", "DOMINANCE"))):
        ry = y0 + 2 + n * 26
        v = model.mood[n]
        _t(letter, px, ry, P["INK"])
        _t(name, px + 12, ry, P["DIM"])
        _rt(_sign(v), px + pw, ry, P["INK"])
        _bipolar(px, ry + 14, pw, 4, v, oct_pen)

    _rule(px, y0 + 84, pw)

    # --- dominant emotion (ALMA reports one only above its baseline)
    _t("DOMINANT EMOTION", px, y0 + 90, P["DIM"])
    dom = model.dominant()
    if dom is None:
        screen.font = F["mid"]
        _t("none", px, y0 + 104, P["FAINT"])
        screen.font = F["body"]
        _t("nothing above baseline %.2f" % cfg.EMOTION_BASELINE,
           px, y0 + 120, P["FAINT"])
    else:
        epen = octant_pen(occ.octant_of(*occ.EMOTIONS[dom.name]))
        screen.font = F["mid"]
        _t(_fit(dom.name, pw - 40), px, y0 + 103, epen)
        _rt("%.2f" % dom.intensity, px + pw, y0 + 103, P["INK"])
        screen.font = F["body"]
        _bar(px, y0 + 124, pw, 4, dom.intensity, epen)

    _rule(px, y0 + 136, pw)

    # --- mood strength, with the slightly/moderate/fully boundaries marked
    word, oct_name = model.mood_words()
    _t("MOOD STRENGTH", px, y0 + 142, P["DIM"])
    _rt("%.2f" % model.strength(), px + pw, y0 + 142, P["INK"])
    by = y0 + 156
    _bar(px, by, pw, 5, model.strength() / occ.SQRT3, oct_pen)
    for limit in (cfg.MOOD_SLIGHT_MAX, cfg.MOOD_MODERATE_MAX):
        _fill(px + pw * (limit / occ.SQRT3), by - 2, 1, 9, P["DIM"])
    _t(word, px, by + 8, P["DIM"])
    _rt("%d active" % len(model.active), px + pw, by + 8, P["DIM"])


# ---- PAD map ---------------------------------------------------------------
# The plot fills the whole body height; the readouts get what is left.
PLOT_X, PLOT_Y, PLOT_S = 4, 21, 176

# Almost nothing in ALMA reaches the corners of PAD space - the strongest
# emotion in Table 2 is Fear at -0.64, and a mood only passes 0.8 on an axis
# after a sustained push. Drawing the full -1..1 range therefore wastes most
# of the plot and leaves the interesting movement crammed into the middle.
#
# So the view zooms, in two discrete steps, with hysteresis so it does not
# flip back and forth mid-animation. Nothing is ever clipped: if any point
# needs the full range, the full range is what gets drawn.
ZOOM_NEAR, ZOOM_FAR = 0.8, 1.0
ZOOM_OUT_AT, ZOOM_IN_AT = 0.78, 0.72
_range = ZOOM_NEAR


def _autoscale(points):
    """Pick the visible range from the extremes actually on screen."""
    global _range
    peak = 0.0
    for p, a in points:
        peak = max(peak, abs(p), abs(a))
    if peak > ZOOM_OUT_AT:
        _range = ZOOM_FAR
    elif peak < ZOOM_IN_AT:
        _range = ZOOM_NEAR
    return _range


def _plot(p, a):
    """PAD (pleasure, arousal) -> pixel, with +arousal upwards."""
    return (PLOT_X + (p / _range + 1.0) * 0.5 * PLOT_S,
            PLOT_Y + (1.0 - a / _range) * 0.5 * PLOT_S)


def _pad_rows(x, w, y, values, pen):
    """Three right-aligned P / A / D rows - used for the mood and the center."""
    for n, letter in enumerate("PAD"):
        ry = y + n * 12
        _t(letter, x, ry, P["DIM"])
        _rt(_sign(values[n]), x + w, ry, pen)


def _view_padmap(model, ui, now):
    y0 = cfg.BODY_Y
    p, a, d = model.mood
    trail = ui["trail"]

    # Scale to what is actually on screen before plotting anything.
    extremes = [(p, a), (model.default_mood[0], model.default_mood[1])]
    if model.vec is not None:
        extremes.append((model.vec[0], model.vec[1]))
    for tp, ta, td in trail:
        extremes.append((tp, ta))
    rng = _autoscale(extremes)

    cx, cy = _plot(0.0, 0.0)
    _panel(PLOT_X, PLOT_Y, PLOT_S, PLOT_S)

    # tint the quadrant the mood currently occupies (its P/A half of the octant)
    qx = cx if p >= 0 else PLOT_X
    qy = PLOT_Y if a >= 0 else cy
    screen.pen = OP[model.octant()]["tint"]
    screen.rectangle(int(qx), int(qy), int(PLOT_S / 2), int(PLOT_S / 2))

    # half-unit gridlines, so the zoom level is legible at a glance
    for g in (-0.5, 0.5):
        gx, gy = _plot(g, g)
        if PLOT_X < gx < PLOT_X + PLOT_S:
            _fill(gx, PLOT_Y + 2, 1, PLOT_S - 4, P["PANEL"])
            _fill(PLOT_X + 2, gy, PLOT_S - 4, 1, P["PANEL"])

    # axes + frame
    _fill(PLOT_X, cy, PLOT_S, 1, P["EDGE"])
    _fill(cx, PLOT_Y, 1, PLOT_S, P["EDGE"])
    screen.pen = P["EDGE"]
    screen.shape(shape.rounded_rectangle(PLOT_X, PLOT_Y, PLOT_S, PLOT_S, 3)
                 .stroke(1))

    screen.font = F["body"]
    _t("+A", cx + 3, PLOT_Y + 2, P["FAINT"])
    _t("-P", PLOT_X + 3, cy + 2, P["FAINT"])
    _rt("+P", PLOT_X + PLOT_S - 3, cy + 2, P["FAINT"])
    _t("-A", cx + 3, PLOT_Y + PLOT_S - M["body_h"] - 3, P["FAINT"])
    _t("range %.1f" % rng, PLOT_X + 3,
       PLOT_Y + PLOT_S - M["body_h"] - 3, P["FAINT"])

    # the default mood: a hollow ring the current mood is always drawn back to
    dx, dy = _plot(model.default_mood[0], model.default_mood[1])
    _ring(dx, dy, 7, 1, P["DIM"])
    if dy + 9 + M["body_h"] < PLOT_Y + PLOT_S:      # an extreme personality
        _ct("base", dx, dy + 9, P["FAINT"])         # can park it on the edge

    # every active emotion as a dot at its Table 2 position
    for e in model.active:
        ep, ea, ed = e.pad()
        ex, ey = _plot(ep, ea)
        _dot(ex, ey, 3, OP[occ.octant_of(ep, ea, ed)]["fade"][
            _level(e.intensity, FADE_STEPS)])

    # The mood trail as a continuous line rather than loose dots: a path reads
    # as motion, where a sparse dot per sample reads as stuttering.
    n = len(trail)
    if n > 1:
        px, py = _plot(trail[0][0], trail[0][1])
        for i in range(1, n):
            tp, ta, td = trail[i]
            tx, ty = _plot(tp, ta)
            screen.pen = OP[occ.octant_of(tp, ta, td)]["fade"][
                _level(i / (n - 1), FADE_STEPS)]
            screen.shape(shape.line(px, py, tx, ty, 2))
            px, py = tx, ty

    mx, my = _plot(p, a)

    # the virtual emotion center - the paper's dark grey ball - and the line
    # along which the mood is being pulled towards it or pushed past it
    if model.vec is not None:
        vp, va, vd, vi = model.vec
        vx, vy = _plot(vp, va)
        screen.pen = P["EDGE"]
        screen.shape(shape.line(mx, my, vx, vy, 1))
        _dot(vx, vy, 4 + 4 * vi, P["VEC"])
        _dot(vx, vy, 2, P["BG"])

    # the character itself: radius carries dominance, colour the octant
    _dot(mx, my, 6.0 + 4.0 * (d + 1.0) / 2.0, octant_pen(model.octant()))
    _dot(mx, my, 2.5, P["BG"])

    # --- right column
    rx = PLOT_X + PLOT_S + 6
    rw = cfg.W - rx - 4
    oct_pen = octant_pen(model.octant())

    _t("MOOD", rx, y0 + 2, P["DIM"])
    _pad_rows(rx, rw, y0 + 16, model.mood, P["INK"])

    _rule(rx, y0 + 52, rw)
    _t("DOMINANCE", rx, y0 + 56, P["DIM"])
    _bipolar(rx, y0 + 70, rw, 5, d, oct_pen)

    _rule(rx, y0 + 80, rw)
    _t("CENTER", rx, y0 + 84, P["DIM"])
    _rt("%d" % len(model.active), rx + rw, y0 + 84, P["DIM"])
    if model.vec is None:
        _t("none active", rx, y0 + 100, P["FAINT"])
        _t("returning to", rx, y0 + 114, P["FAINT"])
        _t("baseline", rx, y0 + 126, P["FAINT"])
    else:
        vp, va, vd, vi = model.vec
        _pad_rows(rx, rw, y0 + 98, (vp, va, vd), P["VEC"])
        _t("INTENSITY", rx, y0 + 136, P["DIM"])
        _rt("%.2f" % vi, rx + rw, y0 + 136, P["VEC"])

    _rule(rx, y0 + 152, rw)
    _t("PHASE", rx, y0 + 156, P["DIM"])
    _rt(affect.PHASE_NAMES[model.phase], rx + rw, y0 + 156,
        P["ACCENT"] if model.phase != affect.IDLE else P["FAINT"])


# ---- emotions list ---------------------------------------------------------
def _view_emotions(model, ui, now):
    y0 = cfg.BODY_Y
    x, w = 6, cfg.W - 12
    screen.font = F["body"]

    _t("ACTIVE EMOTIONS", x, y0, P["DIM"])
    _rt("BASELINE %.2f  DECAY %ds" % (cfg.EMOTION_BASELINE,
                                      cfg.EMOTION_DECAY_MS // 1000),
        x + w, y0, P["FAINT"])
    _rule(x, y0 + 14, w)

    rows = model.by_intensity()
    if not rows:
        _ct("no active emotions", cfg.W / 2, y0 + 60, P["FAINT"])
        _ct("the mood is drifting back to its personality baseline",
            cfg.W / 2, y0 + 76, P["FAINT"])
        _ct("UP / DOWN to choose a stimulus, C to apply it",
            cfg.W / 2, y0 + 100, P["DIM"])
        return

    shown = rows[:6]
    for n, e in enumerate(shown):
        ry = y0 + 20 + n * 20
        ep, ea, ed = e.pad()
        pen = octant_pen(occ.octant_of(ep, ea, ed))
        faded = e.intensity < cfg.EMOTION_BASELINE
        _t(_fit(e.name, 92), x, ry, P["DIM"] if faded else pen)
        _t("P%s A%s D%s" % (_sign(ep), _sign(ea), _sign(ed)),
           x + 98, ry, P["FAINT"])
        _rt("%.2f" % e.intensity, x + w, ry, P["DIM"] if faded else P["INK"])
        # the decaying bar, with ALMA's baseline threshold marked on it
        by = ry + M["body_h"] + 1
        _bar(x, by, w, 3, e.intensity, pen)
        _fill(x + w * cfg.EMOTION_BASELINE, by - 1, 1, 5, P["DIM"])

    if len(rows) > len(shown):
        _t("+%d more" % (len(rows) - len(shown)),
           x, y0 + 20 + len(shown) * 20, P["FAINT"])

    ry = cfg.BODY_Y + cfg.BODY_H - M["body_h"] - 6
    _rule(x, ry - 6, w)
    if model.vec is not None:
        vp, va, vd, vi = model.vec
        _t("VIRTUAL EMOTION CENTER", x, ry, P["VEC"])
        _rt("P%s A%s D%s   i %.2f" % (_sign(vp), _sign(va), _sign(vd), vi),
            x + w, ry, P["INK"])


# ---- personality -----------------------------------------------------------
def _view_personality(model, ui, now):
    y0 = cfg.BODY_Y
    x, w = 6, cfg.W - 12
    screen.font = F["body"]

    _t("BIG FIVE", x, y0, P["DIM"])
    _rt("MEHRABIAN REGRESSION -> DEFAULT MOOD", x + w, y0, P["FAINT"])

    for n, trait in enumerate(cfg.TRAITS):
        ry = y0 + 16 + n * 22
        sel = (n == ui["trait"])
        v = model.personality[trait]
        if sel:
            screen.pen = P["PANEL"]
            screen.shape(shape.rounded_rectangle(x - 3, ry - 2, w + 6, 20, 3))
        _t(cfg.TRAIT_LABELS[trait], x, ry, P["ACCENT"] if sel else P["DIM"])
        _rt(_sign(v), x + w, ry, P["INK"] if sel else P["DIM"])
        _bipolar(x + 128, ry + 3, w - 128 - 34, 5, v,
                 P["ACCENT"] if sel else P["DIM"])

    ry = y0 + 16 + len(cfg.TRAITS) * 22 + 2
    _rule(x, ry, w)
    dp, da, dd = model.default_mood
    word = affect.intensity_word(occ.norm(dp, da, dd))
    oct_name = occ.octant_of(dp, da, dd)
    _t("DEFAULT MOOD", x, ry + 6, P["DIM"])
    _rt("P%s  A%s  D%s" % (_sign(dp), _sign(da), _sign(dd)),
        x + w, ry + 6, P["INK"])
    screen.font = F["mid"]
    _t("%s %s" % (word, oct_name), x, ry + 20, octant_pen(oct_name))
    screen.font = F["body"]


# ---- mood dynamics tuner ---------------------------------------------------
def _ladder(x, y, w, ladder, index, paper_index, sel):
    """A rung-per-value strip: the current value lit, the paper's value ticked."""
    n = len(ladder)
    cw = (w - (n - 1) * 2) / n
    for i in range(n):
        cx = x + i * (cw + 2)
        if i == index:
            pen = P["ACCENT"] if sel else P["DIM"]
        else:
            pen = P["TRACK"]
        _fill(cx, y, cw, 5, pen)
        if i == paper_index:
            _fill(cx + cw / 2, y - 4, 1, 3, P["DIM"])


def _view_dynamics(model, ui, now):
    y0 = cfg.BODY_Y
    x, w = 6, cfg.W - 12
    screen.font = F["body"]

    _t("MOOD DYNAMICS", x, y0, P["DIM"])
    _rt("tick = the paper's value", x + w, y0, P["FAINT"])

    for n, entry in enumerate(cfg.DYNAMICS):
        name, label, unit, ladder, paper = entry
        ry = y0 + 16 + n * 32
        sel = (n == ui["param"])
        if sel:
            screen.pen = P["PANEL"]
            screen.shape(shape.rounded_rectangle(x - 3, ry - 3, w + 6, 28, 3))
        _t(label, x, ry, P["ACCENT"] if sel else P["DIM"])
        _rt(_param_text(entry), x + w, ry, P["INK"] if sel else P["DIM"])
        _ladder(x, ry + 16, w, ladder,
                cfg.nearest_index(ladder, cfg.param_value(name)),
                cfg.nearest_index(ladder, paper), sel)

    # What the numbers above actually buy you, in the units you can see on the
    # PAD map: a linearly decaying emotion of intensity i integrates
    # i * decay / 2 of center-intensity-seconds, and the mood covers SQRT3 per
    # mood change time at full intensity.
    ry = y0 + 16 + len(cfg.DYNAMICS) * 32 - 2
    _rule(x, ry, w)
    reach = (occ.SQRT3 / cfg.MOOD_CHANGE_MS) * (SAMPLE_INTENSITY
                                                * cfg.EMOTION_DECAY_MS / 2.0)
    _t("IMPACT", x, ry + 6, P["DIM"])
    _rt("%.2f of PAD per %.2f stimulus" % (reach, SAMPLE_INTENSITY),
        x + w, ry + 6, P["INK"])
    _t("RECOVERY", x, ry + 20, P["DIM"])
    _rt("%s back to baseline" % _secs((reach / occ.SQRT3) * cfg.MOOD_RETURN_MS),
        x + w, ry + 20, P["INK"])


# ---- guide -----------------------------------------------------------------
GUIDE_ROW_H = 15
GUIDE_GAP_H = 7


def guide_rows_visible():
    return cfg.BODY_H // GUIDE_ROW_H


def guide_max_scroll():
    return max(0, len(cfg.GUIDE) - guide_rows_visible())


def _view_guide(model, ui, now):
    y0 = cfg.BODY_Y
    x, w = 6, cfg.W - 12
    screen.font = F["body"]

    top = ui["guide"]
    y = y0
    i = top
    while i < len(cfg.GUIDE) and y + GUIDE_ROW_H <= y0 + cfg.BODY_H:
        kind, left, right = cfg.GUIDE[i]
        if kind == "h":
            _t(left, x, y, P["ACCENT"])
            _rule(x, y + M["body_h"] + 1, w)
        elif kind == "o":
            # swatch in the octant's own colour, so the legend matches the orb
            _ellipse(x + 5, y + M["body_h"] / 2, 9, 9, octant_pen(left))
            _t(left, x + 14, y, octant_pen(left))
            _rt(right, x + w, y, P["DIM"])
        elif kind == "t":
            _t(left, x, y, P["INK"] if left else P["DIM"])
            _rt(right, x + w, y, P["DIM"])
        y += GUIDE_GAP_H if kind == "-" else GUIDE_ROW_H
        i += 1

    # scrollbar: how far through the guide you are
    if guide_max_scroll():
        track_h = cfg.BODY_H - 4
        knob = max(12, int(track_h * guide_rows_visible() / len(cfg.GUIDE)))
        pos = int((track_h - knob) * top / guide_max_scroll())
        _fill(cfg.W - 3, y0 + 2, 2, track_h, P["PANEL"])
        _fill(cfg.W - 3, y0 + 2 + pos, 2, knob, P["DIM"])


# ---- entry point -----------------------------------------------------------
_VIEWS = (_view_character, _view_padmap, _view_emotions,
          _view_personality, _view_dynamics, _view_guide)


def draw(model, ui, now):
    screen.pen = P["BG"]
    screen.clear()
    _header(model, ui)
    screen.font = F["body"]
    _VIEWS[ui["view"]](model, ui, now)
    _rail(model, ui)
