# Retro Taboo

A pass-and-play **Taboo** party game for the Pimoroni Tufty 2350, in a 16-bit
SUNSET palette, drawn on a locked pixel grid (320×240, HIRES). Ported from the
design in [`taboo/`](../../taboo) (`HANDOVER.md` + `Pixel Mockup.dc.html`).

The **UI is English**; the **card content is Turkish**, generated on demand by a
**Mistral Agent** and cached on the device (the 5×7 font carries Ç Ğ İ Ö Ş Ü).

## Controls (B is always the "proceed" button)

| State | A | B (primary) | C | ▲ | ▼ |
|-------|---|-------------|---|---|---|
| SETUP     | — | Start game | — | Category prev | Category next |
| HANDOFF   | — | Start turn | — | Back → setup | — |
| TURN      | **Taboo −1** | **Skip** | **Got it +1** | Undo last | End turn |
| SUMMARY   | — | Next / results | — | Back → setup | — |
| WIN       | — | Play again | — | — | — |

CONNECTING / COUNTDOWN / LOADING / REFILL lock input (any button skips the
startup wi-fi wait). NOCARDS: **B** back, **▲** retry the connection.

## Rules

- Scoring: Got it **+1**, Taboo (self-reported) **−1**, Skip **0** (unlimited).
- Turn: **2:00** (`TURN_SECONDS` = 120); ▼ ends early; auto-advances at 0:00; the
  screen edge pulses red under 10 s. If the card pile runs out mid-turn the timer
  **pauses** while fresh cards are fetched (the REFILL screen), then resumes.
- Win: first team to **7** (`TARGET_SCORE`).

## Card generation & caching

Cards come from a Mistral Agent over **raw HTTP** (`POST /v1/conversations`) — no
SDK (the SDK is CPython-only and won't run on MicroPython). The agent takes one
Turkish category word and returns 10 cards as JSON; we uppercase (Turkish-aware:
`i→İ`, `ı→I`), strip anything the font can't draw, and add them to a per-category
pool.

Smart caching (the API is hit sparingly, and the **same card never repeats while
online** — only offline play recycles cards):

- **Round start**: each turn tops the unused pile up to **`MIN_CARDS`** (10).
  Leftovers from a previous turn carry over and are played first (end a round with
  6 spare → the next round fetches to reach 10, or just plays them if already ≥10).
- **Mid-turn refill**: if the unused pile empties *during* a turn, the timer
  **pauses**, more cards are fetched, and the turn resumes where it left off — the
  network time never eats the clock.
- Every fetch appends unique cards (deduped by word) and is persisted to
  **`/cards.json`** on the writable internal flash (the read-only `/system` app
  folder can't be written at runtime). Pull it with `tools/pull_cards.sh`.
- **Used across boots**: the set of already-played cards is saved via badgeware
  `State` and restored on every launch, so cards don't repeat between sessions or
  matches while online.
- **Offline**: if wi-fi/the API is unavailable, the game plays from `/cards.json`,
  recycling cards as needed (the only time a card is shown twice). With no key and
  no cache, a category shows NOCARDS.
- **Resume**: scores / whose-turn / category (plus the used-card set) are saved via
  badgeware `State` (key `"taboo"`), so an interrupted match resumes.

### Setup (one-time)

1. Put your key in [`secrets.py`](../../secrets.py): `MISTRAL_API_KEY = "..."`
   (alongside `WIFI_SSID` / `WIFI_PASSWORD`). It lives only on the device.
2. Point [`config.py`](config.py) at your agent: `AGENT_ID` / `AGENT_VERSION`.

> HTTPS note: the call is TLS to `api.mistral.ai`. If your firmware's `requests`
> can't do HTTPS (or runs low on RAM), run a tiny HTTP→HTTPS proxy and set
> `API_URL` to it — the rest of the app is unchanged.

## Architecture

For the full engineering deep-dive — execution model, the state-machine diagram, the
card-supply logic, the timer-pause math, the Mistral request/parse path, and the
storage model — see **[`WIKI.md`](WIKI.md)**. Quick map:

| File | Role |
|------|------|
| `__init__.py` | bootstrap, startup wi-fi, deferred blocking fetch, input→state→render loop |
| `game.py`     | pure state machine (scoring, timer, undo) — pulls cards from `cards.py` |
| `cards.py`    | per-category card pool: fetch + dedup + JSON cache + used-state + recycle |
| `agent.py`    | wi-fi + the raw HTTP call + response parsing (network imports are lazy) |
| `textutil.py` | Turkish uppercasing + font-charset sanitising |
| `config.py`   | constants, the 10 Turkish categories, agent/cache config |
| `render.py`   | the 10 screen renderers + 5×7 text primitives |
| `font.py`     | the 5×7 glyph table (Latin + digits + Turkish + `: ' - + . /`) |
| `assets/bg.png` · `icon.png` | baked SUNSET dither background; menu icon |

`/cards.json` (internal flash) is generated at runtime — the offline card
library; pull it with `tools/pull_cards.sh`. Match progress lives in badgeware
`State`.

## Regenerating assets

```
python3 tools/gen_taboo_assets.py   # bg.png + icon.png
```
