import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { ChatMessage, TripCard, ItineraryPayload } from "../types";
import { sendChat, sendChatStream, ChatError } from "../api/client";
import type { ChatResponse } from "../types";
import { resolveUserId } from "../utils/zalo";
import { uid } from "../utils/format";
import { orsEnabled } from "../api/ors";
import { buildItineraryFromPlaces, type DestinationItinerary } from "../data/itineraries";

export type Tab = "discover" | "chat" | "itinerary" | "trips";

const HISTORY_KEY = "odysseus_history";
const SAVED_KEY = "odysseus_saved_itineraries";
const MAX_PERSISTED = 60;

interface AppState {
  ready: boolean;
  userId: string;
  tab: Tab;
  setTab: (t: Tab) => void;
  messages: ChatMessage[];
  sending: boolean;
  /** send a message to the AI agent (POST /chat) */
  send: (text: string) => Promise<void>;
  /** jump to the chat tab and send in one go (used by Discover) */
  planWith: (text: string) => void;
  clearChat: () => void;
  /** all trip_summary cards the agent has produced, newest first */
  trips: TripCard[];
  /** currently selected destination for the itinerary tab (id or name) */
  itineraryDest: string;
  setItineraryDest: (dest: string) => void;
  /** jump to the itinerary tab for a given destination */
  openItinerary: (dest: string) => void;

  // ---- AI-generated itinerary ----
  /** the itinerary the AI just built from a conversation (overrides curated) */
  activeItinerary: DestinationItinerary | null;
  generating: boolean;
  genError: string | null;
  /** can we geocode / draw a real map? (needs an ORS key) */
  orsReady: boolean;
  /** render an itinerary the agent already built (generate_itinerary tool) */
  showItinerary: (payload: ItineraryPayload) => void;
  clearGenerated: () => void;
  /** true when the itinerary tab is showing the AI-built (activeItinerary) one
   *  rather than a curated destination. Switching between them keeps both. */
  showingGenerated: boolean;
  /** view the AI-built itinerary (does not discard it) */
  viewGenerated: () => void;
  /** view a curated destination without discarding the AI-built itinerary */
  viewCurated: (dest: string) => void;

  // ---- Saved itineraries (tracked in the Trips tab) ----
  savedItineraries: DestinationItinerary[];
  saveItinerary: (it: DestinationItinerary) => void;
  removeItinerary: (id: string) => void;
  openSavedItinerary: (id: string) => void;
  isItinerarySaved: (id: string) => boolean;
}

const Ctx = createContext<AppState | null>(null);

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatMessage[];
    return Array.isArray(parsed) ? parsed.filter((m) => !m.pending) : [];
  } catch {
    return [];
  }
}

