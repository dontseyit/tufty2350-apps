"""
A pure-Python + pygame reimplementation of the Tufty 2350 "badgeware" runtime.

Enough of the firmware API is faked here to run real apps (e.g.
snarky_sciuridae) on a desktop with no hardware. On-device, badgeware *injects*
its API as builtins (screen, badge, image, SpriteSheet, color, shape, vec2,
rect, clamp, run, ...) and exposes `State` via `from badgeware import State`.
`install()` reproduces both so an app's `__init__.py` runs unmodified.

Only the slice of the API the target apps actually touch is implemented. Text
is drawn with the REAL device fonts: tools/ppf.py parses the .ppf bitmaps and
the shim blits the same glyphs the badge does, so a screenshot can be trusted
to the pixel when a line is being fitted to a 320x240 screen.
"""

import builtins
import json
import os
import sys
import types

import pygame

# Root that "/system/..." device paths are rewritten onto (set by the launcher).
SYSTEM_ROOT = None
# Where device "internal flash" root files ("/tdf.json", "/cards.json") are
# redirected so apps can actually persist (set by the launcher).
FLASH_ROOT = None

# Supersampling factor: the canvas is rendered this many times larger than the
# device's logical resolution so text and shapes are crisp at the display size,
# while apps keep drawing in logical device coordinates. Set by the launcher.
RENDER_SCALE = 1


def _translate(path):
    """Map an on-device absolute path ("/system/...") onto the desktop repo."""
    p = str(path)
    if p.startswith("/system") and SYSTEM_ROOT is not None:
        return SYSTEM_ROOT + p[len("/system"):]
    return p


def _flash_translate(path):
    """Redirect bare device-flash root files ("/tdf.json") into FLASH_ROOT.

    Matches a single leading "/" with no further separators -- exactly the
    writable internal-flash files apps use -- and leaves "/system/...",
    "/Users/...", and relative paths untouched.
    """
    import os as _os
    p = str(path)
    if FLASH_ROOT and p.startswith("/") and p.count("/") == 1 and len(p) > 1:
        return _os.path.join(FLASH_ROOT, p[1:])
    return p


# --------------------------------------------------------------------------- #
# Geometry / scalar helpers
# --------------------------------------------------------------------------- #
class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y


class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h


def vec2(x, y):
    return Vec2(x, y)


def rect(x, y, w, h):
    return Rect(x, y, w, h)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# --------------------------------------------------------------------------- #
# Colour + shapes
# --------------------------------------------------------------------------- #
class _Color:
    @staticmethod
    def rgb(r, g, b, a=255):
        return (int(r), int(g), int(b), int(a))


color = _Color()


class _Stroked:
    """Device API: a shape is filled unless .stroke(n) is called on it, which
    returns the shape so the two forms read the same at the call site:

        screen.shape(shape.rounded_rectangle(x, y, w, h, 3))
        screen.shape(shape.rounded_rectangle(x, y, w, h, 3).stroke(2))
    """
    line = 0

    def stroke(self, width=1):
        self.line = max(1, int(width))
        return self


class _RoundRect(_Stroked):
    __slots__ = ("x", "y", "w", "h", "r", "line")

    def __init__(self, x, y, w, h, r=0):
        self.x, self.y, self.w, self.h, self.r = x, y, w, h, r
        self.line = 0


class _Circle(_Stroked):
    __slots__ = ("cx", "cy", "rad", "line")

    def __init__(self, cx, cy, rad):
        self.cx, self.cy, self.rad = cx, cy, rad
        self.line = 0


class _Poly(_Stroked):
    """An arbitrary polygon, which the device offers as shape.custom.

    Added because the simulator did not have it and an app that used it - the
    clock does, and dwell's TIES page now does - ran perfectly here and would
    have thrown on the badge, which is the exact failure this simulator exists
    to prevent.
    """

    __slots__ = ("points", "line")

    def __init__(self, points):
        # THE DEVICE WANTS vec2, NOT TUPLES, and it raises a TypeError naming
        # custom([P1,P2,P3,...]) when it does not get them.  The first version
        # of this stub took anything two numbers long, so a page built on
        # tuples drew perfectly here and threw on the badge - which is the
        # single failure this simulator exists to prevent, committed by the
        # simulator itself.  Be as strict as the firmware.
        out = []
        for p in points:
            if not (hasattr(p, "x") and hasattr(p, "y")):
                raise TypeError(
                    "invalid parameter, expected custom([P1,P2,P3,...]) "
                    "of vec2 - got %r" % (p,))
            out.append((float(p.x), float(p.y)))
        self.points = out
        self.line = 0


