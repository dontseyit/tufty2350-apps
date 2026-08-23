# TdF Live

A **Tour de France live dashboard** for the Pimoroni Tufty 2350 (320×240,
HIRES) in a maillot-jaune yellow-on-dark theme. Five pages, cycled with A / C:
the live **race situation** (km to go, progress, breakaway/peloton gaps with
rider nationalities, next climb with gradient), the PCS **live ticker** with
on-device scrollback, the **GC** top 20, **today's points** (green & KOM), and
the **roadbook** (all climbs & sprints with length + gradient).

## How the data flows (why there's a proxy)

procyclingstats.com sits entirely behind a **Cloudflare JS challenge** — the
badge's plain HTTP client gets a 403. So a tiny proxy on your LAN does the
scraping (with `curl_cffi` impersonating Chrome, which passes cleanly) and
serves the flattened, ASCII-folded JSON the badge understands:

```
PCS (Cloudflare) <-- curl_cffi --> tools/tdf_proxy.py <-- plain HTTP --> badge
```

1. `pip install curl_cffi`, then run `python3 tools/tdf_proxy.py` on a machine
   on the same network.
2. Point [`config.py`](config.py) `PROXY_URL` at it (default
   `http://192.168.0.134:8321/live.json`).
3. Wi-fi credentials are read from **`/system/secrets.py`** — the file you can
   edit directly on the badge's USB drive (`WIFI_SSID` / `WIFI_PASSWORD`), see
   [`secrets.py.example`](../../secrets.py.example). An optional backup network
   (`WIFI_SSID2` / `WIFI_PASSWORD2`, e.g. a phone hotspot) is tried when the
   primary won't associate, and the two alternate while offline. The app puts
   `/system` on the import path so `import secrets` reads this USB-visible file
   (not `/secrets.py` on the internal flash). No credentials are stored in the
   app code; with no `WIFI_SSID` in the file, the app just runs offline-only.

The badge polls the proxy every 10 s (`POLL_MS`), rendering one "updating"
frame before each blocking fetch so the UI never looks frozen. The tab bar
shows the data age with a green/yellow/red dot; if the proxy stops answering
(or the data is >60 s old) a red **STALE DATA** strip appears. No wi-fi at
boot → offline mode showing the last-known state, retrying in the background.

## Controls

| Button | Action |
|--------|--------|
| **A** | ◀ previous page (cycles) |
| **C** | ▶ next page (cycles) |
| **B** | in-page action (on POINTS: toggle GREEN / KOM) |
| **▲ / ▼** | scroll the current page |

Pages cycle RACE → TICKER → GC → POINTS → ROUTE. Each page keeps its own scroll
position.

## History on flash

Ticker posts are merged (deduped by `seq`, newest first, capped at 150) and
persisted to **`/tdf.json`** on the writable internal flash root (the
`/system` app folder is read-only at runtime). It's written **only** when new
posts arrive or the stage changes — flash-write discipline — and loaded at
boot, so the ticker has scrollback and the dashboard shows the last-known race
state even before wi-fi/proxy are up. A stage change resets the post history.

## File map

| File | Role |
|------|------|
| `__init__.py` | bootstrap, wi-fi state machine, poll scheduler (render-then-block fetch), buttons |
| `data.py`     | fetch + payload ingest, ticker history merge/persist, age math, formatting (pure, CPython-testable) |
| `render.py`   | tab bar + the three pages + waiting/stale overlays |
| `config.py`   | proxy URL, poll cadence, theme colours, debug `log()` |
| `icon.png` · `assets/icon.png` | menu icon (yellow jersey) |

## Regenerating assets

```
python3 tools/gen_tdf_assets.py   # icon.png + assets/icon.png
```
