# All drawing for the Character Creator - 320x240 HIRES.
#
# The screen is a room: wallpaper, baseboard, floor. The character hangs on the
# wall full length in one of the pack's picture frames, breathing; the part list
# leans beside it; and five more of them stand on the floor wearing the options
# either side of the one you have. The line-up exists so you never have to guess
# what "Bouffant" or "Dungarees" looks like on you.
#
# Device globals (screen, color, image, ...) are only touched inside functions,
# so this module imports cleanly off-device; init() runs once after badge.mode.

import character as ch
import config as cfg
import parts
import sprites

P = {}          # pens by palette name
F = {}          # fonts
M = {}          # font heights
BACKDROP = []   # one pen per room: what the character stands against

# Bottom layer up. The outfit goes on early so hair falls over its collar; a hat
# goes on last so it sits over the hair.
LAYERS = (ch.SKIN, ch.OUTFIT, ch.EYES, ch.HAIR, ch.FACE, ch.HEAD)

# glyph sheet columns
G_NEXT, G_PREV, G_UP, G_DOWN = 0, 1, 2, 3

def _blend(fg, bg, t):
    return tuple(int(fg[i] + (bg[i] - fg[i]) * t) for i in range(3))


def init():
    for name, rgb in cfg.RGB.items():
        P[name] = color.rgb(*rgb)
    P["veil"] = color.rgb(0, 0, 0, 70)     # the frame's shadow on the wall
    # A sitter needs something to stand against. Each room paints the backdrop
    # inside the frame in its own wallpaper, taken halfway to the frame's dark
    # outline so a pale character reads against it whichever room you are in.
    BACKDROP.extend(color.rgb(*_blend(room[1], cfg.RGB["ink"], 0.55))
                    for room in parts.ROOM)
    # Size hierarchy picked with the fonttest app (see the repo's font notes):
    #   body  - nope (~h13) : part names and values
    #   small - ark  (~h10) : counts and the button hints
    F["body"] = pixel_font.load("/system/assets/fonts/nope.ppf")
    F["small"] = pixel_font.load("/system/assets/fonts/ark.ppf")
    for key in F:
        screen.font = F[key]
        M[key] = int(screen.measure_text("0")[1])   # floats on-device
    sprites.init()


# ---- primitives ------------------------------------------------------------
def _text(s, x, y, pen, font="body"):
    screen.font = F[font]
    screen.pen = P[pen]
    screen.text(s, int(x), int(y))


def _width(s, font="body"):
    screen.font = F[font]
    return int(screen.measure_text(s)[0])


def _rtext(s, right, y, pen, font="body"):
    _text(s, right - _width(s, font), y, pen, font)


def _fill(x, y, w, h, pen):
    screen.pen = P[pen]
    screen.rectangle(int(x), int(y), int(w), int(h))


def _swatch(x, y, rgb, ringed=False):
    """Every row carries the colour it is about. An empty one (nothing worn
    yet) is drawn hollow rather than left blank, so the column stays a column."""
    w, h = cfg.SWATCH_W, cfg.SWATCH_H
    if ringed:
        _fill(x - 2, y - 2, w + 4, h + 4, "accent")
    _fill(x, y, w, h, "ink")
    screen.pen = P["parchment"] if rgb is None else color.rgb(*rgb)
    screen.rectangle(int(x) + 1, int(y) + 1, w - 2, h - 2)


def breath(now):
    """Standing, or the top of a breath. A plain cycle rather than the blink's
    scattered gaps - breathing is rhythmic and looks wrong when it is not."""
    return (sprites.BREATH if now % cfg.BREATH_MS < cfg.BREATH_UP_MS
            else sprites.STAND)


# ---- the room --------------------------------------------------------------
def _room(option, floor_top):
    # The wallpaper is one flat row repeated (the generator builds it that way),
    # so a column can be stretched down the whole wall in a single blit rather
    # than tiled - twenty blits a frame instead of two hundred.
    wall = sprites.room(option, 0)
    for x in range(0, screen.width, cfg.TILE):
        screen.blit(wall, rect(x, 0, cfg.TILE, floor_top))
    board = sprites.room(option, 2)
    floor = sprites.room(option, 1)
    for x in range(0, screen.width, cfg.TILE):
        screen.blit(board, vec2(x, floor_top - cfg.TILE))
        for y in range(floor_top, cfg.BAR_TOP, cfg.TILE):
            screen.blit(floor, vec2(x, y))


