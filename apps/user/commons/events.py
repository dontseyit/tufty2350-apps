# The social events one resident can set off in the others.
#
# An event carries TWO already-appraised payloads: what it elicits in the person
# it happened to, and what it elicits in everyone else in the room.  That split
# is the whole difference between this app and alma, where a stimulus had only
# one person to land on.
#
# OCC gives the shape.  Its fortunes-of-others branch says the same good news
# produces HappyFor in someone who likes you and Resentment in someone who does
# not; its attribution branch pairs your Pride with their Admiration, and your
# Shame with their Reproach.  ALMA models mood from personality, not
# relationships, so there is no liking variable here to choose between those
# branches with.  Instead the CHOICE IS WRITTEN INTO THE EVENT: "shares good
# news" is the version housemates are glad about, "brags about it" is the
# version that grates, and both are on the list.  Add a relationship model later
# and these become the two outcomes of one event.
#
# Between them the 18 events elicit all 24 emotions of the paper's Table 2, so
# every row of the mapping is reachable from the badge - the self-test at the
# bottom asserts it.
#
# Pure data: no badgeware globals, so it imports on the desktop.

# (label, what it does to them, what it does to the room)
EVENTS = (
    ("SHARES GOOD NEWS",
     (("Joy", 0.70), ("Pride", 0.35)),
     (("HappyFor", 0.60), ("Joy", 0.30))),

    ("BRAGS ABOUT IT",
     (("Pride", 0.80), ("Gratification", 0.50)),
     (("Resentment", 0.60), ("Reproach", 0.45))),

    ("COOKS FOR EVERYONE",
     (("Pride", 0.55), ("Satisfaction", 0.50)),
     (("Gratitude", 0.65), ("Joy", 0.40))),

    ("DOES A KINDNESS UNASKED",
     (("Pride", 0.45),),
     (("Gratitude", 0.70), ("Admiration", 0.55), ("Liking", 0.40))),

    ("SAYS SOMETHING TRUE AND KIND",
     (("Liking", 0.55), ("Joy", 0.35)),
     (("Love", 0.55), ("Liking", 0.60))),

    ("BREAKS SOMETHING SHARED",
     (("Shame", 0.65), ("Remorse", 0.55)),
     (("Anger", 0.55), ("Reproach", 0.60))),

    ("APOLOGISES, AND MEANS IT",
     (("Remorse", 0.50), ("Relief", 0.40)),
     (("Gratitude", 0.50), ("Liking", 0.45))),

    ("EATS SOMEONE ELSE'S DINNER",
     (("Gratification", 0.45), ("Shame", 0.30)),
     (("Anger", 0.60), ("Disliking", 0.45))),

    ("PROMISES, THEN FORGETS",
     (("Shame", 0.50),),
     (("Disappointment", 0.70), ("Reproach", 0.40))),

    ("SULKS IN THE CORNER",
     (("Distress", 0.60),),
     (("Pity", 0.50),)),

    ("GETS BAD NEWS",
     (("Distress", 0.75),),
     (("Pity", 0.60),)),

    ("PICKS A FIGHT",
     (("Anger", 0.75), ("Reproach", 0.55)),
     (("Anger", 0.60), ("Fear", 0.35))),

    ("STORMS OUT",
     (("Anger", 0.65), ("Distress", 0.40)),
     (("Fear", 0.40), ("Distress", 0.35))),

    ("MOCKS SOMEONE'S BAD LUCK",
     (("Gloating", 0.65),),
     (("Reproach", 0.65), ("Disliking", 0.50))),

    ("WILL NOT LET IT GO",
     (("Hate", 0.60), ("Resentment", 0.55)),
     (("Fear", 0.35), ("Disliking", 0.40))),

    ("IS WAITING ON A VERDICT",
     (("Hope", 0.60), ("Fear", 0.50)),
     (("Hope", 0.35),)),

    ("THE VERDICT IS GOOD",
     (("Satisfaction", 0.75), ("Relief", 0.55)),
     (("HappyFor", 0.55), ("Relief", 0.40))),

    ("THE VERDICT IS BAD",
     (("FearsConfirmed", 0.75), ("Distress", 0.50)),
     (("Pity", 0.55), ("Disappointment", 0.35))),
)


def label(i):
    return EVENTS[i][0]


def payloads(i):
    """(what it does to the actor, what it does to everyone else)."""
    return EVENTS[i][1], EVENTS[i][2]


if __name__ == "__main__":
    import occ

    fired = set()
    for lab, mine, theirs in EVENTS:
        assert mine, lab + " does nothing to the person it happened to"
        assert theirs, lab + " does nothing to the room - use alma for those"
        for name, intensity in mine + theirs:
            assert name in occ.EMOTIONS, "unknown emotion: " + name
            assert 0.0 < intensity <= 1.0, lab
            fired.add(name)
    missing = sorted(set(occ.EMOTIONS) - fired)
    print("%d events firing %d/%d emotions of Table 2 %s"
          % (len(EVENTS), len(fired), len(occ.EMOTIONS),
             "ok" if not missing else "MISSING " + str(missing)))
    assert not missing

    # Every event should read as one social act: the two payloads must not be
    # the same list, or there was no reason to write it here rather than in alma.
    for lab, mine, theirs in EVENTS:
        assert set(mine) != set(theirs), lab

    # How far apart the two sides are, as a sanity check on the writing: the
    # actor's centre and the room's centre in PAD space.
    print()
    def centre(pairs):
        w = sum(i for _, i in pairs)
        return tuple(sum(occ.EMOTIONS[n][k] * i for n, i in pairs) / w
                     for k in range(3))
    for lab, mine, theirs in EVENTS:
        a, b = centre(mine), centre(theirs)
        gap = sum((a[k] - b[k]) ** 2 for k in range(3)) ** 0.5
        print("%-30s self %-11s room %-11s  gap %.2f"
              % (lab, occ.octant_of(*a), occ.octant_of(*b), gap))
