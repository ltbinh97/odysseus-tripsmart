import type { TripCard as TripCardData } from "../types";
import { formatVND } from "../utils/format";
import { shareText } from "../utils/zalo";
import { useState } from "react";
import { useApp } from "../store/AppContext";
import { daysFromDates } from "../utils/itinerary";

interface Props {
  card: TripCardData;
  /** when present, shows a "Đặt ngay" button that sends this text back to chat */
  onBook?: () => void;
}

function cardToText(c: TripCardData): string {
  const lines = [`✈️ Chuyến đi ${c.destination}`];
  if (c.dates) lines.push(`🗓️ ${c.dates}`);
  if (c.traveler_count) lines.push(`👥 ${c.traveler_count} người`);
  if (c.flight_summary) lines.push(`✈️ ${c.flight_summary}`);
  if (c.hotel_summary) lines.push(`🏨 ${c.hotel_summary}`);
  if (c.total_vnd) lines.push(`💰 Tổng: ${formatVND(c.total_vnd)}`);
  if (c.visa_status) lines.push(`✅ ${c.visa_status}`);
  if (c.tip) lines.push(`💡 ${c.tip}`);
  lines.push("— tạo bởi Odysseus");
  return lines.join("\n");
}

export function TripCard({ card, onBook }: Props) {
  const [shared, setShared] = useState<string>("");
  const { planWith } = useApp();

  const onShare = async () => {
    const r = await shareText(cardToText(card));
    setShared(r === "copied" ? "Đã sao chép" : r === "shared" ? "Đã chia sẻ" : "Không chia sẻ được");
    setTimeout(() => setShared(""), 1800);
  };

  return (
    <div className="tripcard">
      <div className="tripcard__head">
        <div className="tripcard__title">
          <span className="tripcard__pin">📍</span>
          <span>{card.destination}</span>
        </div>
        {card.dates && <div className="tripcard__dates">{card.dates}</div>}
      </div>

      <div className="tripcard__rows">
        {card.traveler_count != null && (
          <Row icon="👥" label="Số người" value={`${card.traveler_count} người`} />
        )}
        {card.flight_summary && <Row icon="✈️" label="Chuyến bay" value={card.flight_summary} />}
        {card.hotel_summary && <Row icon="🏨" label="Khách sạn" value={card.hotel_summary} />}
        {card.visa_status && <Row icon="✅" label="Nhập cảnh" value={card.visa_status} />}
      </div>

      {(card.total_vnd != null || card.budget_vnd != null) && (
        <div className={`tripcard__total ${card.over_budget ? "is-over" : ""}`}>
          <div>
            <div className="tripcard__total-label">Tổng chi phí</div>
            {card.budget_vnd != null && (
              <div className="tripcard__budget">Ngân sách: {formatVND(card.budget_vnd)}</div>
            )}
          </div>
          <div className="tripcard__total-value">{formatVND(card.total_vnd)}</div>
        </div>
      )}

      {card.over_budget && <div className="tripcard__warn">⚠️ Vượt ngân sách</div>}

      {card.tip && <div className="tripcard__tip">💡 {card.tip}</div>}

      <button
        className="tripcard__itin"
        onClick={() =>
          planWith(`Lên lịch trình chi tiết ${daysFromDates(card.dates)} ngày ở ${card.destination}`)
        }
      >
        ✨ Tạo lịch trình chi tiết bằng AI
      </button>

      <div className="tripcard__actions">
        <button className="btn btn--ghost" onClick={onShare}>
          {shared || "Chia sẻ"}
        </button>
        {onBook && (
          <button className="btn btn--primary" onClick={onBook}>
            Đặt ngay
          </button>
        )}
      </div>
    </div>
  );
}

function Row({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="triprow">
      <span className="triprow__icon">{icon}</span>
      <span className="triprow__label">{label}</span>
      <span className="triprow__value">{value}</span>
    </div>
  );
}
