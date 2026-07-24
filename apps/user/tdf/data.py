# TdF data layer: proxy fetch, ticker history merge, flash persistence, age
# math. Pure logic - imports cleanly on CPython (the `requests` import is lazy
# inside fetch(), exactly like taboo/agent.py), so all of this is unit-testable
# off-device. Never crashes on missing/short fields: .get with defaults
# everywhere; the proxy may serve ok:false while warming up.

import json

import config as cfg

# ---- module state ----------------------------------------------------------
payload = None            # last good (ok: true) payload dict
posts = []                # merged timeline posts, newest first, deduped by seq
stage_nr = 0              # stage the posts belong to
ticks_at_fetch = None     # badge.ticks (ms) at the last good fetch; None = never
last_fetch_failed = False # the most recent fetch attempt errored
warming = False           # proxy reachable but serving ok:false
save_count = 0            # how many times save() wrote flash (test/diagnostic)
_unsaved = False          # merged posts not yet on flash (save() failed / pending)


def reset():
    """Back to boot state (used by tests)."""
    global payload, posts, stage_nr, ticks_at_fetch
    global last_fetch_failed, warming, save_count, _unsaved
    payload = None
    posts = []
    stage_nr = 0
    ticks_at_fetch = None
    last_fetch_failed = False
    warming = False
    save_count = 0
    _unsaved = False


# ---- age math (no RTC needed) ----------------------------------------------
def age_seconds(now_ticks):
    """Seconds since the proxy last scraped PCS, or None before the first
    successful fetch (e.g. history loaded from flash after a reboot)."""
    if payload is None or ticks_at_fetch is None:
        return None
    a = (payload.get("age_s") or 0) + (now_ticks - ticks_at_fetch) / 1000.0
    return a if a >= 0 else 0


def post_age(post_ts, now_ticks):
    """Seconds since a timeline post, or None if unknowable.
    post age = (payload.ts - post.ts) + age_seconds(now)."""
    if payload is None or not post_ts:
        return None
    base = (payload.get("ts") or 0) - post_ts
    if base < 0:
        base = 0
    a = age_seconds(now_ticks)
    if a is None:
        # no fresh fetch yet: the post is AT LEAST this old (flash-loaded state)
        return base
    return base + a


# ---- display formatting (pure, testable) -----------------------------------
def fmt_gap(sec):
    """Group gap seconds -> '+m:ss'."""
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        sec = 0
    if sec < 0:
        sec = 0
    return "+%d:%02d" % (sec // 60, sec % 60)


def fmt_age(sec):
    """Age seconds -> '13S' / '2M' / '1H12M'; None -> '--'."""
    if sec is None:
        return "--"
    sec = int(sec)
    if sec < 0:
        sec = 0
    if sec < 60:
        return "%dS" % sec
    m = sec // 60
    if m < 60:
        return "%dM" % m
    return "%dH%02dM" % (m // 60, m % 60)


# ---- history: merge / persist ----------------------------------------------
def merge(timeline):
    """Fold a payload's timeline into `posts` (newest first, deduped by seq,
    capped at cfg.HISTORY_POSTS). Returns how many genuinely-new posts landed."""
    global posts
    if not timeline:
        return 0
    seen = set()
    for p in posts:
        seen.add(p.get("seq"))
    new = 0
    for p in timeline:
        if not isinstance(p, dict):
            continue
        s = p.get("seq")
        if s in seen:
            continue
        seen.add(s)
        posts.append(p)
        new += 1
    if new:
        posts.sort(key=lambda p: p.get("seq") or 0, reverse=True)
        posts = posts[:cfg.HISTORY_POSTS]
    return new


def save():
    """Persist history per the contract:
    {"stage": nr, "saved_ts": ts, "last": payload-without-timeline, "posts": [...]}
    Writes go to the internal flash root - /system is read-only at runtime."""
    global save_count, _unsaved
    last = {}
    if isinstance(payload, dict):
        for k in payload:
            if k != "timeline":
                last[k] = payload[k]
    doc = {
        "stage": stage_nr,
        "saved_ts": last.get("ts", 0),
        "last": last,
        "posts": posts,
    }
    try:
        with open(cfg.HISTORY_FILE, "w") as f:
            f.write(json.dumps(doc))
        save_count += 1
        _unsaved = False
        cfg.log("history saved:", len(posts), "posts, stage", stage_nr)
    except Exception as e:
        cfg.log("history save failed:", repr(e))


def save_if_needed():
    """on_exit hook: only rewrite flash if a merge is still unsaved."""
    if _unsaved:
        save()


def load():
    """Boot: restore ticker history + last-known race state from flash so the
    app has content offline / before wi-fi. Data age stays unknown (None)."""
    global posts, stage_nr, payload
    try:
        with open(cfg.HISTORY_FILE) as f:
            doc = json.loads(f.read())
    except Exception:
        cfg.log("no history file yet:", cfg.HISTORY_FILE)
        return False
    if not isinstance(doc, dict):
        return False
    posts = [p for p in (doc.get("posts") or []) if isinstance(p, dict)]
    stage_nr = doc.get("stage", 0) or 0
    last = doc.get("last")
    if isinstance(last, dict) and last.get("ok"):
        payload = last
    cfg.log("history loaded:", len(posts), "posts, stage", stage_nr)
    return True


# ---- fetch / apply -----------------------------------------------------------
def apply(p, now_ticks):
    """Ingest one payload dict. Returns True if it replaced the live state.
    Saves to flash ONLY when new posts arrived or the stage changed."""
    global payload, stage_nr, ticks_at_fetch, warming, posts, _unsaved
    if not isinstance(p, dict):
        return False
    if not p.get("ok"):
        warming = True
        cfg.log("payload ok:false - proxy warming up")
        return False
    warming = False
    stage_changed = False
    nr = 0
    st = p.get("stage")
    if isinstance(st, dict):
        try:
            nr = int(st.get("nr") or 0)   # render does "S%d" / stage_nr - 1
        except (TypeError, ValueError):
            nr = 0
    if nr and stage_nr and nr != stage_nr:
        cfg.log("stage change", stage_nr, "->", nr, "- resetting posts")
        posts = []
        stage_changed = True
    if nr:
        stage_nr = nr
    payload = p
    ticks_at_fetch = now_ticks
    new = merge(p.get("timeline") or [])
    if new or stage_changed:
        _unsaved = True
        save()
    return True


def fetch():
    """One blocking GET of the proxy. Returns the parsed dict or None on any
    network/parse error. Network modules are imported lazily so this file
    imports cleanly off-device."""
    try:
        import requests
    except Exception as e:
        cfg.log("fetch: no requests module:", repr(e))
        return None
    r = None
    try:
        r = requests.get(cfg.PROXY_URL, timeout=cfg.HTTP_TIMEOUT)
        p = r.json()
    except Exception as e:
        # broad on purpose (like taboo/agent.py): MicroPython's requests can
        # raise more than OSError/ValueError (e.g. NotImplementedError on a
        # redirect) and an uncaught error here would kill the whole app loop
        cfg.log("fetch failed:", repr(e))
        return None
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:
                pass
    return p if isinstance(p, dict) else None


def refresh(now_ticks):
    """fetch + apply. Returns True when fresh live data landed."""
    global last_fetch_failed
    p = fetch()
    if p is None:
        last_fetch_failed = True
        return False
    last_fetch_failed = False
    return apply(p, now_ticks)
