# Tunables, personality archetypes, layout metrics and palette for Commons.
#
# Pure data only - no badgeware globals - so this imports on the desktop, and
# affect.py's self-test (`python3 affect.py` in this folder) runs against it.
#
# The four ALMA dynamics constants below are deliberately the same names and
# values the alma app ships, because affect.py here is a byte-identical copy of
# alma/affect.py: the point of this app is to run THAT engine on three people at
# once, not a variant of it.  Tune them live on alma's DYNAMICS view first, then
# write the numbers you liked in here.

from occ import SQRT3

DEBUG = False


def log(*args):
    if DEBUG:
        print("[commons]", *args)


# ---- ALMA dynamics ---------------------------------------------------------
# Global, and shared by every resident: three people running different clocks
# would make it impossible to read one mood against another, which is the whole
# reason there are three of them.
EMOTION_DECAY_MS = 60000            # an emotion's linear life
EMOTION_BASELINE = 0.4              # below this it is too faint to be "dominant"
MOOD_CHANGE_MS = 2 * 60 * 1000      # to walk SQRT3 at full center intensity
MOOD_RETURN_MS = 40 * 60 * 1000     # to walk SQRT3 back to the baseline

MOOD_SLIGHT_MAX = SQRT3 / 3.0
MOOD_MODERATE_MAX = SQRT3 * 2.0 / 3.0
INTENSITY_WORDS = ("slightly", "moderate", "fully")

RETURN_WHILE_ACTIVE = False
WEIGHTED_CENTER = True

# affect.py's self-test reads this table (and set_param) to pin the paper's
# values before checking the model against the worked examples.  Commons has no
# editor for them; alma does.
SECONDS = "s"
UNITLESS = ""
DYNAMICS = (
    ("EMOTION_DECAY_MS", "EMOTION DECAY", SECONDS, (), 20000),
    ("MOOD_CHANGE_MS", "MOOD CHANGE", SECONDS, (), 600000),
    ("MOOD_RETURN_MS", "MOOD RETURN", SECONDS, (), 1200000),
    ("EMOTION_BASELINE", "EMOTION BASELINE", UNITLESS, (), 0.4),
)


def set_param(name, value):
    globals()[name] = value


def param_value(name):
    return globals()[name]


# ---- the clock -------------------------------------------------------------
TIME_SCALES = (1, 10, 60)
DEFAULT_SCALE_INDEX = 1              # start at 10x

# A real frame longer than this is a stall (app switch, a blocking call), not
# elapsed time, so nobody's mood jumps on a hiccup.
MAX_FRAME_MS = 200

# How often a mood position is remembered for the detail view's trail, and how
# many are kept per resident.  Three residents pay for this, so it is half the
# length alma keeps for its one character.
TRAIL_PERIOD_MS = 1200
TRAIL_LEN = 32


# ---- scheduled events ------------------------------------------------------
# With AUTO on, the room lives without you: one event fires from a random
# resident every so often.  Uniformly random on purpose - weighting the roll by
# personality would be inventing psychology the OCC model does not contain.
SCHEDULE_MS = 40 * 1000              # simulated ms between scheduled events
SCHEDULE_JITTER_MS = 25 * 1000       # ...plus up to this much


# ---- personality -----------------------------------------------------------
TRAITS = ("open", "con", "extra", "agree", "neur")
TRAIT_SHORT = {
    "open": "OPEN", "con": "CONSC", "extra": "EXTRA", "agree": "AGREE",
    "neur": "NEUR",
}
TRAIT_STEP = 0.05
DEFAULT_PERSONALITY = {
    "open": 0.4, "con": 0.8, "extra": 0.6, "agree": 0.3, "neur": 0.4,
}

# Mehrabian's regression is on STANDARDISED traits, so 0.0 is the average person
# and the useful range is -1..+1 - not 0..1.  Every archetype below is a profile
# written to land in a different octant of the PAD cube, so a world rolled from
# three of them starts with three genuinely different people rather than three
# shades of content.  The octant each implies is asserted in the self-test.
#
#   (label, open, con, extra, agree, neur)
ARCHETYPES = (
    ("SUNNY",   0.5,  0.3,  0.8,  0.8, -0.4),   # Exuberant
    ("SETTLED", 0.2,  0.8,  0.1,  0.6,  0.5),   # Relaxed
    ("ALOOF",   0.2,  0.5,  0.4, -0.7,  0.3),   # Disdainful
    ("PRICKLY", 0.2,  0.3,  0.6, -0.8, -0.6),   # Hostile
    ("JUMPY",   0.4, -0.4, -0.5, -0.5, -0.5),   # Anxious
    ("EAGER",   0.3, -0.3, -0.4,  0.7, -0.2),   # Dependent
    ("MEEK",    0.0, -0.2, -0.6,  0.6,  0.5),   # Docile
    ("FLAT",   -0.5, -0.4, -0.5, -0.3,  0.2),   # Bored
    # The paper's own worked example: the virtual teacher whose default mood
    # Gebhard prints as slightly relaxed, P=0.38 A=-0.08 D=0.50.
    ("VALERIE", 0.4,  0.8,  0.6,  0.3,  0.4),   # Relaxed
)