# ---- the hero --------------------------------------------------------------
def _stack(char, x, y, w, h, pose, part=None, value=None, shade=False):
    """Composite one character. With part/value given, that one slot is swapped
    - which is how the line-up wears an option you have not chosen yet, on your
    own character."""
    for layer in LAYERS:
        option, tint = char.option[layer], char.tint[layer]
        swapped = layer == part and not shade and value != option
        if layer == part:
            if shade:
                tint = value
            else:
                option = value
        if swapped and layer in sprites.FOLDER:
            # another family, so only its catalogue entry (first shade) is in
            # memory - keeping all 33 outfit sheets resident to preview five is
            # not a trade worth making
            img = sprites.preview(layer, option)
        else:
            img = sprites.layer(layer, option, tint, pose)
        if img:
            screen.blit(img, rect(x, y, w, h))


def _hero(char, pose, lift):
    """The character, full length and framed, against a backdrop painted in the
    room's own wallpaper."""
    x, y = cfg.FRAME_X, cfg.FRAME_Y - lift
    art = sprites.S["frame"]
    screen.pen = P["veil"]
    screen.rectangle(x + 4, y + 5, art.width, art.height)
    screen.blit(art, vec2(x, y))
    mx, my, mw, mh = cfg.MAT_BOX
    screen.pen = BACKDROP[char.option[ch.ROOM]]
    screen.rectangle(x + mx, y + my, mw, mh)
    _stack(char, x + cfg.MAT_X, y + cfg.MAT_Y, cfg.HERO_W, cfg.HERO_H, pose)


# ---- the part list ---------------------------------------------------------
def _panel(char):
    """Six rows, always the same six: what the part is, what colour it is,
    what it is called, and how far along its list you are."""
    screen.pen = P["veil"]
    screen.rectangle(cfg.PANEL_X + 4, cfg.PANEL_Y + 5, cfg.PANEL_W, cfg.PANEL_H)
    screen.blit(sprites.S["panel"], vec2(cfg.PANEL_X, cfg.PANEL_Y))

    sel_part, sel_shade = char.stop
    for i, part in enumerate(ch.ORDER):
        y = cfg.ROW_TOP + i * cfg.ROW_H
        here = part == sel_part
        if here:
            screen.blit(sprites.S["pill"], vec2(cfg.PILL_X, y - 2))

        option, tint = char.option[part], char.tint[part]
        _text(ch.LABEL[part], cfg.LABEL_X, y + 1, "ink" if here else "dim")
        _swatch(cfg.SWATCH_X, y + 2, ch.swatch(part, option, tint),
                here and sel_shade)
        label = ch.name(part, option)
        if label:
            _text(label, cfg.NAME_X, y + 1, "ink")

        # the count follows the cursor: on a shade chip it counts shades
        on_shade = here and sel_shade
        n = ch.tint_count(part, option) if on_shade else ch.option_count(part)
        at = (tint if on_shade else option) + 1
        _rtext(f"{at}/{n}", cfg.COUNT_R, y + 4, "dim", "small")


