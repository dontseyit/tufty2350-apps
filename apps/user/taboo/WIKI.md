# Taboo — Technical Wiki

The engineering companion to [`README.md`](README.md) (which covers controls, rules,
and setup). This document explains *how the app works*: the execution model, the
state machine, and the card-supply logic that is the real heart of the program.

Everything here is plain MicroPython for the Pimoroni Tufty 2350 running the
**badgeware** firmware. The design goal is a pass-and-play party game with an
**English UI**, **Turkish card content** generated on demand by a Mistral Agent,
and graceful degradation to an offline cache when there is no network.

---

## 1. Execution model

badgeware discovers an app from `/system/apps/<dir>` (needs `icon.png` +
`__init__.py`) and injects a set of globals — `screen`, `badge`, `color`, `image`,
`vec2`, `run`, `BUTTON_A/B/C/UP/DOWN`, `HIRES`, `State` — so the app never imports
them. `__init__.py` is the only file that touches these globals; every other module
is plain, importable Python (which is what makes them testable off-device).

The app is a single per-frame callback handed to `run()`:

```
update(now)            # now = badge.ticks, a millisecond clock
  ├─ _handle_input()   # at most one button press -> a state transition
  ├─ _tick()           # time-driven transitions (countdown, timeout, fetch)
  └─ render.draw()     # paint the screen for the current state
```

There is **no threading**. The one genuinely blocking operation — the HTTPS call to
the agent — is deliberately run inside `_tick` during a dedicated loading state, never
mid-turn, so the turn clock is never stalled by the network (see §4, §5).

`badge.mode(HIRES)` locks the canvas to the native 320×240 so the pixel-grid layout
in `render.py` maps 1:1 to the original design.

---

## 2. Module map

Each file has one responsibility; the dependency arrows only ever point "down".

| File | Responsibility | Imports |
|------|----------------|---------|
| `__init__.py` | Harness glue: bootstrap, wi-fi lifecycle, the blocking fetch, input→state→render loop, persistence | everything |
| `game.py` | **Pure** state machine: scoring, timer, transitions. No drawing, no network. | `config`, `cards` |
| `cards.py` | Card pool: fetch + dedup + cache + used-state + recycle | `config`, `textutil`, `agent` |
| `agent.py` | Wi-fi + the raw HTTP call + response parsing. Network imports are lazy. | `config`, `textutil` |
| `render.py` | The 10 screen renderers + 5×7 text primitives | `config`, `textutil`, `font` |
| `textutil.py` | Turkish uppercasing + font-charset sanitising | `font` |
| `font.py` | The 5×7 glyph table (Latin, digits, Turkish, `: ' - + . /`) | — |
| `config.py` | Constants, the 10 categories, agent/cache config, `log()` | — |

`game.py` and `cards.py` are pure logic and run under CPython, so the whole core is
covered by headless tests and an offline render simulator (§12).

---

## 3. State machine

Ten states (`config.py`), each with exactly one renderer in `render.py`'s `_DRAWERS`
dispatch. `game.py` owns the transitions; `__init__.py` supplies the inputs (buttons,
clock) and performs the side effects (network, persistence) the pure machine asks for.

| State | Meaning | Leaves when |
|-------|---------|-------------|
| `CONNECTING` | Startup wi-fi attempt | associated, timeout (`WIFI_TIMEOUT_MS`), or any button → offline |
| `SETUP` | Pick a category | **B** start, ▲▼ cycle category |
| `HANDOFF` | "Pass the device to TEAM x" | **B** start turn, ▲ back to setup |
| `LOADING` | Pre-turn fetch (top up to `MIN_CARDS`) | fetch attempt completes |
| `COUNTDOWN` | 3-2-1-GO | `COUNTDOWN_MS` elapsed |
| `TURN` | Live turn | A/B/C resolve a card, ▲ undo, ▼ end, or clock hits 0 |
| `REFILL` | **Mid-turn** fetch, timer paused | fetch attempt completes |
| `SUMMARY` | Per-turn stats | **B** continue, ▲ back to setup |
| `WIN` | A team reached `TARGET_SCORE` | **B** new match |
| `NOCARDS` | No cards and no way to get them | **B** back, ▲ retry connection |

