import { useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "../store/AppContext";
import { ITINERARIES, findItinerary } from "../data/itineraries";
import type { DayRoute, Leg } from "../api/ors";
import { buildDayRoute } from "../api/ors";
import { ItineraryMap } from "../components/ItineraryMap";

export function ItineraryPage() {
  const {
    itineraryDest,
    activeItinerary,
    showingGenerated,
    viewGenerated,
    viewCurated,
    generating,
    saveItinerary,
    isItinerarySaved,
  } = useApp();

  const dest = useMemo(
    () =>
      showingGenerated && activeItinerary
        ? activeItinerary
        : findItinerary(itineraryDest) ?? ITINERARIES[0],
    [showingGenerated, activeItinerary, itineraryDest],
  );
  const [dayIndex, setDayIndex] = useState(0);
  const day = dest.days[Math.min(dayIndex, dest.days.length - 1)];

  const [route, setRoute] = useState<DayRoute | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const listRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    setDayIndex(0);
  }, [dest.id]);

  useEffect(() => {
    if (generating) return;
    if (dest.geoLimited) {
      setRoute(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    const ctrl = new AbortController();
    setLoading(true);
    setRoute(null);
    buildDayRoute(
      day.stops.map((s) => ({ lat: s.lat, lng: s.lng })),
      ctrl.signal,
    )
      .then((r) => {
        if (!cancelled) {
          setRoute(r);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dest.id, dayIndex, generating]);

  const onSelect = (id: string) => {
    setActiveId(id);
    listRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const totalMin = route?.legs.reduce((a, l) => a + l.durationMin, 0) ?? 0;
  const saved = isItinerarySaved(dest.id);

  if (generating) {
    return (
      <div className="page itinerary">
        <div className="itin-loading">
          <div className="itin-loading__spin">🧭</div>
          <div className="itin-loading__title">AI đang dựng lịch trình…</div>
          <div className="itin-loading__sub">Tìm địa điểm, định vị trên bản đồ và tối ưu lộ trình.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="page itinerary">
      <header className="itin-head">
        <div className="itin-head__row">
          <div>
            <h1 className="itin-title">{dest.name}</h1>
            <div className="itin-prefs">
              {dest.generated ? (
                <span className="pref pref--ai">✨ AI tạo từ hội thoại</span>
              ) : (
                <>
                  <span className="pref">
                    <i className="dot dot--amber" /> Vừa phải
                  </span>
                  <span className="pref">
                    <i className="dot dot--green" /> Cân bằng
                  </span>
                </>
              )}
            </div>
          </div>
          <button
            className={`itin-save ${saved ? "is-saved" : ""}`}
            onClick={() => saveItinerary(dest)}
            disabled={saved}
          >
            {saved ? "✓ Đã lưu" : "💾 Lưu"}
          </button>
        </div>

        <div className="itin-dest-switch">
          {activeItinerary && (
            <button
              className={`chip ${showingGenerated ? "is-active" : ""}`}
              onClick={viewGenerated}
            >
              {activeItinerary.generated ? "✨ " : ""}
              {activeItinerary.name.split(",")[0]}
            </button>
          )}
          {ITINERARIES.map((it) => (
            <button
              key={it.id}
              className={`chip ${!showingGenerated && it.id === dest.id ? "is-active" : ""}`}
              onClick={() => viewCurated(it.id)}
            >
              {it.name.split(",")[0]}
            </button>
          ))}
        </div>
      </header>

      {dest.geoLimited ? (
        <div className="itin-geolimited">
          🗺️ Khu vực này chưa đủ dữ liệu bản đồ để vẽ tuyến đường. Dưới đây là danh sách gợi ý theo
          ngày — bạn vẫn có thể lưu và tham khảo.
        </div>
      ) : (
        <ItineraryMap
          stops={day.stops.map((s) => ({ id: s.id, lat: s.lat, lng: s.lng }))}
          route={route?.geometry ?? []}
          center={dest.center}
          activeId={activeId}
          onSelect={onSelect}
        />
      )}

      <div className="itin-body">
        <div className="itin-daybar">
          <div className="itin-daybar__info">
            <div className="itin-daybar__title">Ngày {day.day}</div>
            <div className="itin-daybar__meta">
              {day.stops.length} điểm
              {dest.geoLimited
                ? ""
                : ` · ${
                    loading
                      ? "đang tính lộ trình…"
                      : `~${Math.round((totalMin / 60) * 10) / 10} giờ di chuyển`
                  }`}
            </div>
          </div>
          <div className="itin-days">
            {dest.days.map((d, i) => (
              <button
                key={d.day}
                className={`day-pill ${i === dayIndex ? "is-active" : ""}`}
                onClick={() => {
                  setDayIndex(i);
                  setActiveId(null);
                }}
              >
                {d.day}
              </button>
            ))}
          </div>
        </div>

        {!dest.geoLimited && (
          <div className="itin-note">
            🧭{" "}
            {route?.anyOrs
              ? "Lộ trình tối ưu bằng OpenRouteService — bạn không phải đi lòng vòng."
              : "Lộ trình tối ưu (ước lượng). Thêm ORS key để vẽ tuyến đường thật."}
          </div>
        )}

        <div className="timeline">
          {day.stops.map((s, i) => (
            <div key={s.id}>
              <div
                className={`stop ${activeId === s.id ? "is-active" : ""}`}
                ref={(el) => (listRefs.current[s.id] = el)}
                onClick={() => onSelect(s.id)}
              >
                <div className="stop__num">{i + 1}</div>
                <div className="stop__thumb" style={{ background: s.gradient }}>
                  <span>{s.emoji}</span>
                </div>
                <div className="stop__body">
                  <div className="stop__name">{s.name}</div>
                  <div className="stop__meta">
                    {s.rating != null && <span className="stop__rating">★ {s.rating.toFixed(1)}</span>}
                    {s.price && <span className="stop__price">{s.price}</span>}
                    <span className="stop__badge">{s.category}</span>
                  </div>
                </div>
                <div className="stop__time">{s.time}</div>
              </div>

              {!dest.geoLimited && i < day.stops.length - 1 && (
                <div className="transit">
                  <span className="transit__line" />
                  <span className="transit__label">{legLabel(route?.legs[i], loading)}</span>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="itin-source">
          {route?.anyOrs
            ? "Tuyến đường & thời gian bởi OpenRouteService · Bản đồ © OpenStreetMap, CARTO"
            : "Bản đồ © OpenStreetMap, CARTO"}
        </div>
      </div>
    </div>
  );
}

function legLabel(leg: Leg | undefined, loading: boolean): string {
  if (loading || !leg) return "· · ·";
  const icon = leg.mode === "walk" ? "🚶" : "🚗";
  const verb = leg.mode === "walk" ? "đi bộ" : "đi xe";
  return `${icon} ${leg.durationMin} phút ${verb}`;
}