class _Shape:
    @staticmethod
    def custom(points):
        return _Poly(points)

    @staticmethod
    def rounded_rectangle(x, y, w, h, r=0, *extra_radii):
        # Device supports per-corner radii; we approximate with a single radius.
        return _RoundRect(x, y, w, h, r)

    @staticmethod
    def rectangle(x, y, w, h):
        return _RoundRect(x, y, w, h, 0)

    @staticmethod
    def circle(cx, cy, rad):
        return _Circle(cx, cy, rad)


shape = _Shape()


# --------------------------------------------------------------------------- #
# Images + spritesheets
# --------------------------------------------------------------------------- #
class Img:
    def __init__(self, surface):
        self.surface = surface.convert_alpha()
        self.alpha = 255

    @property
    def width(self):
        return self.surface.get_width()

    @property
    def height(self):
        return self.surface.get_height()

    def blit(self, img, dst):
        """Composite another image onto this one, at 1:1.

        This is what an offscreen canvas is for on the badge - compose a
        character out of six layers once, then draw the result with a single
        screen.blit thereafter (see the factory apps 30_minutes_to_alpha_centauri
        and sketchy_sketch, the character creator's gallery, and household's
        sprites.dress).  The device offers no scaling form here, so neither does
        this: scale when you blit the finished canvas to the screen.
        """
        src = img.surface
        if getattr(img, "alpha", 255) != 255:
            src = src.copy()
            src.set_alpha(img.alpha)
        self.surface.blit(src, (int(dst.x), int(dst.y)))


class _ImageAPI:
    # Antialias / supersample modes. We render at 1x so these are inert markers.
    X = 1
    X2 = 2
    X4 = 4

    def __call__(self, w, h):
        # image(w, h) -> a blank drawable canvas.
        return Img(pygame.Surface((int(w), int(h)), pygame.SRCALPHA))

    def load(self, path):
        return Img(pygame.image.load(_translate(path)))


image = _ImageAPI()


class _Animation:
    def __init__(self, sheet):
        self._sheet = sheet
        self._n = sheet.cols

    def frame(self, i):
        return self._sheet.cell(int(i) % self._n, 0)


class SpriteSheet:
    def __init__(self, path, cols, rows):
        self.sheet = pygame.image.load(_translate(path)).convert_alpha()
        self.cols, self.rows = cols, rows
        self.cw = self.sheet.get_width() // cols
        self.ch = self.sheet.get_height() // rows

    def cell(self, u, v):
        r = pygame.Rect(u * self.cw, v * self.ch, self.cw, self.ch)
        return Img(self.sheet.subsurface(r).copy())

    def sprite(self, u, v):
        return self.cell(u, v)

    def animation(self):
        return _Animation(self)


# --------------------------------------------------------------------------- #
# Fonts (substitute)
# --------------------------------------------------------------------------- #
# The device .ppf glyphs aren't parsed; we substitute a pygame font sized to
# roughly match each .ppf's on-device pixel height (from the apps' own notes),
# so e.g. tdf's body/mid/hero fonts stay visibly distinct.
_FONT_HEIGHTS = {"nope": 13, "smart": 16, "bacteria": 20, "ark": 10}
_font_cache = {}
_ppf_cache = {}

# THE SIMULATOR DRAWS THE REAL FONTS.  It used to substitute a system typeface
# at a guessed pixel size, which is fine for "is the text roughly here" and
# useless for the thing a 320x240 screen actually needs answering: does this
# line fit.  Every .ppf in the repo is a fixed-size bitmap and tools/ppf.py
# already parses them for the content build, so the shim renders the same
# glyphs the badge does and a screenshot can be trusted to the pixel.
#
# ONE NUMBER IS STILL A GUESS: the space.  Its glyph is blank and its width is
# zero in the file, so the firmware supplies a gap we cannot see; ppf.py bounds
# it at 2..6.  Four is the middle of that, and it is here as a named constant
# rather than inline so it can be corrected the day somebody measures it on the
# badge.
SPACE_ADVANCE = 4


