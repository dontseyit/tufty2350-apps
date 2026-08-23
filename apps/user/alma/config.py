# Tunable parameters for the ALMA affect simulation, plus the palette and
# layout metrics.  Everything the model's behaviour depends on lives here, so
# the simulation is genuinely parametric: change a number, reload, watch it.
#
# Pure data only - no badgeware globals - so this imports on the desktop.
# render.py turns the RGB tuples into pen objects in its init().

from occ import SQRT3

DEBUG = False


def log(*args):
    if DEBUG:
        print("[alma]", *args)


# ---- ALMA timing constants -------------------------------------------------
# Straight from the paper's example <AffectComputation> document (Figure 3) and
# the surrounding prose.  All in milliseconds of SIMULATED time.

# <EmotionDecay time="20000" function="linear"/>
# An elicited emotion falls linearly from the intensity it was elicited at to
# zero over this span, then leaves the active set.
#
# We ship the prose's looser alternative instead ("decayed over a certain
# amount of time (for example, 1 minute)") - equally the paper's, and it
# integrates three times as much mood displacement per stimulus.
EMOTION_DECAY_MS = 60000

# <EmotionBaseline threshold="0.4"/>
# ALMA's baseline: an emotion below this is too faint to be reported as the
# character's dominant emotion.  It still counts towards the virtual emotion
# center - the paper folds *all* active emotions into that - so a swarm of
# weak emotions can still move the mood.
EMOTION_BASELINE = 0.4

# The time the pull and push function needs to carry a mood one octant centre
# to another, measured against the reference length SQRT3, at full virtual-
# emotion-center intensity (1.0).  A weaker center moves proportionally slower.
#
# DEPARTURE FROM THE PAPER: "our character's usual mood change time is
# 10 minutes" (PAPER_MOOD_CHANGE_MS below).  Against a one-minute emotion that
# makes a single stimulus worth 0.07 of PAD displacement - true to the model,
# but it reads as an inert character on a badge you look at for a minute.  At
# two minutes a stimulus lands visibly without the mood snapping about.
# Tunable live on the DYNAMICS view; C there restores every paper value.
MOOD_CHANGE_MS = 2 * 60 * 1000

# How long the mood takes to walk the reference length SQRT3 back to the
# personality baseline, so a mood half that far away takes half as long.
#
# NOTE: the paper contradicts itself here - the prose says 20 minutes, while
# Figure 3's XML shows <MoodReturn time="600000"/>, i.e. 10.
#
# DEPARTURE FROM THE PAPER: 40 minutes, double the prose's figure, so a mood a
# stimulus worked for stays worked-for instead of evaporating while you watch.
MOOD_RETURN_MS = 40 * 60 * 1000

# Mood strength wording.  The paper divides "the longest distance in a mood
# octant" (SQRT3) into three parts and names them slightly / moderate / fully.
#
# NOTE: both worked examples in the paper are labelled "slightly" at a distance
# of ~0.63, which is past the 0.577 boundary that rule produces.  We implement
# the rule as stated and leave the thresholds here to be nudged.
MOOD_SLIGHT_MAX = SQRT3 / 3.0        # 0.577
MOOD_MODERATE_MAX = SQRT3 * 2.0 / 3.0  # 1.155
INTENSITY_WORDS = ("slightly", "moderate", "fully")

# The mood's drift back to the personality baseline is suspended while any
# emotion is active.  The paper describes pull/push and mood return as separate
# concerns without saying which wins; running them together lets a weak virtual
# emotion center be out-paced by the return, so the mood would never move.
RETURN_WHILE_ACTIVE = False

# The virtual emotion center is placed at the intensity-WEIGHTED centre of the
# active emotions.  The paper says "center"; Gebhard elsewhere describes it as a
# weighted sum.  With equal intensities the two agree, so weighting only adds
# the sensible behaviour that a strong emotion pulls the center towards itself.
WEIGHTED_CENTER = True