# ---- the try-on row --------------------------------------------------------
def _room_preview(option, cx):
    """A room shown as a room: papered wall, baseboard, floor. Outlined, or the
    one you are already standing in would vanish into the wall behind it."""
    wall = sprites.room(option, 0)
    floor = sprites.room(option, 1)
    board = sprites.room(option, 2)
    x, y = cx - cfg.ROOM_W // 2, cfg.TRY_FEET - cfg.ROOM_H
    for i in range(cfg.ROOM_W // cfg.TILE):
        tx = x + i * cfg.TILE
        screen.blit(wall, rect(tx, y, cfg.TILE, cfg.ROOM_H - cfg.TILE))
        screen.blit(board, vec2(tx, y + cfg.ROOM_H - cfg.TILE * 2))
        screen.blit(floor, vec2(tx, y + cfg.ROOM_H - cfg.TILE))
    screen.pen = P["ink"]
    screen.shape(shape.rectangle(x, y, cfg.ROOM_W, cfg.ROOM_H).stroke(1))


def _lineup(char):
    part, shade = char.stop
    span = char.span()
    shown = min(2 * cfg.TRY_SPAN + 1, span)
    if not shown % 2:
        shown -= 1                    # keep the one you have in the middle

    for i in range(shown):
        value = char.at(i - shown // 2)
        cx = screen.width // 2 + (i - shown // 2) * cfg.TRY_PITCH
        if part == ch.ROOM:
            _room_preview(value, cx)
        else:
            _stack(char, cx - cfg.TRY_W // 2, cfg.TRY_FEET - cfg.TRY_H,
                   cfg.TRY_W, cfg.TRY_H, sprites.STAND, part, value, shade)
        if i == shown // 2:
            # five near-identical characters need one of them marked as yours
            _fill(cx - cfg.TRY_W // 2, cfg.TRY_FEET + 3, cfg.TRY_W, 2, "accent")

    if span > shown:
        y = cfg.ARROW_Y
        screen.blit(sprites.S["glyphs"].cell(G_PREV), vec2(cfg.ARROW_INSET, y))
        screen.blit(sprites.S["glyphs"].cell(G_NEXT),
                    vec2(screen.width - cfg.ARROW_INSET - 16, y))


# ---- the hint bar ----------------------------------------------------------
# What each button does *right now*, in the order the buttons sit on the badge.
# Arrows are the pack's own button sprites - the same two that mark the ends of
# the line-up, so the row and the buttons that drive it read as one thing.
GLYPH = 16
GLYPH_GAP = 2

ROOM_HINTS = (((G_UP, G_DOWN), (), "PART"), ((G_PREV,), (), "A"),
              ((), (G_NEXT,), "C"), ((), (), "B SHUFFLE"),
              ((), (), "HOLD B  GALLERY"))
HUNG_HINTS = (((G_UP, G_DOWN), (), "BACK"), ((G_PREV,), (), "A"),
              ((), (G_NEXT,), "C"), ((), (), "B WEAR"),
              ((), (), "HOLD B  REMOVE"))
BARE_HINTS = (((G_UP, G_DOWN), (), "BACK"), ((G_PREV,), (), "A"),
              ((), (G_NEXT,), "C"), ((), (), "B  HANG THIS ONE HERE"))


def _hint(hints):
    _fill(0, cfg.BAR_TOP, screen.width, screen.height - cfg.BAR_TOP, "ink")
    widths = [(len(before) + len(after)) * (GLYPH + GLYPH_GAP)
              + _width(label, "small") + 4
              for before, after, label in hints]
    # spread the groups evenly, with the same air at both ends
    gap = max(4, (screen.width - sum(widths)) // (len(hints) + 1))
    y = cfg.BAR_TOP + (screen.height - cfg.BAR_TOP - GLYPH) // 2
    x = gap
    for before, after, label in hints:
        for glyph in before:
            screen.blit(sprites.S["glyphs"].cell(glyph), vec2(x, y))
            x += GLYPH + GLYPH_GAP
        _text(label, x + 2, y + (GLYPH - M["small"]) // 2, "parchment", "small")
        x += _width(label, "small") + 4
        for glyph in after:
            screen.blit(sprites.S["glyphs"].cell(glyph), vec2(x, y))
            x += GLYPH + GLYPH_GAP
        x += gap


# ---- the gallery -----------------------------------------------------------
def _slot_at(i):
    col, row = i % cfg.GAL_COLS, i // cfg.GAL_COLS
    return (cfg.GAL_X + col * (cfg.HUNG_FRAME_W + cfg.GAL_GAP_X),
            cfg.GAL_Y + row * (cfg.HUNG_FRAME_H + cfg.GAL_GAP_Y))


def _paint_one(gal, room):
    """Compose one hung character into its own canvas - at most one a frame, so
    walking into the gallery fills the wall in rather than stalling on it."""
    i = gal.stale()
    if i is None:
        return
    options, tints = gal.worn(i)
    picture = image(cfg.FIGURE_W, cfg.FIGURE_H)
    for layer in LAYERS:
        cell = sprites.layer(layer, options[layer], tints[layer], sprites.STAND)
        if cell:
            picture.blit(cell, vec2(0, 0))
    gal.put_picture(i, picture)


def draw_gallery(char, gal):
    room = char.option[ch.ROOM]
    _room(room, cfg.GAL_FLOOR_TOP)
    _paint_one(gal, room)
    mx, my, mw, mh = cfg.HUNG_MAT_BOX
    for i in range(cfg.SLOTS):
        x, y = _slot_at(i)
        screen.pen = P["veil"]
        screen.rectangle(x + 3, y + 4, cfg.HUNG_FRAME_W, cfg.HUNG_FRAME_H)
        screen.blit(sprites.S["frame_small"], vec2(x, y))
        screen.pen = BACKDROP[room]
        screen.rectangle(x + mx, y + my, mw, mh)
        picture = gal.picture(i)
        if picture:
            screen.blit(picture, rect(x + cfg.HUNG_MAT_X, y + cfg.HUNG_MAT_Y,
                                      cfg.HUNG_W, cfg.HUNG_H))
        if i == gal.cursor:
            screen.pen = P["accent"]
            screen.shape(shape.rounded_rectangle(
                x - 3, y - 3, cfg.HUNG_FRAME_W + 6, cfg.HUNG_FRAME_H + 6,
                3).stroke(2))
    _hint(HUNG_HINTS if gal.filled() else BARE_HINTS)


def draw(char, now, bumped_at):
    lift = cfg.BUMP_PX if now - bumped_at < cfg.BUMP_MS else 0
    _room(char.option[ch.ROOM], cfg.FLOOR_TOP)
    _hero(char, breath(now), lift)
    _panel(char)
    _lineup(char)
    _hint(ROOM_HINTS)
