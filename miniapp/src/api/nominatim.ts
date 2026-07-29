import type { GeoPoint, LatLng } from "./ors";

// OpenStreetMap Nominatim geocoder — used as a FALLBACK when OpenRouteService's
// Pelias can't find a POI (common in remote regions like Shangri-La, where ORS
// only knows the city and every stop collapses to one point). Nominatim's OSM
// POI coverage is far richer globally.
//
// Usage policy: max ~1 request/second. Callers must serialise fallback lookups
// (see the store) — do NOT fire these in parallel.

const NOMINATIM = "https://nominatim.openstreetmap.org/search";

// OSM place classes/types that mean "a city/region", not a specific venue — we
// tag these as a coarse "locality" so the caller's existing filter drops them.
const COARSE_TYPES = new Set([
  "country",
  "state",
  "region",
  "province",
  "county",
  "city",
  "town",
  "municipality",
  "administrative",
  "state_district",
  "political",
]);

export interface NominatimOpts {
  /** restrict results to a box around this point (bounded search) */
  center?: LatLng;
  /** half-size of the viewbox in degrees (~0.6 ≈ 60km) */
  radiusDeg?: number;
  /** ISO-2 country code, e.g. "CN" */
  country?: string;
  signal?: AbortSignal;
}

export async function nominatimGeocode(
  text: string,
  opts: NominatimOpts = {},
): Promise<GeoPoint | null> {
  const { center, radiusDeg = 0.6, country, signal } = opts;
  const params = new URLSearchParams({ q: text, format: "json", limit: "1", addressdetails: "0" });
  if (center) {
    // viewbox = left,top,right,bottom (lon/lat)
    params.set(
      "viewbox",
      [center.lng - radiusDeg, center.lat + radiusDeg, center.lng + radiusDeg, center.lat - radiusDeg].join(
        ",",
      ),
    );
    params.set("bounded", "1");
  }
  if (country) params.set("countrycodes", country.toLowerCase());

  try {
    const res = await fetch(`${NOMINATIM}?${params.toString()}`, {
      signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    const arr = (await res.json()) as any[];
    const f = arr?.[0];
    if (!f) return null;
    const coarse =
      f.class === "boundary" ||
      COARSE_TYPES.has(String(f.type)) ||
      COARSE_TYPES.has(String(f.addresstype));
    return {
      lat: parseFloat(f.lat),
      lng: parseFloat(f.lon),
      label: f.display_name,
      // Reuse the caller's COARSE_LAYERS filter by tagging coarse hits "locality".
      layer: coarse ? "locality" : String(f.type || f.class || "venue"),
    };
  } catch (e) {
    if (signal?.aborted) throw e;
    return null;
  }
}