# ---- runtime-tunable dynamics ---------------------------------------------
# The DYNAMICS view edits these four in place. Each entry is
#   (config attribute, label, unit, ladder of values, the paper's value)
# and UP/DOWN step along the ladder - a ladder rather than a fixed increment so
# a couple of presses cross an order of magnitude and every stop is a sane
# number. C on that view restores the whole PAPER column.
SECONDS = "s"
UNITLESS = ""

DYNAMICS = (
    ("EMOTION_DECAY_MS", "EMOTION DECAY", SECONDS,
     (5000, 10000, 20000, 30000, 45000, 60000, 90000, 120000, 180000, 300000),
     20000),
    ("MOOD_CHANGE_MS", "MOOD CHANGE", SECONDS,
     (15000, 30000, 60000, 120000, 180000, 300000, 600000, 1200000),
     600000),
    ("MOOD_RETURN_MS", "MOOD RETURN", SECONDS,
     (60000, 120000, 300000, 600000, 1200000, 2400000, 3600000),
     1200000),
    ("EMOTION_BASELINE", "EMOTION BASELINE", UNITLESS,
     (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8),
     0.4),
)


def set_param(name, value):
    """Assign one of the DYNAMICS parameters at runtime.

    Goes through globals() rather than setattr so it behaves identically under
    MicroPython, and keeps every read site as a plain `cfg.NAME` lookup - the
    model picks the new value up on its very next step.
    """
    globals()[name] = value


def param_value(name):
    return globals()[name]


def nearest_index(ladder, value):
    """The rung of a ladder a (possibly restored) value sits closest to."""
    best, best_d = 0, None
    for i, v in enumerate(ladder):
        d = abs(v - value)
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


# ---- simulation clock ------------------------------------------------------
# ALMA's constants are honest but slow: at 1x you would watch for ten minutes
# to see the mood cross an octant.  B steps through these multipliers; the
# active one is always shown in the header so the display never lies.
TIME_SCALES = (1, 10, 60, 300)
DEFAULT_SCALE_INDEX = 1              # start at 10x

# How often (in simulated ms) a point is appended to the PAD map's mood trail,
# and how many points are kept.
# Sampled often enough that the trail draws as a smooth path rather than a row
# of separate dots, while still remembering about a minute of simulated time -
# long enough for a journey across two or three octants to stay on screen.
# The count is also the per-frame line-segment budget, so it stays modest.
TRAIL_PERIOD_MS = 900
TRAIL_LEN = 64


# ---- personality -----------------------------------------------------------
# The Big Five profile the paper uses for its worked example (the virtual
# teacher Valerie): open=0.4 con=0.8 extra=0.6 agree=0.3 neur=0.4, which the
# Mehrabian regression turns into P=0.38 A=-0.08 D=0.50, "slightly relaxed".
TRAITS = ("open", "con", "extra", "agree", "neur")
TRAIT_LABELS = {
    "open": "OPENNESS",
    "con": "CONSCIENTIOUSNESS",
    "extra": "EXTRAVERSION",
    "agree": "AGREEABLENESS",
    "neur": "NEUROTICISM",
}
DEFAULT_PERSONALITY = {
    "open": 0.4, "con": 0.8, "extra": 0.6, "agree": 0.3, "neur": 0.4,
}
TRAIT_STEP = 0.05


# ---- views -----------------------------------------------------------------
(V_CHARACTER, V_PADMAP, V_EMOTIONS, V_PERSONALITY, V_DYNAMICS,
 V_GUIDE) = range(6)
VIEW_NAMES = ("CHARACTER", "PAD MAP", "EMOTIONS", "PERSONALITY", "DYNAMICS",
              "GUIDE")

# Views where UP/DOWN edit a value instead of choosing a stimulus.
EDIT_VIEWS = (V_PERSONALITY, V_DYNAMICS)

# Views that watch the simulation, so UP/DOWN pick a stimulus and C applies it.
# The guide is in neither group: UP/DOWN scroll it and C jumps to the top.
STIMULUS_VIEWS = (V_CHARACTER, V_PADMAP, V_EMOTIONS)