```
            ┌──────────── any button / timeout ───────────┐
 boot ─▶ CONNECTING ───── connected ─────▶ (resume?) ──────┤
            │                                              ▼
            └───────────────────────────────────────▶  SETUP ◀──────────────┐
                                                          │ B                │
                                                          ▼                  │
                                       ┌──────────────▶ HANDOFF              │ ▲ back
                                       │                  │ B                │
                                       │      online & unused<MIN_CARDS?     │
                                       │            yes ↙       ↘ no         │
                                       │         LOADING ──────▶ COUNTDOWN   │
                                       │                            │        │
                                       │                            ▼        │
                                       │   pile empty mid-turn?    TURN ──────┘ (▲ back from SUMMARY)
                                       │     online ↙   ↘ offline   │
                                       │      REFILL    recycle     │ ▼ end / time-up
                                       │        └─ resume ─▶ TURN    ▼
                                       │                          SUMMARY
                                       │           target? no ↙        ↘ yes
                                       └──────────── (other team)        WIN ─▶ SETUP
```

`after_summary()` is the match's branch point: if the team that just played has
reached `TARGET_SCORE` it goes to `WIN`, otherwise it flips `current` and returns to
`HANDOFF` for the other team.

---

## 4. Card supply — the core

This is where most of the program's subtlety lives. The governing rule:

> **A card is never shown twice while online.** The only path that repeats a card is
> offline recycling — i.e. when there is genuinely no way to get fresh ones.

### The pool

`cards._pool` maps a category to a list of `{word, taboo, used}` dicts. `used` is the
entire memory of the game: a card is consumed by setting `used = True`, and that bit
is what survives across turns, matches, and reboots (§7).

| Predicate / op | Meaning |
|----------------|---------|
| `unused_count(cat)` | how many cards are still playable |
| `has_unused(cat)` | `unused_count > 0` |
| `has_any(cat)` | the pool is non-empty (used or not) |
| `next_card(cat)` | hand out the first unused card, mark it used; **`None` if all used** |
| `recycle(cat)` | clear every `used` flag — the *only* way a card comes back |

The critical detail: `next_card` **does not** auto-recycle. When the pile is dry it
returns `None` and lets the caller decide what "dry" means — which is how the
online/offline asymmetry is enforced.

### Acquiring cards: dedup + bounded top-up

`agent.generate()` can (and does) return `main_word`s the device already holds. Dedup
happens in `_add_unique`, which compares against **every** word in the pool (used or
not) and returns how many were genuinely new:

```
fetch(cat)          -> int   # ask the agent once; discard duplicates; persist if it grew
ensure_supply(cat, target):
    while unused_count(cat) < target and tries < MAX_FETCH_TRIES:
        added = fetch(cat); tries += 1
        if added == 0: break        # agent only repeats words we have -> stop asking
    return unused_count(cat)
```

`ensure_supply` encodes the supply policy precisely:

- It keeps calling **only while** the cache is short **and** the agent is still
  producing new words. Discarded duplicates do not, by themselves, force another call.
- A fetch that adds nothing new means the agent is tapped out for that category, so it
  **stops** rather than spinning.
- `MAX_FETCH_TRIES` (3) caps calls per top-up so a chatty-but-repetitive agent can't
  hammer the API or block the UI. Falling short of `target` is acceptable — play
  proceeds with whatever is on hand.

### Two fetch points, one policy

`ensure_supply(category, MIN_CARDS)` is called from exactly two places in `__init__`'s
`_tick`, and both top up to the same target of 10:

