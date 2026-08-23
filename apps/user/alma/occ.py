# The two lookup tables from ALMA - A Layered Model of Affect (Patrick Gebhard,
# DFKI, AAMAS'05).  Reproduced verbatim from the paper so the simulation rests
# on the published numbers rather than on plausible-looking invented ones.
#
# Pure data + pure functions: this module touches no badgeware globals, so it
# imports and runs on the desktop too (see tools/sim, and the self-test at the
# bottom of affect.py).

# Longest distance inside one octant of the PAD cube, i.e. the corner (1,1,1).
# The paper uses it as the reference length for BOTH mood strength wording and
# the mood movement speeds.  math.sqrt is avoided at import time on purpose -
# this is a constant, not a computation.
SQRT3 = 1.7320508075688772


# ---- Table 1: mood octants of the PAD space --------------------------------
# Keyed by the sign triple (pleasure, arousal, dominance), +1 / -1.
OCTANTS = {
    (+1, +1, +1): "Exuberant",
    (-1, -1, -1): "Bored",
    (+1, +1, -1): "Dependent",
    (-1, -1, +1): "Disdainful",
    (+1, -1, +1): "Relaxed",
    (-1, +1, -1): "Anxious",
    (+1, -1, -1): "Docile",
    (-1, +1, +1): "Hostile",
}

# ---- Table 2: mapping of OCC emotions into PAD space -----------------------
# 24 emotion types (the 22 OCC types plus the Liking/Disliking and Love/Hate
# attraction pairs the EmotionEngine distinguishes).  Values are exactly as
# printed in the paper, including its inconsistent decimal places (0.5 for
# Admiration but 0.40/0.16/-0.24 for Liking).
EMOTIONS = {
    "Admiration":     (0.5, 0.3, -0.2),
    "Anger":          (-0.51, 0.59, 0.25),
    "Disliking":      (-0.4, 0.2, 0.1),
    "Disappointment": (-0.3, 0.1, -0.4),
    "Distress":       (-0.4, -0.2, -0.5),
    "Fear":           (-0.64, 0.60, -0.43),
    "FearsConfirmed": (-0.5, -0.3, -0.7),
    "Gloating":       (0.3, -0.3, -0.1),
    "Gratification":  (0.6, 0.5, 0.4),
    "Gratitude":      (0.4, 0.2, -0.3),
    "HappyFor":       (0.4, 0.2, 0.2),
    "Hate":           (-0.6, 0.6, 0.3),
    "Hope":           (0.2, 0.2, -0.1),
    "Joy":            (0.4, 0.2, 0.1),
    "Liking":         (0.40, 0.16, -0.24),
    "Love":           (0.3, 0.1, 0.2),
    "Pity":           (-0.4, -0.2, -0.5),
    "Pride":          (0.4, 0.3, 0.3),
    "Relief":         (0.2, -0.3, 0.4),
    "Remorse":        (-0.3, 0.1, -0.6),
    "Reproach":       (-0.3, -0.1, 0.4),
    "Resentment":     (-0.2, -0.3, -0.2),
    "Satisfaction":   (0.3, -0.2, 0.4),
    "Shame":          (-0.3, 0.1, -0.6),
}

def octant_of(p, a, d):
    """Table 1 lookup: the discrete mood word for a point in PAD space.

    A coordinate of exactly 0.0 is counted as positive - the paper leaves the
    boundary undefined and something has to win, so the default mood of a
    blank personality (0,0,0) reads as Exuberant rather than crashing.
    """
    return OCTANTS[(1 if p >= 0 else -1,
                    1 if a >= 0 else -1,
                    1 if d >= 0 else -1)]


def norm(p, a, d):
    """Strength of a mood: its distance from the PAD zero point."""
    return (p * p + a * a + d * d) ** 0.5
