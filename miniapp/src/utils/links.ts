// The backend's initiate_booking tool returns a checkout_url, but /chat only
// surfaces {reply, card, blocked} — the url is not a separate field. We must not
// change the backend, so instead we detect the url inside the assistant's reply
// text (the agent is instructed to hand the user off to checkout) and turn it
// into a real, tappable action.

const URL_RE = /\bhttps?:\/\/[^\s<>()]+/gi;

/** All distinct http(s) URLs found in a piece of text, trailing punctuation trimmed. */
export function extractUrls(text?: string | null): string[] {
  if (!text) return [];
  const matches = text.match(URL_RE) ?? [];
  const cleaned = matches.map((u) => u.replace(/[.,;:!?)\]]+$/, ""));
  return Array.from(new Set(cleaned));
}

/** Heuristic: does this URL look like a booking/checkout/payment hand-off? */
export function isCheckoutUrl(u: string): boolean {
  return /(checkout|thanh.?toan|booking|\/book|payment|\bpay\b|zalo\.me\/s\/)/i.test(u);
}

/** A compact, human-friendly label for a URL, e.g. "zalo.me/s/…/checkout". */
export function shortUrl(u: string): string {
  try {
    const url = new URL(u);
    const path = url.pathname.length > 1 ? url.pathname.replace(/\/$/, "") : "";
    const label = (url.host + path).replace(/^www\./, "");
    return label.length > 36 ? label.slice(0, 34) + "…" : label;
  } catch {
    return u;
  }
}
