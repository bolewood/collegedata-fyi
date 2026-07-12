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
    // schema v2 rounds-slice fields
    ["non-array concepts", { concepts: "environment-climate" }],
    ["non-string concept entries", { concepts: [42] }],
    ["non-array reactions", { reactions: {} }],
    ["non-array round_history", { round_history: "corrupt" }],
    ["negative current_round", { current_round: -1 }],
    ["non-integer current_round", { current_round: 0.5 }],
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

describe("rounds-era session guards", () => {
  const store = () => {
    const m = new Map<string, string>();
    return {
      getItem: (k: string) => m.get(k) ?? null,
      setItem: (k: string, v: string) => void m.set(k, v),
      removeItem: (k: string) => void m.delete(k),
    };
  };
  const NOW = new Date("2026-07-12T12:00:00Z");

  it("discards schema v1 sessions (pre-rounds) rather than migrating", () => {
    const s = store();
    const v1 = { ...newSession(NOW), schema_version: 1 };
    s.setItem(SESSION_STORAGE_KEY, JSON.stringify(v1));
    expect(loadSession(NOW, s)).toBeNull();
    expect(s.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it("a bundle bump resets round history but keeps the student's own work", () => {
    const s = store();
    const sess = newSession(NOW);
    sess.bundle_version = "evidence-v0";
    sess.reactions = [{
      school_id: "a", reaction: "research_next", key: null,
      saved_reason_text: "kept", familiarity: "no", round_index: 0,
    }];
    sess.round_history = [
      { round_index: 0, school_ids: ["a", "b"], roles: ["anchor", "exploration"], revisit_ids: [] },
    ];
    sess.current_round = 0;
    s.setItem(SESSION_STORAGE_KEY, JSON.stringify(sess));
    const loaded = loadSession(NOW, s);
    expect(loaded).not.toBeNull();
    expect(loaded!.round_history).toEqual([]);
    expect(loaded!.current_round).toBe(0);
    expect(loaded!.reactions).toHaveLength(1);
    expect(loaded!.bundle_version).not.toBe("evidence-v0");
  });

  it("discards sessions with tampered round-history entries", () => {
    const s = store();
    const sess = newSession(NOW);
    sess.round_history = [
      { round_index: 0, school_ids: [42], roles: [], revisit_ids: [] },
    ] as never;
    s.setItem(SESSION_STORAGE_KEY, JSON.stringify(sess));
    expect(loadSession(NOW, s)).toBeNull();
  });

  it("discards sessions with tampered reaction entries", () => {
    const s = store();
    const sess = newSession(NOW);
    sess.reactions = [
      { school_id: "a", reaction: "rank_this_number_one", key: null,
        saved_reason_text: null, familiarity: null, round_index: 0 },
    ] as never;
    s.setItem(SESSION_STORAGE_KEY, JSON.stringify(sess));
    expect(loadSession(NOW, s)).toBeNull();
  });
});
