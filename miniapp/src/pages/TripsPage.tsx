import { useApp } from "../store/AppContext";
import { TripCard } from "../components/TripCard";

export function TripsPage() {
  const { trips, savedItineraries, openSavedItinerary, removeItinerary, setTab } = useApp();
  const empty = trips.length === 0 && savedItineraries.length === 0;

  return (
    <div className="page trips">
      <header className="page__header">
        <h1>Chuyến đi của bạn</h1>
        <p>Lịch trình và kế hoạch AI đã dựng cho bạn. Chạm để mở lại hoặc chia sẻ.</p>
      </header>

      {empty ? (
        <div className="trips__empty">
          <div className="trips__empty-emoji">🗺️</div>
          <div className="trips__empty-title">Chưa có chuyến đi nào</div>
          <div className="trips__empty-sub">
            Chọn một vibe ở tab Khám phá, hoặc nhắn cho trợ lý AI để bắt đầu.
          </div>
          <button className="btn btn--primary" onClick={() => setTab("discover")}>
            Khám phá ngay
          </button>
        </div>
      ) : (
        <>
          {savedItineraries.length > 0 && (
            <section className="trips__section">
              <h2 className="trips__section-title">🗺️ Lịch trình đã lưu</h2>
              <div className="saved-list">
                {savedItineraries.map((it) => {
                  const stopCount = it.days.reduce((a, d) => a + d.stops.length, 0);
                  const preview = it.days[0]?.stops.slice(0, 3).map((s) => s.name).join(" · ");
                  return (
                    <div key={it.id} className="saved" onClick={() => openSavedItinerary(it.id)}>
                      <div className="saved__body">
                        <div className="saved__name">
                          {it.generated && <span className="saved__ai">✨</span>}
                          {it.name}
                        </div>
                        <div className="saved__meta">
                          {it.days.length} ngày · {stopCount} điểm
                        </div>
                        {preview && <div className="saved__preview">{preview}…</div>}
                      </div>
                      <button
                        className="saved__del"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeItinerary(it.id);
                        }}
                        aria-label="Xoá"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {trips.length > 0 && (
            <section className="trips__section">
              <h2 className="trips__section-title">🎫 Phương án chuyến đi</h2>
              <div className="trips__list">
                {trips.map((c, i) => (
                  <TripCard key={`${c.destination}-${i}`} card={c} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
