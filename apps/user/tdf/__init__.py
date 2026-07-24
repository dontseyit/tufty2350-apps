APP_DIR = "/system/apps/user/tdf"

import os
import sys

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

import config as cfg
import data
import render

# Wi-fi: primary + optional backup network, tried in order. Credentials come
# entirely from /system/secrets.py - the file you can edit directly on the
# badge's USB drive from your computer (WIFI_SSID/WIFI_PASSWORD, plus optional
# WIFI_SSID2/WIFI_PASSWORD2 for the backup). We put /system on the import path
# and drop any stale copy a previously-run app may have cached, so `import
# secrets` reads THAT file and not /secrets.py on the internal flash. No
# credentials live in this file - if secrets.py has no WIFI_SSID, the app runs
# offline-only.
sys.path.insert(0, "/system")
sys.modules.pop("secrets", None)
try:
    import secrets as _secrets
except Exception as _e:
    cfg.log("wifi: no secrets.py (", repr(_e), ")")
    _secrets = None


def _sec(name):
    return (getattr(_secrets, name, "") or "") if _secrets else ""


# primary first, then the optional backup - both from secrets.py
_NETWORKS = [(s, p) for s, p in (
    (_sec("WIFI_SSID"), _sec("WIFI_PASSWORD")),
    (_sec("WIFI_SSID2"), _sec("WIFI_PASSWORD2")),
) if s]
if _NETWORKS:
    cfg.log("wifi: %d network(s) from /system/secrets.py" % len(_NETWORKS))
else:
    cfg.log("wifi: no WIFI_SSID in /system/secrets.py - running offline only")

# The dashboard is authored for the Tufty's native 320x240; switch to hi-res.
badge.mode(HIRES)
render.init()

# Boot: restore ticker scrollback + last-known race state from flash so there
# is something to show offline / before wi-fi is up.
data.load()

# UI state shared with render (render clamps the scroll values to content size).
# With no configured network we start OFFLINE rather than perpetually "connecting".
ui = {
    "page": cfg.RACE,
    "scroll": [0] * cfg.NPAGES,
    "wifi": cfg.WIFI_CONNECTING if _NETWORKS else cfg.WIFI_OFF,
    "updating": False,
    "pts_kom": False,
}

_connect_start = badge.ticks
_net_idx = 0           # which _NETWORKS entry is being tried
_nets_tried = 1        # networks given a window in this connecting round
_retry_at = 0          # next wi-fi retry when offline
_last_poll = None      # badge.ticks of the last proxy poll; None forces one now
_fetch_armed = False   # two-phase fetch: render one "updating" frame, then block
_last_progress = 0     # throttle for the once-per-3s connecting log line

ui["ssid"] = _NETWORKS[_net_idx][0] if _NETWORKS else ""


def _wifi_reset():
    """Clear the wifi module's association state. After a hard failure the
    frozen module stays wedged (further connect() calls are ignored) until
    disconnect() is called - this is THE fix for 'never connects again'."""
    try:
        import wifi
        wifi.disconnect()
    except Exception as e:
        cfg.log("wifi: reset failed:", repr(e))


def _wifi_ip():
    try:
        import wifi
        return wifi.ip()
    except Exception:
        return "?"


def _wifi_connect():
    """Kick/poll the association with the current network. Guarded so a
    missing wifi module (or no configured network) can never crash the loop."""
    if not _NETWORKS:
        return False
    ssid, psk = _NETWORKS[_net_idx]
    try:
        import wifi
        return bool(wifi.connect(ssid=ssid, psk=psk))
    except Exception as e:
        cfg.log("wifi: connect(%s) raised:" % ssid, repr(e))
        return False


def _next_network(now):
    """Advance to the next candidate network (primary -> backup -> primary...)
    and restart the attempt window. Always resets the module state first so
    the new attempt starts clean. No-op network-wise with a single entry."""
    global _net_idx, _connect_start
    _wifi_reset()
    if len(_NETWORKS) > 1:
        _net_idx = (_net_idx + 1) % len(_NETWORKS)
        ui["ssid"] = _NETWORKS[_net_idx][0]
    cfg.log("wifi: trying", ui["ssid"])
    _connect_start = now


