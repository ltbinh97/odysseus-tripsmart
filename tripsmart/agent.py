"""TripSmart Agent — the core tool-calling loop.

On every user turn:
    1. Guard checks rate limits / input size
    2. Load session history + preferences from memory
    3. Build the Claude API request (cached system prompt + tools + history)
    4. Send it. If Claude emits tool_use, run the tool and feed the result back
    5. Repeat until Claude returns a final text answer
    6. Trim + persist history, log usage, return the reply

Claude NEVER calls an external API directly. It emits a tool_use block telling
THIS code which tool to run with which arguments.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from . import config
from .guard import Guard
from .memory import Memory, merge_summary, split_history
from .tools import TOOL_IMPLS

# ---- Load static config once (this is what prompt caching makes cheap) ----
_raw_prompt = config.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
if "<<<PROMPT-BODY>>>" not in _raw_prompt:
    raise RuntimeError("system_prompt.md is missing the <<<PROMPT-BODY>>> marker")
PROMPT_BODY: str = _raw_prompt.split("<<<PROMPT-BODY>>>", 1)[1].strip()

TOOL_SCHEMAS: list[dict] = json.loads(config.TOOLS_SCHEMA_PATH.read_text(encoding="utf-8"))


@dataclass
class AgentResult:
    reply: str | None
    card: dict | None = None
    itinerary: dict | None = None
    blocked: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "card": self.card,
            "itinerary": self.itinerary,
            "blocked": self.blocked,
        }


class TripSmartAgent:
    def __init__(
        self,
        client: Any | None = None,
        memory: Memory | None = None,
        guard: Guard | None = None,
        model: str | None = None,
    ) -> None:
        if client is None:
            import anthropic  # imported lazily so tests can run without a key

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.client = client
        self.memory = memory or Memory()
        self.guard = guard or Guard()
        self.model = model or config.MODEL

    # ---- Request construction ----

    def _build_system(
        self,
        user_id: str,
        trip_state: dict | None = None,
        summary: str | None = None,
    ) -> list[dict]:
        """System blocks. Block 1 (the big static prompt) carries cache_control so
        repeat turns bill at ~0.1x input. Per-turn context — the durable trip
        state and the rolling summary of trimmed history — goes in a SECOND,
        uncached block: it changes every turn, and putting it inside the cached
        block would bust the prompt cache on each message."""
        body = PROMPT_BODY.replace("{{TODAY}}", date.today().isoformat()).replace(
            "{{USER_PREFERENCES}}", self.memory.render_preferences(user_id)
        )
        block: dict[str, Any] = {"type": "text", "text": body}
        if config.ENABLE_PROMPT_CACHE:
            block["cache_control"] = {"type": "ephemeral"}
        blocks = [block]

        dyn: list[str] = []
        state_text = _render_trip_state(trip_state or {})
        if state_text:
            dyn.append(
                "## Established trip context (auto-tracked from this conversation)\n"
                f"{state_text}\n"
                "These facts are already settled — use them and do NOT re-ask, "
                "unless the user changes them."
            )
        if summary:
            dyn.append(
                "## Earlier in this conversation (condensed)\n"
                f"{summary}\n"
                "(Older messages were trimmed for cost; this digest is what happened.)"
            )
        if dyn:
            blocks.append({"type": "text", "text": "\n\n".join(dyn)})
        return blocks

    def _build_tools(self) -> list[dict]:
        """Tool schemas; cache_control on the last covers the whole array."""
        if not config.ENABLE_PROMPT_CACHE:
            return TOOL_SCHEMAS
        tools = [dict(t) for t in TOOL_SCHEMAS]
        tools[-1]["cache_control"] = {"type": "ephemeral"}
        return tools

    # ---- Tool execution ----

    def _run_tool(self, name: str, args: dict, ctx: dict) -> dict:
        """Execute one tool, never raising — errors become tool results."""
        impl = TOOL_IMPLS.get(name)
        if impl is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return impl(args or {}, ctx)
        except Exception as exc:  # noqa: BLE001 - a tool must never kill the loop
            print(f"[tool error] {name}: {exc!r}")
            return {"error": str(exc), "tool": name}

    def _create_with_retry(self, **kwargs) -> Any:
        """Call the API, retrying transient failures (429, 5xx, connection drops).

        Without this, a single transient 529 overloaded_error kills the user's
        turn — a realistic and highly visible failure during a live demo.
        """
        last_exc: Exception | None = None
        for attempt in range(config.API_MAX_RETRIES):
            try:
                return self.client.messages.create(**kwargs)
            except Exception as exc:  # noqa: BLE001
                if not _is_retryable(exc) or attempt == config.API_MAX_RETRIES - 1:
                    raise
                last_exc = exc
                delay = (config.API_RETRY_BASE_MS * (2**attempt)) / 1000
                print(f"[api retry {attempt + 1}/{config.API_MAX_RETRIES}] {exc!r}; sleeping {delay}s")
                time.sleep(delay)
        raise last_exc  # pragma: no cover - loop always returns or raises

    # ---- The loop ----

    def handle_message(self, user_id: str, user_message: str, emit=None) -> AgentResult:
        """Handle one user message end to end.

        `emit(event, data)` is an optional callback for progress streaming — the
        streaming endpoint passes one to surface "đang tìm khách sạn…" style status
        while tools run. When None (the default, and every unit test), the method
        behaves exactly as before."""
        # ---- 1. Abuse guard ----
        verdict = self.guard.check(user_id, user_message)
        if not verdict.allowed:
            return AgentResult(reply=verdict.reply, blocked=verdict.reason)

        # ---- 2. Load memory ----
        session = self.memory.load_session(user_id)
        # Durable per-session trip facts (destination, dates, pax, budget) —
        # extracted from successful tool calls, so they survive history trimming.
        trip_state: dict = dict(session.get("trip_state") or {})
        summary: str | None = session.get("summary")
        # `observed` is the ground-truth ledger of what external APIs actually
        # returned this turn; generate_summary_card checks its numbers against it
        # so the headline figures can't be fabricated.
        ctx = {
            "user_id": user_id,
            "memory": self.memory,
            "observed": {
                "amounts": set(),
                "flight_totals": set(),
                "hotel_totals": set(),
                "visa_checked": False,
            },
        }

        messages: list[dict] = [*session["messages"], {"role": "user", "content": user_message}]
        card: dict | None = None
        itinerary: dict | None = None
        total_in = total_out = 0
        tools_used = 0
        prev_sig: tuple | None = None  # last turn's tool-call signature (thrash guard)

        # ---- 3-5. Reasoning loop ----
        for _ in range(config.MAX_TOOL_TURNS):
            try:
                response = self._create_with_retry(
                    model=self.model,
                    max_tokens=config.MAX_TOKENS,
                    system=self._build_system(user_id, trip_state, summary),
                    tools=self._build_tools(),
                    messages=messages,
                )
            except Exception as exc:  # noqa: BLE001
                # Persist nothing half-written; tell the user plainly.
                print(f"[api error] {exc!r}")
                self.memory.log_usage(user_id, total_in, total_out)
                return AgentResult(
                    reply=(
                        "Xin lỗi, hệ thống đang quá tải. Bạn thử lại sau một chút nhé!"
                    ),
                    blocked="api_error",
                )

            usage = getattr(response, "usage", None)
            total_in += getattr(usage, "input_tokens", 0) or 0
            total_out += getattr(usage, "output_tokens", 0) or 0

            content = _normalise_content(response.content)
            messages.append({"role": "assistant", "content": content})
            stop_reason = getattr(response, "stop_reason", None)

            # A server-side tool (Anthropic web_search) may pause a long turn.
            # The API has already appended its server_tool_use / result blocks to
            # `content`; re-send to let it resume, don't treat this as the answer.
            if stop_reason == "pause_turn":
                continue

            if stop_reason != "tool_use":
                reply = "\n".join(
                    b.get("text", "") for b in content if b.get("type") == "text"
                ).strip()

                # A response truncated at max_tokens can end with no usable text
                # (e.g. cut off mid tool_use). Never hand the user an empty reply.
                if not reply:
                    reply = (
                        "Xin lỗi, mình chưa trả lời trọn vẹn được. "
                        "Bạn nhắn lại ngắn gọn hơn giúp mình nhé!"
                    )
                    blocked = "empty_reply" if stop_reason != "max_tokens" else "truncated"
                    self._persist(user_id, messages, summary, trip_state)
                    self.memory.log_usage(user_id, total_in, total_out)
                    return AgentResult(reply=reply, card=card, itinerary=itinerary, blocked=blocked)

                # Optional reflection: verify a tool-grounded answer before sending.
                if config.ENABLE_REFLECTION and tools_used:
                    reply = self._reflect(user_id, messages, reply, total_in, total_out) or reply

                self._persist(user_id, messages, summary, trip_state)
                self.memory.log_usage(user_id, total_in, total_out)
                return AgentResult(reply=reply, card=card, itinerary=itinerary)

            # ---- Progress guard: catch a model stuck repeating the same call ----
            sig = _tool_signature(content)
            if sig and sig == prev_sig:
                messages.pop()  # drop the dangling repeated assistant turn (tool_use, no result)
                self._persist(user_id, messages, summary, trip_state)
                self.memory.log_usage(user_id, total_in, total_out)
                return AgentResult(
                    reply=(
                        "Xin lỗi, mình đang bị lặp và chưa hoàn tất được yêu cầu này. "
                        "Bạn thử diễn đạt ngắn gọn hơn giúp mình nhé!"
                    ),
                    card=card,
                    itinerary=itinerary,
                    blocked="no_progress",
                )
            prev_sig = sig

            # Progress streaming: tell the user which (slow) tool is running now.
            if emit:
                for b in content:
                    if b.get("type") == "tool_use":
                        emit("status", {"text": _TOOL_LABELS.get(b.get("name"), "⏳ Đang xử lý…")})

            # Run every requested tool, collect results.
            results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tools_used += 1
                name = block.get("name")
                result = self._run_tool(name, block.get("input", {}), ctx)
                _observe(name, result, ctx["observed"])
                _update_trip_state(name, block.get("input") or {}, result, trip_state)
                if block.get("name") == "generate_summary_card" and result.get("card"):
                    card = result["card"]
                if block.get("name") == "generate_itinerary" and result.get("itinerary"):
                    itinerary = result["itinerary"]
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.get("id"),
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            messages.append({"role": "user", "content": results})

        # Loop cap hit — persist what we have and fail gracefully.
        self._persist(user_id, messages, summary, trip_state)
        self.memory.log_usage(user_id, total_in, total_out)
        return AgentResult(
            reply=(
                "Xin lỗi, mình chưa hoàn tất được yêu cầu này. "
                "Bạn thử diễn đạt ngắn gọn hơn giúp mình nhé!"
            ),
            card=card,
            itinerary=itinerary,
            blocked="max_tool_turns",
        )

    def _persist(
        self,
        user_id: str,
        messages: list[dict],
        summary: str | None,
        trip_state: dict | None = None,
    ) -> None:
        """Trim history AND fold what was cut into the rolling summary, so no
        conversation context is silently lost (it previously was)."""
        kept, dropped = split_history(messages)
        self.memory.save_session(user_id, kept, merge_summary(summary, dropped), trip_state)

    def _reflect(
        self, user_id: str, messages: list[dict], reply: str, total_in: int, total_out: int
    ) -> str | None:
        """One verification pass over a tool-grounded answer.

        Asks the model to re-check its own reply against the tool results already
        in context and return a corrected version if needed. Best-effort: on any
        failure or empty result we keep the original reply. Off unless
        ENABLE_REFLECTION is set (one extra API call).
        """
        check = [
            *messages,
            {
                "role": "user",
                "content": (
                    "Kiểm tra lại câu trả lời vừa rồi CHỈ dựa trên kết quả tool trong "
                    "hội thoại: số liệu có khớp không, có bỏ sót ý người dùng hỏi "
                    "không, có bịa thông tin không? Nếu đã đúng và đủ, in lại y nguyên "
                    "câu trả lời. Nếu sai hoặc thiếu, in lại câu trả lời ĐÃ SỬA. Chỉ in "
                    "nội dung trả lời cuối cùng cho người dùng, không giải thích, không gọi tool."
                ),
            },
        ]
        try:
            resp = self._create_with_retry(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                system=self._build_system(user_id),
                tools=self._build_tools(),
                messages=check,
            )
        except Exception as exc:  # noqa: BLE001 - reflection must never break the turn
            print(f"[reflect] {exc!r}")
            return reply
        content = _normalise_content(resp.content)
        revised = "\n".join(
            b.get("text", "") for b in content if b.get("type") == "text"
        ).strip()
        return revised or reply

    def housekeeping(self) -> dict[str, int]:
        """Periodic maintenance — call from a scheduled task in server.py."""
        purged = self.memory.purge_expired_sessions()
        self.guard.sweep()
        return {"purged_sessions": purged}


_RETRYABLE_MARKERS = (
    "overloaded",
    "rate_limit",
    "rate limit",
    "timeout",
    "timed out",
    "connection",
    "temporarily unavailable",
    "service unavailable",
    "internal server error",
)


def _is_retryable(exc: Exception) -> bool:
    """Transient failures worth retrying: 429, 5xx, and connection problems.

    Checks an explicit status_code when the SDK provides one, and otherwise
    falls back to matching the message, so this also works with mock clients.
    """
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    if isinstance(status, int):
        return status == 429 or status >= 500

    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in _RETRYABLE_MARKERS)


# Friendly Vietnamese labels for progress streaming (see handle_message `emit`).
_TOOL_LABELS = {
    "search_flights": "🔍 Đang tìm chuyến bay…",
    "search_hotels": "🏨 Đang tìm khách sạn…",
    "check_travel_requirements": "🛂 Đang tra cứu quy định visa…",
    "family_travel_checklist": "👨‍👩‍👧 Đang chuẩn bị lưu ý cho gia đình…",
    "generate_itinerary": "🗺️ Đang dựng lịch trình…",
    "suggest_destinations": "✨ Đang xem điểm đến được ưa chuộng…",
    "generate_summary_card": "🧾 Đang tổng hợp chi phí…",
    "initiate_booking": "🔗 Đang tạo liên kết đặt chỗ…",
    "save_user_preference": "💾 Đang ghi nhớ sở thích…",
    "forget_user_preference": "🗑️ Đang cập nhật ghi nhớ…",
}


# Which tool args feed the durable trip state. Extracted from SUCCESSFUL tool
# calls (the model already normalised them there), so tracking costs zero extra
# model calls and can't hallucinate: it only records what searches actually ran.
_TRIP_ARG_MAP: dict[str, tuple[tuple[str, str], ...]] = {
    "search_flights": (
        ("origin_city", "origin"), ("destination", "destination"),
        ("depart_date", "depart_date"), ("return_date", "return_date"),
        ("traveler_count", "pax"), ("budget_vnd", "budget_vnd"),
    ),
    "search_hotels": (
        ("destination", "destination"), ("checkin_date", "depart_date"),
        ("checkout_date", "return_date"), ("guests", "pax"),
        ("budget_vnd", "budget_vnd"),
    ),
    "generate_itinerary": (("destination", "destination"), ("days", "days")),
}

_TRIP_LABELS = {
    "destination": "Destination", "origin": "Origin",
    "depart_date": "Departure", "return_date": "Return",
    "pax": "Travellers", "budget_vnd": "Budget (VND)", "days": "Itinerary days",
}


# Errors that mean the ARGUMENTS were invalid — those settle nothing. Transient
# failures (prices_unavailable, itinerary_unavailable…) keep valid args: the trip
# facts were established even if the live lookup happened to fail.
_ARG_REJECTING_ERRORS = {
    "invalid_date", "date_in_past", "date_too_far", "dates_reversed",
    "stay_too_long", "invalid_count", "too_many_travelers",
    "unsupported_airport", "same_route", "destination_conflict",
    "ambiguous_city", "no_destination",
}


def _update_trip_state(name: str, args: dict, result: Any, state: dict) -> None:
    """Fold a tool call's arguments into the durable trip state (unless the tool
    rejected those arguments as invalid)."""
    if not isinstance(result, dict) or result.get("error") in _ARG_REJECTING_ERRORS:
        return
    for src, dst in _TRIP_ARG_MAP.get(name, ()):
        val = args.get(src)
        if val not in (None, ""):
            state[dst] = val


def _render_trip_state(state: dict) -> str:
    lines = []
    for key in ("destination", "origin", "depart_date", "return_date", "pax", "budget_vnd", "days"):
        val = state.get(key)
        if val not in (None, ""):
            if key == "budget_vnd":
                try:
                    val = f"{int(val):,}"
                except (TypeError, ValueError):
                    pass
            lines.append(f"- {_TRIP_LABELS[key]}: {val}")
    return "\n".join(lines)


def _observe(name: str, result: Any, observed: dict) -> None:
    """Record the real numbers an external-API tool returned, so downstream
    verification (generate_summary_card) can check the model didn't invent them."""
    if not isinstance(result, dict):
        return
    if name in ("search_flights", "search_hotels"):
        bucket = observed["flight_totals"] if name == "search_flights" else observed["hotel_totals"]
        for opt in result.get("options") or []:
            for key in ("price_total", "price_per_person", "price_per_night"):
                val = opt.get(key)
                if isinstance(val, int) and val > 0:
                    observed["amounts"].add(val)
            total = opt.get("price_total")
            if isinstance(total, int) and total > 0:
                bucket.add(total)
    elif name == "check_travel_requirements":
        if result.get("found") is True or result.get("visa_type") or result.get("domestic"):
            observed["visa_checked"] = True


def _tool_signature(content: list[dict]) -> tuple:
    """A stable signature of the tool calls in an assistant turn, so the loop can
    detect a model repeating the exact same call(s) and stop instead of spinning."""
    calls = []
    for block in content:
        if block.get("type") == "tool_use":
            calls.append(
                (block.get("name"), json.dumps(block.get("input", {}), sort_keys=True, ensure_ascii=False))
            )
    return tuple(sorted(calls))


def _normalise_content(content: Any) -> list[dict]:
    """Convert SDK content blocks into plain dicts (also accepts plain dicts,
    which is what the test suite's mock client returns)."""
    out: list[dict] = []
    for block in content or []:
        if isinstance(block, dict):
            out.append(block)
            continue
        # SDK objects expose .model_dump() (pydantic v2)
        dump = getattr(block, "model_dump", None)
        if callable(dump):
            out.append(dump(exclude_none=True))
            continue
        btype = getattr(block, "type", None)
        if btype == "text":
            out.append({"type": "text", "text": getattr(block, "text", "")})
        elif btype == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", {}) or {},
                }
            )
    return out