class _PpfFont:
    """A .ppf rendered through the pygame API that Screen.text already uses."""

    def __init__(self, font, scale):
        self.f = font
        self.scale = scale
        self._glyphs = {}

    def size(self, text):
        return (self.f.measure(str(text), SPACE_ADVANCE) * self.scale,
                self.f.rows * self.scale)

    def _glyph(self, ch, rgb):
        key = (ch, rgb)
        got = self._glyphs.get(key)
        if got is not None:
            return got
        f, s = self.f, self.scale
        w = f.advance(ch, SPACE_ADVANCE)
        surf = pygame.Surface((max(1, w * s), f.rows * s), pygame.SRCALPHA)
        for y in range(f.rows):
            for x in range(w):
                if f.pixel(ch, x, y):
                    surf.fill(rgb, (x * s, y * s, s, s))
        self._glyphs[key] = surf
        return surf

    def render(self, text, antialias, rgb):
        text = str(text)
        w, h = self.size(text)
        out = pygame.Surface((max(1, int(w)), max(1, int(h))), pygame.SRCALPHA)
        x = 0
        for ch in text:
            adv = self.f.advance(ch, SPACE_ADVANCE) * self.scale
            if ch != " ":
                out.blit(self._glyph(ch, tuple(rgb)), (x, 0))
            x += adv
        return out


def _font(px):
    px = max(6, int(px))
    f = _font_cache.get(px)
    if f is None:
        if not pygame.font.get_init():
            pygame.font.init()
        f = pygame.font.Font(None, px)  # rendered at supersampled size -> crisp
        _font_cache[px] = f
    return f


def _default_font():
    return _font(13 * RENDER_SCALE)


class _PixelFontAPI:
    def load(self, path):
        name = str(path).split("/")[-1].split(".")[0]
        key = (name, RENDER_SCALE)
        got = _ppf_cache.get(key)
        if got is not None:
            return got
        # _translate turns the device path the app asked for into the repo
        # copy, which is exactly the mapping the rest of the shim uses for
        # images - so the font the badge would open is the font opened here.
        full = _translate(str(path))
        if os.path.exists(full):
            try:
                here = os.path.dirname(os.path.abspath(__file__))
                tools = os.path.normpath(os.path.join(here, "..", ".."))
                tools = os.path.join(tools, "tools")
                if tools not in sys.path:
                    sys.path.insert(0, tools)
                import ppf as _ppf
                got = _PpfFont(_ppf.load(full), RENDER_SCALE)
                _ppf_cache[key] = got
                return got
            except Exception as exc:      # a corrupt font must not stop the app
                print("sim: could not read %s (%s), falling back" % (full, exc))
        return _font(_FONT_HEIGHTS.get(name, 13) * RENDER_SCALE)


pixel_font = _PixelFontAPI()