# ---- the guide -------------------------------------------------------------
# Rows of (kind, left, right). Kinds:
#   "h"    section heading
#   "t"    label + value/explanation
#   "o"    a mood octant: swatch + name + its PAD signs
#   "-"    spacer
GUIDE = (
    ("h", "BUTTONS", ""),
    ("t", "UP / DOWN", "pick a stimulus"),
    ("t", "C", "apply it - HOLD to repeat"),
    ("t", "A", "next view"),
    ("t", "B", "time scale x1..x300"),
    ("t", "on editor views", "B picks, UP/DN adjusts"),
    ("-", "", ""),

    ("h", "THE ORB IS THE MOOD", ""),
    ("t", "colour", "which octant it is in"),
    ("t", "size", "dominance"),
    ("t", "tall vs squat", "pleasure"),
    ("t", "breathing, sway", "arousal"),
    ("t", "halo", "distance from PAD zero"),
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

    ("h", "WHAT THE MOOD IS DOING", ""),
    ("t", "PULL", "drawn toward the center"),
    ("t", "PUSH", "past it, deeper in"),
    ("t", "RETURN", "drifting home, no emotions"),
    ("t", "STEADY", "sitting on its baseline"),
    ("-", "", ""),

    ("h", "DYNAMICS: WHAT MOVES WHAT", ""),
    ("t", "EMOTION DECAY", "how long one emotion lives."),
    ("t", "", "longer = further mood shift"),
    ("t", "MOOD CHANGE", "time to cross the space."),
    ("t", "", "SHORTER = BIGGER IMPACT"),
    ("t", "MOOD RETURN", "time to drift home."),
    ("t", "", "longer = the mood lingers"),
    ("t", "EMOTION BASELINE", "floor to be called dominant"),
    ("t", "IMPACT", "how far one stimulus moves it"),
    ("t", "RECOVERY", "how long that takes to undo"),
    ("-", "", ""),

    ("h", "PERSONALITY", ""),
    ("t", "Big Five", "-> a PAD baseline"),
    ("t", "", "(Mehrabian regression)"),
    ("t", "the baseline", "is where the mood goes home"),
    ("t", "C on that page", "re-seed + clear emotions"),
    ("-", "", ""),

    ("h", "SOURCE", ""),
    ("t", "ALMA", "Gebhard, DFKI, AAMAS'05"),
    ("t", "emotions", "24 OCC types, Table 2"),
)


# ---- palette ---------------------------------------------------------------
# Near-black instrument panel; each mood octant owns a hue so the character's
# colour, the map's ball and the header word always agree.
THEME = {
    "BG":     (13, 14, 18),
    "PANEL":  (23, 25, 32),
    "EDGE":   (44, 48, 60),
    "TRACK":  (40, 44, 56),      # empty part of a bar
    "INK":    (232, 236, 245),
    "DIM":    (116, 124, 144),
    "FAINT":  (62, 68, 84),
    "ACCENT": (255, 214, 92),
    "VEC":    (176, 186, 210),   # the paper's "dark grey ball"
    # Pre-blended, not translucent: black at ~43% over PANEL. The badge draws
    # this every frame under a moving character, and a translucent pen would
    # mean per-pixel compositing for no visual difference - the colour behind
    # the contact shadow is always the PANEL-coloured ground pad.
    "SHADOW": (13, 14, 18),
}

OCTANT_COLORS = {
    "Exuberant":  (255, 190, 60),    # warm, bright, up
    "Dependent":  (255, 132, 176),   # warm but yielding
    "Relaxed":    (86, 214, 168),    # calm green
    "Docile":     (128, 198, 226),   # quiet blue
    "Hostile":    (240, 78, 68),     # hot red
    "Anxious":    (168, 112, 236),   # jittery violet
    "Disdainful": (150, 162, 186),   # cold steel
    "Bored":      (122, 116, 104),   # flat grey-brown
}


# ---- layout ----------------------------------------------------------------
W, H = 320, 240
HEADER_H = 18          # top bar: app name, mood word, speed
RAIL_H = 40            # bottom bar: the selected external stimulus
RAIL_Y = H - RAIL_H    # 200
BODY_Y = HEADER_H + 2  # 20
BODY_H = RAIL_Y - BODY_Y - 2
