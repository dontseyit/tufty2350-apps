# Tufty badgeware desktop simulator

Run real, **unmodified** badgeware apps (e.g. `snarky_sciuridae`) on your
desktop in a live pygame window — so you can iterate without flashing the badge
and rebooting.

## How it works

On the device, badgeware *injects* its API as builtins (`screen`, `badge`,
`image`, `SpriteSheet`, `color`, `shape`, `vec2`, `rect`, `clamp`, `run`, …) and
exposes `State` via `from badgeware import State`. The app's `__init__.py` is the
only file that touches these; `ui.py` / `vpet.py` just use them.

- [`badgeware_sim.py`](badgeware_sim.py) reimplements that API on pygame + PIL-free
  pure Python, and rewrites on-device `/system/...` paths onto this repo.
- [`run.py`](run.py) injects the shim, `exec`s the app's real source, and drives a
  per-frame loop in a window. `run(update)` becomes register-and-return so the
  launcher owns the loop (which is what makes hot-reload possible).

Only the slice of the API the apps use is implemented. Text uses a substitute
font — the device `.ppf` pixel fonts aren't parsed (snarky draws no visible
text anyway).

## Usage

```bash
source .venv/bin/activate
pip install pygame                       # one-time
python tools/sim/run.py                  # runs snarky_sciuridae
python tools/sim/run.py --app apps/user/clock --scale 5 --speed 4
```

Flags: `--app <dir>` (default `apps/factory/snarky_sciuridae`),
`--scale <n>` render/window scale (default 4 — try 6–8 for a bigger, sharper
window), `--speed <x>` initial time scale, `--fps <n>`, plus the networked-app
flags below.

`--scale` is a **supersampling** factor: the scene is rendered at N× the device
resolution (fonts at large point size, shapes with smooth curves) and shown 1:1,
so text/UI are crisp rather than magnified low-res pixels. Pixel-art
sprites/backgrounds stay nearest-neighbour crisp.

### Networked apps (tdf)

Apps that import `wifi` / `requests` / `secrets` (e.g. `tdf`) run too — the
simulator provides fakes:

- a fake `wifi` that associates instantly (or never, with `--wifi off`),
- a fake `secrets` so the app sees a configured network,
- a fake `requests` whose `get()` serves a **local JSON fixture** instead of
  hitting the LAN proxy — so no proxy/Wi-Fi is needed.

```bash
python tools/sim/run.py --app apps/user/tdf --scale 3
# uses tdf_cache.json as the live feed; --data <file> to use another snapshot,
# --wifi off to exercise the offline path.
```

`badge.mode(HIRES)` is honoured (the window resizes to the app's 320×240). Apps
that write to device internal flash (`/tdf.json`, `/cards.json`) are redirected
to `tools/sim/.sim_flash/` so persistence works.

## Controls

| Key | Action |
|-----|--------|
| `A` `S` `D` (or `1` `2` `3`) | badge buttons A / B / C (play / feed / clean) |
| `+` / `-` | speed time up / down — fast-forward stat decay & death |
| `T` | cycle time-of-day (day → dusk → night background) |
| `L` | hot-reload the app source — edit `vpet.py`/`ui.py` and see it instantly |
| `P` | save a screenshot next to the sim |
| `Esc` / close | quit (fires the app's `on_exit`) |

## Iterating on snarky_sciuridae

Edit [`../../apps/factory/snarky_sciuridae/vpet.py`](../../apps/factory/snarky_sciuridae/vpet.py)
or `ui.py`, then press `L` in the window (or just restart). Bump `--speed` (or `+`)
to watch the ~20–40 min stat decay and death in seconds. Persistent stats are
written to `tools/sim/.sim_state.json` (delete it to start fresh).

## Caveats

- Rendering is *functional*, not pixel-exact: real sprites/backgrounds/layout,
  but text uses a **substitute** pygame font sized per `.ppf` (the device pixel
  fonts aren't parsed), so glyph shapes differ from the hardware.
- `wifi`/`requests`/`secrets` are faked (see above). The fake `requests` serves
  one local fixture for every URL — enough for a single-endpoint app like `tdf`,
  but an app hitting several endpoints would need per-URL fixtures added to
  [`stubs/requests.py`](stubs/requests.py). `clock`/`taboo` also import extra
  firmware modules (`ntptime`, `machine`, a real agent endpoint) not stubbed yet.
