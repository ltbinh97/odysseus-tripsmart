"""Central configuration. Every value can be overridden by an environment
variable of the same name."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _bool(key: str, default: bool) -> bool:
    return os.environ.get(key, str(default)).strip().lower() in {"1", "true", "yes"}


# ---- Model ----
# Sonnet 5 is the price/performance workhorse and is capable enough for reliable
# multi-tool orchestration. Use claude-haiku-4-5 for cheap simple sub-tasks, or
# claude-opus-4-8 only if reasoning genuinely needs it.
MODEL = _env("MODEL", "claude-sonnet-5")

# Output cap. Zalo replies are short, and output bills at ~5x the input rate,
# so a low cap is the most direct cost lever.
MAX_TOKENS = _int("MAX_TOKENS", 1000)

# Safety cap on the reasoning loop: how many tool round-trips one user message
# may trigger. Bounds the worst-case cost of a single message. Raised from 6 to
# give multi-step requests (flights + hotels + visa + itinerary + card) headroom.
MAX_TOOL_TURNS = _int("MAX_TOOL_TURNS", 8)

# Reflection pass: after a tool-using turn, run one extra call that verifies the
# reply against the tool results before sending it. Improves correctness on
# complex multi-tool answers at the cost of one extra API call + latency, so it
# is OFF by default — enable for higher accuracy when latency is acceptable.
ENABLE_REFLECTION = _bool("ENABLE_REFLECTION", False)

# ---- Prompt caching ----
# The system prompt + tool schemas are identical on every turn, so caching them
# means repeated input bills at ~0.1x instead of full price.
ENABLE_PROMPT_CACHE = _bool("ENABLE_PROMPT_CACHE", True)

# ---- Memory / history trimming ----
KEEP_RECENT_MESSAGES = _int("KEEP_RECENT_MESSAGES", 8)
SESSION_TTL_HOURS = _int("SESSION_TTL_HOURS", 48)

# ---- Shared result cache (save external API calls; refresh on demand) ----
# Flight and hotel prices are cached the first time any user searches a given
# route / stay, then reused by later users. The first request that arrives
# after the TTL lapses triggers a single refresh — so a route is re-priced at
# most once per TTL no matter how many people ask. Directly cuts SerpApi usage
# (free tier is ~250 searches/month) and latency.
CACHE_TTL_HOURS = _int("CACHE_TTL_HOURS", 24)
# POIs change far more slowly than prices, so their cache can live much longer.
PLACES_TTL_HOURS = _int("PLACES_TTL_HOURS", 24 * 7)
# How many previously-searched destinations to surface as suggestions.
SUGGESTIONS_LIMIT = _int("SUGGESTIONS_LIMIT", 6)

# ---- Abuse prevention (Tier 1) ----
RATE_PER_MINUTE = _int("RATE_PER_MINUTE", 10)
RATE_PER_DAY = _int("RATE_PER_DAY", 100)
MAX_INPUT_CHARS = _int("MAX_INPUT_CHARS", 2000)
DEBOUNCE_MS = _int("DEBOUNCE_MS", 800)

# ---- Input sanity limits (rejected with a helpful message, not a crash) ----
MAX_TRAVELERS = _int("MAX_TRAVELERS", 9)      # typical single-booking airline cap
MAX_NIGHTS = _int("MAX_NIGHTS", 30)           # longer stays need a different product
MAX_ADVANCE_DAYS = _int("MAX_ADVANCE_DAYS", 365)

# ---- API resilience ----
API_MAX_RETRIES = _int("API_MAX_RETRIES", 3)  # transient 429 / 5xx / connection errors
API_RETRY_BASE_MS = _int("API_RETRY_BASE_MS", 500)

# ---- Storage ----
DB_PATH = _env("DB_PATH", str(ROOT / "tripsmart.db"))

# ---- Paths ----
SYSTEM_PROMPT_PATH = ROOT / "system_prompt.md"
TOOLS_SCHEMA_PATH = ROOT / "tools.json"
DATA_DIR = ROOT / "data"

# ---- Server ----
PORT = _int("PORT", 3000)

# ---- Integrations ----
AFFILIATE_TAG = _env("AFFILIATE_TAG", "zahackathon-tripsmart")
