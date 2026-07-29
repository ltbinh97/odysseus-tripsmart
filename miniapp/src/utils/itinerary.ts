// Turn a free-form chat into a structured itinerary WITHOUT changing the
// backend: we send a strict-format request to /chat, then parse the lines the
// model returns. Robust to extra prose — we only keep lines that match the
// "day|time|name|category" shape.

export interface RawRow {
  day: number;
  time: string;
  /** Vietnamese display name */
  name: string;
  /** international / English name used for geocoding (falls back to name) */
  query: string;
  category: string;
}

export const VALID_CATEGORIES = [
  "Văn hoá",
  "Ẩm thực",
  "Mua sắm",
  "Ngoài trời",
  "Biển",
  "Biểu tượng",
  "Bảo tàng",
  "Về đêm",
  "Vui chơi",
];

/** The strict-format request we send to the AI agent. */
export function buildItineraryPrompt(dest: string, days: number): string {
  return [
    `Tạo LỊCH TRÌNH MẪU để tham khảo cho ${dest} trong ${days} ngày.`,
    `Đây KHÔNG phải yêu cầu đặt vé/khách sạn và KHÔNG cần hỏi thêm bất kỳ thông tin nào (ngày đi, sở thích, số người).`,
    `Chỉ chọn ĐỊA DANH NỔI TIẾNG, tra được trên Google Maps. TRÁNH tên chung chung như "nhà hàng địa phương", "chợ địa phương", "quán ăn", "quảng trường trung tâm".`,
    `TUYỆT ĐỐI KHÔNG hỏi lại, KHÔNG viết câu mở đầu hay kết luận, KHÔNG markdown.`,
    `Trả lời NGAY. Dòng ĐẦU TIÊN phải bắt đầu bằng "1|". Mỗi điểm một dòng theo đúng định dạng 5 cột:`,
    `NGÀY|GIỜ|TÊN TIẾNG VIỆT|TÊN QUỐC TẾ|LOẠI`,
    `- TÊN QUỐC TẾ: tên tiếng Anh hoặc tên gốc phổ biến để tra bản đồ (vd: Fushimi Inari Taisha, Ganden Sumtseling Monastery, Napa Lake).`,
    `- TÊN TIẾNG VIỆT: tên tiếng Việt dễ hiểu cho người Việt (vd: Đền Fushimi Inari, Tu viện Tùng Tán Lâm, Hồ Napa).`,
    `- GIỜ dạng HH:MM. LOẠI chọn một trong: ${VALID_CATEGORIES.join(", ")}.`,
    `Mỗi ngày 4-5 địa danh nổi tiếng, sắp theo vị trí địa lý và thời gian trong ngày.`,
    `Ví dụ đúng định dạng:`,
    `1|08:00|Đền Fushimi Inari|Fushimi Inari Taisha|Văn hoá`,
    `1|11:00|Chùa Thanh Thuỷ|Kiyomizu-dera Temple|Văn hoá`,
  ].join("\n");
}

/** A one-shot question to recover the destination from the ongoing conversation. */
export const EXTRACT_DEST_PROMPT =
  "Dựa trên cuộc trò chuyện, chuyến đi đang hướng tới thành phố/điểm đến chính nào? " +
  "Chỉ trả lời tên điểm đến, ví dụ 'Tokyo' hoặc 'Bangkok, Thái Lan'. " +
  "KHÔNG viết câu nào khác, KHÔNG hỏi lại.";

function normTime(t: string): string {
  const m = t.match(/(\d{1,2})[:h.\s]?(\d{2})?/);
  if (!m) return t.trim();
  const h = m[1].padStart(2, "0");
  const min = (m[2] ?? "00").padStart(2, "0");
  return `${h}:${min}`;
}

/**
 * Parse the model reply into itinerary rows, ignoring surrounding prose.
 * Preferred format has 5 columns (day|time|VN name|international name|category);
 * we still accept the older 4-column format (no international name).
 */
export function parseItineraryRows(reply: string): RawRow[] {
  const rows: RawRow[] = [];
  for (const raw of reply.split(/\r?\n/)) {
    if (!raw.includes("|")) continue;
    const cleaned = raw.trim().replace(/^[-*•\d.\)\s]*?(?=\d\s*\|)/, "").trim();
    const parts = cleaned.split("|").map((s) => s.trim());
    if (parts.length < 4) continue;
    const day = parseInt(parts[0].replace(/[^\d]/g, ""), 10);
    if (!day || day < 1 || day > 14) continue;

    const name = parts[2];
    if (!name || name.length < 2) continue;

    let query: string;
    let category: string;
    if (parts.length >= 5) {
      query = parts[3] || name;
      category = parts[4] || "Biểu tượng";
    } else {
      query = name;
      category = parts[3] || "Biểu tượng";
    }
    rows.push({ day, time: normTime(parts[1]), name, query, category });
  }
  return rows;
}

/** Rough nights count from a "28/08 - 31/08" style string (clamped 1..4). */
export function daysFromDates(dates?: string): number {
  if (!dates) return 2;
  const nums = dates.match(/(\d{1,2})\/(\d{1,2})/g);
  if (!nums || nums.length < 2) return 2;
  const [d1, m1] = nums[0].split("/").map(Number);
  const [d2, m2] = nums[1].split("/").map(Number);
  const diff = m2 * 31 + d2 - (m1 * 31 + d1);
  return Math.min(4, Math.max(1, diff || 2));
}

