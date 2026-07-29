/** Format a VND amount as e.g. "3.600.000₫". */
export function formatVND(v?: number | null): string {
  if (v == null) return "";
  return v.toLocaleString("vi-VN") + "₫";
}

/** Compact VND, e.g. 3_600_000 -> "3,6 triệu". */
export function compactVND(v?: number | null): string {
  if (v == null) return "";
  if (v >= 1_000_000) {
    const m = v / 1_000_000;
    return (Number.isInteger(m) ? m.toString() : m.toFixed(1).replace(".", ",")) + " triệu";
  }
  if (v >= 1_000) return Math.round(v / 1_000) + "k";
  return String(v);
}

/** A short, stable id without external deps. */
export function uid(prefix = ""): string {
  const rand = Math.random().toString(36).slice(2, 8);
  const t = Date.now().toString(36);
  return `${prefix}${t}${rand}`;
}

/** yyyy-mm-dd for an offset from today, for the composer defaults. */
export function isoInDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

/** dd/mm from an iso date string. */
export function ddmm(iso?: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}/${m}`;
}
