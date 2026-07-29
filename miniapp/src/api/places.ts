// Real POIs for itineraries, from the backend POST /places (Google Maps via
// SerpApi). This replaces AI-invented place names: names, ratings and
// coordinates all come from Google Maps.

const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export interface PlaceResult {
  name: string;
  category: string;
  rating?: number | null;
  reviews?: number | null;
  lat: number;
  lng: number;
  address?: string | null;
}

export interface PlacesResponse {
  destination: string;
  center?: { lat: number; lng: number } | null;
  places: PlaceResult[];
  error?: string;
  data_source?: string;
}

/** Fetch real attractions + restaurants (with ratings) for a destination. */
export async function fetchPlaces(destination: string, days = 2): Promise<PlacesResponse> {
  const res = await fetch(`${API_BASE}/places`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ destination, days }),
  });
  if (!res.ok) throw new Error(`places HTTP ${res.status}`);
  const data = (await res.json()) as Partial<PlacesResponse>;
  return {
    destination: data.destination ?? destination,
    center: data.center ?? null,
    places: Array.isArray(data.places) ? data.places : [],
    error: data.error,
    data_source: data.data_source,
  };
}
