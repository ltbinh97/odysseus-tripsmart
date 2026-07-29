import { Fragment, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useApp } from "../store/AppContext";
import { TripCard } from "../components/TripCard";
import type { ChatMessage, ItineraryPayload } from "../types";
import { extractUrls, isCheckoutUrl, shortUrl } from "../utils/links";
import { openExternal } from "../utils/zalo";

interface Followup {
  label: string;
  msg: string;
}

// Foreign-travel hints: the visa chip only appears when the conversation looks
// international — for "đi Tây Ninh" it was pure noise. Only unambiguous phrases:
// short words like "hàn"/"mỹ"/"úc" match inside Vietnamese words ("nhà hàng"!),
// so they appear only anchored ("đi hàn", "hàn quốc").
const FOREIGN_HINTS =
  /visa|hộ chiếu|passport|nước ngoài|quốc tế|nhật bản|hàn quốc|thái lan|bangkok|singapore|trung quốc|đài loan|tokyo|seoul|osaka|bali|malaysia|dubai|châu âu|paris|london|new york|hoa kỳ|đi nhật|đi hàn|đi mỹ|đi úc|đi thái|đi sing|đi trung/i;
const PRICE_HINTS = /vé máy bay|khách sạn|triệu|vnd|₫|giá vé|giá phòng|khứ hồi/i;
const DATE_HINTS = /ngày \d|\d{1,2}\/\d{1,2}|check-?in|khởi hành/i;

/** Context-aware follow-up chips for the latest assistant reply. The itinerary
 * chip leads because it saves the most typing ("muốn mình lên lịch trình
 * không?" → one tap instead of composing a sentence). */
function buildFollowups(msgs: ChatMessage[]): Followup[] {
  const last = msgs[msgs.length - 1];
  if (!last || last.role !== "assistant" || last.pending) return [];
  const lastUser = [...msgs].reverse().find((m) => m.role === "user")?.text ?? "";
  const ctx = `${lastUser}\n${last.text ?? ""}`;

  const out: Followup[] = [];
  // Already built an itinerary in this bubble -> the map button covers it.
  if (!last.itinerary) {
    out.push({
      label: "🗺️ Lên lịch trình chi tiết",
      msg: "Lên lịch trình chi tiết cho chuyến này giúp mình nhé.",
    });
  }
  if (PRICE_HINTS.test(ctx)) {
    out.push({ label: "Xem lựa chọn khác", msg: "Xem lựa chọn khác" });
    out.push({ label: "Rẻ hơn nữa được không?", msg: "Rẻ hơn nữa được không?" });
  }
  if (DATE_HINTS.test(ctx)) {
    out.push({ label: "Đổi sang ngày khác", msg: "Đổi sang ngày khác" });
  }
  if (FOREIGN_HINTS.test(ctx)) {
    out.push({ label: "Cần visa không?", msg: "Cần visa không?" });
  }
  return out.slice(0, 4);
}

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
            {buildFollowups(messages).map((f) => (
              <button key={f.label} className="chip chip--soft" onClick={() => void send(f.msg)}>
                {f.label}
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
                <Linkified text={mdLite(m.text)} />
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

/** Light markdown cleanup for chat bubbles: turn "### Heading" lines into bold
 * lines and drop bare "---" rulers — the model emits both and they rendered as
 * raw symbols. Everything else passes through untouched. */
function mdLite(text: string): string {
  return text
    .split("\n")
    .filter((l) => !/^\s*-{3,}\s*$/.test(l))
    .map((l) => l.replace(/^\s*#{1,4}\s+(.+)$/, "**$1**"))
    .join("\n");
}

/** Render `**bold**` markdown the model emits as real bold text — before this,
 * bubbles showed raw asterisks ("**Vé máy bay:**"). Unpaired ** is left as-is. */
function Bolded({ text, keyBase }: { text: string; keyBase: number }) {
  const parts = text.split("**");
  if (parts.length < 3) return <Fragment key={keyBase}>{text}</Fragment>;
  const nodes: ReactNode[] = [];
  parts.forEach((p, i) => {
    // Odd indexes sit between a ** pair -> bold. A trailing unpaired segment
    // (even count of "**") stays plain because split gives it an even index.
    if (i % 2 === 1 && i < parts.length - (parts.length % 2 === 0 ? 1 : 0)) {
      nodes.push(<strong key={`${keyBase}-${i}`}>{p}</strong>);
    } else {
      nodes.push(<Fragment key={`${keyBase}-${i}`}>{p}</Fragment>);
    }
  });
  return <>{nodes}</>;
}

/** Render text with http(s) URLs as tappable links and **bold** as bold. */
function Linkified({ text }: { text: string }) {
  const re = /\bhttps?:\/\/[^\s<>()]+/gi;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  for (const match of text.matchAll(re)) {
    const raw = match[0];
    const url = raw.replace(/[.,;:!?)\]]+$/, "");
    const start = match.index ?? 0;
    if (start > lastIndex) nodes.push(<Bolded key={key} keyBase={key++} text={text.slice(lastIndex, start)} />);
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
  if (lastIndex < text.length) nodes.push(<Bolded key={key} keyBase={key++} text={text.slice(lastIndex)} />);
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
