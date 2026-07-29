import { Fragment, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useApp } from "../store/AppContext";
import { TripCard } from "../components/TripCard";
import type { ChatMessage, ItineraryPayload } from "../types";
import { extractUrls, isCheckoutUrl, shortUrl } from "../utils/links";
import { openExternal } from "../utils/zalo";

const FOLLOWUPS = ["Xem lựa chọn khác", "Rẻ hơn nữa được không?", "Đổi sang ngày khác", "Cần visa không?"];

export function ChatPage() {
  const { messages, send, sending, clearChat, showItinerary } = useApp();
  const [text, setText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const submit = () => {
    const t = text.trim();
    if (!t || sending) return;
    setText("");
    void send(t);
  };

  const empty = messages.length === 0;

  return (
    <div className="page chat">
      <header className="chat__bar">
        <div className="chat__id">
          <span className="chat__avatar">🧭</span>
          <div>
            <div className="chat__name">Trợ lý Odysseus</div>
            <div className="chat__status">{sending ? "đang soạn…" : "trực tuyến"}</div>
          </div>
        </div>
        {!empty && (
          <button className="chat__clear" onClick={clearChat} aria-label="Xoá hội thoại">
            Xoá
          </button>
        )}
      </header>

      <div className="chat__scroll" ref={scrollRef}>
        {empty && <EmptyState onPick={(t) => void send(t)} />}
        {messages.map((m) => (
          <Bubble
            key={m.id}
            m={m}
            onBook={() => void send("Đặt lựa chọn này giúp mình nhé.")}
            onOpenItinerary={showItinerary}
          />
        ))}

        {!empty && !sending && lastIsAssistant(messages) && (
          <div className="followups">
            {FOLLOWUPS.map((f) => (
              <button key={f} className="chip chip--soft" onClick={() => void send(f)}>
                {f}
              </button>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer-bar">
        <input
          className="composer-bar__input"
          placeholder="Nhắn cho Odysseus…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          enterKeyHint="send"
        />
        <button className="composer-bar__send" onClick={submit} disabled={!text.trim() || sending}>
          ➤
        </button>
      </div>
    </div>
  );
}

function Bubble({
  m,
  onBook,
  onOpenItinerary,
}: {
  m: ChatMessage;
  onBook: () => void;
  onOpenItinerary: (p: ItineraryPayload) => void;
}) {
  if (m.role === "user") {
    return (
      <div className="row row--user">
        <div className="bubble bubble--user">{m.text}</div>
      </div>
    );
  }

  // The checkout URL only reaches us inside the reply text (see utils/links.ts).
  const urls = m.pending ? [] : extractUrls(m.text);
  const checkout = urls.find(isCheckoutUrl);

  return (
    <div className="row row--bot">
      <div className="bubble bubble--bot">
        {m.pending ? (
          m.statusText ? (
            <div className="bubble__status">
              <TypingDots />
              <span className="bubble__status-text">{m.statusText}</span>
            </div>
          ) : (
            <TypingDots />
          )
        ) : (
          <>
            {m.text && (
              <div className="bubble__text">
                <Linkified text={m.text} />
              </div>
            )}
            {checkout && (
              <button className="bubble__checkout" onClick={() => void openExternal(checkout)}>
                🔒 Mở trang thanh toán
              </button>
            )}
            {m.itinerary && (m.itinerary.places?.length ?? 0) >= 2 && (
              <button
                className="bubble__checkout"
                onClick={() => onOpenItinerary(m.itinerary!)}
              >
                🗺️ Xem lịch trình trên bản đồ
              </button>
            )}
            {m.blocked && isNotice(m.blocked) && (
              <div className="bubble__notice">{noticeText(m.blocked)}</div>
            )}
          </>
        )}
      </div>
      {m.card && (
        <div className="row__card">
          <TripCard card={m.card} onBook={onBook} />
        </div>
      )}
    </div>
  );
}

/** Render text with any http(s) URLs turned into tappable links. */
function Linkified({ text }: { text: string }) {
  const re = /\bhttps?:\/\/[^\s<>()]+/gi;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  for (const match of text.matchAll(re)) {
    const raw = match[0];
    const url = raw.replace(/[.,;:!?)\]]+$/, "");
    const start = match.index ?? 0;
    if (start > lastIndex) nodes.push(<Fragment key={key++}>{text.slice(lastIndex, start)}</Fragment>);
    nodes.push(
      <a
        key={key++}
        className="inline-link"
        onClick={(e) => {
          e.preventDefault();
          void openExternal(url);
        }}
      >
        {shortUrl(url)}
      </a>,
    );
    lastIndex = start + url.length;
  }
  if (lastIndex < text.length) nodes.push(<Fragment key={key++}>{text.slice(lastIndex)}</Fragment>);
  return <>{nodes}</>;
}

function EmptyState({ onPick }: { onPick: (t: string) => void }) {
  const starters = [
    "Đi Bangkok cuối tháng 8, 2 người, 8 triệu",
    "Gợi ý điểm đến biển trong nước dịp lễ",
    "Đi Nhật tự túc cần chuẩn bị gì?",
  ];
  return (
    <div className="empty">
      <div className="empty__logo">🧭</div>
      <div className="empty__title">Xin chào 👋</div>
      <div className="empty__sub">
        Mình là trợ lý du lịch của Odysseus. Hỏi mình bất cứ điều gì về chuyến đi của bạn.
      </div>
      <div className="empty__starters">
        {starters.map((s) => (
          <button key={s} className="starter" onClick={() => onPick(s)}>
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="typing">
      <span />
      <span />
      <span />
    </div>
  );
}

function lastIsAssistant(msgs: ChatMessage[]): boolean {
  const last = msgs[msgs.length - 1];
  return !!last && last.role === "assistant" && !last.pending;
}

// The reply text already carries a user-facing message for these; we add a small
// contextual hint so the state isn't silent.
function isNotice(blocked: string): boolean {
  // client_error bubbles already carry the full message as their text, so we
  // don't add a second (and possibly contradictory) notice line for them.
  return ["rate_limited", "cooldown", "too_long", "api_error", "truncated"].includes(blocked);
}
function noticeText(blocked: string): string {
  switch (blocked) {
    case "rate_limited":
    case "cooldown":
      return "Bạn đang gửi hơi nhanh — chờ một chút nhé.";
    case "too_long":
      return "Tin nhắn hơi dài, bạn rút gọn giúp mình.";
    case "truncated":
      return "Câu trả lời hơi dài nên bị cắt — hỏi lại ngắn gọn hơn nhé.";
    case "api_error":
      return "Hệ thống đang bận. Thử lại sau giây lát.";
    case "client_error":
      return "Không kết nối được máy chủ.";
    default:
      return "";
  }
}
