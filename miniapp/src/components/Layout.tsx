import { AppProvider, useApp } from "../store/AppContext";
import type { Tab } from "../store/AppContext";
import { DiscoverPage } from "../pages/DiscoverPage";
import { ChatPage } from "../pages/ChatPage";
import { ItineraryPage } from "../pages/ItineraryPage";
import { TripsPage } from "../pages/TripsPage";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "discover", label: "Khám phá", icon: "🧭" },
  { id: "chat", label: "Trợ lý AI", icon: "💬" },
  { id: "itinerary", label: "Lịch trình", icon: "🗺️" },
  { id: "trips", label: "Chuyến đi", icon: "🎫" },
];

function Shell() {
  const { tab, setTab, ready } = useApp();

  if (!ready) {
    return (
      <div className="boot">
        <div className="boot__logo">🧭</div>
        <div className="boot__name">Odysseus</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <main className="app-main">
        {tab === "discover" && <DiscoverPage />}
        {tab === "chat" && <ChatPage />}
        {tab === "itinerary" && <ItineraryPage />}
        {tab === "trips" && <TripsPage />}
      </main>

      <nav className="tabbar">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tabbar__item ${tab === t.id ? "is-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className="tabbar__icon">{t.icon}</span>
            <span className="tabbar__label">{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}

export function AppRoot() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
