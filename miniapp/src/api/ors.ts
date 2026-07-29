// OpenRouteService client — draws the real route between itinerary stops and
// estimates travel time per leg. Works WITHOUT a key too: if VITE_ORS_API_KEY is
// unset (or a request fails), we fall back to straight segments + a speed-based
// time estimate, so the map/itinerary always renders.
//
// Get a free key at https://openrouteservice.org/dev/#/signup and put it in
// miniapp/.env as VITE_ORS_API_KEY=...

const ORS_KEY = (import.meta.env.VITE_ORS_API_KEY as string | undefined)?.trim();
export const orsEnabled = !!ORS_KEY;

const ORS_BASE = "https://api.openrouteservice.org/v2/directions";
const ORS_GEOCODE = "https://api.openrouteservice.org/geocode/search";

export interface LatLng {
  lat: number;
  lng: number;
}

export interface GeoPoint extends LatLng {
  label?: string;
  /** Pelias result layer: "venue" | "street" | "address" | "locality" | ... */
  layer?: string;
  confidence?: number;
}

export interface GeocodeOpts {
  /** bias + (with boundaryKm) restrict results near this point */
  focus?: LatLng;
  /** restrict results to a circle of this radius (km) around `focus` */
  boundaryKm?: number;
  /** Pelias layers filter, e.g. "locality,localadmin,county,region" */
  layers?: string;
  /** ISO-2 country code to restrict to, e.g. "CN" */
  country?: string;
  signal?: AbortSignal;
}

/**
 * Geocode a place name via OpenRouteService (Pelias). `focus` biases toward a
 * city; `boundaryKm`/`country`/`layers` restrict results so a weak text match
 * can't resolve to a same-named place on another continent. Returns the result
 * `layer` so callers can tell a real venue from a coarse city-level fallback.
 */
export async function geocode(text: string, opts: GeocodeOpts = {}): Promise<GeoPoint | null> {
  if (!ORS_KEY) return null;
  const { focus, boundaryKm, layers, country, signal } = opts;
  const params = new URLSearchParams({ api_key: ORS_KEY, text, size: "1" });
  if (focus) {
    params.set("focus.point.lon", String(focus.lng));
    params.set("focus.point.lat", String(focus.lat));
    if (boundaryKm) {
      params.set("boundary.circle.lon", String(focus.lng));
      params.set("boundary.circle.lat", String(focus.lat));
      params.set("boundary.circle.radius", String(boundaryKm));
    }
  }
  if (layers) params.set("layers", layers);
  if (country) params.set("boundary.country", country);
  try {
    const res = await fetch(`${ORS_GEOCODE}?${params.toString()}`, { signal });
    if (!res.ok) return null;
    const gj = await res.json();
    const f = gj?.features?.[0];
    const coords = f?.geometry?.coordinates;
    if (!coords || coords.length < 2) return null;
    return {
      lat: coords[1],
      lng: coords[0],
      label: f?.properties?.label,
      layer: f?.properties?.layer,
      confidence: f?.properties?.confidence,
    };
  } catch (e) {
    if (signal?.aborted) throw e;
    return null;
  }
}

/** Pelias layers that mean "fell back to a city/region", not a real venue. */
export const COARSE_LAYERS = new Set([
  "locality",
  "localadmin",
  "county",
  "region",
  "macrocounty",
  "macroregion",
  "country",
  "continent",
  "dependency",
  "empire",
]);

export type TravelMode = "walk" | "car";

export interface Leg {
  durationMin: number;
  distanceKm: number;
  mode: TravelMode;
  source: "ors" | "estimated";
}

export interface DayRoute {
  /** polyline as [lat, lng] pairs, ready for Leaflet */
  geometry: [number, number][];
  legs: Leg[];
  anyOrs: boolean;
}

const WALK_THRESHOLD_KM = 1.6; // below this we walk, above we take a car
const WALK_KM_PER_MIN = 0.075; // ~4.5 km/h
const CAR_KM_PER_MIN = 0.5; // ~30 km/h city driving