def _wifi_tick():
    """Drive the association. The module RAISES on hard failures ('Access
    point X not found.', 'Incorrect password.') - surface the reason in the
    log and reset so the next attempt isn't ignored. Returns True on a hard
    failure so the caller can move on without waiting out the window."""
    try:
        import wifi
        wifi.tick()
        return False
    except Exception as e:
        cfg.log("wifi:", str(e) or repr(e))
        _wifi_reset()
        return True


def _cycle(delta):
    ui["page"] = (ui["page"] + delta) % cfg.NPAGES


def _page_action():
    # B: per-page action. On POINTS it toggles GREEN <-> KOM; other pages none.
    if ui["page"] == cfg.POINTS:
        ui["pts_kom"] = not ui["pts_kom"]


def _handle_input():
    if badge.pressed(BUTTON_A):
        _cycle(-1)
    elif badge.pressed(BUTTON_C):
        _cycle(1)
    elif badge.pressed(BUTTON_B):
        _page_action()
    elif badge.pressed(BUTTON_UP):
        p = ui["page"]
        if ui["scroll"][p] > 0:
            ui["scroll"][p] -= 1
    elif badge.pressed(BUTTON_DOWN):
        # upper clamp happens in render, where the content size is known
        ui["scroll"][ui["page"]] += 1


def _tick_net(now):
    global _connect_start, _retry_at, _last_poll, _fetch_armed, _nets_tried
    global _last_progress

    if ui["wifi"] == cfg.WIFI_CONNECTING:
        if _wifi_connect():
            cfg.log("wifi up:", ui["ssid"], "ip=", _wifi_ip(),
                    "after", now - _connect_start, "ms")
            ui["wifi"] = cfg.WIFI_UP
            _last_poll = None            # poll the proxy immediately
        else:
            hard_fail = _wifi_tick()     # True: AP not found / bad password
            if now - _last_progress >= 3000:
                _last_progress = now
                cfg.log("wifi: connecting to", ui["ssid"],
                        "(%dms)" % (now - _connect_start))
            # a hard failure ends this network's window early; otherwise wait
            # out WIFI_TIMEOUT_MS. Only go offline once every configured
            # network has had a window.
            if hard_fail or now - _connect_start >= cfg.WIFI_TIMEOUT_MS:
                if not hard_fail:
                    cfg.log("wifi:", ui["ssid"], "window timed out")
                if _nets_tried < len(_NETWORKS):
                    _nets_tried += 1
                    _next_network(now)
                else:
                    cfg.log("wifi: all networks failed -> offline mode",
                            "(retrying in background)")
                    _wifi_reset()
                    ui["wifi"] = cfg.WIFI_OFF
                    _retry_at = now + cfg.POLL_MS

    elif ui["wifi"] == cfg.WIFI_OFF:
        # offline: keep showing last-known data, retry every POLL_MS,
        # alternating between the configured networks
        if now >= _retry_at:
            _retry_at = now + cfg.POLL_MS
            if _wifi_connect():
                cfg.log("wifi recovered:", ui["ssid"], "ip=", _wifi_ip())
                ui["wifi"] = cfg.WIFI_UP
                _last_poll = None
            else:
                _wifi_tick()
                _next_network(now)

    else:  # WIFI_UP
        if _fetch_armed:
            # the "updating" frame was rendered last tick; now do the blocking
            # fetch (taboo's _load_armed pattern)
            _fetch_armed = False
            if _wifi_connect():          # re-check: the link may have dropped
                data.refresh(badge.ticks)
                _last_poll = badge.ticks
            else:
                cfg.log("wifi dropped -> reconnecting")
                _wifi_reset()            # start the new round clean
                ui["wifi"] = cfg.WIFI_CONNECTING
                _connect_start = now
                _nets_tried = 1
        elif _last_poll is None or now - _last_poll >= cfg.POLL_MS:
            _fetch_armed = True

    ui["updating"] = _fetch_armed


def update():
    now = badge.ticks
    _handle_input()
    _tick_net(now)
    render.draw(ui, now)


def on_exit():
    # the launcher calls this when the app exits - flush any unsaved history
    data.save_if_needed()


run(update)
