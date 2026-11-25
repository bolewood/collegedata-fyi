import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * False on the server and during the browser's first (hydrating) render, true afterwards.
 *
 * A statically built page has no query string at build time, so its HTML is the page for no query. The browser's first
 * render must produce that same markup or React throws hydration error #418. A component that shows something chosen by
 * the query string (the year picker on /data-quality) reads it only once this is true, so the markup it hydrates against
 * is the markup it was built with, and the chosen view follows in the next render.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(subscribe, () => true, () => false);
}
