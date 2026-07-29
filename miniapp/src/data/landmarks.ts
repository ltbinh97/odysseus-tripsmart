import type { LatLng } from "../api/ors";

// Curated coordinates for iconic landmarks that public geocoders place wrongly.
// Checked BEFORE geocoding, so these are always correct regardless of how the AI
// names them (VN or English). The caller still rejects an override that is >80km
// from the itinerary centre, so a same-named place elsewhere can't sneak in.
//
// `aliases` MUST be normalised: lowercase, no diacritics, đ -> d.
interface Landmark {
  aliases: string[];
  lat: number;
  lng: number;
}

const LANDMARKS: Landmark[] = [
  // Cầu Vàng / Bàn Tay Vàng (Golden Bridge) — at Bà Nà Hills, ~23km W of Đà Nẵng,
  // NOT in the city centre where geocoders drop "Bàn Tay Vàng"/"Cầu Vàng".
  { aliases: ["ban tay vang", "cau vang", "golden bridge"], lat: 15.9951, lng: 107.9964 },
  {
    aliases: ["ba na hills", "bana hills", "sun world ba na", "nui chua ba na", "ba na hill"],
    lat: 15.9977,
    lng: 107.9967,
  },
];

function norm(s: string): string {
  return s
    .toLowerCase()
    .replace(/đ/g, "d")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Exact coordinates for a known landmark, matched against any of the given names. */
export function landmarkOverride(...names: (string | undefined)[]): LatLng | null {
  for (const raw of names) {
    if (!raw) continue;
    const k = norm(raw);
    for (const lm of LANDMARKS) {
      if (lm.aliases.some((a) => k.includes(a))) return { lat: lm.lat, lng: lm.lng };
    }
  }
  return null;
}
