import { useState } from "react";
import { useApp } from "../store/AppContext";
import { VIBES, DESTINATIONS, QUICK_PROMPTS } from "../data/content";
import type { Vibe, Destination } from "../types";
import { ComposerSheet } from "../components/ComposerSheet";

export function DiscoverPage() {
  const { planWith } = useApp();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [vibe, setVibe] = useState<Vibe | null>(null);
  const [dest, setDest] = useState<Destination | null>(null);

  const openForVibe = (v: Vibe) => {
    setVibe(v);
    setDest(null);
    setSheetOpen(true);
  };
  const openForDest = (d: Destination) => {
    setDest(d);
    setVibe(null);
    setSheetOpen(true);
  };

  return (
    <div className="page discover">
      <header className="hero">
        <div className="hero__brand">
          <span className="hero__logo">🧭</span>
          <span className="hero__name">Odysseus</span>
        </div>
        <h1 className="hero__headline">Chọn vibe, AI dựng chuyến đi.</h1>
        <p className="hero__sub">
          Không cần mở chục tab. Nói cho Odysseus biết bạn muốn gì — phần còn lại để AI lo.
        </p>
        <button className="hero__cta" onClick={() => planWith(pickRandom(QUICK_PROMPTS))}>
          <span>💬</span> Bắt đầu với trợ lý AI
        </button>
      </header>

      <section className="section">
        <div className="section__head">
          <h2>Bạn đang muốn kiểu gì?</h2>
        </div>
        <div className="vibe-grid">
          {VIBES.map((v) => (
            <button
              key={v.id}
              className="vibe"
              style={{ background: v.gradient }}
              onClick={() => openForVibe(v)}
            >
              <span className="vibe__emoji">{v.emoji}</span>
              <span className="vibe__label">{v.label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>Điểm đến gợi ý</h2>
        </div>
        <div className="dest-rail">
          {DESTINATIONS.map((d) => (
            <button key={d.id} className="dest" onClick={() => openForDest(d)}>
              <div className="dest__cover" style={{ background: d.gradient }}>
                <span className="dest__emoji">{d.emoji}</span>
                {d.domestic && <span className="dest__badge">Trong nước</span>}
              </div>
              <div className="dest__name">{d.name}</div>
              <div className="dest__country">{d.country}</div>
              <div className="dest__tag">{d.tagline}</div>
            </button>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>Hỏi nhanh</h2>
        </div>
        <div className="prompt-list">
          {QUICK_PROMPTS.map((p) => (
            <button key={p} className="prompt" onClick={() => planWith(p)}>
              <span className="prompt__spark">✦</span>
              <span>{p}</span>
              <span className="prompt__arrow">→</span>
            </button>
          ))}
        </div>
      </section>

      <div className="foot-note">
        Giá vé, khách sạn và quy định visa đều do AI truy vấn trực tiếp khi bạn lên kế hoạch — không
        phải số liệu dựng sẵn.
      </div>

      <ComposerSheet
        open={sheetOpen}
        vibe={vibe}
        destination={dest}
        onClose={() => setSheetOpen(false)}
        onSubmit={(msg) => planWith(msg)}
      />
    </div>
  );
}

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
