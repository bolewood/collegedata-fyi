import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { newSession } from "./session";
import {
  cardStatementForKey,
  composeNextRound,
  renderStoredRound,
  roundExclusions,
} from "./round-session";
import type { DiscoverySessionV1, EvidenceBundle } from "./types";

const bundle: EvidenceBundle = JSON.parse(
  readFileSync(
    join(__dirname, "../../../public/discovery/evidence-v1.json"),
    "utf-8",
  ),
);

const NOW = new Date("2026-07-12T12:00:00Z");

function session(over: Partial<DiscoverySessionV1> = {}): DiscoverySessionV1 {
  return {
    ...newSession(NOW),
    step: "rounds",
    concepts: ["environment-climate"],
    card_responses: { "small-school-known": "essential" },
    ...over,
  };
}

describe("composeNextRound", () => {
  it("produces a full round with fail-closed reasons for every school", () => {
    const round = composeNextRound(session(), bundle);
    expect(round.schools.length).toBeGreaterThanOrEqual(4);
    for (const s of round.schools) {
      expect(s.reasons.length).toBeGreaterThanOrEqual(1);
      for (const r of s.reasons) {
        expect(r.text).toBeTruthy();
        expect(r.limitation).toBeTruthy();
        expect(r.data_year).toBeTruthy();
        expect(r.text).not.toMatch(/\{[a-z_]+\}/); // no unresolved placeholders
      }
    }
    expect(round.zip_unresolved).toBe(false);
  });

  it("is deterministic for identical sessions", () => {
    const a = composeNextRound(session(), bundle);
    const b = composeNextRound(session(), bundle);
    expect(a.schools.map((s) => [s.school.school_id, s.role])).toEqual(
      b.schools.map((s) => [s.school.school_id, s.role]),
    );
  });

  it("respects a hard maximum radius from a resolved ZIP", () => {
    const round = composeNextRound(
      session({
        geography: {
          zip: "59457", // Lewistown MT
          preferred_miles: 100,
          maximum_miles: 250,
          allow_wildcards: false,
        },
      }),
      bundle,
    );
    for (const s of round.schools) {
      expect(s.distance_miles).not.toBeNull();
      expect(s.distance_miles as number).toBeLessThanOrEqual(250 + 1);
      expect(["MT", "WY", "ND", "SD", "ID"]).toContain(s.school.state);
    }
  });

  it("disables ALL distance settings when the ZIP cannot be resolved", () => {
    const round = composeNextRound(
      session({
        geography: {
          zip: "00000",
          preferred_miles: 100,
          maximum_miles: 250,
          allow_wildcards: false,
        },
      }),
      bundle,
    );
    expect(round.zip_unresolved).toBe(true);
    // The hard cap must not be applied against an unknown origin — the pool
    // is nationwide again, visibly flagged.
    expect(round.eligible_candidates).toBeGreaterThan(100);
  });

  it("never repeats saved or rejected schools and cools down shown ones", () => {
    const first = composeNextRound(session(), bundle);
    const ids = first.schools.map((s) => s.school.school_id);
    const s2 = session({
      reactions: [
        {
          school_id: ids[0],
          reaction: "research_next",
          key: null,
          saved_reason_text: first.schools[0].reasons[0].text,
          familiarity: "no",
          round_index: 0,
        },
        {
          school_id: ids[1],
          reaction: "not_for_me",
          key: null,
          saved_reason_text: null,
          familiarity: null,
          round_index: 0,
        },
      ],
      round_history: [
        { round_index: 0, school_ids: ids, roles: [], revisit_ids: [] },
      ],
    });
    const second = composeNextRound(s2, bundle);
    const secondIds = new Set(second.schools.map((s) => s.school.school_id));
    for (const id of ids) {
      expect(secondIds.has(id)).toBe(false); // saved/rejected never, others cooling down
    }
  });

  it("more_like_this reactions shift subsequent rounds and surface in the change note", () => {
    const base = session();
    const first = composeNextRound(base, bundle);
    const s2 = session({
      reactions: [
        {
          school_id: first.schools[0].school.school_id,
          reaction: "more_like_this",
          key: "cost.low_debt",
          saved_reason_text: null,
          familiarity: null,
          round_index: 0,
        },
      ],
      round_history: [
        {
          round_index: 0,
          school_ids: first.schools.map((s) => s.school.school_id),
          roles: [],
          revisit_ids: [],
        },
      ],
    });
    const second = composeNextRound(s2, bundle);
    expect(second.changed_keys).toEqual([
      { key: "cost.low_debt", direction: "seek" },
    ]);
  });
});

describe("renderStoredRound", () => {
  it("re-renders a recorded round identically — even after recording and reacting", () => {
    const base = session();
    const composed = composeNextRound(base, bundle);
    const afterRecord = session({
      current_round: 0,
      round_history: [composed.history_entry],
      reactions: [
        {
          school_id: composed.schools[0].school.school_id,
          reaction: "more_like_this",
          key: composed.schools[0].reasons.find((r) => r.tunable_key)?.tunable_key ?? "cost.low_debt",
          saved_reason_text: null,
          familiarity: null,
          round_index: 0,
        },
      ],
    });
    const rendered = renderStoredRound(afterRecord, bundle, composed.history_entry);
    // Same schools in the same order with the same roles — the round the
    // student is looking at never shifts under them.
    expect(rendered.schools.map((s) => [s.school.school_id, s.role])).toEqual(
      composed.schools.map((s) => [s.school.school_id, s.role]),
    );
    expect(rendered.schools.every((s) => s.reasons.length > 0)).toBe(true);
  });
});

describe("roundExclusions", () => {
  it("separates never-repeat from cooldown", () => {
    const s = session({
      reactions: [
        {
          school_id: "a", reaction: "research_next", key: null,
          saved_reason_text: "r", familiarity: "no", round_index: 0,
        },
      ],
      round_history: [
        { round_index: 0, school_ids: ["a", "b"], roles: [], revisit_ids: [] },
      ],
    });
    const { never, cooldown } = roundExclusions(s);
    expect(never.has("a")).toBe(true);
    expect(cooldown.has("b")).toBe(true);
    expect(cooldown.has("a")).toBe(false);
  });
});

describe("cardStatementForKey", () => {
  it("maps preference keys back to their card statements", () => {
    expect(cardStatementForKey("scale.small")).toMatch(/small enough/);
    expect(cardStatementForKey("unknown.key")).toBeNull();
  });
});
