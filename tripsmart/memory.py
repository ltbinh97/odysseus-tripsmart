"""Memory layer — three distinct kinds, one small SQLite file.

    1. Session memory    : the conversation message list (expires)
    2. Preference memory : durable self-declared preferences (persists)
    3. Knowledge base    : static JSON in ../data (not here — that's reference data)

Uses the standard-library `sqlite3`, so there is nothing to install or compile
on the VPS. Swap in Postgres later and only this file changes.

PRIVACY: preferences only. Never names, phones, passports, dates of birth, or
payment details. Companion ages are stored as ranges, never birthdates.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Any

from . import config

# Keys the agent may persist. Anything else is refused. This is a hard backstop
# in code, independent of what the model decides to call.
ALLOWED_PREF_KEYS: set[str] = {
    "home_city",
    "budget_tier",
    "companions",
    "dietary",
    "flight_preference",
    "hotel_preference",
}

# Values matching any of these look like PII and are refused.
PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{9,12}\b"),               # long digit runs (phone / passport / ID)
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),      # full dates (DOB)
    re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),      # full dates, other format
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),    # card-like number sequences
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),    # email
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_prefs (
    user_id    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, key)
);
CREATE TABLE IF NOT EXISTS sessions (
    user_id    TEXT PRIMARY KEY,
    messages   TEXT NOT NULL,
    summary    TEXT,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_log (
    user_id    TEXT NOT NULL,
    ts         INTEGER NOT NULL,
    in_tokens  INTEGER,
    out_tokens INTEGER
);
CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON usage_log(user_id, ts);

-- Shared cache of external-API results (flight/hotel prices, POIs). Keyed by a
-- normalised query so the first user's search is reused by everyone after them
-- until it goes stale, then refreshed on the next request. Not per-user.
CREATE TABLE IF NOT EXISTS api_cache (
    kind        TEXT NOT NULL,        -- 'flights' | 'hotels' | 'places'
    cache_key   TEXT NOT NULL,        -- normalised query signature
    payload     TEXT NOT NULL,        -- JSON of the cached (pax/budget-independent) result
    created_at  INTEGER NOT NULL,     -- ms, first time we fetched this key
    updated_at  INTEGER NOT NULL,     -- ms, last refresh (drives the TTL)
    hits        INTEGER NOT NULL DEFAULT 0,  -- times served from cache (API calls saved)
    PRIMARY KEY (kind, cache_key)
);

-- Destinations users have searched, accumulated across everyone, so we can
-- suggest popular places to the next user. sample_places holds a few top POIs
-- (name + rating) to preview without another API call.
CREATE TABLE IF NOT EXISTS place_searches (
    destination   TEXT PRIMARY KEY,   -- normalised destination name (lowercased)
    display_name  TEXT NOT NULL,      -- nicest-cased name to show back
    search_count  INTEGER NOT NULL DEFAULT 1,
    last_searched INTEGER NOT NULL,
    sample_places TEXT NOT NULL DEFAULT '[]'  -- JSON list of {name, rating}
);
CREATE INDEX IF NOT EXISTS idx_place_pop ON place_searches(search_count DESC, last_searched DESC);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


class Memory:
    def __init__(self, db_path: str | None = None) -> None:
        self.db = sqlite3.connect(
            db_path or config.DB_PATH,
            check_same_thread=False,  # FastAPI may touch this from a threadpool
        )
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ---------------- Preferences (durable) ----------------

    def get_preferences(self, user_id: str) -> dict[str, str]:
        rows = self.db.execute(
            "SELECT key, value FROM user_prefs WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def save_preference(self, user_id: str, key: str, value: Any) -> dict[str, Any]:
        """Persist a preference. Returns {"saved": bool, "reason": str | None}."""
        if key not in ALLOWED_PREF_KEYS:
            return {"saved": False, "reason": f"key '{key}' is not an allowed preference key"}

        val = str(value).strip()
        if not val:
            return {"saved": False, "reason": "empty value"}
        if len(val) > 200:
            return {"saved": False, "reason": "value too long"}
        if any(p.search(val) for p in PII_PATTERNS):
            return {"saved": False, "reason": "value looks like personal data and was not stored"}

        self.db.execute(
            """INSERT INTO user_prefs (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET
                 value = excluded.value, updated_at = excluded.updated_at""",
            (user_id, key, val, _now_ms()),
        )
        self.db.commit()
        return {"saved": True, "reason": None}

    def render_preferences(self, user_id: str) -> str:
        """Format preferences for injection into the system prompt."""
        prefs = self.get_preferences(user_id)
        if not prefs:
            return "(No stored preferences — treat as a new user.)"
        return "\n".join(f"- {k}: {v}" for k, v in prefs.items())

    def delete_preference(self, user_id: str, key: str) -> int:
        """Remove one stored preference. Returns rows deleted."""
        cur = self.db.execute(
            "DELETE FROM user_prefs WHERE user_id = ? AND key = ?", (user_id, key)
        )
        self.db.commit()
        return cur.rowcount or 0

    def clear_preferences(self, user_id: str) -> int:
        """Remove every stored preference for a user (their right to be forgotten)."""
        cur = self.db.execute("DELETE FROM user_prefs WHERE user_id = ?", (user_id,))
        self.db.commit()
        return cur.rowcount or 0

    # ---------------- Sessions (expiring conversation history) ----------------

    def load_session(self, user_id: str) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT messages, summary, updated_at FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return {"messages": [], "summary": None}

        age_hours = (_now_ms() - row["updated_at"]) / 3_600_000
        if age_hours > config.SESSION_TTL_HOURS:
            self.clear_session(user_id)  # expired — start fresh
            return {"messages": [], "summary": None}

        try:
            return {"messages": json.loads(row["messages"]), "summary": row["summary"]}
        except (json.JSONDecodeError, TypeError):
            return {"messages": [], "summary": None}

    def save_session(
        self, user_id: str, messages: list[dict], summary: str | None = None
    ) -> None:
        self.db.execute(
            """INSERT INTO sessions (user_id, messages, summary, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 messages = excluded.messages, summary = excluded.summary,
                 updated_at = excluded.updated_at""",
            (user_id, json.dumps(messages, ensure_ascii=False), summary, _now_ms()),
        )
        self.db.commit()

    def clear_session(self, user_id: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self.db.commit()

    def purge_expired_sessions(self) -> int:
        """Housekeeping: drop sessions past their TTL. Returns rows removed."""
        cutoff = _now_ms() - config.SESSION_TTL_HOURS * 3_600_000
        cur = self.db.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
        self.db.commit()
        return cur.rowcount or 0

    # ---------------- Usage tracking (cost visibility) ----------------

    def log_usage(self, user_id: str, in_tokens: int, out_tokens: int) -> None:
        self.db.execute(
            "INSERT INTO usage_log (user_id, ts, in_tokens, out_tokens) VALUES (?, ?, ?, ?)",
            (user_id, _now_ms(), in_tokens or 0, out_tokens or 0),
        )
        self.db.commit()

    def usage_today(self, user_id: str) -> dict[str, int]:
        since = _now_ms() - 24 * 3_600_000
        row = self.db.execute(
            """SELECT COALESCE(SUM(in_tokens), 0) AS i, COALESCE(SUM(out_tokens), 0) AS o
               FROM usage_log WHERE user_id = ? AND ts > ?""",
            (user_id, since),
        ).fetchone()
        return {"in_tokens": row["i"], "out_tokens": row["o"]}

    # ---------------- Shared result cache (external API savings) ----------------

    def cached_or_fetch(
        self, kind: str, key: str, ttl_hours: float, fetch_fn
    ) -> tuple[Any, dict[str, Any]]:
        """Serve a fresh cached payload; otherwise fetch, store, and serve it.

        - Fresh hit (younger than ttl_hours)  -> return cache, no API call.
        - Miss or stale                        -> call fetch_fn(), store, return.
        - fetch_fn() fails but a stale entry   -> serve the stale entry (better
          than nothing during an outage / rate-limit).
        - Miss and fetch_fn() fails            -> re-raise (caller decides).

        Returns (payload, meta) where meta = {from_cache, stale, age_ms}. fetch_fn
        is only invoked on a miss/stale, so identical searches within the TTL cost
        zero external calls no matter how many users ask.
        """
        row = self.db.execute(
            "SELECT payload, updated_at FROM api_cache WHERE kind = ? AND cache_key = ?",
            (kind, key),
        ).fetchone()
        now = _now_ms()

        if row is not None:
            age_ms = now - row["updated_at"]
            if age_ms <= ttl_hours * 3_600_000:
                self._bump_cache_hits(kind, key)
                print(f"[cache hit] {kind}:{key} (age {age_ms // 60000}m)")
                return json.loads(row["payload"]), {
                    "from_cache": True, "stale": False, "age_ms": age_ms,
                }

        try:
            payload = fetch_fn()
        except Exception:
            if row is not None:  # refresh failed — fall back to the stale copy
                self._bump_cache_hits(kind, key)
                print(f"[cache stale-serve] {kind}:{key} (refresh failed)")
                return json.loads(row["payload"]), {
                    "from_cache": True, "stale": True, "age_ms": now - row["updated_at"],
                }
            raise

        self.cache_put(kind, key, payload)
        print(f"[cache miss] {kind}:{key} (fetched + stored)")
        return payload, {"from_cache": False, "stale": False, "age_ms": 0}

    def cache_put(self, kind: str, key: str, payload: Any) -> None:
        now = _now_ms()
        self.db.execute(
            """INSERT INTO api_cache (kind, cache_key, payload, created_at, updated_at, hits)
               VALUES (?, ?, ?, ?, ?, 0)
               ON CONFLICT(kind, cache_key) DO UPDATE SET
                 payload = excluded.payload, updated_at = excluded.updated_at""",
            (kind, key, json.dumps(payload, ensure_ascii=False), now, now),
        )
        self.db.commit()

    def _bump_cache_hits(self, kind: str, key: str) -> None:
        self.db.execute(
            "UPDATE api_cache SET hits = hits + 1 WHERE kind = ? AND cache_key = ?",
            (kind, key),
        )
        self.db.commit()

    def cache_stats(self) -> dict[str, int]:
        """Aggregate cache stats — handy for a demo ('API calls saved')."""
        row = self.db.execute(
            "SELECT COUNT(*) AS entries, COALESCE(SUM(hits), 0) AS hits FROM api_cache"
        ).fetchone()
        return {"entries": row["entries"], "hits_served": row["hits"]}

    # ---------------- Destination suggestions (crowd-sourced) ----------------

    def record_place_search(
        self, destination: str, sample_places: list[dict] | None = None
    ) -> None:
        """Note that someone searched `destination`, so we can suggest it later.

        Bumps a popularity counter and, when POIs are supplied (from a places
        lookup), stores a small preview sample. A count-only bump (from a flight/
        hotel search) keeps whatever sample was stored before.
        """
        name = str(destination or "").strip()
        if not name:
            return
        key = name.lower()
        sample_json = json.dumps(sample_places or [], ensure_ascii=False)
        self.db.execute(
            """INSERT INTO place_searches
                   (destination, display_name, search_count, last_searched, sample_places)
               VALUES (?, ?, 1, ?, ?)
               ON CONFLICT(destination) DO UPDATE SET
                   search_count  = search_count + 1,
                   last_searched = excluded.last_searched,
                   display_name  = excluded.display_name,
                   sample_places = CASE
                       WHEN excluded.sample_places = '[]' THEN place_searches.sample_places
                       ELSE excluded.sample_places
                   END""",
            (key, name, _now_ms(), sample_json),
        )
        self.db.commit()

    def top_place_suggestions(self, limit: int = 6) -> list[dict[str, Any]]:
        """Most-searched destinations across all users, popular first."""
        rows = self.db.execute(
            """SELECT display_name, search_count, sample_places
               FROM place_searches
               ORDER BY search_count DESC, last_searched DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                sample = json.loads(r["sample_places"] or "[]")
            except (json.JSONDecodeError, TypeError):
                sample = []
            out.append({
                "destination": r["display_name"],
                "search_count": r["search_count"],
                "sample_places": sample,
            })
        return out

    def close(self) -> None:
        self.db.close()


# ---------------- History trimming (the part that controls cost) ----------------


def _has_block(msg: dict, block_type: str) -> bool:
    content = msg.get("content")
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == block_type for b in content
    )


def _digest_old_tool_results(messages: list[dict], recent: int) -> list[dict]:
    """Shrink bulky tool_result payloads except in the last `recent` messages."""
    boundary = max(0, len(messages) - recent)
    out: list[dict] = []
    for i, msg in enumerate(messages):
        content = msg.get("content")
        if i >= boundary or not isinstance(content, list):
            out.append(msg)
            continue

        new_content = []
        for block in content:
            if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                new_content.append(block)
                continue
            raw = block.get("content")
            text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            if len(text) <= 200:
                new_content.append(block)
            else:
                new_content.append(
                    {**block, "content": f"[trimmed tool result, {len(text)} chars] {text[:160]}…"}
                )
        out.append({**msg, "content": new_content})
    return out


def trim_history(messages: list[dict], keep_recent: int | None = None) -> list[dict]:
    """Keep history bounded so cost doesn't grow without limit.

    - Keeps the most recent `keep_recent` messages verbatim.
    - Digests bulky tool_result payloads in older messages (tool results
      dominate history size in a tool-heavy agent).
    - Never starts the retained window on a tool_result, because the API rejects
      a tool_use block whose matching tool_result is missing.
    """
    keep = config.KEEP_RECENT_MESSAGES if keep_recent is None else keep_recent

    if len(messages) <= keep:
        return _digest_old_tool_results(messages, keep)

    cut = len(messages) - keep
    while cut < len(messages) and _has_block(messages[cut], "tool_result"):
        cut += 1

    return _digest_old_tool_results(messages[cut:], keep)
