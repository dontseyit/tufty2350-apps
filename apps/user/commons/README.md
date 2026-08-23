# Commons

Three people share a room. Each of them runs the ALMA affect model — the one
`apps/user/alma` proved on a single character — wearing a body built out of the
same LimeZu pieces `apps/user/character_creator` dresses. One of them does
something; everybody has to live with it.

The point is not the room. The point is that **an event elicits the same
emotions in everyone who notices it, and they still end up in different moods**,
because ALMA pulls each mood away from a different personality baseline and then
lets it drift back there. Watching that happen to three people at once is
something a single-character simulation cannot show you.

## Buttons

**Setting up** — three residents are rolled at random, and you choose who they
are before the clock starts.

| | |
|---|---|
| `UP` / `DOWN` | move down the cast: archetype, then the five traits, then the next resident |
| `A` / `C` | previous / next value for the row you are on |
| `B` | roll a new body for this resident |
| hold `B` | begin. **Personalities are fixed from here on.** |

**Running**

| | |
|---|---|
| `UP` / `DOWN` | pick an event |
| `C` | make it happen — hold to repeat |
| `B` | pick who it happens to |
| hold `B` | time scale ×1 / ×10 / ×60 |
| `A` | next view: COMMONS → DETAIL → LOG → GUIDE |
| hold `A` | roll a new world |
| `C` on LOG | let the room run itself (scheduled events) |

Nothing is saved. Leaving the app ends the world, which is the point: every run
is a fresh experiment.

## Reading a resident

| what you see | what it means |
|---|---|
| the cone of light they stand in | which mood octant, and how far the mood is from PAD zero |
| the word over their head | the same octant, spelled out, with ALMA's strength wording |
| the bar under their name | the same distance, precisely |
| the pill on their chest | an emotion currently above ALMA's baseline threshold |
| how fast they breathe | arousal |
| a ripple on the floor | an event just reached them — accent if it happened *to* them |

The DETAIL view is one resident's instrument panel: pleasure across, arousal up,
dominance as the size of the mood dot. The hollow ring is where their
personality parks them, the cross is where the active emotions are pulling, and
the fading dots are the path they took to get where they are.

## The model

`occ.py` and `affect.py` are **byte-identical copies** of `apps/user/alma/`:

```sh
diff apps/user/alma/affect.py apps/user/commons/affect.py   # silent
diff apps/user/alma/occ.py    apps/user/commons/occ.py      # silent
```

That is deliberate. This app exists to run *that* engine on three people at
once, not a variant of it, and a diff is a stronger claim than a comment. The
four dynamics constants live in `config.py` under the same names and start at
the same values; tune them live on alma's DYNAMICS view first, then write the
numbers you liked in here. They are global — three residents on three different
clocks would make it impossible to read one mood against another, which is the
whole reason there are three of them.

`python3 affect.py` in this folder runs alma's own self-test against the paper's
worked examples, using this app's config.

## Events, and one honest compromise

An event carries **two already-appraised payloads**: what it elicits in the
person it happened to, and what it elicits in everyone else. That split is the
only structural difference from alma's `stimuli.py`.

OCC gives the shape. Its fortunes-of-others branch says the same good news
produces `HappyFor` in someone who likes you and `Resentment` in someone who
does not; its attribution branch pairs your `Pride` with their `Admiration`, and
your `Shame` with their `Reproach`. ALMA models mood from personality, not
relationships, so **there is no liking variable here to choose between those
branches with**.

Rather than invent one, the choice is written into the event: *shares good news*
is the version housemates are glad about, *brags about it* is the version that
grates, and both are on the list. Add a relationship model later and these
become the two outcomes of one event.

Between them the 18 events elicit all 24 emotions of the paper's Table 2:

```sh
python3 events.py    # 18 events firing 24/24 emotions of Table 2 ok
python3 config.py    # 9 archetypes, 8/8 octants covered
python3 world.py     # the same event, three personalities, three places
```

`world.py`'s self-test is the claim the app exists to check, in twenty lines:
three archetypes, one `BRAGS ABOUT IT` held for a simulated minute, and the two
residents who only *watched* — who received an identical payload — end up more
than a full PAD unit apart.

## Bodies

The character creator keeps one wardrobe family resident at a time and
composites live, because you are changing your mind sixty times a second. Nobody
here changes clothes: a resident is dressed **once** into a standing canvas and a
mid-breath canvas, and after that drawing them is a single blit. That is what
makes three of them cost the same as one, and it is why the whole wardrobe is
released the moment the world starts (`sprites.close_wardrobe`).

Rolls are weighted rather than uniform — uniform puts most of the room in a
chef's hat and safety goggles at once — and the three are forced to differ in
skin, hair and outfit, because you have to tell them apart at a glance to read
three moods at a glance.

## Assets

The art is derived from paid LimeZu packs and is **not** in the repo. Rebuild it:

```sh
python3 tools/gen_commons_assets.py     # ~46 KB into assets/, plus parts.py and icon.png
```

That script imports `tools/gen_character_creator_assets.py` as a library rather
than copying its PNG codec and sheet geometry, so the two apps can never
disagree about how a figure is cut. It needs `moderninteriors/` and
`Character Pieces/` in the repo root.

## What this deliberately does not do

- **No relationships.** Everyone in the room reacts to an event identically; the
  divergence is entirely ALMA's. Liking, Love and Hate are in the emotion table
  but not in a social graph.
- **No interaction.** Nobody walks, turns or looks at anybody. The pack has 534
  drawn animation cells and this app uses two of them.
- **No persistence.** Characters, moods and the log die with the app.

Each of those is a seam, not an oversight.