def personality(index):
    """One archetype as the dict affect.Affect wants."""
    row = ARCHETYPES[index % len(ARCHETYPES)]
    return {t: row[i + 1] for i, t in enumerate(TRAITS)}


# ---- rolling an appearance -------------------------------------------------
# Uniform over every piece gives a lot of people in a chef's hat and safety
# goggles.  Hair is near-universal, an outfit is compulsory, and the two
# accessory slots are occasional - which is what a room of housemates looks
# like.  One in N, so 0 disables a slot entirely.
BALD_IN = 12                 # 1 in 12 has no hair
FACE_IN = 3                  # 1 in 3 wears something on their face
HEAD_IN = 4                  # 1 in 4 wears something on their head

# Which room they live in.  Workshop: a mid-brown wall and dark boards, which
# is the only one of the six a coloured light reads on - the pale rooms wash the
# auras out and the blue one tints every mood towards its own hue.
ROOM = 2


# ---- layout ----------------------------------------------------------------
W, H = 320, 240
HEADER_H = 16

STAGE_TOP = HEADER_H
FLOOR_TOP = 150              # where the wallpaper gives way to floorboards
STAGE_BOT = 168
FEET_Y = 160                 # the line all three stand on

FIG_SCALE = 3
ROOM_SCALE = 2               # the trio on the setup screen
TILE = 16

RAIL_TOP = 170
RAIL_H = 46
HINT_TOP = RAIL_TOP + RAIL_H  # 216

# Three columns, centred, with the outer two clear of the screen edges.
SLOTS = 3
COLUMN = (54, 160, 266)

# The band of mood colour on the wall behind each resident. Its width is fixed;
# how far up the wall it reaches is the mood's strength.
AURA_W = 76
AURA_MIN = 0.30              # fraction of the wall a zero-strength mood lights

# The pool of the same colour on the floor at their feet.
POOL_W, POOL_H = 56, 9

# When an event lands, a ring expands from whoever it happened to and from
# everyone who noticed. Real milliseconds - it is a UI flash, not weather.
HIT_MS = 700

# Breathing. The two poses alternate; the rate is read off arousal, so a calm
# resident is visibly slower than an agitated one.
BREATH_SLOW_MS = 3600        # a full breath at arousal -1
BREATH_FAST_MS = 1100        # ...and at +1
BREATH_UP = 0.34             # fraction of the cycle spent at the top of it

# ---- the detail view -------------------------------------------------------
PLOT_X, PLOT_Y, PLOT_S = 6, 22, 140
COL2_X = 154

# ---- the log ---------------------------------------------------------------
LOG_LEN = 24                 # entries kept
LOG_ROW_H = 15
LOG_Y = 24


# ---- views -----------------------------------------------------------------
V_WORLD, V_DETAIL, V_LOG, V_GUIDE = range(4)
VIEW_NAMES = ("COMMONS", "DETAIL", "LOG", "GUIDE")
# Views where UP/DOWN pick an event and C fires it.
FIRING_VIEWS = (V_WORLD, V_DETAIL)


# ---- palette ---------------------------------------------------------------
# ALMA's instrument panel, unchanged, because a mood colour has to mean the same
# thing in both apps.  The stage in the middle is the only warm thing on screen.
THEME = {
    "BG":     (13, 14, 18),
    "PANEL":  (23, 25, 32),
    "EDGE":   (44, 48, 60),
    "TRACK":  (40, 44, 56),
    "INK":    (232, 236, 245),
    "DIM":    (116, 124, 144),
    "FAINT":  (62, 68, 84),
    "ACCENT": (255, 214, 92),
    "VEC":    (176, 186, 210),
}

OCTANT_COLORS = {
    "Exuberant":  (255, 190, 60),
    "Dependent":  (255, 132, 176),
    "Relaxed":    (86, 214, 168),
    "Docile":     (128, 198, 226),
    "Hostile":    (240, 78, 68),
    "Anxious":    (168, 112, 236),
    "Disdainful": (150, 162, 186),
    "Bored":      (122, 116, 104),
}


