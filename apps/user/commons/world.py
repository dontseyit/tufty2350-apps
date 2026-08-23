# Three residents, one clock, one shared room.
#
# Each resident owns a private affect.Affect - the same engine the alma app
# runs on one character - so the interesting behaviour is emergent rather than
# scripted: an event elicits the SAME emotions in everyone who notices it, and
# they still end up in different moods, because ALMA pulls each mood away from
# a different personality baseline and then lets it drift back there.
#
# Nothing is written to flash. Leaving the app ends the world, which is the
# point: every run is a fresh experiment.
#
# No badgeware globals here - only the bodies need those - so `python3 world.py`
# runs the self-test at the bottom on the desktop.

import random

import affect
import config as cfg
import events
import parts

# The six layers a resident is made of, bottom up.  The outfit goes on early so
# hair falls over its collar; a hat goes on last so it sits over the hair.
SKIN, EYES, HAIR, FACE, HEAD, OUTFIT = range(6)
LAYER_ORDER = (SKIN, OUTFIT, EYES, HAIR, FACE, HEAD)
# The four slots that come as a named piece in several shades.  Skin and eyes
# have one axis only - for them the option IS the colour.
PIECES = {HAIR: parts.HAIR, FACE: parts.FACE, HEAD: parts.HEAD,
          OUTFIT: parts.OUTFIT}
FOLDER = {HAIR: "hair", FACE: "face", HEAD: "head", OUTFIT: "outfit"}


def _maybe(one_in):
    """True one time in `one_in` - how often an accessory slot gets used."""
    return one_in > 0 and random.randrange(one_in) == 0


class Resident:
    """One person: a body, a personality, and the mood that follows from it."""

    def __init__(self, name, look, archetype):
        self.name = name
        self.look = look                  # [[option, shade], ...] per layer
        self.archetype = archetype
        self.model = affect.Affect(cfg.personality(archetype))
        self.trail = []                   # recent (p, a) for the detail view
        self.pose = None                  # two canvases, filled in by sprites
        self.hit_at = -cfg.HIT_MS         # real ms of the last event to reach them
        self.hit_actor = False            # ...and whether it happened TO them

    # ---- personality ------------------------------------------------------
    def set_archetype(self, index):
        self.archetype = index % len(cfg.ARCHETYPES)
        self.model = affect.Affect(cfg.personality(self.archetype))
        self.trail = []

    def cycle_archetype(self, step):
        """Step to the next preset. From a nudged personality there is no
        current preset to step from, so forwards lands on the first."""
        if self.archetype is None:
            i = 0 if step > 0 else len(cfg.ARCHETYPES) - 1
        else:
            i = (self.archetype + step) % len(cfg.ARCHETYPES)
        self.set_archetype(i)

    def nudge(self, trait, direction):
        """Adjust one trait. The baseline moves; the mood is re-seeded onto it,
        because a half-built personality with an old mood on it means nothing."""
        self.model.set_trait(trait, self.model.personality[trait]
                             + direction * cfg.TRAIT_STEP)
        self.model.reseed()
        self.trail = []
        self.archetype = None             # no longer any single preset

    def archetype_name(self):
        return "CUSTOM" if self.archetype is None \
            else cfg.ARCHETYPES[self.archetype][0]

    # ---- what to say about them -------------------------------------------
    def dominant(self):
        return self.model.dominant()

    def state(self):
        """The two words over their head: how strong the mood is, and which
        octant it is in."""
        return self.model.mood_words()


