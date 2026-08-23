# The ALMA affect model: personality -> default mood, emotions -> virtual
# emotion center -> pull/push mood change -> return to the default mood.
#
# Deliberately free of badgeware globals so it can be exercised on the desktop;
# run `python3 affect.py` from this directory for a self-test that checks the
# implementation against the worked examples printed in the paper.

import config as cfg
import occ

# Movement phase, for the UI to label what the mood is currently doing.
IDLE, PULL, PUSH, RETURN = range(4)
# IDLE is named STEADY for display: the mood is sitting on its baseline,
# which is distinct from the *character* being idle.
PHASE_NAMES = ("STEADY", "PULL", "PUSH", "RETURN")

_EPS = 1e-9


# ---- personality -> default mood -------------------------------------------
def default_mood(personality):
    """Mehrabian's regression from the Big Five onto a point in PAD space.

    Reproduced from the paper; the coefficients also appear in its Figure 3 as
    <PleasureRelation> / <ArousalRelation> / <DominanceRelation>.  Note that
    dominance has no neuroticism term (the XML spells it out as neur="0.0").
    """
    o = personality["open"]
    c = personality["con"]
    e = personality["extra"]
    a = personality["agree"]
    n = personality["neur"]
    return (
        0.21 * e + 0.59 * a + 0.19 * n,
        0.15 * o + 0.30 * a - 0.57 * n,
        0.25 * o + 0.17 * c + 0.60 * e - 0.32 * a,
    )


def intensity_word(strength):
    """slightly / moderate / fully, from a mood's distance to the zero point."""
    if strength < cfg.MOOD_SLIGHT_MAX:
        return cfg.INTENSITY_WORDS[0]
    if strength < cfg.MOOD_MODERATE_MAX:
        return cfg.INTENSITY_WORDS[1]
    return cfg.INTENSITY_WORDS[2]


def _clamp1(v):
    return -1.0 if v < -1.0 else (1.0 if v > 1.0 else v)


class ActiveEmotion:
    """One elicited OCC emotion, decaying linearly towards zero."""

    def __init__(self, name, intensity):
        self.name = name
        self.start = intensity        # intensity it was elicited at
        self.intensity = intensity
        self.elapsed = 0.0            # simulated ms since elicitation

    def decay(self, dt):
        # <EmotionDecay function="linear"/>: a straight line from the elicited
        # intensity to zero across EMOTION_DECAY_MS, so every emotion lives for
        # exactly that long regardless of how strongly it started.
        self.elapsed += dt
        k = 1.0 - self.elapsed / cfg.EMOTION_DECAY_MS
        self.intensity = self.start * k if k > 0.0 else 0.0
        return self.intensity > 0.0

    def pad(self):
        return occ.EMOTIONS[self.name]