export function haversineKm(a: LatLng, b: LatLng): number {
  const R = 6371;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

function toRad(d: number): number {
  return (d * Math.PI) / 180;
}

function modeFor(distanceKm: number): TravelMode {
  return distanceKm > WALK_THRESHOLD_KM ? "car" : "walk";
}

function estimateLeg(a: LatLng, b: LatLng): { leg: Leg; geometry: [number, number][] } {
  const distanceKm = haversineKm(a, b);
  const mode = modeFor(distanceKm);
  const perMin = mode === "walk" ? WALK_KM_PER_MIN : CAR_KM_PER_MIN;
  return {
    leg: {
      distanceKm,
      mode,
      durationMin: Math.max(1, Math.round(distanceKm / perMin)),
      source: "estimated",
    },
    geometry: [
      [a.lat, a.lng],
      [b.lat, b.lng],
    ],
  };
}

/** Route a single leg through ORS (profile chosen by distance), else estimate. */
async function routeLeg(
  a: LatLng,
  b: LatLng,
  signal?: AbortSignal,
): Promise<{ leg: Leg; geometry: [number, number][] }> {
  const straightKm = haversineKm(a, b);
  const mode = modeFor(straightKm);
  const profile = mode === "walk" ? "foot-walking" : "driving-car";

  if (!ORS_KEY) return estimateLeg(a, b);

  try {
    const res = await fetch(`${ORS_BASE}/${profile}/geojson`, {
      method: "POST",
      headers: { Authorization: ORS_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({
        coordinates: [
          [a.lng, a.lat],
          [b.lng, b.lat],
        ],
      }),
      signal,
    });
    if (!res.ok) return estimateLeg(a, b);
    const gj = await res.json();
    const feat = gj?.features?.[0];
    const coords: [number, number][] = (feat?.geometry?.coordinates ?? []).map(
      ([lng, lat]: [number, number]) => [lat, lng],
    );
    const seg = feat?.properties?.segments?.[0];
    if (!coords.length || !seg) return estimateLeg(a, b);
    return {
      leg: {
        distanceKm: seg.distance / 1000,
        durationMin: Math.max(1, Math.round(seg.duration / 60)),
        mode,
        source: "ors",
      },
      geometry: coords,
    };
  } catch (e) {
    if (signal?.aborted) throw e;
    return estimateLeg(a, b);
  }
}

/** Build the full-day route (all legs) as one polyline + per-leg info. */
export async function buildDayRoute(stops: LatLng[], signal?: AbortSignal): Promise<DayRoute> {
  if (stops.length < 2) {
    return { geometry: stops.map((s) => [s.lat, s.lng] as [number, number]), legs: [], anyOrs: false };
  }
  const pairs: [LatLng, LatLng][] = [];
  for (let i = 0; i < stops.length - 1; i++) pairs.push([stops[i], stops[i + 1]]);

  const results = await Promise.all(pairs.map(([a, b]) => routeLeg(a, b, signal)));

  const geometry: [number, number][] = [];
  const legs: Leg[] = [];
  results.forEach((r, i) => {
    // avoid duplicating the shared vertex between consecutive legs
    const g = i === 0 ? r.geometry : r.geometry.slice(1);
    geometry.push(...g);
    legs.push(r.leg);
  });
  return { geometry, legs, anyOrs: legs.some((l) => l.source === "ors") };
}

/**
 * Nearest-neighbour ordering from the first stop — a light "don't zigzag"
 * optimisation that needs no API. Returns the reordered index list.
 */
export function optimizeOrder(stops: LatLng[]): number[] {
  if (stops.length <= 2) return stops.map((_, i) => i);
  const remaining = stops.map((_, i) => i);
  const order = [remaining.shift() as number];
  while (remaining.length) {
    const last = stops[order[order.length - 1]];
    let bestIdx = 0;
    let bestDist = Infinity;
    remaining.forEach((idx, k) => {
      const d = haversineKm(last, stops[idx]);
      if (d < bestDist) {
        bestDist = d;
        bestIdx = k;
      }
    });
    order.push(remaining.splice(bestIdx, 1)[0]);
  }
  return order;
}
