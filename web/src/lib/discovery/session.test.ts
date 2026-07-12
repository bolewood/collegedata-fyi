import { describe, expect, it } from "vitest";
import { DECK_VERSION } from "./content";
import {
  clearSession,
  isCompatible,
  loadSession,
  newSession,
  saveSession,
  SESSION_STORAGE_KEY,
} from "./session";

function memoryStore() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    _map: map,
  };
}

const NOW = new Date("2026-07-12T12:00:00Z");

describe("discovery session", () => {
  it("round-trips through storage", () => {
    const store = memoryStore();
    const session = newSession(NOW);
    session.step = "sort";
    session.card_responses = { "explore-before-major": "essential" };
    saveSession(session, store);
    expect(loadSession(NOW, store)).toEqual(session);
  });

  it("expires after 30 days and clears itself", () => {
    const store = memoryStore();
    saveSession(newSession(NOW), store);
    const later = new Date(NOW.getTime() + 31 * 24 * 60 * 60 * 1000);
    expect(loadSession(later, store)).toBeNull();
    expect(store._map.has(SESSION_STORAGE_KEY)).toBe(false);
  });

  it("discards sessions written by an incompatible content version", () => {
    const store = memoryStore();
    const stale = { ...newSession(NOW), card_deck_version: "opening-v0" };
    saveSession(stale, store);
    expect(loadSession(NOW, store)).toBeNull();
  });

  it("stamps the session with the build's content versions", () => {
    const session = newSession(NOW);
    expect(session.card_deck_version).toBe(DECK_VERSION);
    expect(isCompatible(session, NOW)).toBe(true);
  });

  it("clears corrupted payloads so they are not re-parsed forever", () => {
    const store = memoryStore();
    store.setItem(SESSION_STORAGE_KEY, "{not json");
    expect(loadSession(NOW, store)).toBeNull();
    expect(store._map.has(SESSION_STORAGE_KEY)).toBe(false);
  });

  it.each([
    ["unknown step", { step: "voyage" }],
    ["negative sort_index", { sort_index: -1 }],
    ["non-integer sort_index", { sort_index: 2.5 }],
    ["invalid bucket value", { card_responses: { "explore-before-major": "maybe" } }],
    ["null card_responses", { card_responses: null }],
    ["malformed geography", { geography: { zip: 30060 } }],
  ])(
    "discards version-valid sessions with a corrupt shape: %s",
    (_label, patch) => {
      const store = memoryStore();
      const bad = { ...newSession(NOW), ...(patch as object) };
      store.setItem(SESSION_STORAGE_KEY, JSON.stringify(bad));
      expect(loadSession(NOW, store)).toBeNull();
      expect(store._map.has(SESSION_STORAGE_KEY)).toBe(false);
    },
  );

  it("discards sessions written by an incompatible policy or library version", () => {
    const store = memoryStore();
    saveSession({ ...newSession(NOW), policy_version: "discovery_policy_v0" }, store);
    expect(loadSession(NOW, store)).toBeNull();
    saveSession({ ...newSession(NOW), card_library_version: "v0" }, store);
    expect(loadSession(NOW, store)).toBeNull();
  });

  it("clearSession removes the stored session", () => {
    const store = memoryStore();
    saveSession(newSession(NOW), store);
    clearSession(store);
    expect(store._map.has(SESSION_STORAGE_KEY)).toBe(false);
    expect(loadSession(NOW, store)).toBeNull();
  });

  it("degrades to no-ops when storage APIs throw (quota/private mode)", () => {
    const throwing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("quota");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    expect(() => saveSession(newSession(NOW), throwing)).not.toThrow();
    expect(loadSession(NOW, throwing)).toBeNull();
    expect(() => clearSession(throwing)).not.toThrow();
  });

  it("no-ops without browser storage (SSR / storage unavailable)", () => {
    // Node test env has no window: the default-store path must return null
    // and never throw, so the in-memory session still carries the tab.
    expect(loadSession(NOW)).toBeNull();
    expect(() => saveSession(newSession(NOW))).not.toThrow();
    expect(() => clearSession()).not.toThrow();
  });
});
