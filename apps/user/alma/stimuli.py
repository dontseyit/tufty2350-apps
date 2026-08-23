# The external stimuli the player scrolls with UP/DOWN and fires with C.
#
# In ALMA these would be the output of a character's subjective appraisal rules
# (AffectML): an event, act or object is appraised, and the appraisal yields
# emotion eliciting conditions which the EmotionEngine turns into OCC emotions
# at some intensity.  We skip the rule engine and ship the appraisal *results*
# directly - each entry is one already-appraised happening.
#
# Between them the 21 stimuli elicit all 24 emotions of Table 2 at least once,
# so every row of the paper's mapping is reachable from the badge.

STIMULI = (
    ("GOOD NEWS ARRIVES",      (("Joy", 0.70), ("Hope", 0.40))),
    ("BAD NEWS ARRIVES",       (("Distress", 0.70),)),
    ("PRAISED IN PUBLIC",      (("Pride", 0.75), ("Joy", 0.45))),
    ("INSULTED TO MY FACE",    (("Anger", 0.80), ("Reproach", 0.50))),
    ("A GIFT, UNASKED FOR",    (("Gratitude", 0.70), ("Joy", 0.40))),
    ("A THREAT LOOMS CLOSER",  (("Fear", 0.85),)),
    ("THE THREAT PASSES",      (("Relief", 0.80),)),
    ("IT WENT WRONG, AS FEARED", (("FearsConfirmed", 0.80), ("Distress", 0.40))),
    ("A FRIEND WINS BIG",      (("HappyFor", 0.70),)),
    ("A FRIEND IS SUFFERING",  (("Pity", 0.65),)),
    ("MY RIVAL TRIPS UP",      (("Gloating", 0.60),)),
    ("A PROMISE IS BROKEN",    (("Disappointment", 0.75),)),
    ("I BROKE THE PROMISE",    (("Shame", 0.65), ("Remorse", 0.60))),
    ("THE WORK IS FINISHED",   (("Satisfaction", 0.70), ("Pride", 0.40))),
    ("I PULLED IT OFF MYSELF", (("Gratification", 0.75),)),
    ("SOMEONE ACTS NOBLY",     (("Admiration", 0.70),)),
    ("A LOVED ONE APPEARS",    (("Love", 0.75), ("Liking", 0.50))),
    ("STUCK WITH A CREEP",     (("Disliking", 0.60),)),
    ("BETRAYED BY A FRIEND",   (("Hate", 0.70), ("Anger", 0.60))),
    ("PASSED OVER AGAIN",      (("Resentment", 0.65), ("Reproach", 0.40))),
    ("WAITING ON A VERDICT",   (("Hope", 0.60), ("Fear", 0.45))),
)


if __name__ == "__main__":
    import occ
    fired = set()
    for label, pairs in STIMULI:
        for name, intensity in pairs:
            assert name in occ.EMOTIONS, "unknown emotion: " + name
            assert 0.0 < intensity <= 1.0, label
            fired.add(name)
    missing = sorted(set(occ.EMOTIONS) - fired)
    print("%d stimuli firing %d/%d emotions of Table 2 %s"
          % (len(STIMULI), len(fired), len(occ.EMOTIONS),
             "ok" if not missing else "MISSING " + str(missing)))
    assert not missing
