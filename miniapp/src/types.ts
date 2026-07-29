// Mirrors exactly what the backend returns. DO NOT change the backend — these
// types are derived from tripsmart/agent.py (AgentResult.as_dict) and the
// generate_summary_card tool output in tripsmart/tools.py.

/** The `card` object produced by the generate_summary_card tool. */
export interface TripCard {
  type: "trip_summary";
  version: number;
  destination: string;
  dates?: string;
  traveler_count?: number;
  flight_summary?: string;
  hotel_summary?: string;
  total_vnd?: number;
  budget_vnd?: number;
  visa_status?: string;
  tip?: string;
  over_budget?: boolean | null;
}

/** A real place returned by the `generate_itinerary` tool (Google Maps POIs). */
export interface ItineraryPlace {
  name: string;
  category: string;
  rating?: number | null;
  reviews?: number | null;
  lat: number;
  lng: number;
  address?: string | null;
}

/** The `itinerary` object produced by the generate_itinerary tool. */
export interface ItineraryPayload {
  destination: string;
  days?: number;
  center?: { lat: number; lng: number } | null;
  places: ItineraryPlace[];
  data_source?: string;
}

/** Shape of POST /chat -> AgentResult.as_dict(). */
export interface ChatResponse {
  reply: string | null;
  card: TripCard | null;
  itinerary: ItineraryPayload | null;
  blocked: string | null;
}

export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  text?: string;
  card?: TripCard | null;
  /** itinerary payload from the generate_itinerary tool, if the agent built one */
  itinerary?: ItineraryPayload | null;
  /** guard/agent block reason, if any (rate_limit, truncated, api_error, ...) */
  blocked?: string | null;
  /** true while the assistant reply is in flight */
  pending?: boolean;
  /** live progress text shown while pending (from the streaming endpoint) */
  statusText?: string;
  ts: number;
}

export interface Vibe {
  id: string;
  emoji: string;
  label: string;
  /** gradient used for the tile background */
  gradient: string;
  /** phrase spliced into the natural-language request sent to the AI */
  phrase: string;
}

export interface Destination {
  id: string;
  name: string;
  country: string;
  emoji: string;
  gradient: string;
  tagline: string;
  domestic?: boolean;
}
