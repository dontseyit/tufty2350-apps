# Retro Taboo - game state machine, scoring, timer.
#
# Pure logic: no drawing and no networking here. Cards come from the cards.py
# pool (which fetches from the agent / cache); render.py reads this object's
# attributes; __init__.py feeds it button presses, the clock, and performs the
# one blocking fetch (so the timer is never stalled mid-turn).

import math

import config as cfg
import cards


class Game:
    def __init__(self):
        self.deck_idx = 0          # selected category index
        self.online = False        # set by __init__ after the wi-fi attempt
        self.category = cfg.CATEGORIES[0]
        self._cd_start = 0
        self._reset_match()
        self.state = cfg.SETUP    # __init__.py may switch to CONNECTING at startup

    # ---- lifecycle -------------------------------------------------------
    def _reset_match(self):
        self.scores = [0, 0]
        self.current = 0           # team whose turn it is (0 = A, 1 = B)
        self.winner = 0
        self.current_card = None
        self._clear_turn()

    def _clear_turn(self):
        self.turn_got = 0
        self.turn_skip = 0
        self.turn_taboo = 0
        self.turn_net = 0
        self._history = []         # [(kind, card, delta)] for undo within the turn
        self._turn_start = 0
        self._refill_start = 0     # when a mid-turn REFILL paused the timer
        self.summary_reason = "time"

    # ---- transitions -----------------------------------------------------
    def start_game(self):
        # B on SETUP always starts a fresh match (team A first)
        self.category = cfg.CATEGORIES[self.deck_idx]
        self._reset_match()
        self.state = cfg.HANDOFF

    def _play_or_nocards(self, now):
        """Start a turn from whatever cards we have: prefer unused, else recycle
        the cache, else report that there is nothing to play."""
        if cards.has_unused(self.category):
            self.start_countdown(now)
        elif cards.has_any(self.category):
            cards.recycle(self.category)
            self.start_countdown(now)
        else:
            self.state = cfg.NOCARDS

    def request_turn(self, now):
        """Leaving HANDOFF: make sure the round has a full pile (>= MIN_CARDS) of
        unused cards. Online and short -> fetch (LOADING). Otherwise play whatever
        leftovers we have (offline falls back to recycle / NOCARDS)."""
        if self.online and cards.unused_count(self.category) < cfg.MIN_CARDS:
            self.state = cfg.LOADING        # __init__ performs the blocking fetch
        else:
            self._play_or_nocards(now)

    def finish_loading(self, now):
        """Called by __init__ right after the blocking fetch attempt."""
        self._play_or_nocards(now)

    def start_countdown(self, now):
        self._cd_start = now
        self.state = cfg.COUNTDOWN

    def countdown_value(self, now):
        phase = (now - self._cd_start) // 1000
        if phase <= 0:
            return "3"
        if phase == 1:
            return "2"
        if phase == 2:
            return "1"
        return "GO"

    def countdown_done(self, now):
        return (now - self._cd_start) >= cfg.COUNTDOWN_MS

    def begin_turn(self, now):
        self._clear_turn()
        self._turn_start = now
        self.current_card = cards.next_card(self.category)
        if self.current_card is None:
            self.state = cfg.NOCARDS
        else:
            self.state = cfg.TURN

    # ---- live turn -------------------------------------------------------
    def remaining_seconds(self, now):
        rem = cfg.TURN_SECONDS - (now - self._turn_start) / 1000.0
        if rem < 0:
            rem = 0
        return int(math.ceil(rem))

    def time_up(self, now):
        return (now - self._turn_start) >= cfg.TURN_SECONDS * 1000

    def resolve(self, kind, now):
        # kind in ("got", "skip", "taboo")
        delta = 1 if kind == "got" else (-1 if kind == "taboo" else 0)
        self._history.append((kind, self.current_card, delta))
        self.scores[self.current] += delta
        self.turn_net += delta
        if kind == "got":
            self.turn_got += 1
        elif kind == "skip":
            self.turn_skip += 1
        else:
            self.turn_taboo += 1
        self._draw_or_refill(now)

    def _draw_or_refill(self, now):
        """Pick the next card. If the unused pile is empty: online -> pause the
        timer and fetch more (REFILL); offline -> recycle the cache (the only path
        that repeats a card) and keep going."""
        if cards.has_unused(self.category):
            self.current_card = cards.next_card(self.category)
        elif self.online:
            self.current_card = None
            self._refill_start = now
            self.state = cfg.REFILL         # __init__ fetches, then resume_turn()
        else:
            cards.recycle(self.category)
            self.current_card = cards.next_card(self.category)

    def resume_turn(self, now):
        """Called by __init__ after a mid-turn fetch. Un-pause the timer (the fetch
        must not eat the clock) and deal the next card."""
        self._turn_start += (now - self._refill_start)
        if cards.has_unused(self.category):
            self.current_card = cards.next_card(self.category)
            self.state = cfg.TURN
        elif cards.has_any(self.category):
            cards.recycle(self.category)    # fetch failed / link dropped: reuse
            self.current_card = cards.next_card(self.category)
            self.state = cfg.TURN
        else:
            self.state = cfg.NOCARDS

    def undo(self):
        if not self._history:
            return
        kind, card, delta = self._history.pop()
        self.scores[self.current] -= delta
        self.turn_net -= delta
        if kind == "got":
            self.turn_got -= 1
        elif kind == "skip":
            self.turn_skip -= 1
        else:
            self.turn_taboo -= 1
        # restore the undone card to the screen (and keep it marked used), and
        # only return the just-drawn card to the pool if it is a different card
        # (after a recycle the draw can alias the card we are restoring)
        drawn = self.current_card
        self.current_card = card
        cards.mark_used(self.category, card)
        if drawn is not None and drawn is not card and drawn.get("word") != card.get("word"):
            cards.unmark(self.category, drawn)

    def end_turn(self, reason="ended"):
        self.summary_reason = reason
        self.state = cfg.SUMMARY

    def after_summary(self):
        # first team to reach the target wins; otherwise hand off to the other team
        if self.target_reached():
            self.winner = self.current
            self.state = cfg.WIN
        else:
            self.current = 1 - self.current
            self.state = cfg.HANDOFF

    def to_setup(self):
        self.state = cfg.SETUP

    def target_reached(self):
        return self.scores[self.current] >= cfg.TARGET_SCORE

    # ---- persistence (resume a match across app exits / reboots) ---------
    def save_state(self):
        return {
            "in_progress": self.state in (cfg.HANDOFF, cfg.COUNTDOWN, cfg.TURN,
                                          cfg.SUMMARY, cfg.LOADING, cfg.REFILL),
            "scores": list(self.scores),
            "current": self.current,
            "deck_idx": self.deck_idx,
            "winner": self.winner,
        }

    def restore(self, s):
        self.deck_idx = s.get("deck_idx", 0) % len(cfg.CATEGORIES)
        self.category = cfg.CATEGORIES[self.deck_idx]
        self._reset_match()
        self.scores = list(s.get("scores", [0, 0]))
        self.current = s.get("current", 0)
        self.winner = s.get("winner", 0)
