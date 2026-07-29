import { optimizeOrder, type LatLng } from "../api/ors";
import type { PlaceResult } from "../api/places";

// Curated Points-of-Interest per destination, in a sensible time + geographic
// order. The map/route is drawn by OpenRouteService (see api/ors.ts) from these
// coordinates. Backend is untouched — this is all client-side inspiration data.

export interface Stop {
  id: string;
  name: string;
  category: string; // shown as a badge, e.g. "Cultural", "Shopping", "Restaurant"
  emoji: string;
  gradient: string;
  rating?: number; // curated stops have one; AI-generated stops omit it
  price?: string; // "$$", "$$$"
  time: string; // suggested arrival, e.g. "9:00 AM"
  lat: number;
  lng: number;
}

export interface ItineraryDay {
  day: number;
  hoursLabel: string;
  stops: Stop[];
}

export interface DestinationItinerary {
  id: string;
  name: string;
  center: LatLng;
  days: ItineraryDay[];
  /** true when produced by the AI from a conversation (not curated) */
  generated?: boolean;
  /** true when stops couldn't be geolocated (sparse map data) — show list, no map */
  geoLimited?: boolean;
}

const G = {
  culture: "linear-gradient(135deg,#b06ab3,#4568dc)",
  shopping: "linear-gradient(135deg,#ff9a56,#ff5e62)",
  food: "linear-gradient(135deg,#f6a623,#f76b1c)",
  outdoor: "linear-gradient(135deg,#43a047,#1b5e20)",
  beach: "linear-gradient(135deg,#2193b0,#6dd5ed)",
  landmark: "linear-gradient(135deg,#3a1c71,#d76d77)",
  museum: "linear-gradient(135deg,#11998e,#38ef7d)",
  night: "linear-gradient(135deg,#0b486b,#f56217)",
};