class World:
    def __init__(self):
        self.people = []
        self.sim_ms = 0.0
        self.scale = cfg.DEFAULT_SCALE_INDEX
        self.auto = False
        self.log = []                     # newest first
        self._next_event_at = 0.0
        self.roll()

    # ---- casting ----------------------------------------------------------
    def roll(self):
        """Three residents, rolled from scratch."""
        self.people = []
        for _ in range(cfg.SLOTS):
            self.people.append(Resident(self._name(), self._look(),
                                        self._archetype()))
        self.reset_clock()

    def reroll(self, i):
        """A new body for one of them, keeping their name and personality."""
        self.people[i].look = self._look(exclude=i)

    def reset_clock(self):
        self.sim_ms = 0.0
        self.log = []
        self._arm()
        for who in self.people:
            who.model.reseed()
            who.trail = []

    def _taken(self, get, exclude=None):
        return [get(p) for i, p in enumerate(self.people) if i != exclude]

    def _name(self):
        taken = self._taken(lambda p: p.name)
        while True:
            name = parts.NAMES[random.randrange(len(parts.NAMES))]
            if name not in taken:
                return name

    def _archetype(self):
        taken = self._taken(lambda p: p.archetype)
        while True:
            i = random.randrange(len(cfg.ARCHETYPES))
            if i not in taken:
                return i

    def _look(self, exclude=None):
        """A random body, kept legible and kept distinct.

        Legible: every slot uniform would put most of the room in a chef's hat
        and safety goggles at once. Distinct: three strangers who share a skin
        tone, a haircut and an outfit are three copies of one person, and you
        need to tell them apart at a glance to read three moods at a glance.
        """
        others = self._taken(lambda p: p.look, exclude)
        for _attempt in range(24):
            look = [[0, 0] for _ in range(6)]
            look[SKIN][0] = random.randrange(parts.SKIN)
            look[EYES][0] = random.randrange(parts.EYES)
            look[HAIR][0] = 0 if _maybe(cfg.BALD_IN) else \
                1 + random.randrange(len(parts.HAIR) - 1)
            look[OUTFIT][0] = 1 + random.randrange(len(parts.OUTFIT) - 1)
            look[FACE][0] = 1 + random.randrange(len(parts.FACE) - 1) \
                if _maybe(cfg.FACE_IN) else 0
            look[HEAD][0] = 1 + random.randrange(len(parts.HEAD) - 1) \
                if _maybe(cfg.HEAD_IN) else 0
            for layer, table in PIECES.items():
                shades = table[look[layer][0]][1]
                look[layer][1] = random.randrange(shades) if shades else 0
            if all(any(look[k][0] != other[k][0]
                       for k in (SKIN, HAIR, OUTFIT)) for other in others):
                return look
        return look                        # 24 misses: take it, it is random

    # ---- time -------------------------------------------------------------
    def speed(self):
        return cfg.TIME_SCALES[self.scale]

    def cycle_speed(self):
        self.scale = (self.scale + 1) % len(cfg.TIME_SCALES)

    def clock(self):
        """The world's own elapsed time, as H:MM:SS."""
        s = int(self.sim_ms // 1000)
        return "%d:%02d:%02d" % (s // 3600, (s // 60) % 60, s % 60)

    def _arm(self):
        self._next_event_at = self.sim_ms + cfg.SCHEDULE_MS \
            + random.randrange(cfg.SCHEDULE_JITTER_MS)

    def toggle_auto(self):
        self.auto = not self.auto
        if self.auto:
            self._arm()
        return self.auto

    # ---- what happens -----------------------------------------------------
    def fire(self, actor, event, now, scheduled=False):
        """One event: its first payload lands on the actor, its second on
        everyone else in the room.  Nobody is a special case - three residents
        each run the same elicit() the alma app calls."""
        mine, theirs = events.payloads(event)
        for i, who in enumerate(self.people):
            for name, intensity in (mine if i == actor else theirs):
                who.model.elicit(name, intensity)
            who.hit_at = now
            who.hit_actor = i == actor
        self.log.insert(0, (self.sim_ms, actor, event, scheduled))
        del self.log[cfg.LOG_LEN:]
        cfg.log("fire", self.people[actor].name, events.label(event))

    def update(self, dt, now):
        """Advance every resident by dt simulated ms, and let the room act."""
        self.sim_ms += dt
        for who in self.people:
            who.model.update(dt)
            trail = who.trail
            if not trail or self.sim_ms - trail[-1][2] >= cfg.TRAIL_PERIOD_MS:
                trail.append((who.model.mood[0], who.model.mood[1],
                              self.sim_ms))
                if len(trail) > cfg.TRAIL_LEN:
                    del trail[0]
        if self.auto and self.sim_ms >= self._next_event_at:
            self.fire(random.randrange(len(self.people)),
                      random.randrange(len(events.EVENTS)), now, True)
            self._arm()


# ---------------------------------------------------------------------------
# Self-test: the claim this whole app exists to check is that one shared event
# moves three different personalities to three different places.  Never runs on
# the badge.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import occ

    w = World()
    # Pin the cast so the run is reproducible: the three widest-apart baselines.
    for i, arch in enumerate(("SUNNY", "FLAT", "PRICKLY")):
        w.people[i].set_archetype(
            [n for n, *_ in cfg.ARCHETYPES].index(arch))

    print("%-9s %-8s %-11s %s" % ("", "ARCH", "BASELINE", "P/A/D"))
    for who in w.people:
        p, a, d = who.model.default_mood
        print("%-9s %-8s %-11s %+.2f %+.2f %+.2f"
              % (who.name, who.archetype_name(), who.model.octant(), p, a, d))

    # BRAGS ABOUT IT: Pride+Gratification on the actor, Resentment+Reproach on
    # the other two.  Held down for a simulated minute, as you would on the badge.
    brag = [i for i, e in enumerate(events.EVENTS)
            if e[0] == "BRAGS ABOUT IT"][0]
    print("\n%s brags for one simulated minute:" % w.people[0].name)
    for step in range(600):
        if step % 100 == 0:
            w.fire(0, brag, step * 100)
        w.update(100, step * 100)

    moved = []
    for who in w.people:
        p, a, d = who.model.mood
        dp, da, dd = who.model.default_mood
        dist = occ.norm(p - dp, a - da, d - dd)
        moved.append(dist)
        print("%-9s %-11s -> %-11s  P%+.2f A%+.2f D%+.2f   moved %.2f"
              % (who.name, occ.octant_of(dp, da, dd), who.model.octant(),
                 p, a, d, dist))

    assert all(m > 0.05 for m in moved), "everyone should have been moved"
    ends = {who.model.octant() for who in w.people}
    print("\nthree personalities, %d distinct octants after the same event"
          % len(ends))

    # The observers got an identical payload, so any difference between them is
    # ALMA's doing and not the event's.
    a, b = w.people[1], w.people[2]
    gap = occ.norm(*[a.model.mood[k] - b.model.mood[k] for k in range(3)])
    print("the two who only WATCHED are %.2f apart in PAD space" % gap)
    assert gap > 0.1, "identical input should still land differently"
    print("\nALL CHECKS PASSED")