1. **Round start (`LOADING`).** `request_turn` enters `LOADING` when `online and
   unused_count < MIN_CARDS`; leftovers from the previous turn carry over and count
   toward the 10, so a round that ended with 6 spares just fetches back up to 10.
2. **Mid-turn (`REFILL`).** If the unused pile empties *during* a turn, `resolve` →
   `_draw_or_refill` parks the machine in `REFILL`, the timer pauses (§5), more cards
   are fetched, and `resume_turn` deals the next one.

Both states use the same two-frame trick (the `_load_armed` flag): render the loading
screen for one frame so the player sees feedback, *then* run the blocking call on the
next frame.

### Decision matrix (what happens when the pile is dry)

| Situation | Online | Offline |
|-----------|--------|---------|
| Start of a round, < `MIN_CARDS` unused | `LOADING` → `ensure_supply` → play | play leftovers; none ⇒ `recycle` or `NOCARDS` |
| Pile empties mid-turn | `REFILL` (paused) → fetch → resume | `recycle` in place, keep playing (repeats allowed) |
| Agent tapped out / fetch fails | fall back to `recycle` (last resort) | `recycle` |
| No cards and empty cache | `NOCARDS` | `NOCARDS` |

So the "repeat only offline" invariant holds in normal operation, with online
recycling reserved as a last-resort fallback only when the agent literally cannot
supply a new word.

---

## 5. Turn timer & the refill pause

The clock is a single integer: `_turn_start`, a `badge.ticks` stamp. Remaining time is
derived, never decremented:

```
remaining = ceil(TURN_SECONDS - (now - _turn_start)/1000)   # clamped at 0
time_up   = (now - _turn_start) >= TURN_SECONDS*1000
```

A turn is **2 minutes** (`TURN_SECONDS = 120`); the screen edge pulses red under
`LOW_TIME_SECONDS` (10). Pausing for a mid-turn refill must not burn that clock, so the
pause is implemented as an offset rather than a stopwatch:

```
_draw_or_refill(now):   _refill_start = now ; state = REFILL      # entering the pause
resume_turn(now):       _turn_start += (now - _refill_start)      # discount the gap
```

By sliding `_turn_start` forward by exactly the elapsed fetch span, `remaining`
continues from the value it had when the pile ran dry — a multi-second network call
costs the team nothing. (Headless test: a simulated 5 s fetch leaves `remaining`
identical across the pause.)

---

## 6. Card generation — the Mistral agent

Cards come from a Mistral **Agent** over **raw HTTP** (`POST /v1/conversations`). The
official SDK is CPython-only and won't run on MicroPython, so `agent.py` uses the
firmware's `requests`, exactly like the stock `iss_tracker` / `clock` apps. All
network/secret modules (`wifi`, `requests`, `secrets`) are imported **lazily inside
functions** so `agent.py` still imports cleanly off-device.

**Request.** One category word in, JSON cards out:

```json
{ "agent_id": "...", "agent_version": 2,
  "inputs": [{ "role": "user", "content": "Hayvanlar" }] }
```

with `Authorization: Bearer <key>` and `Content-Type: application/json`.

> **The UTF-8 / Content-Length gotcha.** Turkish category names contain multi-byte
> characters (`ş`, `ğ`, `ü`, …) and MicroPython's `json.dumps` emits raw UTF-8.
> Passing the *string* to `requests.post(data=...)` makes it under-count
> `Content-Length` by the number of extra bytes, the body is truncated server-side,
> and the API returns **HTTP 422 "JSON decode error"** — but only for the
> Turkish-character categories. The fix is to send **encoded bytes** so the length
> matches the payload: `data = json.dumps(body).encode("utf-8")`.

