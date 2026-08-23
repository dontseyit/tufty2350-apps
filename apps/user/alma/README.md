# ALMA — a layered model of affect, running on a badge

A real-time re-implementation of **ALMA** (Patrick Gebhard, DFKI — *ALMA: A
Layered Model of Affect*, AAMAS'05) driving an idle game character. The
character has a Big Five personality, appraises external stimuli into OCC
emotions, and its mood wanders through PAD space and drifts home again.

Paper: <https://alma.dfki.de/papers/aamas05.pdf>

## What is taken from the paper

| Paper | Here |
|---|---|
| **Table 1** — the eight mood octants of PAD space | `occ.OCTANTS` |
| **Table 2** — 24 OCC emotion types mapped to PAD | `occ.EMOTIONS`, verbatim |
| Mehrabian's Big Five → PAD default mood regression | `affect.default_mood` |
| Pull and push mood change function | `Affect._pull_push` |
| Mood return to the default mood | `Affect._return_to_default` |
| `<EmotionDecay time="20000" function="linear"/>` | `cfg.EMOTION_DECAY_MS` * |
| `<EmotionBaseline threshold="0.4"/>` | `cfg.EMOTION_BASELINE` |
| "usual mood change time is 10 minutes" | `cfg.MOOD_CHANGE_MS` * |
| "mood return time … currently 20 minutes" | `cfg.MOOD_RETURN_MS` * |
| slightly / moderate / fully, thirds of √3 | `affect.intensity_word` |

\* retuned for playability — see **Deliberate departures** below. The paper's
values are one button press away on the DYNAMICS view, and the self-test
checks the model against *those*, not against the shipped ones.

`python3 affect.py` checks the implementation against the paper's own worked
examples (personality `O.4 C.8 E.6 A.3 N.4` → `P 0.38 A −0.08 D 0.50`, and
every row of Table 2 landing in the octant the table's last column claims).
`python3 stimuli.py` checks that the stimulus set can elicit all 24 emotions.

## How the loop works

```
stimulus ──appraisal──▶ OCC emotions ──▶ virtual emotion center ──▶ mood
             (stimuli.py)   (decay 20s)     (weighted centre of        (PAD)
                                             the active emotions)        │
personality ──Mehrabian──▶ default mood ◀────── return (20 min) ─────────┘
```

Each frame the model is advanced by `real_ms × time_scale`:

1. every active emotion decays linearly towards zero and is dropped at 0;
2. the **virtual emotion center** is recomputed — a point in PAD space, with an
   intensity equal to the average of the active intensities;
3. the mood is **pulled** towards that center while it is still between the
   center and the PAD origin, and **pushed** outwards, deeper into its own
   octant, once it is at or past the center. The center's intensity sets the
   speed: at full intensity the mood covers √3 in one `MOOD_CHANGE_MS`;
4. with no emotions active at all, the mood walks back to the personality
   baseline at √3 per `MOOD_RETURN_MS`.

A single emotion barely dents the mood — that is the model, not a bug. Twenty
seconds of one emotion against a ten-minute mood change time is a nudge. **Hold
C** to keep re-appraising the same stimulus and you will watch the pull phase
carry the mood across an octant boundary and the push phase drive it outwards.

## Controls

| Button | Everywhere | On an editor view |
|---|---|---|
| `UP` / `DOWN` | choose an external stimulus | adjust the selected value |
| `C` | apply it (**hold to repeat**) | re-seed the mood / restore the paper's values |
| `A` | next view | next view |
| `B` | time scale ×1 / ×10 / ×60 / ×300 | select the next trait / parameter |

The right-hand column covers both editor views, PERSONALITY and DYNAMICS.

## Views

- **CHARACTER** — the idling orb. Colour is the mood octant, size is dominance,
  stretch-and-droop is pleasure, breathing rate and sway are arousal. Beside it,
  the live PAD numbers, the dominant emotion, and the mood's strength against
  the *slightly / moderate / fully* boundaries.
- **PAD MAP** — the paper's own AffectMonitor: the pleasure×arousal plane with a
  fading mood trail, a ring at the personality baseline, the active emotions as
  dots at their Table 2 positions, and the virtual emotion center as a pale ball
  with the pull/push line drawn to the mood.
- **EMOTIONS** — every active emotion decaying, with ALMA's 0.4 baseline marked
  on each bar, plus the virtual emotion center it all adds up to.
- **PERSONALITY** — the five traits, and the PAD baseline the Mehrabian
  regression derives from them, recomputed as you turn the dials.
- **DYNAMICS** — the four constants that govern how hard a stimulus lands and
  how long it lasts, each on a ladder of sane values with a tick marking the
  paper's. Two derived readouts say what the current settings actually buy:
  how far one 0.80 stimulus moves the mood, and how long that takes to undo.
  `C` restores the whole paper column, so you can A/B the two in one press.

## Deliberate departures

The paper's constants are honest and make a nearly inert character: one 0.80
emotion, against a 20-second decay and a ten-minute mood change time, moves the
mood **0.02** of PAD — under two pixels on the map. The shipped defaults trade
some fidelity for a character you can feel:

| | Paper | Shipped | |
|---|---|---|---|
| `EMOTION_DECAY_MS` | 20 s | **60 s** | the paper's own prose alternative ("for example, 1 minute") |
| `MOOD_CHANGE_MS` | 10 min | **2 min** | a real departure |
| `MOOD_RETURN_MS` | 20 min | **40 min** | a real departure — displacement lasts |

Together: **0.35** of PAD per stimulus, ~15× the paper's. One tap of `C` now
visibly shifts the orb; the paper's numbers need a sustained hold.

All four are live on the DYNAMICS view, and `C` there puts the paper's column
back, so nothing is lost — the fidelity is a button press away, and the
self-test always measures the model against the paper's values.

## Two places the paper is ambiguous or inconsistent

Both are called out in the code and left as parameters in `config.py`:

- **Mood strength wording.** The prose divides √3 into thirds, which puts
  "slightly" below 0.577 — but both worked examples in the paper are labelled
  *slightly* at a strength of about 0.63. The stated rule is implemented;
  `MOOD_SLIGHT_MAX` is where to disagree with it.
- **Mood return time.** The prose says 20 minutes, Figure 3's XML says
  `<MoodReturn time="600000"/>` = 10. The prose wins; `MOOD_RETURN_MS`.

Two modelling choices the paper leaves open are flagged the same way:
`WEIGHTED_CENTER` (the center is the intensity-weighted centroid) and
`RETURN_WHILE_ACTIVE` (the drift home is suspended while emotions are active,
so a weak center cannot be out-run by the return).

## Files

| File | |
|---|---|
| `occ.py` | Tables 1 and 2, verbatim. No device dependencies. |
| `affect.py` | The model, plus a self-test against the paper. No device dependencies. |
| `config.py` | Every constant the behaviour depends on, the palette, the layout. |
| `stimuli.py` | 21 appraised happenings covering all 24 emotions. |
| `render.py` | All drawing, from rectangles, rounded rectangles and lines only. |
| `__init__.py` | Bootstrap, button routing, the frame loop. |

## Developing

Runs unmodified in the desktop simulator:

```bash
source .venv/bin/activate
python tools/sim/run.py --app apps/user/alma --scale 3
```

`L` hot-reloads the source, `+`/`-` change the sim's own frame pacing, `A`/`S`/`D`
and the arrow keys are the badge buttons.
