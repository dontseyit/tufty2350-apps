# Card pool with smart caching.
#
# Per category we keep a growing pool of { word, taboo, used }. The flow:
#   - next_card() hands out an UNUSED card and marks it used; cards carry over
#     between turns, so leftovers are played before we hit the API again.
#   - ensure_supply() tops the unused pile up to MIN_CARDS, calling fetch() until
#     it has enough or the agent stops returning new words (all duplicates).
#   - fetch() asks the agent for more cards, DISCARDS any word we already hold,
#     appends the rest, and persists the library to CACHE_FILE (/cards.json on the
#     writable internal flash) so later sessions can play offline.
#   - if there is no connection and no fresh cards, recycle() reuses the cache.
#
# The persisted file is plain { category: [ {word, taboo}, ... ] }. It lives on
# the internal flash (not the USB disk-mode drive); pull it with
# tools/pull_cards.sh.

import json

import config as cfg
import textutil
import agent

# category -> [ {"word": str, "taboo": [str], "used": bool} ]
_pool = {}


def _clean_cards(items):
    out = []
    seen = set()
    for c in (items or []):
        if not isinstance(c, dict):
            continue
        word = textutil.to_card_text(c.get("word", ""))
        taboo = [textutil.to_card_text(t) for t in (c.get("taboo") or [])]
        taboo = [t for t in taboo if t][:5]   # never more than the panel fits
        if word and taboo and word not in seen:
            out.append({"word": word, "taboo": taboo, "used": False})
            seen.add(word)
    return out


def load_cache():
    """Populate the pool from CACHE_FILE (all cards start unused)."""
    _pool.clear()
    try:
        with open(cfg.CACHE_FILE) as f:
            data = json.loads(f.read())
    except Exception:
        cfg.log("no cache file yet:", cfg.CACHE_FILE)
        return
    if isinstance(data, dict):
        for category, items in data.items():
            clean = _clean_cards(items)
            if clean:
                _pool[category] = clean
    cfg.log("cache loaded:", sum(len(v) for v in _pool.values()),
            "cards from", cfg.CACHE_FILE)


def save_cache():
    data = {category: [{"word": c["word"], "taboo": c["taboo"]} for c in cards]
            for category, cards in _pool.items()}
    total = sum(len(v) for v in _pool.values())
    try:
        with open(cfg.CACHE_FILE, "w") as f:
            f.write(json.dumps(data))
        cfg.log("cache saved:", total, "cards to", cfg.CACHE_FILE)
    except Exception as e:
        cfg.log("cache write failed:", repr(e))


def _add_unique(category, cards):
    """Append only cards whose word is new to the pool (used or unused). Words the
    agent repeats are discarded. Returns how many genuinely-new cards were added."""
    pool = _pool.setdefault(category, [])
    existing = set(c["word"] for c in pool)
    added = 0
    for c in cards:
        if c["word"] not in existing:
            pool.append({"word": c["word"], "taboo": list(c["taboo"]), "used": False})
            existing.add(c["word"])
            added += 1
    return added


def has_unused(category):
    return any(not c["used"] for c in _pool.get(category, ()))


def unused_count(category):
    return sum(1 for c in _pool.get(category, ()) if not c["used"])


def has_any(category):
    return bool(_pool.get(category))


def recycle(category):
    for c in _pool.get(category, ()):
        c["used"] = False


def fetch(category):
    """Blocking: ask the agent for more cards. Duplicate words are discarded;
    returns the number of genuinely-new cards added (0 on failure/all-duplicates)."""
    cards = agent.generate(category)
    if not cards:
        cfg.log("fetch: nothing for", category)
        return 0
    added = _add_unique(category, cards)
    cfg.log("fetch:", len(cards), "from agent,", added, "new for", category,
            "- pool now", len(_pool.get(category, [])))
    if added:
        save_cache()        # only rewrite the file when the library actually grew
    return added


def ensure_supply(category, target):
    """Top the unused pile up to `target` cards. Keeps fetching only while we are
    short AND the agent is still producing new words: a fetch that adds nothing new
    (all duplicates) means the agent is tapped out, so we stop asking rather than
    spin. Bounded by cfg.MAX_FETCH_TRIES. Returns the final unused count."""
    tries = 0
    while unused_count(category) < target and tries < cfg.MAX_FETCH_TRIES:
        added = fetch(category)
        tries += 1
        if added == 0:
            break
    return unused_count(category)


def next_card(category):
    """Return an unused card (marking it used), or None when every card has been
    used. Callers decide what 'dry' means: online -> fetch fresh cards, offline ->
    recycle() the cache (the only path that ever repeats a card)."""
    for c in _pool.get(category, ()):
        if not c["used"]:
            c["used"] = True
            return c
    return None


def unmark(category, card):
    """Make a card available again (used by undo)."""
    if card is None:
        return
    for c in _pool.get(category, ()):
        if c is card or c["word"] == card.get("word"):
            c["used"] = False
            return


def mark_used(category, card):
    """Force a card back to used (undo restores the on-screen card)."""
    if card is None:
        return
    for c in _pool.get(category, ()):
        if c is card or c["word"] == card.get("word"):
            c["used"] = True
            return


def snapshot_used():
    """The set of already-played words per category (for resume persistence)."""
    return {cat: [c["word"] for c in lst if c["used"]] for cat, lst in _pool.items()}


def restore_used(snap):
    """Re-mark previously-played words as used after a resume."""
    for cat, words in (snap or {}).items():
        ws = set(words)
        for c in _pool.get(cat, ()):
            if c["word"] in ws:
                c["used"] = True