**Response.** The agent replies with `outputs[]`; `_content_text` pulls the last
`message.output` (its `content` is a string here, but the code also tolerates the
typed-chunk list form). `_strip_fences` removes any ```` ```json ```` wrapper, then the
inner document is parsed:

```json
{ "cards": [ { "main_word": "ASLAN", "taboo_words": ["KEDI","YELE","KRAL", ...] } ] }
```

`_parse` normalises every word through `textutil.to_card_text` (§9) and caps
`taboo_words` at 5 (the panel can't fit more). Any failure anywhere — import, network,
non-200, bad JSON — is caught and surfaced as `None`/`0`, logged via `cfg.log`, and the
supply logic degrades to the cache. `HTTP_TIMEOUT` (12 s) bounds DNS/TCP/TLS/read so a
dropped link can't hang the UI.

> Credentials live in `secrets.py` on the device (`WIFI_SSID`, `WIFI_PASSWORD`,
> `MISTRAL_API_KEY`) and the agent id/version in `config.py`; `online_possible()`
> gates the whole network path on having both creds and a key.

---

## 7. Persistence & storage

### Two filesystems

| Path | What | Writable at runtime? | Visible over USB? |
|------|------|----------------------|-------------------|
| `/system/...` | the app folder, USB disk-mode drive | **No** (read-only to MicroPython) | Yes |
| `/` (internal flash) | `/cards.json`, badgeware `State` | Yes | No |

This split is the source of a common confusion: anything the app writes lands on the
internal flash and therefore **does not appear in USB disk mode**. Pull the card cache
off the device with [`tools/pull_cards.sh`](../../tools/pull_cards.sh) (an `mpremote`
wrapper).

### Card cache — `/cards.json`

The offline library. `save_cache` writes `{ category: [ {word, taboo}, ... ] }` after
any fetch that actually grew the pool; `load_cache` repopulates `_pool` at boot with
every card marked **unused**. `used` is restored separately (below), so the cache is
purely the *word list*, not the play-state.

### Match + used-state — badgeware `State`

`State` persists a small dict to internal flash under the key `"taboo"`. `_persist`
writes two things:

- **`used`** — `cards.snapshot_used()`, the set of already-played words per category.
  Written on **every** checkpoint (even between matches), and restored on **every**
  launch via `cards.restore_used`. This is what stops cards repeating across reboots
  and across matches while online.
- **The in-progress match** — scores, whose turn, category, winner. `save_state`'s
  `in_progress` flag is true for any mid-match state (`HANDOFF…SUMMARY`, `LOADING`,
  `REFILL`); when set, the next launch resumes straight into `HANDOFF` instead of
  `SETUP`.

Checkpoints happen at turn boundaries (start game, after each summary), after each
top-up (`LOADING`/`REFILL`), and on `on_exit()` — frequent enough to survive an
unplugged cable, sparse enough to spare the flash.

---

## 8. Rendering

`render.py` is a faithful port of the original canvas mockup to badgeware's `screen`
API: 320×240, the **SUNSET** 16-bit palette, a pre-baked dithered background
(`assets/bg.png`) blitted each frame.

**The 5×7 font** has no native renderer — `text()` draws each glyph as filled
`screen.rectangle` cells. The one performance concession is run-length batching: each
row of a glyph coalesces contiguous lit pixels into a single rectangle rather than
drawing them one at a time. `measure()`/`ctext()` mirror the mockup's text metrics for
pixel-exact centring.

Notable layout logic:

- **Hero word auto-shrink.** The target word is drawn at 3× with a 1px drop-shadow,
  stepping down to 2× then 1× so an over-long agent word still fits the 292px play area
  (the right 28px are reserved for the floating ▲▼ buttons), clamped so it never draws
  off-edge.
- **Taboo panel** renders at most 5 words (`[:5]`), matching the agent-side cap, so
  nothing spills past the panel.
- `_edge_pulse` is the low-time warning; `_dots` animates the "…" on the wait screens
  at fixed width so centred text doesn't jitter.

Adding a state means adding a renderer and one `_DRAWERS` entry — that is the entire
contract between `game.py` and the screen.

---

## 9. Turkish text

Two helpers in `textutil.py` keep the UI English-clean and the cards font-safe:

- **`tr_upper(s)`** — locale-correct uppercasing for theme/labels: `i → İ`, `ı → I`
  (the dotted/dotless distinction ASCII `.upper()` gets wrong), plus accent fallbacks
  and typographic punctuation normalisation (curly `'`/`'` → `'`, en/em dashes → `-`).
