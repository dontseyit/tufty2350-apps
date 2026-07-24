# Networking for the Taboo card generator: wi-fi + a raw HTTP call to the
# Mistral Agents "conversations" endpoint. No SDK (it is CPython-only); we use
# the firmware's `requests`, exactly like iss_tracker/clock use it.
#
# Hardware/secret modules (wifi, requests, secrets) are imported lazily inside
# the functions so this module (and cards.py / game.py) still import cleanly off
# device for testing.

import json

import config as cfg
import textutil

# Wi-fi credentials and the Mistral API key come from /system/secrets.py; the
# app bootstrap (__init__.py) puts /system on the import path so this lazy
# `import secrets` reads that USB-editable file. No credentials live in code.


def online_possible():
    """True if we have both wi-fi credentials and an API key to even try."""
    try:
        import secrets
    except Exception:
        return False
    ssid = getattr(secrets, "WIFI_SSID", "") or ""
    key = getattr(secrets, "MISTRAL_API_KEY", "") or ""
    return bool(ssid and key)


def connect():
    """Kick/poll the wi-fi connection. Returns True once associated."""
    try:
        import wifi
        import secrets
        ssid = getattr(secrets, "WIFI_SSID", "") or ""
        psk = getattr(secrets, "WIFI_PASSWORD", "") or ""
        return bool(ssid and wifi.connect(ssid=ssid, psk=psk))
    except Exception:
        return False


def tick():
    try:
        import wifi
        wifi.tick()
    except Exception:
        pass


def generate(category):
    """Ask the agent for cards in `category`. Returns a list of
    {"word", "taboo"} (uppercased, font-safe) or None on any failure."""
    try:
        import requests
        import secrets
    except Exception as e:
        cfg.log("generate: import failed:", repr(e))
        return None

    key = getattr(secrets, "MISTRAL_API_KEY", "") or ""
    if not key:
        cfg.log("generate: no API key")
        return None

    body = {
        "agent_id": cfg.AGENT_ID,
        "agent_version": cfg.AGENT_VERSION,
        "inputs": [{"role": "user", "content": category}],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    }

    # Encode to UTF-8 BYTES so Content-Length matches the byte count. Turkish
    # letters (ş, ğ, ü, ...) are multi-byte and MicroPython's json.dumps emits
    # raw UTF-8; sending a str makes requests under-count Content-Length, the
    # body is truncated, and the API returns HTTP 422 "JSON decode error".
    payload = json.dumps(body).encode("utf-8")
    cfg.log("POST", cfg.API_URL, "category=", category)
    r = None
    try:
        # timeout bounds DNS/TCP/TLS/read so a dropped link can't hang the UI forever
        r = requests.post(cfg.API_URL, headers=headers, data=payload,
                          timeout=cfg.HTTP_TIMEOUT)
        cfg.log("HTTP", getattr(r, "status_code", "?"))
        env = r.json()
    except Exception as e:
        cfg.log("request error:", repr(e))
        return None
    finally:
        try:
            if r is not None:
                r.close()
        except Exception:
            pass

    cards = _parse(env)
    if cards is None:
        cfg.log("no cards parsed; response head:", str(env)[:200])
    else:
        cfg.log("parsed", len(cards), "cards")
    return cards


def _content_text(env):
    """Pull the assistant's text out of a conversations response. `content` is a
    string for this agent, but may be a list of typed chunks for others."""
    outputs = env.get("outputs") or []
    for o in reversed(outputs):
        if not isinstance(o, dict) or o.get("type") != "message.output":
            continue
        c = o.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts = [p.get("text", "") for p in c
                     if isinstance(p, dict) and p.get("type") == "text"]
            return "".join(parts)
    return None


def _strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def _parse(env):
    try:
        content = _content_text(env)
        if not content:
            return None
        obj = json.loads(_strip_fences(content))
        raw = obj.get("cards") or []
        cards = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            word = textutil.to_card_text(item.get("main_word", ""))
            taboo = [textutil.to_card_text(t) for t in (item.get("taboo_words") or [])]
            taboo = [t for t in taboo if t][:5]   # never more than the panel fits
            if word and taboo:
                cards.append({"word": word, "taboo": taboo})
        return cards or None
    except Exception as e:
        cfg.log("parse error:", repr(e))
        return None