# ---- the guide -------------------------------------------------------------
# Rows of (kind, left, right): "h" heading, "t" label + explanation,
# "o" an octant swatch + its PAD signs, "-" spacer.
GUIDE = (
    ("h", "BUTTONS", ""),
    ("t", "UP / DOWN", "pick an event"),
    ("t", "C", "make it happen - HOLD to repeat"),
    ("t", "B", "pick who it happens to"),
    ("t", "HOLD B", "time scale x1 / x10 / x60"),
    ("t", "A", "next view"),
    ("t", "HOLD A", "start a new world"),
    ("t", "C on LOG", "let the room run itself"),
    ("-", "", ""),

    ("h", "READING A RESIDENT", ""),
    ("t", "the word", "the octant their mood is in"),
    ("t", "wall colour", "the same octant"),
    ("t", "how high it reaches", "how far from PAD zero"),
    ("t", "breathing rate", "arousal"),
    ("t", "the bright badge", "an emotion above baseline"),
    ("t", "a ring", "an event just reached them"),
    ("-", "", ""),

    ("h", "THE DETAIL VIEW", ""),
    ("t", "the square", "pleasure across, arousal up"),
    ("t", "the big dot", "the mood now; its size is"),
    ("t", "", "dominance, the third axis"),
    ("t", "the hollow ring", "where their personality"),
    ("t", "", "parks them - mood goes home"),
    ("t", "the cross", "where the active emotions"),
    ("t", "", "are pulling, all averaged"),
    ("t", "the faint dots", "the path they took to here"),
    ("-", "", ""),

    ("h", "MOOD OCTANTS", ""),
    ("o", "Exuberant", "+P +A +D"),
    ("o", "Dependent", "+P +A -D"),
    ("o", "Relaxed", "+P -A +D"),
    ("o", "Docile", "+P -A -D"),
    ("o", "Hostile", "-P +A +D"),
    ("o", "Anxious", "-P +A -D"),
    ("o", "Disdainful", "-P -A +D"),
    ("o", "Bored", "-P -A -D"),
    ("-", "", ""),

    ("h", "WHY THEY DIVERGE", ""),
    ("t", "one event", "elicits the SAME emotions"),
    ("t", "", "in everyone who notices it"),
    ("t", "but", "each of them has their own"),
    ("t", "", "baseline to be pulled away from"),
    ("t", "so", "the same news lands differently"),
    ("t", "", "on a SUNNY and on a FLAT"),
    ("-", "", ""),

    ("h", "WHAT THE MOOD IS DOING", ""),
    ("t", "PULL", "drawn toward the center"),
    ("t", "PUSH", "past it, deeper in"),
    ("t", "RETURN", "drifting home, no emotions"),
    ("t", "STEADY", "sitting on its baseline"),
    ("-", "", ""),

    ("h", "NOTHING IS SAVED", ""),
    ("t", "leaving the app", "ends the world"),
    ("t", "HOLD A", "rolls three new people"),
    ("-", "", ""),

    ("h", "SOURCE", ""),
    ("t", "ALMA", "Gebhard, DFKI, AAMAS'05"),
    ("t", "emotions", "24 OCC types, Table 2"),
    ("t", "bodies", "LimeZu Modern Interiors"),
)


# ---------------------------------------------------------------------------
# Self-test: every archetype must land in the octant its comment claims, and no
# two may share one.  Never runs on the badge.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import occ

    WANT = ("Exuberant", "Relaxed", "Disdainful", "Hostile", "Anxious",
            "Dependent", "Docile", "Bored", "Relaxed")
    seen = {}
    ok = True
    for i, (label, *_) in enumerate(ARCHETYPES):
        p = personality(i)
        pl = 0.21 * p["extra"] + 0.59 * p["agree"] + 0.19 * p["neur"]
        ar = 0.15 * p["open"] + 0.30 * p["agree"] - 0.57 * p["neur"]
        do = (0.25 * p["open"] + 0.17 * p["con"] + 0.60 * p["extra"]
              - 0.32 * p["agree"])
        got = occ.octant_of(pl, ar, do)
        good = got == WANT[i]
        ok = ok and good
        seen.setdefault(got, []).append(label)
        print("%-8s P%+.2f A%+.2f D%+.2f  %-11s |%.2f|  %s"
              % (label, pl, ar, do, got, occ.norm(pl, ar, do),
                 "ok" if good else "WANT " + WANT[i]))
    # VALERIE deliberately shares Relaxed with SETTLED; everything else is its
    # own octant, so the eight presets cover the whole cube.
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    print("\n%d/8 octants covered, duplicates: %s"
          % (len(seen), dupes or "none"))
    ok = ok and len(seen) == 8 and list(dupes) == ["Relaxed"]
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
