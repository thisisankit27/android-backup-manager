const KEY = "abm.lastDiscoveryId";

/** Remembers the most recent discovery run so navigating between pages
 * (e.g. via the sidebar, which doesn't carry the ?discovery= query param)
 * doesn't force a fresh device scan to see the same results again. */
export function getLastDiscoveryId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setLastDiscoveryId(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // storage unavailable (private mode, etc.) — falls back to query-param-only behavior
  }
}
