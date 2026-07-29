"""HTTP server — receives Zalo messages, replies via the agent.

Wire the webhook URL into your Zalo Bot Platform / OA settings.
The exact payload shape depends on which Zalo product you use, so
`extract_message` and `send_zalo_reply` are the two adapters you customise.

Run:  uvicorn tripsmart.server:app --host 0.0.0.0 --port 3000
 or:  python -m tripsmart.server
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import queue
import threading
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import config
from .agent import TripSmartAgent

agent = TripSmartAgent()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Run hourly housekeeping: expire old sessions, sweep rate-limit counters."""

    async def loop():
        while True:
            await asyncio.sleep(3600)
            try:
                result = await asyncio.to_thread(agent.housekeeping)
                if result["purged_sessions"]:
                    print(f"[housekeeping] purged {result['purged_sessions']} sessions")
            except Exception as exc:  # noqa: BLE001
                print(f"[housekeeping] {exc!r}")

    task = asyncio.create_task(loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="Zalo TripSmart", version="1.0.0", lifespan=lifespan)

# CORS: the Zalo Mini App runs in a WebView and calls this backend cross-origin
# (dev avoids it with a Vite proxy; production cannot). No cookies are used, so a
# wildcard origin is safe here — tighten `allow_origins` to the Zalo WebView
# origins if you prefer. Override the allow-list via CORS_ALLOW_ORIGINS (CSV).
_cors = os.environ.get("CORS_ALLOW_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",")] if _cors != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def extract_message(body: dict[str, Any]) -> tuple[str | None, str]:
    """Adapter: pull (user_id, text) out of the Zalo webhook payload.

    Adjust the field paths to match the Zalo product you are using.
    """
    sender = body.get("sender") or {}
    user_id = (
        sender.get("id")
        or body.get("user_id")
        or body.get("from_id")
        or body.get("userId")
    )

    message = body.get("message")
    if isinstance(message, dict):
        text = message.get("text", "")
    elif isinstance(message, str):
        text = message
    else:
        text = body.get("text", "")

    return (str(user_id) if user_id else None), str(text or "")


async def send_zalo_reply(user_id: str, reply: str, card: dict | None = None) -> None:
    """Adapter: send a reply back through Zalo.

    Replace with a real call to the Zalo Bot/OA send-message API, e.g.

        async with httpx.AsyncClient() as http:
            await http.post(
                "https://openapi.zalo.me/v3.0/oa/message",
                headers={"access_token": os.environ["ZALO_OA_TOKEN"]},
                json={"recipient": {"user_id": user_id},
                      "message": {"text": reply}},
            )
    """
    print(f"[→ {user_id}] {reply}")
    if card:
        print(f"[→ {user_id}] card: {card}")


async def _process(user_id: str, text: str) -> None:
    """Run the agent off the event loop (the SDK call is blocking) and reply."""
    try:
        result = await asyncio.to_thread(agent.handle_message, user_id, text)
        if result.blocked:
            print(f"[guard] {user_id} blocked: {result.blocked}")
        if result.reply:  # reply is None for silent drops (duplicates)
            await send_zalo_reply(user_id, result.reply, result.card)
    except Exception as exc:  # noqa: BLE001
        print(f"[webhook] agent error: {exc!r}")
        await send_zalo_reply(
            user_id, "Xin lỗi, hệ thống đang gặp sự cố. Bạn thử lại sau nhé!"
        )


@app.get("/webhook/zalo")
async def zalo_webhook_verify() -> dict:
    """Zalo (and most platforms) ping the webhook URL with a GET to validate it
    before saving the config — answer 200 so the console accepts the URL."""
    return {"ok": True}


@app.post("/webhook/zalo")
async def zalo_webhook(request: Request, background: BackgroundTasks) -> dict:
    """Acknowledge fast so Zalo does not retry; process in the background."""
    body = await request.json()
    user_id, text = extract_message(body)
    if not user_id:
        print("[webhook] no user id in payload")
        return {"ok": True}

    background.add_task(_process, user_id, text)
    return {"ok": True}


@app.post("/chat")
async def chat(request: Request) -> dict:
    """Synchronous endpoint for local testing without Zalo."""
    body = await request.json()
    user_id = str(body.get("userId") or "local-test")
    text = str(body.get("message") or "")
    result = await asyncio.to_thread(agent.handle_message, user_id, text)
    return result.as_dict()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    """Like /chat, but streams progress (Server-Sent Events) so the user sees
    'đang tìm khách sạn…' while tools run, instead of a silent wait. Emits
    `status` events during the turn and one final `done` event with the reply +
    card/itinerary/blocked. /chat remains for clients that don't stream."""
    body = await request.json()
    user_id = str(body.get("userId") or "local-test")
    text = str(body.get("message") or "")

    def gen():
        q: "queue.Queue" = queue.Queue()

        def emit(event: str, data: dict) -> None:
            q.put((event, data))

        def run() -> None:
            try:
                result = agent.handle_message(user_id, text, emit=emit)
                q.put(("done", result.as_dict()))
            except Exception as exc:  # noqa: BLE001
                print(f"[chat_stream] agent error: {exc!r}")
                q.put((
                    "done",
                    {
                        "reply": "Xin lỗi, hệ thống đang gặp sự cố. Bạn thử lại sau nhé!",
                        "card": None,
                        "itinerary": None,
                        "blocked": "api_error",
                    },
                ))
            finally:
                q.put(None)  # sentinel

        threading.Thread(target=run, daemon=True).start()
        yield _sse("status", {"text": "🧭 Đang xử lý…"})
        while True:
            item = q.get()
            if item is None:
                break
            event, data = item
            yield _sse(event, data)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/places")
async def places(request: Request) -> dict:
    """Real POIs (with ratings + coordinates) for building an itinerary.

    Used by the Mini App itinerary tab so places come from Google Maps instead
    of being invented by the model. Returns {places: []} on any failure so the
    client can degrade gracefully.
    """
    from .tools import fetch_places

    body = await request.json()
    destination = str(body.get("destination") or "").strip()
    days = body.get("days") or 2
    if not destination:
        return {"error": "no_destination", "places": []}
    try:
        # Pass the shared memory so POIs are cached and the destination is
        # recorded for crowd-sourced suggestions (see GET /suggestions).
        return await asyncio.to_thread(fetch_places, destination, days, agent.memory)
    except Exception as exc:  # noqa: BLE001
        print(f"[places] {exc!r}")
        return {"error": "unavailable", "destination": destination, "places": []}


@app.get("/suggestions")
async def suggestions(limit: int = config.SUGGESTIONS_LIMIT) -> dict:
    """Popular destinations other users have searched (crowd-sourced).

    Powers a 'trending / mọi người đang tìm' surface in the Mini App. Returns an
    empty list (not an error) when nothing has been logged yet."""
    limit = max(1, min(20, int(limit or config.SUGGESTIONS_LIMIT)))
    items = await asyncio.to_thread(agent.memory.top_place_suggestions, limit)
    return {"suggestions": items, "cache": agent.memory.cache_stats()}


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "model": config.MODEL}


if __name__ == "__main__":
    import uvicorn

    print(f"TripSmart listening on :{config.PORT}  (model: {config.MODEL})")
    print("  POST /webhook/zalo   — Zalo webhook")
    print("  POST /chat           — local testing")
    print("  GET  /health         — health check")
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