class Affect:
    """A character's affective state: personality, mood, and active emotions."""

    def __init__(self, personality=None):
        self.personality = dict(personality or cfg.DEFAULT_PERSONALITY)
        self.default_mood = default_mood(self.personality)
        self.mood = list(self.default_mood)
        self.active = []
        self.vec = None      # (p, a, d, intensity) of the virtual emotion center
        self.phase = IDLE

    # ---- input ------------------------------------------------------------
    def elicit(self, name, intensity):
        """Appraisal result: an OCC emotion at an intensity in (0, 1].

        Re-eliciting an emotion that is still active refreshes it rather than
        stacking a duplicate - it keeps the stronger intensity and restarts the
        decay clock.  Repetition still intensifies the *mood*, but through
        ALMA's own mechanism: the center stays put and the push phase drives
        the mood further into its octant.
        """
        intensity = _clamp1(intensity)
        if intensity <= 0.0 or name not in occ.EMOTIONS:
            return
        for e in self.active:
            if e.name == name:
                e.start = max(e.intensity, intensity)
                e.intensity = e.start
                e.elapsed = 0.0
                return
        self.active.append(ActiveEmotion(name, intensity))

    def clear(self):
        self.active = []
        self.vec = None
        self.phase = IDLE

    def reseed(self):
        """Drop all emotions and put the mood back on the personality baseline."""
        self.clear()
        self.mood = list(self.default_mood)

    def set_trait(self, trait, value):
        self.personality[trait] = _clamp1(value)
        self.default_mood = default_mood(self.personality)

    # ---- per-frame update -------------------------------------------------
    def update(self, dt):
        """Advance the model by dt milliseconds of simulated time."""
        if dt <= 0:
            return
        self._decay(dt)
        self.vec = self._virtual_emotion_center()
        self._move_mood(dt)

    def _decay(self, dt):
        if self.active:
            self.active = [e for e in self.active if e.decay(dt)]

    def _virtual_emotion_center(self):
        """The centre of all active emotions in PAD space, plus its intensity.

        Position is the intensity-weighted centroid (see cfg.WEIGHTED_CENTER);
        intensity is the plain average of the active intensities, capped at 1.0
        exactly as the paper specifies.  No active emotions means no center,
        and a mood that is not influenced by emotions at all.
        """
        n = len(self.active)
        if n == 0:
            return None
        p = a = d = 0.0
        total = 0.0
        weight = 0.0
        for e in self.active:
            ep, ea, ed = e.pad()
            w = e.intensity if cfg.WEIGHTED_CENTER else 1.0
            p += ep * w
            a += ea * w
            d += ed * w
            weight += w
            total += e.intensity
        if weight <= _EPS:
            return None
        return (p / weight, a / weight, d / weight, min(1.0, total / n))

    def _move_mood(self, dt):
        if self.vec is None:
            self._return_to_default(dt)
            return
        moved = self._pull_push(dt)
        if cfg.RETURN_WHILE_ACTIVE:
            self._return_to_default(dt, keep_phase=moved)

    def _pull_push(self, dt):
        """ALMA's pull and push mood change function.

        The current mood is attracted towards the virtual emotion center while
        it lies between the zero point and that center (pull phase); once it is
        at or beyond the center it is pushed away from the origin, further into
        the octant it already occupies (push phase).  The center's intensity
        sets the speed: at full intensity the mood covers the reference length
        SQRT3 in one MOOD_CHANGE_MS.
        """
        cp, ca, cd, ci = self.vec
        if ci <= _EPS:
            return False
        step = ci * (occ.SQRT3 / cfg.MOOD_CHANGE_MS) * dt
        if step <= _EPS:
            return False

        m = self.mood
        cc = cp * cp + ca * ca + cd * cd
        if cc <= _EPS:
            # The center sits on the zero point - no direction to move along.
            return False

        # Where the mood falls along the origin -> center line.  Below 1 it is
        # still short of the center (pull); at or past 1 it has crossed it (push).
        t = (m[0] * cp + m[1] * ca + m[2] * cd) / cc

        if t < 1.0:
            dx, dy, dz = cp - m[0], ca - m[1], cd - m[2]
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            if dist <= _EPS:
                return False
            if step > dist:
                step = dist          # land on the center; push from here on
            self.phase = PULL
        else:
            dx, dy, dz = m[0], m[1], m[2]
            dist = occ.norm(dx, dy, dz)
            if dist <= _EPS:
                # Mood is on the origin and the center is too close to call;
                # head outwards along the center instead of stalling.
                dx, dy, dz = cp, ca, cd
                dist = cc ** 0.5
            self.phase = PUSH

        k = step / dist
        m[0] = _clamp1(m[0] + dx * k)
        m[1] = _clamp1(m[1] + dy * k)
        m[2] = _clamp1(m[2] + dz * k)
        return True

    def _return_to_default(self, dt, keep_phase=False):
        """The mood's slow drift back towards the personality baseline.

        Constant speed: the paper defines the return time as the time to cover
        the longest distance in a mood octant (SQRT3), so a mood that is half
        that far away takes half as long to get home.
        """
        m = self.mood
        dp, da, dd = self.default_mood
        dx, dy, dz = dp - m[0], da - m[1], dd - m[2]
        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
        if dist <= _EPS:
            if not keep_phase:
                self.phase = IDLE
            return
        step = (occ.SQRT3 / cfg.MOOD_RETURN_MS) * dt
        if step >= dist:
            m[0], m[1], m[2] = dp, da, dd
            if not keep_phase:
                self.phase = IDLE
            return
        k = step / dist
        m[0] = _clamp1(m[0] + dx * k)
        m[1] = _clamp1(m[1] + dy * k)
        m[2] = _clamp1(m[2] + dz * k)
        if not keep_phase:
            self.phase = RETURN

    # ---- readouts ---------------------------------------------------------
    def strength(self):
        return occ.norm(self.mood[0], self.mood[1], self.mood[2])

    def mood_words(self):
        """(intensity word, octant name) - e.g. ("slightly", "Relaxed")."""
        return (intensity_word(self.strength()),
                occ.octant_of(self.mood[0], self.mood[1], self.mood[2]))

    def octant(self):
        return occ.octant_of(self.mood[0], self.mood[1], self.mood[2])

    def dominant(self):
        """The strongest active emotion above ALMA's baseline, or None."""
        best = None
        for e in self.active:
            if e.intensity >= cfg.EMOTION_BASELINE and (
                    best is None or e.intensity > best.intensity):
                best = e
        return best

    def by_intensity(self):
        return sorted(self.active, key=lambda e: -e.intensity)

    # ---- persistence (badgeware State) ------------------------------------
    def save_state(self):
        return {"personality": self.personality, "mood": list(self.mood)}

    def restore(self, saved):
        p = saved.get("personality")
        if isinstance(p, dict) and all(t in p for t in cfg.TRAITS):
            self.personality = {t: _clamp1(float(p[t])) for t in cfg.TRAITS}
            self.default_mood = default_mood(self.personality)
        m = saved.get("mood")
        if isinstance(m, (list, tuple)) and len(m) == 3:
            self.mood = [_clamp1(float(v)) for v in m]


