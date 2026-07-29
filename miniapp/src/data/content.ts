import type { Vibe, Destination } from "../types";

// "Pick the vibe, it builds the trip" — each vibe becomes a phrase spliced into
// the natural-language request we hand to the AI agent. The agent (backend) does
// the real planning: search_flights, search_hotels, check_travel_requirements...
export const VIBES: Vibe[] = [
  {
    id: "beach",
    emoji: "🏝️",
    label: "Biển & nghỉ dưỡng",
    gradient: "linear-gradient(135deg,#1fb6c9,#0d7ea6)",
    phrase: "nghỉ dưỡng biển, thư giãn",
  },
  {
    id: "food",
    emoji: "🍜",
    label: "Ẩm thực",
    gradient: "linear-gradient(135deg,#ff9a56,#ff5e62)",
    phrase: "khám phá ẩm thực địa phương",
  },
  {
    id: "culture",
    emoji: "🏛️",
    label: "Văn hoá & lịch sử",
    gradient: "linear-gradient(135deg,#b06ab3,#4568dc)",
    phrase: "tìm hiểu văn hoá, lịch sử",
  },
  {
    id: "nature",
    emoji: "⛰️",
    label: "Thiên nhiên & phiêu lưu",
    gradient: "linear-gradient(135deg,#43a047,#1b5e20)",
    phrase: "phiêu lưu, gần gũi thiên nhiên",
  },
  {
    id: "city",
    emoji: "🌃",
    label: "Thành phố & về đêm",
    gradient: "linear-gradient(135deg,#3a1c71,#d76d77)",
    phrase: "khám phá thành phố sôi động, về đêm",
  },
  {
    id: "family",
    emoji: "👨‍👩‍👧",
    label: "Gia đình & trẻ nhỏ",
    gradient: "linear-gradient(135deg,#f6a623,#f76b1c)",
    phrase: "phù hợp cho gia đình có trẻ nhỏ",
  },
  {
    id: "romantic",
    emoji: "💑",
    label: "Lãng mạn",
    gradient: "linear-gradient(135deg,#ff6a88,#ff99ac)",
    phrase: "lãng mạn cho cặp đôi",
  },
  {
    id: "budget",
    emoji: "💰",
    label: "Tiết kiệm",
    gradient: "linear-gradient(135deg,#11998e,#38ef7d)",
    phrase: "tiết kiệm, hợp lý ngân sách",
  },
];

// Featured destinations. These are just inspiration tiles on the frontend — all
// real facts (price, visa) come from the backend when the user plans a trip.
export const DESTINATIONS: Destination[] = [
  { id: "bangkok", name: "Bangkok", country: "Thái Lan", emoji: "🛕", gradient: "linear-gradient(135deg,#f7971e,#ffd200)", tagline: "Đền chùa, street food, chợ đêm" },
  { id: "tokyo", name: "Tokyo", country: "Nhật Bản", emoji: "🗼", gradient: "linear-gradient(135deg,#ee9ca7,#ffdde1)", tagline: "Hiện đại gặp truyền thống" },
  { id: "seoul", name: "Seoul", country: "Hàn Quốc", emoji: "🏙️", gradient: "linear-gradient(135deg,#4b6cb7,#182848)", tagline: "K-culture, mua sắm, cà phê" },
  { id: "singapore", name: "Singapore", country: "Singapore", emoji: "🌆", gradient: "linear-gradient(135deg,#f857a6,#ff5858)", tagline: "Sạch, an toàn, đa văn hoá" },
  { id: "bali", name: "Bali", country: "Indonesia", emoji: "🌊", gradient: "linear-gradient(135deg,#11998e,#38ef7d)", tagline: "Biển, resort, tâm linh" },
  { id: "danang", name: "Đà Nẵng", country: "Việt Nam", emoji: "🌉", gradient: "linear-gradient(135deg,#2193b0,#6dd5ed)", tagline: "Biển đẹp, Bà Nà, cầu Vàng", domestic: true },
  { id: "dalat", name: "Đà Lạt", country: "Việt Nam", emoji: "🌲", gradient: "linear-gradient(135deg,#5a3f37,#2c7744)", tagline: "Se lạnh, săn mây, cà phê", domestic: true },
  { id: "phuquoc", name: "Phú Quốc", country: "Việt Nam", emoji: "🏖️", gradient: "linear-gradient(135deg,#00b4db,#0083b0)", tagline: "Đảo ngọc, biển xanh", domestic: true },
];

export const QUICK_PROMPTS: string[] = [
  "Gợi ý điểm đến cuối tháng 8, ngân sách 8 triệu",
  "Đi Nhật mùa lá đỏ cần chuẩn bị gì?",
  "Đi Đà Lạt 3 ngày 2 đêm với gia đình",
  "Visa đi Hàn Quốc cho hộ chiếu Việt Nam?",
];