function loadSaved(): DestinationItinerary[] {
  try {
    const raw = localStorage.getItem(SAVED_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as DestinationItinerary[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [userId, setUserId] = useState("");
  const [tab, setTab] = useState<Tab>("discover");
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadHistory());
  const [sending, setSending] = useState(false);
  const [itineraryDest, setItineraryDest] = useState<string>("danang");
  const [activeItinerary, setActiveItinerary] = useState<DestinationItinerary | null>(null);
  const [showingGenerated, setShowingGenerated] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [savedItineraries, setSavedItineraries] = useState<DestinationItinerary[]>(() => loadSaved());
  const autoSentRef = useRef(false);

  useEffect(() => {
    resolveUserId().then((id) => {
      setUserId(id);
      setReady(true);
    });
  }, []);

  // Persist history (skip the in-flight pending bubble).
  useEffect(() => {
    try {
      const persist = messages.filter((m) => !m.pending).slice(-MAX_PERSISTED);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(persist));
    } catch {
      /* storage full / disabled — non-fatal */
    }
  }, [messages]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;

      const id = await resolveUserId();
      const userMsg: ChatMessage = { id: uid("u_"), role: "user", text: trimmed, ts: Date.now() };
      const pendingId = uid("a_");
      const pendingMsg: ChatMessage = { id: pendingId, role: "assistant", pending: true, ts: Date.now() };
      setMessages((prev) => [...prev, userMsg, pendingMsg]);
      setSending(true);

      const finalize = (res: ChatResponse) =>
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? {
                  ...m,
                  pending: false,
                  statusText: undefined,
                  text: res.reply ?? undefined,
                  card: res.card,
                  itinerary: res.itinerary,
                  blocked: res.blocked,
                }
              : m,
          ),
        );

      try {
        // Prefer the streaming endpoint (live progress); fall back to /chat.
        await sendChatStream(id, trimmed, {
          onStatus: (text) =>
            setMessages((prev) =>
              prev.map((m) => (m.id === pendingId ? { ...m, statusText: text } : m)),
            ),
          onDone: finalize,
        });
      } catch {
        try {
          finalize(await sendChat(id, trimmed));
        } catch (e) {
          const msg = e instanceof ChatError ? e.message : "Có lỗi xảy ra, bạn thử lại nhé.";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === pendingId
                ? { ...m, pending: false, statusText: undefined, text: msg, blocked: "client_error" }
                : m,
            ),
          );
        }
      } finally {
        setSending(false);
      }
    },
    [sending],
  );

  const planWith = useCallback(
    (text: string) => {
      setTab("chat");
      // let the chat view mount before sending
      setTimeout(() => void send(text), 60);
    },
    [send],
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(HISTORY_KEY);
  }, []);

  const openItinerary = useCallback((dest: string) => {
    // View a curated destination. Keep any AI-built itinerary so the user can
    // switch back to it via its chip.
    setGenError(null);
    setShowingGenerated(false);
    setItineraryDest(dest);
    setTab("itinerary");
  }, []);

  // Toggle between the AI-built itinerary and curated ones WITHOUT discarding
  // the AI-built one (the reported bug: switching to Tokyo lost the generated trip).
  const viewGenerated = useCallback(() => setShowingGenerated(true), []);
  const viewCurated = useCallback((dest: string) => {
    setShowingGenerated(false);
    setItineraryDest(dest);
  }, []);

  const clearGenerated = useCallback(() => {
    setActiveItinerary(null);
    setShowingGenerated(false);
    setGenError(null);
  }, []);

  // Render an itinerary the AGENT built (via the generate_itinerary tool) on the
  // map tab — real places with ratings, no throwaway session or geocoding needed.
  const showItinerary = useCallback((payload: ItineraryPayload) => {
    const places = (payload.places || []).filter(
      (p) => typeof p.lat === "number" && typeof p.lng === "number",
    );
    if (places.length < 2) return;
    const it = buildItineraryFromPlaces(
      payload.destination,
      payload.center ?? null,
      places,
      payload.days ?? 2,
    );
    setGenError(null);
    setGenerating(false);
    setActiveItinerary(it);
    setShowingGenerated(true);
    setTab("itinerary");
  }, []);


  const saveItinerary = useCallback((it: DestinationItinerary) => {
    setSavedItineraries((prev) => {
      const next = [it, ...prev.filter((s) => s.id !== it.id)];
      try {
        localStorage.setItem(SAVED_KEY, JSON.stringify(next));
      } catch {
        /* non-fatal */
      }
      return next;
    });
  }, []);

  const removeItinerary = useCallback((id: string) => {
    setSavedItineraries((prev) => {
      const next = prev.filter((s) => s.id !== id);
      try {
        localStorage.setItem(SAVED_KEY, JSON.stringify(next));
      } catch {
        /* non-fatal */
      }
      return next;
    });
  }, []);

  const openSavedItinerary = useCallback(
    (id: string) => {
      const it = savedItineraries.find((s) => s.id === id);
      if (!it) return;
      setGenError(null);
      setActiveItinerary(it);
      setShowingGenerated(true);
      setTab("itinerary");
    },
    [savedItineraries],
  );

  const isItinerarySaved = useCallback(
    (id: string) => savedItineraries.some((s) => s.id === id),
    [savedItineraries],
  );

  const trips = useMemo(() => {
    const out: TripCard[] = [];
    for (let i = messages.length - 1; i >= 0; i--) {
      const c = messages[i].card;
      if (c) out.push(c);
    }
    return out;
  }, [messages]);

  const value: AppState = {
    ready,
    userId,
    tab,
    setTab,
    messages,
    sending,
    send,
    planWith,
    clearChat,
    trips,
    itineraryDest,
    setItineraryDest,
    openItinerary,
    activeItinerary,
    generating,
    genError,
    orsReady: orsEnabled,
    showItinerary,
    clearGenerated,
    showingGenerated,
    viewGenerated,
    viewCurated,
    savedItineraries,
    saveItinerary,
    removeItinerary,
    openSavedItinerary,
    isItinerarySaved,
  };

  // suppress unused warning for autoSentRef (reserved for future deep-links)
  void autoSentRef;

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
