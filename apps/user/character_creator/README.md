# Character Creator — a dressing room on a badge

Build a character out of LimeZu's character-generator art, in a room built out
of *Modern Interiors*, using the badge's five buttons. The character hangs on
the wall full length in one of the pack's picture frames, breathing; five more
of them stand on the floor below wearing the options either side of the one you
have, so you can see a choice before you make it.

Full length, not a portrait: half of what you can choose — the outfit, and two
of the hats — does not exist above the neck.

**Hold `B`** and the room gives way to a gallery: a wall of ten picture frames
hung with the characters you saved. `A`/`C` walks the wall, `B` wears the one
you are looking at (or hangs the one you are wearing, if the frame is empty),
holding `B` takes a picture down, and `▲`/`▼` goes back. The hint bar always
says which of those `B` means right now.

The gallery is the only thing the app remembers. What you are *building* is
not: leave mid-outfit and you come back to a fresh character, so the booth
still starts clean.

```
UP / DOWN   choose a part (and, under a part that is wearing something, its shade)
A / C       previous / next value — hold to run through a long list
B           shuffle the character — hold to open the gallery
```

## What you can change

| Part | Options | Shades |
|---|---|---|
| Skin | 9 | — (the option *is* the colour) |
| Eyes | 7 | — |
| Hair | 29 styles + none | 6–7 per style |
| Face | glasses, monocle, mask, moustache, beard + none | 3–6 each |
| Hat | 12 hats and headwear + none | 3–6 each |
| Outfit | 33 + none | 3–10 each |
| Room | 6 | — |

Two of the pack's accessories are deliberately left out: the backpack is behind
a front-facing character, and the gloves are two pixels of hand.

The room is not just wallpaper: the backdrop the character stands against is
that room's wall colour, taken halfway to black so a pale face still reads.
`B` deliberately leaves the room alone — the room is where you are, not who you
are, and re-rolling it makes the whole screen flinch.

## Two axes, one cursor

The art has two axes — *which* hairstyle, and *which colour* that style comes
in — so the app does too. The panel always shows the same six rows, and a row
whose part is wearing something has a second cursor stop on its colour chip.
The layout never jumps under you, and the cursor never lands on a control with
nothing to do (there is no shade to pick for a hat you are not wearing).

## Building the assets

**The LimeZu packs are not in this repo, and neither is the art baked out of
them** — they are paid assets and not ours to redistribute. Buy them from
[LimeZu](https://limezu.itch.io/) and unzip them at the repo root as
`Character Pieces/` (the character), `modernuserinterface/` (the frame, panel
and button glyphs) and `moderninteriors/` (the rooms), then:

```bash
python3 tools/gen_character_creator_assets.py
```

That writes `assets/`, `icon.png` and `parts.py` — all generated, all ignored
by git. Without them the app has no icon and so does not appear in the menu.

`HERO_SCALE` at the top of the generator is the one knob worth turning: it sets
how big the framed character is (4 = 64x128), and the frame is baked and the
layout re-centred to match. It is a magnification, not a resolution: a
character is natively 16x32 real pixels, and **the pack's `32x32/` and `48x48/`
folders are nearest-neighbour upscales of those same pixels**, not
higher-detail redraws — so there is nothing to gain by reading them instead.

The generator does the work that would otherwise cost the badge memory or
milliseconds:

- **crops** every layer to one 16x32 window, so a character is six blits at a
  single position with no per-layer offsets;
- **takes two poses** out of the 56x20 grid of walking, sitting, reading and
  phone animation: the front-facing stand, and the frame a third of the way
  into the walk — seen head-on that one lifts the body a pixel and leaves the
  legs alone, so alternating them reads as breathing rather than marching;
- **reads only the top two rows** of each 896x640 sheet. Unfiltering is the
  expensive part of decoding a PNG, and the other 18 rows are animation nobody
  looks at; skipping them turns a two-minute bake into a fifteen-second one;
- **nine-slices** the picture frame, the panel and the row highlight to their
  exact on-screen sizes, so the badge never stretches anything at runtime;
- **flattens the wallpaper** to a tile that repeats seamlessly (a pack wall is
  a whole 32px wall, shaded top to bottom, and does not tile), which also lets
  the renderer paint a wall column in one stretched blit instead of ten;
- **reads the palette out of the art** — every colour on screen is a pixel
  LimeZu drew.

## Where the gallery lives

A character is fourteen small integers — an option and a shade per part — so
ten of them is about a kilobyte of JSON. That goes to the badge's **internal
flash** through `badgeware.State`, because the app's own folder is the USB
drive and is read-only while the app runs. It survives a reboot, and it is
**not** a file you can copy off over USB.

Everything that comes back out of flash is checked before it is trusted: an
entry must be a list of the right length, its values must be integers, and each
is clamped into range. A half-written file, or a gallery saved before the
outfits existed, must not stop the app from starting.

Each hung character is composed once into its own 16x32 canvas via
`image(w, h)` and `img.blit(...)`, then blitted from there. Drawing ten of them
live would mean loading ten characters' worth of hair, hat and outfit sheets
every frame, and only one family of each is ever resident. The gallery paints
at most one picture per frame, so walking in fills the wall rather than
stalling on it.

## Memory

What stays loaded does not grow with how much of the pack is on offer: the skin
and eye sheets, the four catalogue sheets (one thumbnail per option, which is
what the line-up draws) and the chrome are always in. The hair, face, hat and
outfit *families* arrive one at a time as they are selected, and the one before
is dropped and collected before the next lands. Choosing an outfit costs its
own handful of shades, not all 33.

## Running it

On the badge, copy the app to `/system/apps/user/character_creator` and pick it
from the menu. On the desktop:

```bash
python tools/sim/run.py --app apps/user/character_creator --scale 3
```
