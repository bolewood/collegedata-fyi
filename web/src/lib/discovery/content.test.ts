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
