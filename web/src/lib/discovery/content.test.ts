import { describe, expect, it } from "vitest";
import {
  AGGREGATE_CLAMP,
  BUCKET_WEIGHTS,
  CARD_LIBRARY_VERSION,
  DECK_CARDS,
  DECK_VERSION,
  getCard,
  LIMITATIONS,
  POLICY_VERSION,
  resolveZip,
} from "./content";
import { BUCKETS } from "./types";

describe("discovery content binding", () => {
  it("exposes non-empty content versions for session stamping", () => {
    expect(CARD_LIBRARY_VERSION).toBeTruthy();
    expect(DECK_VERSION).toBeTruthy();
    expect(POLICY_VERSION).toBeTruthy();
  });

  it("getCard resolves every deck card and misses gracefully", () => {
    for (const card of DECK_CARDS) {
      expect(getCard(card.card_id)).toBe(card);
    }
    expect(getCard("no-such-card")).toBeUndefined();
  });

  it("every deck card's limitation resolves to honest-limits copy", () => {
    // The ledger renders LIMITATIONS[card.limitation_id] as the evidence
    // badge tooltip; an unresolved id would render as empty.
    for (const card of DECK_CARDS) {
      expect(LIMITATIONS[card.limitation_id], card.card_id).toBeTruthy();
    }
  });

  it("policy scoring constants cover every bucket and clamp sanely", () => {
    for (const bucket of BUCKETS) {
      expect(BUCKET_WEIGHTS[bucket], bucket).toBeDefined();
    }
    const [lo, hi] = AGGREGATE_CLAMP;
    expect(lo).toBeLessThan(0);
    expect(hi).toBeGreaterThan(0);
  });

  it("deck cards carry a known evidence status for badge rendering", () => {
    const valid = new Set(["data", "proxy", "reflection_only"]);
    for (const card of DECK_CARDS) {
      expect(valid.has(card.evidence_status), card.card_id).toBe(true);
    }
  });
});

describe("resolveZip (browser-local ZIP3 centroid lookup)", () => {
  it("resolves a known ZIP to its 3-digit-prefix centroid", () => {
    const origin = resolveZip("30060"); // Marietta GA
    expect(origin).not.toBeNull();
    expect(origin?.lat).toBeGreaterThan(30);
    expect(origin?.lat).toBeLessThan(36);
    expect(origin?.lon).toBeLessThan(-80);
    // Same prefix, same centroid — resolution is prefix-coarse by design.
    expect(resolveZip("30099")).toEqual(origin);
  });

  it("tolerates surrounding whitespace", () => {
    expect(resolveZip(" 30060 ")).toEqual(resolveZip("30060"));
  });

  it("returns null for malformed input (UI validation owns the message)", () => {
    expect(resolveZip("1234")).toBeNull(); // too short
    expect(resolveZip("123456")).toBeNull(); // too long
    expect(resolveZip("abcde")).toBeNull();
    expect(resolveZip("")).toBeNull();
  });

  it("returns null for an unknown-but-well-formed prefix (ZIP-no-match state)", () => {
    expect(resolveZip("00000")).toBeNull();
  });
});