export const ITINERARIES: DestinationItinerary[] = [
  {
    // Toạ độ + rating lấy từ dữ liệu Google Maps thật (backend /places).
    id: "phuquoc",
    name: "Phú Quốc, Việt Nam",
    center: { lat: 10.2172, lng: 103.9564 },
    days: [
      {
        day: 1,
        hoursLabel: "~11 giờ",
        stops: [
          { id: "vinwonders", name: "VinWonders Phú Quốc", category: "Vui chơi", emoji: "🎢", gradient: G.landmark, rating: 4.8, time: "9:00", lat: 10.3407, lng: 103.854 },
          { id: "safari", name: "Vinpearl Safari Phú Quốc", category: "Vui chơi", emoji: "🦒", gradient: G.outdoor, rating: 4.6, time: "13:00", lat: 10.337, lng: 103.8914 },
          { id: "grandworld", name: "Grand World Phú Quốc", category: "Biểu tượng", emoji: "🎡", gradient: G.night, rating: 4.5, time: "16:00", lat: 10.3285, lng: 103.863 },
          { id: "dinhcau", name: "Dinh Cậu", category: "Văn hoá", emoji: "🛕", gradient: G.culture, rating: 4.5, time: "17:45", lat: 10.2172, lng: 103.9564 },
          { id: "chodempq", name: "Chợ đêm Phú Quốc", category: "Mua sắm", emoji: "🦑", gradient: G.shopping, rating: 4.0, time: "19:00", lat: 10.216, lng: 103.9604 },
        ],
      },
      {
        day: 2,
        hoursLabel: "~10 giờ",
        stops: [
          { id: "suoitranh", name: "Khu du lịch Suối Tranh", category: "Ngoài trời", emoji: "💦", gradient: G.outdoor, rating: 4.3, time: "8:30", lat: 10.1767, lng: 104.0125 },
          { id: "sori", name: "SORI Restaurant Phú Quốc", category: "Ẩm thực", emoji: "🍜", gradient: G.food, rating: 4.7, price: "$$", time: "12:00", lat: 10.1994, lng: 103.9643 },
          { id: "captreo", name: "Cáp treo Hòn Thơm", category: "Vui chơi", emoji: "🚠", gradient: G.beach, rating: 4.5, time: "14:00", lat: 10.027, lng: 104.0072 },
          { id: "sunsettown", name: "Thị trấn Hoàng Hôn (Sunset Town)", category: "Biểu tượng", emoji: "🌇", gradient: G.landmark, rating: 4.6, time: "17:00", lat: 10.0269, lng: 104.0079 },
          { id: "cauhon", name: "Cầu Hôn Phú Quốc", category: "Biểu tượng", emoji: "🌉", gradient: G.night, rating: 4.6, time: "18:30", lat: 10.028, lng: 104.0038 },
        ],
      },
    ],
  },
  {
    // Toạ độ + rating lấy từ dữ liệu Google Maps thật (backend /places).
    id: "dalat",
    name: "Đà Lạt, Việt Nam",
    center: { lat: 11.9404, lng: 108.438 },
    days: [
      {
        day: 1,
        hoursLabel: "~10 giờ",
        stops: [
          { id: "lamvien", name: "Quảng trường Lâm Viên", category: "Biểu tượng", emoji: "🌻", gradient: G.landmark, rating: 4.5, time: "8:30", lat: 11.9394, lng: 108.4452 },
          { id: "vuonhoa", name: "Vườn hoa thành phố Đà Lạt", category: "Ngoài trời", emoji: "🌷", gradient: G.outdoor, rating: 4.2, time: "10:00", lat: 11.9502, lng: 108.4498 },
          { id: "chodalat", name: "Chợ Đà Lạt", category: "Mua sắm", emoji: "🧺", gradient: G.shopping, rating: 4.5, time: "11:30", lat: 11.943, lng: 108.4369 },
          { id: "dalatpho", name: "Tiệm ăn Đà Lạt Phố", category: "Ẩm thực", emoji: "🍲", gradient: G.food, rating: 4.7, price: "$$", time: "12:30", lat: 11.9443, lng: 108.4349 },
          { id: "dinhbaodai", name: "Dinh Bảo Đại III", category: "Văn hoá", emoji: "🏛️", gradient: G.culture, rating: 4.2, time: "14:30", lat: 11.93, lng: 108.4296 },
          { id: "linhson", name: "Chùa Linh Sơn", category: "Văn hoá", emoji: "🛕", gradient: G.culture, rating: 4.5, time: "16:30", lat: 11.9502, lng: 108.437 },
        ],
      },
      {
        day: 2,
        hoursLabel: "~10 giờ",
        stops: [
          { id: "thunglung", name: "Thung lũng Tình Yêu", category: "Ngoài trời", emoji: "💐", gradient: G.outdoor, rating: 4.4, time: "8:30", lat: 11.9788, lng: 108.4483 },
          { id: "langbiang", name: "Khu du lịch Lang Biang", category: "Ngoài trời", emoji: "⛰️", gradient: G.outdoor, rating: 4.1, time: "10:30", lat: 12.0193, lng: 108.4244 },
          { id: "chefsdalat", name: "Chef's Dalat", category: "Ẩm thực", emoji: "🍽️", gradient: G.food, rating: 4.7, price: "$$", time: "13:00", lat: 11.9477, lng: 108.4321 },
          { id: "datanla", name: "Thác Datanla", category: "Vui chơi", emoji: "💦", gradient: G.beach, rating: 4.4, time: "15:00", lat: 11.9034, lng: 108.4497 },
          { id: "duonghamdieukhac", name: "Đường Hầm Điêu Khắc", category: "Biểu tượng", emoji: "🗿", gradient: G.museum, rating: 4.2, time: "17:00", lat: 11.8825, lng: 108.4116 },
        ],
      },
    ],
  },
  {
    id: "danang",
    name: "Đà Nẵng, Việt Nam",
    center: { lat: 16.0544, lng: 108.2022 },
    days: [
      {
        day: 1,
        hoursLabel: "~11 giờ",
        stops: [
          { id: "marble", name: "Ngũ Hành Sơn", category: "Ngoài trời", emoji: "⛰️", gradient: G.outdoor, rating: 4.5, time: "8:30", lat: 16.004, lng: 108.2637 },
          { id: "mykhe", name: "Biển Mỹ Khê", category: "Biển", emoji: "🏖️", gradient: G.beach, rating: 4.6, time: "11:00", lat: 16.0596, lng: 108.247 },
          { id: "beman", name: "Hải sản Bé Mặn", category: "Ẩm thực", emoji: "🦐", gradient: G.food, rating: 4.3, price: "$$", time: "12:30", lat: 16.054, lng: 108.243 },
          { id: "sontra", name: "Chùa Linh Ứng - Sơn Trà", category: "Văn hoá", emoji: "🛕", gradient: G.culture, rating: 4.6, time: "15:00", lat: 16.1006, lng: 108.2977 },
          { id: "dragon", name: "Cầu Rồng", category: "Biểu tượng", emoji: "🐉", gradient: G.landmark, rating: 4.5, time: "19:00", lat: 16.0614, lng: 108.227 },
        ],
      },
      {
        day: 2,
        hoursLabel: "~10 giờ",
        stops: [
          { id: "banahills", name: "Bà Nà Hills & Cầu Vàng", category: "Vui chơi", emoji: "🌉", gradient: G.landmark, rating: 4.4, time: "8:00", lat: 15.9977, lng: 107.9967 },
          { id: "hanmarket", name: "Chợ Hàn", category: "Mua sắm", emoji: "🧺", gradient: G.shopping, rating: 4.2, time: "15:00", lat: 16.0678, lng: 108.2244 },
          { id: "hancruise", name: "Du thuyền sông Hàn", category: "Ngoài trời", emoji: "🚤", gradient: G.outdoor, rating: 4.3, time: "18:00", lat: 16.07, lng: 108.227 },
        ],
      },
    ],
  },
];