- **`to_card_text(s)`** — uppercases, then **strips any character the 5×7 font cannot
  draw**, so a stray emoji or Latin-extended letter from the agent can never punch a
  hole in a card.

`font.py` carries the six Turkish glyphs the cards need — **Ç Ğ İ Ö Ş Ü** — alongside
the Latin set, digits, and `: ' - + . /`.

---

## 10. Configuration (`config.py`)

| Constant | Default | Role |
|----------|---------|------|
| `TURN_SECONDS` | 120 | turn length (2:00) |
| `TARGET_SCORE` | 7 | first team to this wins |
| `COUNTDOWN_MS` | 3500 | 3-2-1-GO duration |
| `LOW_TIME_SECONDS` | 10 | red-edge warning threshold |
| `WIFI_TIMEOUT_MS` | 9000 | startup wi-fi wait before going offline |
| `HTTP_TIMEOUT` | 12 | seconds bounding the agent request |
| `MIN_CARDS` | 10 | unused-card target per round / refill |
| `MAX_FETCH_TRIES` | 3 | cap on agent calls per top-up |
| `CATEGORIES` | 10 Turkish words | the deck list |
| `API_URL` / `AGENT_ID` / `AGENT_VERSION` | — | Mistral agent endpoint |
| `CACHE_FILE` | `/cards.json` | offline library (internal flash) |
| `DEBUG` / `log()` | True | `[taboo]` serial-REPL logging |

`DEBUG` prints API calls and HTTP status codes to the USB serial REPL — watch with
`mpremote connect <port> repl`.

---

## 11. Failure modes & fallbacks

The app is built to never dead-end mid-party:

| Failure | Behaviour |
|---------|-----------|
| No wi-fi at boot | `WIFI_TIMEOUT_MS` then offline; play from cache |
| Wi-fi drops later | re-checked before every fetch; falls back to cache/recycle |
| HTTP 422 / non-200 / bad JSON | `generate` → `None`, logged; supply uses the cache |
| Agent returns only duplicates | `ensure_supply` stops asking; play with what's cached |
| Pile dry, online, fetch fails | recycle as last resort (the rare online repeat) |
| Pile dry, offline | recycle (expected repeats) |
| No cards, no cache, no key | `NOCARDS` screen, ▲ to retry the connection |

---

## 12. Testing & tools

Because `game.py`/`cards.py` are pure and `agent.py`/`render.py` use lazy or stubbable
dependencies, the whole core runs under CPython on a dev machine:

- **Headless logic tests** stub the agent and exercise the state machine directly:
  round-start top-up, the refill timer-pause math, offline recycle, `next_card`
  no-recycle, dedup discard, `ensure_supply` looping/stopping/capping, undo, and the
  `used` snapshot/restore round-trip.
- **Offline render simulator** reimplements `screen`/`color`/`image`/`vec2` in pure
  Python to rasterise the real `render.py` screens to PNGs — used to eyeball layout,
  the hero-word shrink, Turkish glyphs, and the wait screens without hardware.
- **`tools/pull_cards.sh`** pulls `/cards.json` off the device via `mpremote`;
  **`tools/gen_taboo_assets.py`** regenerates `assets/bg.png` + `icon.png`.

**Deploy:** copy `apps/taboo/*.py` onto the badge's USB drive at
`/system/apps/user/taboo/`. Runtime writes (`/cards.json`, `State`) go to internal flash and
are not visible there — pull them with the script above.