/** Clean a destination string the extractor returned (strip quotes/trailing dot). */
export function cleanDestination(s: string): string {
  return s
    .split(/\r?\n/)[0]
    .replace(/^["'“”\s]+|["'“”.\s]+$/g, "")
    .trim();
}

/**
 * Turn an AI place name into a better geocoder query by dropping the leading
 * Vietnamese place-type word, so "Chùa Fushimi Inari" -> "Fushimi Inari" and
 * "Khu phố Gion" -> "Gion" — the proper noun a geocoder actually matches.
 */
export function geocodeQuery(name: string): string {
  return name
    .replace(
      /^(Chùa|Đền|Miếu|Nhà thờ|Tu viện|Công viên quốc gia|Công viên|Vườn quốc gia|Vườn|Bảo tàng|Khu phố cổ|Phố cổ|Khu phố|Thị trấn cổ|Thị trấn|Quảng trường|Làng|Bản|Chợ|Thị trường|Phố|Quán|Nhà hàng|Cầu|Núi|Đèo|Thác|Suối|Động|Hang|Bãi biển|Bãi|Vịnh|Hồ|Cung điện|Lâu đài|Tháp|Ga|Sân vận động|Sân bay|Sân|Trung tâm|Đảo|Đường)\s+/i,
      "",
    )
    .trim();
}

// Geocoders (esp. Nominatim) match a bare proper noun far better than
// "Name + generic type word + country" — e.g. "Ganden Sumtseling" resolves but
// "Ganden Sumtseling Monastery, Shangri-La, China" does not. Strip the type word.
const TYPE_WORDS =
  /\b(National Park|Ancient Town|Old Town|Hot Spring|Scenic Area|Nature Reserve|Monastery|Temple|Shrine|Pagoda|Cathedral|Church|Mosque|Lake|Park|Market|Restaurant|Street|Avenue|Road|Square|Museum|Palace|Castle|Bridge|Mountain|Gorge|Tower|Garden|Valley|River|Waterfall|Grassland|Peak|Cave|Beach|Bay|Island|District)\b/gi;

export function properNoun(name: string): string {
  return name
    .replace(/,.*$/, "")
    .replace(TYPE_WORDS, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/** Ordered, deduped geocoder query candidates (proper-noun form first). */
export function geoCandidates(name: string, city: string): string[] {
  const base = name.replace(/,.*$/, "").trim();
  const pn = properNoun(name);
  const out: string[] = [];
  const add = (s: string) => {
    const t = s.trim();
    if (t && !out.some((o) => o.toLowerCase() === t.toLowerCase())) out.push(t);
  };
  const distinct = pn && pn.toLowerCase() !== base.toLowerCase();
  if (distinct) add(`${pn}, ${city}`);
  add(`${base}, ${city}`);
  if (distinct) add(pn);
  add(base);
  return out;
}

// Common Vietnamese country names -> English + ISO-2, so a geocoder that indexes
// local/English names ("Trung Quốc" -> "China"/CN) resolves the right country.
const VN_COUNTRY: Record<string, { en: string; iso: string }> = {
  "trung quốc": { en: "China", iso: "CN" },
  "trung quoc": { en: "China", iso: "CN" },
  "nhật bản": { en: "Japan", iso: "JP" },
  "nhat ban": { en: "Japan", iso: "JP" },
  "hàn quốc": { en: "South Korea", iso: "KR" },
  "han quoc": { en: "South Korea", iso: "KR" },
  "thái lan": { en: "Thailand", iso: "TH" },
  "thai lan": { en: "Thailand", iso: "TH" },
  "việt nam": { en: "Vietnam", iso: "VN" },
  "viet nam": { en: "Vietnam", iso: "VN" },
  "đài loan": { en: "Taiwan", iso: "TW" },
  "ấn độ": { en: "India", iso: "IN" },
  "in-đô-nê-xi-a": { en: "Indonesia", iso: "ID" },
  indonesia: { en: "Indonesia", iso: "ID" },
  malaysia: { en: "Malaysia", iso: "MY" },
  singapore: { en: "Singapore", iso: "SG" },
  campuchia: { en: "Cambodia", iso: "KH" },
  lào: { en: "Laos", iso: "LA" },
  pháp: { en: "France", iso: "FR" },
  đức: { en: "Germany", iso: "DE" },
  "tây ban nha": { en: "Spain", iso: "ES" },
  "mỹ": { en: "United States", iso: "US" },
  "hoa kỳ": { en: "United States", iso: "US" },
  úc: { en: "Australia", iso: "AU" },
};

/**
 * Normalise an AI destination string for geocoding: swap a Vietnamese country
 * name for its English form and return the ISO-2 code to restrict the search.
 * "Shangri-La, Vân Nam, Trung Quốc" -> { text: "...China", country: "CN" }.
 */
export function normalizeDestination(dest: string): { text: string; country?: string } {
  const low = dest.toLowerCase();
  for (const [vn, info] of Object.entries(VN_COUNTRY)) {
    if (low.includes(vn)) {
      return { text: dest.replace(new RegExp(vn, "i"), info.en), country: info.iso };
    }
  }
  return { text: dest };
}
