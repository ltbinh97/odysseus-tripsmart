import type { ChatResponse } from "../types";

// VITE_API_BASE:
//  - dev:  "/api"  (Vite proxies /api/chat -> BACKEND_ORIGIN/chat, no CORS)
//  - prod: "https://your-domain" (Mini App calls /chat on the whitelisted origin)
const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export class ChatError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ChatError";
  }
}

/**
 * Call the backend's POST /chat. The request/response shape is fixed by the
 * backend (tripsmart/server.py): body {userId, message} -> {reply, card, blocked}.
 */
export async function sendChat(
  userId: string,
  message: string,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId, message }),
      signal,
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new ChatError("Không kết nối được máy chủ. Kiểm tra backend có đang chạy không.");
  }

  if (!res.ok) {
    throw new ChatError(`Máy chủ trả về lỗi (HTTP ${res.status}).`, res.status);
  }

  const data = (await res.json()) as Partial<ChatResponse>;
  return {
    reply: data.reply ?? null,
    card: (data.card as ChatResponse["card"]) ?? null,
    itinerary: (data.itinerary as ChatResponse["itinerary"]) ?? null,
    blocked: data.blocked ?? null,
  };
}

export interface StreamHandlers {
  /** progress text while the agent works ("đang tìm khách sạn…") */
  onStatus?: (text: string) => void;
  /** final result (reply + card/itinerary/blocked) */
  onDone: (res: ChatResponse) => void;
}

/**
 * Stream POST /chat/stream (Server-Sent Events): `status` events during the
 * turn, then one `done` event. Throws (so the caller can fall back to sendChat)
 * on connection error or if the stream ends without a result.
 */
export async function sendChatStream(
  userId: string,
  message: string,
  handlers: StreamHandlers,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId, message }),
    });
  } catch {
    throw new ChatError("Không kết nối được máy chủ (stream).");
  }
  if (!res.ok || !res.body) throw new ChatError(`Máy chủ trả về lỗi (HTTP ${res.status}).`, res.status);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let gotDone = false;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      let parsed: Partial<ChatResponse> & { text?: string };
      try {
        parsed = JSON.parse(data);
      } catch {
        continue;
      }
      if (event === "status") {
        handlers.onStatus?.(String(parsed.text ?? ""));
      } else if (event === "done") {
        gotDone = true;
        handlers.onDone({
          reply: parsed.reply ?? null,
          card: (parsed.card as ChatResponse["card"]) ?? null,
          itinerary: (parsed.itinerary as ChatResponse["itinerary"]) ?? null,
          blocked: parsed.blocked ?? null,
        });
      }
    }
  }
  if (!gotDone) throw new ChatError("Luồng phản hồi kết thúc bất thường.");
}

/** Optional health probe against GET /health. */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
