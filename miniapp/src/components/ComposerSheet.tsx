import { useState } from "react";
import type { Vibe, Destination } from "../types";
import { compactVND, ddmm, isoInDays } from "../utils/format";

interface Props {
  open: boolean;
  vibe?: Vibe | null;
  destination?: Destination | null;
  onClose: () => void;
  onSubmit: (message: string) => void;
}

const BUDGETS = [5_000_000, 8_000_000, 12_000_000, 20_000_000];

/**
 * Turns a vibe + a few light inputs into a natural-language request for the AI.
 * We never call search tools here — the backend agent decides what to do.
 */
export function ComposerSheet({ open, vibe, destination, onClose, onSubmit }: Props) {
  const [dest, setDest] = useState(destination?.name ?? "");
  const [origin, setOrigin] = useState("TP.HCM");
  const [depart, setDepart] = useState(isoInDays(30));
  const [ret, setRet] = useState(isoInDays(33));
  const [pax, setPax] = useState(2);
  const [budget, setBudget] = useState<number | null>(8_000_000);

  if (!open) return null;

  const buildMessage = (): string => {
    const parts: string[] = ["Mình muốn một chuyến đi"];
    if (vibe) parts.push(vibe.phrase);
    if (dest.trim()) parts.push(`tới ${dest.trim()}`);
    parts.push(`khởi hành từ ${origin.trim() || "TP.HCM"}`);
    parts.push(`ngày ${ddmm(depart)} về ${ddmm(ret)}`);
    parts.push(`${pax} người`);
    if (budget) parts.push(`ngân sách khoảng ${compactVND(budget)}`);
    let msg = parts.join(", ") + ".";
    if (!dest.trim()) {
      msg += " Bạn gợi ý giúp mình vài điểm đến hợp vibe này nhé.";
    }
    return msg;
  };

  const submit = () => {
    onSubmit(buildMessage());
    onClose();
  };

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet__grip" />
        <div className="sheet__title">
          {vibe ? (
            <>
              <span className="sheet__emoji">{vibe.emoji}</span> {vibe.label}
            </>
          ) : (
            "Lên kế hoạch chuyến đi"
          )}
        </div>
        <div className="sheet__sub">Điền nhanh vài thông tin, AI sẽ dựng chuyến đi cho bạn.</div>

        <label className="field">
          <span className="field__label">Điểm đến {vibe && !dest ? "(để trống để AI gợi ý)" : ""}</span>
          <input
            className="field__input"
            placeholder="VD: Bangkok, Đà Nẵng, Tokyo…"
            value={dest}
            onChange={(e) => setDest(e.target.value)}
          />
        </label>

        <label className="field">
          <span className="field__label">Khởi hành từ</span>
          <input
            className="field__input"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span className="field__label">Ngày đi</span>
            <input
              type="date"
              className="field__input"
              value={depart}
              onChange={(e) => setDepart(e.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Ngày về</span>
            <input
              type="date"
              className="field__input"
              value={ret}
              onChange={(e) => setRet(e.target.value)}
            />
          </label>
        </div>

        <div className="field">
          <span className="field__label">Số người</span>
          <div className="stepper">
            <button onClick={() => setPax((p) => Math.max(1, p - 1))} aria-label="Giảm">
              −
            </button>
            <span>{pax}</span>
            <button onClick={() => setPax((p) => Math.min(9, p + 1))} aria-label="Tăng">
              +
            </button>
          </div>
        </div>

        <div className="field">
          <span className="field__label">Ngân sách</span>
          <div className="chips">
            {BUDGETS.map((b) => (
              <button
                key={b}
                className={`chip ${budget === b ? "is-active" : ""}`}
                onClick={() => setBudget(b)}
              >
                {compactVND(b)}
              </button>
            ))}
            <button
              className={`chip ${budget === null ? "is-active" : ""}`}
              onClick={() => setBudget(null)}
            >
              Linh hoạt
            </button>
          </div>
        </div>

        <button className="btn btn--primary btn--block" onClick={submit}>
          ✨ Dựng chuyến đi
        </button>
      </div>
    </div>
  );
}