// Thứ tự chip trong tab Lịch trình; phần tử đầu là fallback mặc định.
const _VN_FIRST = ["danang", "phuquoc", "dalat"];
ITINERARIES.sort((a, b) => _VN_FIRST.indexOf(a.id) - _VN_FIRST.indexOf(b.id));

export function findItinerary(idOrName: string): DestinationItinerary | undefined {
  const q = idOrName.toLowerCase();
  return ITINERARIES.find(
    (it) => it.id === q || it.name.toLowerCase().includes(q) || q.includes(it.id),
  );
}

const CATEGORY_STYLE: Record<string, { emoji: string; gradient: string }> = {
  "Văn hoá": { emoji: "⛩️", gradient: G.culture },
  "Ẩm thực": { emoji: "🍜", gradient: G.food },
  "Mua sắm": { emoji: "🛍️", gradient: G.shopping },
  "Ngoài trời": { emoji: "🌳", gradient: G.outdoor },
  Biển: { emoji: "🏖️", gradient: G.beach },
  "Biểu tượng": { emoji: "📍", gradient: G.landmark },
  "Bảo tàng": { emoji: "🎨", gradient: G.museum },
  "Về đêm": { emoji: "🌃", gradient: G.night },
  "Vui chơi": { emoji: "🎡", gradient: G.landmark },
};

export function styleForCategory(cat: string): { emoji: string; gradient: string } {
  return CATEGORY_STYLE[cat.trim()] ?? { emoji: "📍", gradient: G.landmark };
}

function slug(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[đĐ]/g, "d")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

/** Build a DestinationItinerary from AI-parsed + geocoded rows. */
export function buildGeneratedItinerary(
  name: string,
  center: LatLng | null,
  rows: { day: number; time: string; name: string; category: string; lat: number; lng: number; rating?: number }[],
): DestinationItinerary {
  const dayNums = [...new Set(rows.map((r) => r.day))].sort((a, b) => a - b);
  const days: ItineraryDay[] = dayNums.map((dn) => {
    const dayRows = rows.filter((r) => r.day === dn);

    // Reorder the day's stops by nearest-neighbour so the route doesn't zigzag,
    // then reassign the visit times in ascending order so the schedule still
    // reads chronologically (08:00 → … regardless of the AI's original order).
    const order = optimizeOrder(dayRows.map((r) => ({ lat: r.lat, lng: r.lng })));
    const ordered = order.map((i) => dayRows[i]);
    const times = dayRows.map((r) => r.time).sort();

    const stops: Stop[] = ordered.map((r, i) => {
      const st = styleForCategory(r.category);
      return {
        id: `ai-${dn}-${i}-${slug(r.name)}`,
        name: r.name,
        category: r.category,
        emoji: st.emoji,
        gradient: st.gradient,
        rating: r.rating,
        time: times[i] ?? r.time,
        lat: r.lat,
        lng: r.lng,
      };
    });
    return { day: dn, hoursLabel: `${stops.length} điểm`, stops };
  });

  const c =
    center ??
    (rows.length
      ? {
          lat: rows.reduce((a, r) => a + r.lat, 0) / rows.length,
          lng: rows.reduce((a, r) => a + r.lng, 0) / rows.length,
        }
      : { lat: 0, lng: 0 });

  return { id: `ai-${slug(name)}`, name, center: c, days, generated: true };
}

/** Build a DestinationItinerary from REAL Google Maps places (with ratings).
 * Splits the places across `days`, then reuses buildGeneratedItinerary to
 * optimise the route order and assign chronological visit times. */
export function buildItineraryFromPlaces(
  name: string,
  center: LatLng | null,
  places: PlaceResult[],
  days: number,
): DestinationItinerary {
  const d = Math.max(1, days);
  const perDay = Math.max(1, Math.min(5, Math.ceil(places.length / d)));
  const TIMES = ["08:00", "10:00", "12:30", "14:30", "16:30", "19:00"];
  const rows = places.map((p, i) => ({
    day: Math.min(d, Math.floor(i / perDay) + 1),
    time: TIMES[i % perDay] ?? "20:00",
    name: p.name,
    category: p.category || "Biểu tượng",
    lat: p.lat,
    lng: p.lng,
    rating: typeof p.rating === "number" ? p.rating : undefined,
  }));
  return buildGeneratedItinerary(name, center, rows);
}
