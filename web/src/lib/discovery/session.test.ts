import { describe, expect, it } from "vitest";
import { DECK_VERSION } from "./content";
import {
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

  it("survives corrupted storage without throwing", () => {
    const store = memoryStore();
    store.setItem(SESSION_STORAGE_KEY, "{not json");
    expect(loadSession(NOW, store)).toBeNull();
  });
});