# ---------------------------------------------------------------------------
# Self-test against the paper.  Never runs on the badge.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = True

    def check(label, got, want, tol=0.005):
        global ok
        good = abs(got - want) <= tol
        ok = ok and good
        print("%-46s %8.3f  want %8.3f  %s"
              % (label, got, want, "ok" if good else "FAIL"))

    # Paper, section 3: "a person, whose personality is defined with the
    # following big five personality traits: openness=0.4, conscientiousness=0.8,
    # extraversion=0.6, agreeableness=0.3, and neuroticism=0.4 has the default
    # mood slightly relaxed (pleasure=0.38, arousal=-0.08, dominance=0.50)."
    a = Affect()
    p, ar, d = a.default_mood
    check("Valerie default pleasure", p, 0.38)
    check("Valerie default arousal", ar, -0.08)
    check("Valerie default dominance", d, 0.50)
    word, octant = a.mood_words()
    print("%-46s %s %s (strength %.3f)"
          % ("Valerie default mood", word, octant, a.strength()))
    assert octant == "Relaxed", octant
    # The paper calls this one "slightly relaxed", but its own stated rule
    # (thirds of SQRT3) puts a strength of 0.632 in the middle band.  We follow
    # the rule; cfg.MOOD_SLIGHT_MAX is where to change that.
    if word != "slightly":
        print("%-46s paper says 'slightly', stated rule says '%s'"
              % ("  ^ known divergence in the source", word))

    # Paper, section 3: mood (0.25, -0.18, 0.12) is "slightly relaxed".
    a.mood = [0.25, -0.18, 0.12]
    print("%-46s %s %s (strength %.3f)"
          % ("worked example (0.25,-0.18,0.12)",
             a.mood_words()[0], a.mood_words()[1], a.strength()))
    assert a.mood_words() == ("slightly", "Relaxed")

    # Every emotion in Table 2 must land in the octant the paper's own last
    # column claims it does - a direct proof-read of the transcribed table.
    TABLE2_OCTANTS = {
        "Admiration": "Dependent", "Anger": "Hostile", "Disliking": "Hostile",
        "Disappointment": "Anxious", "Distress": "Bored", "Fear": "Anxious",
        "FearsConfirmed": "Bored", "Gloating": "Docile",
        "Gratification": "Exuberant", "Gratitude": "Dependent",
        "HappyFor": "Exuberant", "Hate": "Hostile", "Hope": "Dependent",
        "Joy": "Exuberant", "Liking": "Dependent", "Love": "Exuberant",
        "Pity": "Bored", "Pride": "Exuberant", "Relief": "Relaxed",
        "Remorse": "Anxious", "Reproach": "Disdainful",
        "Resentment": "Bored", "Satisfaction": "Relaxed", "Shame": "Anxious",
    }
    bad = [n for n, want in TABLE2_OCTANTS.items()
           if occ.octant_of(*occ.EMOTIONS[n]) != want]
    print("%-46s %d/24 rows agree with the paper's octant column %s"
          % ("Table 2", 24 - len(bad), "ok" if not bad else "FAIL " + str(bad)))
    ok = ok and not bad
    assert len(occ.EMOTIONS) == 24

    # Dynamics. The app ships deliberately punchier constants than the paper
    # (see config.py), so pin the paper's values first and check the model
    # against those - then measure what the shipped defaults change.
    def fear_run(decay_ms, change_ms):
        cfg.set_param("EMOTION_DECAY_MS", decay_ms)
        cfg.set_param("MOOD_CHANGE_MS", change_ms)
        m = Affect()
        m.reseed()
        m.elicit("Fear", 1.0)
        steps = int(decay_ms // 100)
        for _ in range(steps):
            m.update(100)                  # exactly one decay lifetime
        return m

    shipped = (cfg.EMOTION_DECAY_MS, cfg.MOOD_CHANGE_MS, cfg.MOOD_RETURN_MS)
    paper = {name: value for name, _l, _u, _ld, value in cfg.DYNAMICS}

    a = fear_run(paper["EMOTION_DECAY_MS"], paper["MOOD_CHANGE_MS"])
    paper_shift = abs(a.mood[0] - a.default_mood[0])
    print("%-46s %s %s  P%+.2f A%+.2f D%+.2f"
          % ("paper constants, one Fear(1.0)", a.mood_words()[0],
             a.mood_words()[1], a.mood[0], a.mood[1], a.mood[2]))
    assert not a.active, "emotion should have fully decayed"
    assert a.mood[0] < a.default_mood[0], "fear should have lowered pleasure"

    cfg.set_param("MOOD_RETURN_MS", paper["MOOD_RETURN_MS"])
    for _ in range(1200):
        a.update(1000)                     # 20 min of return
    check("returned to baseline pleasure", a.mood[0], a.default_mood[0], 0.01)
    check("returned to baseline dominance", a.mood[2], a.default_mood[2], 0.01)

    b = fear_run(shipped[0], shipped[1])
    shipped_shift = abs(b.mood[0] - b.default_mood[0])
    print("%-46s %s %s  P%+.2f A%+.2f D%+.2f"
          % ("shipped constants, one Fear(1.0)", b.mood_words()[0],
             b.mood_words()[1], b.mood[0], b.mood[1], b.mood[2]))
    print("%-46s %.3f -> %.3f  (%.1fx)"
          % ("  pleasure moved", paper_shift, shipped_shift,
             shipped_shift / paper_shift))
    assert shipped_shift > paper_shift * 5, "the retune should be felt"

    for name, value in ((n, v) for n, v in zip(
            ("EMOTION_DECAY_MS", "MOOD_CHANGE_MS", "MOOD_RETURN_MS"), shipped)):
        cfg.set_param(name, value)         # leave the module as we found it

    # Push phase: with the mood parked past a strong center, it must keep
    # moving *outwards*, not stall on the center.
    cfg.set_param("EMOTION_DECAY_MS", 20000)
    a = Affect()
    a.mood = [0.8, 0.8, 0.8]
    a.elicit("Joy", 1.0)                   # center at (0.4, 0.2, 0.1)
    before = a.strength()
    for _ in range(50):
        a.update(100)
    print("%-46s %.3f -> %.3f  phase=%s"
          % ("push phase grows mood strength", before, a.strength(),
             PHASE_NAMES[a.phase]))
    assert a.phase == PUSH and a.strength() > before

    print("\n%s" % ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
