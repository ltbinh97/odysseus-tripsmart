// Thin, defensive wrappers over zmp-sdk. Every call is guarded so the app also
// runs in a plain browser (outside Zalo) during development.
//
// Detection matters: inside Zalo we must use the native bridges (openWebview,
// openShareSheet) because window.open / clipboard are unreliable there. In a
// plain browser those bridges silently no-op, so we must use the web fallbacks
// instead — hence inZalo() gates which path we take.

import { uid } from "./format";

const UID_KEY = "odysseus_uid";

/** True when running inside the Zalo Mini App webview (not a normal browser). */
export function inZalo(): boolean {
  if (typeof navigator !== "undefined" && /zalo/i.test(navigator.userAgent)) return true;
  const w = window as unknown as Record<string, unknown>;
  return typeof w.ZaloJavaScriptInterface !== "undefined" || typeof w.zbrowser !== "undefined";
}

/** Stable per-user id. Uses the real Zalo user id inside Zalo, else a local id. */
export async function resolveUserId(): Promise<string> {
  const cached = localStorage.getItem(UID_KEY);
  if (cached) return cached;

  let id = "";
  if (inZalo()) {
    try {
      const api = await import("zmp-sdk/apis");
      // getUserID resolves to the Zalo user id when inside Zalo.
      const maybe = await (api as any).getUserID?.({});
      id = typeof maybe === "string" ? maybe : maybe?.userID ?? "";
    } catch {
      /* fall through to a local id */
    }
  }
  if (!id) id = uid("guest-");
  localStorage.setItem(UID_KEY, id);
  return id;
}

/** Share plain text (a trip summary) via the native Zalo share sheet, else copy. */
export async function shareText(text: string): Promise<"shared" | "copied" | "failed"> {
  if (inZalo()) {
    try {
      const api = await import("zmp-sdk/apis");
      if ((api as any).openShareSheet) {
        await (api as any).openShareSheet({ type: "text", data: { text } });
        return "shared";
      }
    } catch {
      /* fall through to clipboard */
    }
  }
  try {
    await navigator.clipboard.writeText(text);
    return "copied";
  } catch {
    return "failed";
  }
}

/** Open an external checkout / partner URL (native webview in Zalo, new tab in browser). */
export async function openExternal(url: string): Promise<void> {
  if (inZalo()) {
    try {
      const api = await import("zmp-sdk/apis");
      if ((api as any).openWebview) {
        await (api as any).openWebview({ url });
        return;
      }
    } catch {
      /* fall through to window.open */
    }
  }
  window.open(url, "_blank", "noopener");
}