# --------------------------------------------------------------------------- #
# Screen
# --------------------------------------------------------------------------- #
class Screen:
    def __init__(self, w, h, scale=1):
        self.scale = scale
        self.width, self.height = w, h  # logical device resolution (app-facing)
        self.surface = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
        self.pen = (255, 255, 255, 255)
        self.antialias = 1
        self.font = None

    def resize(self, w, h):
        self.width, self.height = w, h
        self.surface = pygame.Surface(
            (w * self.scale, h * self.scale), pygame.SRCALPHA)

    def clear(self, rgba=None):
        # No arg -> fill with the current pen (device behaviour used by tdf).
        self.surface.fill(self.pen if rgba is None else rgba)

    def rectangle(self, x, y, w, h):
        s = self.scale
        tw, th = int(abs(w) * s), int(abs(h) * s)
        if tw <= 0 or th <= 0:
            return
        r = pygame.Rect(int(x * s), int(y * s), tw, th)
        if self.pen[3] >= 255:
            pygame.draw.rect(self.surface, self.pen, r)
        else:  # translucent pen: composite so alpha blends correctly
            tmp = pygame.Surface((tw, th), pygame.SRCALPHA)
            tmp.fill(self.pen)
            self.surface.blit(tmp, r.topleft)

    @staticmethod
    def _with_alpha(img):
        if img.alpha >= 255:
            return img.surface
        s = img.surface.copy()
        s.fill((255, 255, 255, img.alpha), special_flags=pygame.BLEND_RGBA_MULT)
        return s

    def blit(self, img, dst, dst2=None):
        s = self.scale
        src = self._with_alpha(img)
        # 3-arg form blit(img, src_rect, dst_rect): sample src_rect, draw to dst_rect.
        if dst2 is not None and isinstance(dst, Rect) and isinstance(dst2, Rect):
            sub = src.subsurface(
                pygame.Rect(int(dst.x), int(dst.y), int(abs(dst.w)), int(abs(dst.h)))
            )
            self._blit_rect(sub, dst2)
            return
        if isinstance(dst, Vec2):
            if s != 1:
                src = pygame.transform.scale(
                    src, (img.width * s, img.height * s))
            self.surface.blit(src, (int(dst.x * s), int(dst.y * s)))
        elif isinstance(dst, Rect):
            self._blit_rect(src, dst)

    def _blit_rect(self, src, dst):
        s = self.scale
        tw, th = int(abs(dst.w) * s), int(abs(dst.h) * s)
        if tw <= 0 or th <= 0:
            return
        if (tw, th) != src.get_size():
            # nearest-neighbour keeps pixel-art sprites/backgrounds crisp
            src = pygame.transform.scale(src, (tw, th))
        flip_x, flip_y = dst.w < 0, dst.h < 0
        if flip_x or flip_y:
            src = pygame.transform.flip(src, flip_x, flip_y)
        self.surface.blit(src, (int(dst.x * s), int(dst.y * s)))

    def shape(self, sh):
        # A rounded rectangle or a circle in the current pen, filled unless the
        # shape was .stroke()d.  Drawn onto a scratch surface first so a
        # translucent pen composites once rather than per primitive.
        s = self.scale
        if isinstance(sh, _Poly):
            pts = [(int(x * s), int(y * s)) for x, y in sh.points]
            if len(pts) < 2:
                return
            w = max(1, int(sh.line * s)) if sh.line else 0
            if w:
                # A stroked custom shape is an open path on the device, not a
                # closed outline: the clock draws seven-segment strokes with it.
                pygame.draw.lines(self.surface, self.pen, False, pts, w)
            else:
                if len(pts) >= 3:
                    pygame.draw.polygon(self.surface, self.pen, pts)
            return
        if isinstance(sh, _Circle):
            rad = int(sh.rad * s)
            if rad <= 0:
                return
            tmp = pygame.Surface((rad * 2 + 2, rad * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(tmp, self.pen, (rad + 1, rad + 1), rad,
                               min(rad, int(sh.line * s)) if sh.line else 0)
            self.surface.blit(tmp, (int(sh.cx * s) - rad - 1,
                                    int(sh.cy * s) - rad - 1))
            return
        tw, th = int(abs(sh.w) * s), int(abs(sh.h) * s)
        if tw <= 0 or th <= 0:
            return
        tmp = pygame.Surface((tw, th), pygame.SRCALPHA)
        r = int(min(sh.r * s, tw // 2, th // 2))
        width = min(tw // 2, th // 2, int(sh.line * s)) if sh.line else 0
        pygame.draw.rect(tmp, self.pen, pygame.Rect(0, 0, tw, th),
                         width=max(0, width), border_radius=max(0, r))
        self.surface.blit(tmp, (int(sh.x * s), int(sh.y * s)))

    def text(self, s, x, y):
        f = self.font or _default_font()
        surf = f.render(str(s), True, self.pen[:3])
        self.surface.blit(surf, (int(x * self.scale), int(y * self.scale)))

    def measure_text(self, s):
        f = self.font or _default_font()
        w, h = f.size(str(s))
        # Report LOGICAL metrics so apps lay out in device coordinates.
        return (w / self.scale, h / self.scale)


# --------------------------------------------------------------------------- #
# Real-time clock
# --------------------------------------------------------------------------- #
class _RTC:
    def __init__(self):
        self.hour = 12  # noon -> daytime background by default

    def datetime(self):
        # Device returns a 7-tuple with the hour at index 3.
        return (2026, 7, 20, self.hour, 0, 0, 0)


rtc = _RTC()


# --------------------------------------------------------------------------- #
# Buttons + badge (input + millisecond clock)
# --------------------------------------------------------------------------- #
BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_UP, BUTTON_DOWN = 0, 1, 2, 3, 4
HIRES, VSYNC = 1, 2


class Badge:
    def __init__(self):
        self._ticks = 0.0
        self._delta = 0
        self._pressed = set()
        self._held = set()
        self._released = set()
        # The colour the device clears the screen to before every frame.  Apps
        # may set it; the frame wrapper in get_callback() uses it, which is
        # what makes this shim clear the way the badge does.
        self.default_clear = (0, 0, 0, 255)
        self.default_pen = (255, 255, 255, 255)

    @property
    def ticks(self):
        return int(self._ticks)

    @property
    def ticks_delta(self):
        return int(self._delta)

    def advance(self, ms):
        self._ticks += ms
        self._delta = ms

    def set_frame_input(self, pressed, held, released):
        self._pressed, self._held, self._released = pressed, held, released

    def pressed(self, btn=None):
        return bool(self._pressed) if btn is None else btn in self._pressed

    def held(self, btn=None):
        return bool(self._held) if btn is None else btn in self._held

    def released(self, btn=None):
        return bool(self._released) if btn is None else btn in self._released

    def poll(self):
        pass

    def mode(self, m):
        if m & HIRES:
            screen.resize(320, 240)


badge = Badge()


# --------------------------------------------------------------------------- #
# Persistent State (badgeware.State) -> a JSON file on disk
# --------------------------------------------------------------------------- #
class State:
    _path = None
    _data = {}

    @classmethod
    def configure(cls, path):
        cls._path = path
        try:
            with open(path) as f:
                cls._data = json.load(f)
        except Exception:
            cls._data = {}

    @classmethod
    def load(cls, key, into):
        saved = cls._data.get(key)
        if isinstance(saved, dict):
            into.update(saved)
            return True
        return False

    @classmethod
    def save(cls, key, data):
        cls._data[key] = data
        if cls._path:
            try:
                with open(cls._path, "w") as f:
                    json.dump(cls._data, f)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# run() + install()
# --------------------------------------------------------------------------- #
# The device's run(update) blocks forever. Here it just registers the per-frame
# callback and returns, so the launcher owns the loop (and can hot-reload).
_run_callback = None
_app_globals = None

# The single shared screen the launcher blits into the window.
screen = Screen(160, 120)


def set_render_scale(s):
    """Set the supersampling factor before loading the app (launcher calls this)."""
    global RENDER_SCALE
    RENDER_SCALE = max(1, int(s))
    screen.scale = RENDER_SCALE
    screen.resize(screen.width, screen.height)


def run(update):
    global _run_callback, _app_globals
    _run_callback = update
    _app_globals = sys._getframe(1).f_globals  # so the launcher can find on_exit


def get_callback():
    """The app's per-frame callback, wrapped so the SCREEN IS CLEARED FIRST.

    The device clears the whole screen before every frame - read back off
    `screen.raw`, a rectangle drawn and then `badge.update()` and the pixel is
    gone, replaced by `badge.default_clear`.  A pygame surface does not do
    that, and the difference hid a real bug: an app that drew its room every
    frame and its text only when the text changed looked perfect here and
    flickered on the badge, because something drawn on one frame in three is on
    screen one frame in three.

    So the shim does what the device does.  Every app in this repo redraws
    everything every frame, so nothing is broken by it - and the next person to
    try a partial repaint finds out on a desktop instead of on hardware.
    """
    if _run_callback is None:
        return None

    def framed():
        screen.pen = badge.default_clear
        screen.clear()
        _run_callback()

    return framed


def get_app_globals():
    return _app_globals


def install():
    """Inject the badgeware API as builtins + register the `badgeware` module."""
    # Apps do os.chdir("/system/apps/...") on boot; translate that to the repo
    # so their relative asset loads resolve, without editing the app source.
    import os as _os
    if not getattr(_os.chdir, "_bw_wrapped", False):
        _real_chdir = _os.chdir

        def _chdir(p):
            return _real_chdir(_translate(p))

        _chdir._bw_wrapped = True
        _os.chdir = _chdir

    # Redirect device internal-flash writes ("/tdf.json") to FLASH_ROOT so
    # apps persist to a real writable location instead of the macOS root.
    if FLASH_ROOT:
        _os.makedirs(FLASH_ROOT, exist_ok=True)
    if not getattr(builtins.open, "_bw_wrapped", False):
        _real_open = builtins.open

        def _open(file, *a, **k):
            return _real_open(_flash_translate(file), *a, **k)

        _open._bw_wrapped = True
        builtins.open = _open

    api = dict(
        screen=screen, badge=badge, image=image, SpriteSheet=SpriteSheet,
        color=color, shape=shape, vec2=vec2, rect=rect, clamp=clamp, run=run,
        rtc=rtc, pixel_font=pixel_font,
        BUTTON_A=BUTTON_A, BUTTON_B=BUTTON_B, BUTTON_C=BUTTON_C,
        BUTTON_UP=BUTTON_UP, BUTTON_DOWN=BUTTON_DOWN, HIRES=HIRES, VSYNC=VSYNC,
        launch=lambda *a, **k: None, reset=lambda *a, **k: None,
    )
    for k, v in api.items():
        setattr(builtins, k, v)

    mod = types.ModuleType("badgeware")
    mod.State = State
    sys.modules["badgeware"] = mod
