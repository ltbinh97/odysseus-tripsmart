"""Tier-1 abuse prevention.

Protects three things:
    1. Token budget  — per-user rate limits (per minute + per day)
    2. Cost per call — input size cap (MAX_TOOL_TURNS in agent.py caps the rest)
    3. Accidental flooding — debounce of near-instant duplicate messages

Counters are in-process: simple, fast, and fine for a single-worker demo. For
multiple workers, back these with Redis — only this file changes.

Design note: escalating friction rather than hard bans, so an enthusiastic
legitimate user is slowed down, not locked out.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import config


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class _Entry:
    times: list[int] = field(default_factory=list)
    last_text: str | None = None
    last_ts: int = 0


@dataclass
class Verdict:
    allowed: bool
    reason: str | None = None
    reply: str | None = None  # user-facing Vietnamese message when blocked


class Guard:
    def __init__(
        self,
        per_minute: int | None = None,
        per_day: int | None = None,
        max_chars: int | None = None,
        debounce_ms: int | None = None,
    ) -> None:
        self.per_minute = config.RATE_PER_MINUTE if per_minute is None else per_minute
        self.per_day = config.RATE_PER_DAY if per_day is None else per_day
        self.max_chars = config.MAX_INPUT_CHARS if max_chars is None else max_chars
        self.debounce_ms = config.DEBOUNCE_MS if debounce_ms is None else debounce_ms
        self.hits: dict[str, _Entry] = {}

    def _entry(self, user_id: str) -> _Entry:
        if user_id not in self.hits:
            self.hits[user_id] = _Entry()
        return self.hits[user_id]

    def check(self, user_id: str | None, text: Any, now: int | None = None) -> Verdict:
        """Decide whether a message may proceed."""
        now = _now_ms() if now is None else now

        if not user_id:
            return Verdict(False, "missing_user", "Không xác định được người dùng.")

        message = "" if text is None else str(text)

        # --- Empty / oversized input ---------------------------------------
        if not message.strip():
            return Verdict(False, "empty", "Bạn nhắn gì đó cho mình nhé! 🙂")
        if len(message) > self.max_chars:
            return Verdict(
                False,
                "too_long",
                f"Tin nhắn hơi dài (tối đa {self.max_chars} ký tự). "
                "Bạn rút ngắn lại giúp mình nhé!",
            )

        e = self._entry(user_id)

        # --- Debounce identical rapid-fire messages ------------------------
        if e.last_text == message and now - e.last_ts < self.debounce_ms:
            return Verdict(False, "duplicate", None)  # silently ignore

        # --- Rate limits ---------------------------------------------------
        minute_ago = now - 60_000
        day_ago = now - 86_400_000
        e.times = [t for t in e.times if t > day_ago]  # prune old entries

        if sum(1 for t in e.times if t > minute_ago) >= self.per_minute:
            return Verdict(
                False, "rate_minute", "Bạn gửi hơi nhanh 😅 Chờ một chút rồi thử lại nhé!"
            )
        if len(e.times) >= self.per_day:
            return Verdict(
                False,
                "rate_day",
                "Bạn đã dùng hết lượt trò chuyện hôm nay. Hẹn gặp lại bạn ngày mai nhé!",
            )

        # --- Allowed: record the hit --------------------------------------
        e.times.append(now)
        e.last_text = message
        e.last_ts = now
        return Verdict(True)

    def stats(self, user_id: str, now: int | None = None) -> dict[str, int]:
        """Current counters — useful for debugging and dashboards."""
        now = _now_ms() if now is None else now
        e = self.hits.get(user_id)
        if e is None:
            return {"last_minute": 0, "last_day": 0}
        return {
            "last_minute": sum(1 for t in e.times if t > now - 60_000),
            "last_day": sum(1 for t in e.times if t > now - 86_400_000),
        }

    def sweep(self, now: int | None = None) -> None:
        """Drop stale entries so the dict doesn't grow forever."""
        now = _now_ms() if now is None else now
        day_ago = now - 86_400_000
        for user_id in list(self.hits):
            e = self.hits[user_id]
            e.times = [t for t in e.times if t > day_ago]
            if not e.times:
                del self.hits[user_id]
