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
      { key: "cost.low_debt", direction: "seek", conflicted: false },
    ]);
  });

  it("keeps a more_like_this school on cooldown instead of bouncing it back", () => {
    const first = composeNextRound(session(), bundle);
    const likedId = first.schools[0].school.school_id;
    const s2 = session({
      reactions: [
        {
          school_id: likedId,
          reaction: "more_like_this",
          key: first.schools[0].reasons.find((r) => r.tunable_key)?.tunable_key ?? "cost.low_debt",
          saved_reason_text: null,
          familiarity: null,
          round_index: 0,
        },
      ],
      round_history: [first.history_entry],
    });
    const second = composeNextRound(s2, bundle);
    // The boosted key must find NEW schools like it — the reacted school
    // itself cools down like every other shown school.
    expect(second.schools.map((x) => x.school.school_id)).not.toContain(likedId);
  });

  it("expires the shown-school cooldown after the policy window", () => {
    const first = composeNextRound(session(), bundle);
    const ids = first.schools.map((x) => x.school.school_id);
    // Two later rounds recorded -> the round-0 schools are outside the
    // 2-round cooldown window for round 3.
    const history = [
      first.history_entry,
      { round_index: 1, school_ids: ["x1"], roles: [], revisit_ids: [] },
      { round_index: 2, school_ids: ["x2"], roles: [], revisit_ids: [] },
    ];
    const { cooldown } = roundExclusions(session({ round_history: history }));
    for (const id of ids) expect(cooldown.has(id)).toBe(false);
    expect(cooldown.has("x1")).toBe(true);
    expect(cooldown.has("x2")).toBe(true);
  });

  it("never reports research_next in the change note", () => {
    const first = composeNextRound(session(), bundle);
    const s2 = session({
      reactions: [
        {
          school_id: first.schools[0].school.school_id,
          reaction: "research_next",
          key: first.schools[0].reasons[0].tunable_key ?? "cost.low_debt",
          saved_reason_text: first.schools[0].reasons[0].text,
          familiarity: "no",
          round_index: 0,
        },
      ],
      round_history: [first.history_entry],
    });
    // Saving to the shelf writes no preference signal, so claiming the round
    // "leans away" from the saved reason would be false.
    expect(composeNextRound(s2, bundle).changed_keys).toEqual([]);
  });

  it("marks a reaction that opposes an essential card as conflicted, not a lean", () => {
    // The card sort says small-school is essential (seek scale.small); a
    // not_for_me reaction keyed on scale.small opposes it.
    const first = composeNextRound(session(), bundle);
    const s2 = session({
      reactions: [
        {
          school_id: first.schools[0].school.school_id,
          reaction: "not_for_me",
          key: "scale.small",
          saved_reason_text: null,
          familiarity: null,
          round_index: 0,
        },
      ],
      round_history: [first.history_entry],
    });
    const second = composeNextRound(s2, bundle);
    expect(second.changed_keys).toEqual([
      { key: "scale.small", direction: "avoid", conflicted: true },
    ]);
  });

  it("renders the affordability slot's own evidence on affordability-role schools", () => {
    const round = composeNextRound(session(), bundle);
    const afford = round.schools.find((x) => x.role === "affordability");
    expect(afford).toBeTruthy();
    expect(
      afford!.reasons.some(
        (r) => r.kind === "affordability_slot" && r.text.includes("Average net price $"),
      ),
    ).toBe(true);
    expect(afford!.reasons.length).toBeLessThanOrEqual(3);
  });
});

describe("re-admission under pool starvation", () => {
  // Lewistown MT with a 250-mile hard cap leaves ~7 eligible schools: one
  // recorded round puts most of them on cooldown, starving the next round
  // below the four-school minimum and forcing the re-admission path.
  const TIGHT_GEO = {
    zip: "59457",
    preferred_miles: 100,
    maximum_miles: 250,
    allow_wildcards: false,
  };

  it("re-admits only oldest unreacted schools, labeled Revisit — never saved ones", () => {
    const first = composeNextRound(session({ geography: TIGHT_GEO }), bundle);
    expect(first.schools.length).toBeGreaterThanOrEqual(4);
    const savedId = first.schools[0].school.school_id;
    const shownUnreacted = first.schools.slice(1).map((x) => x.school.school_id);

    const s2 = session({
      geography: TIGHT_GEO,
      reactions: [
        {
          school_id: savedId,
          reaction: "research_next",
          key: null,
          saved_reason_text: first.schools[0].reasons[0].text,
          familiarity: "no",
          round_index: 0,
        },
      ],
      round_history: [first.history_entry],
    });
    const second = composeNextRound(s2, bundle);

    // The starved round still reaches the minimum via re-admission.
    expect(second.schools.length).toBeGreaterThanOrEqual(4);
    const revisits = second.schools.filter((x) => x.revisit);
    expect(revisits.length).toBeGreaterThan(0);
    // Every Revisit is a previously shown, unreacted school.
    for (const r of revisits) {
      expect(shownUnreacted).toContain(r.school.school_id);
    }
    // The shelved school never returns, even when the pool is starving.
    expect(second.schools.map((x) => x.school.school_id)).not.toContain(savedId);
    // Revisit labels persist into the history entry so the stored round
    // re-renders with the same labels.
    expect(second.history_entry.revisit_ids).toEqual(
      revisits.map((x) => x.school.school_id),
    );
  });

  it("a roomy pool never triggers re-admission after a single round", () => {
    const first = composeNextRound(session(), bundle); // nationwide pool
    const s2 = session({ round_history: [first.history_entry] });
    const second = composeNextRound(s2, bundle);
    expect(second.schools.every((x) => !x.revisit)).toBe(true);
    expect(second.history_entry.revisit_ids).toEqual([]);
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

  it("skips school ids the bundle no longer carries instead of crashing", () => {
    const base = session();
    const composed = composeNextRound(base, bundle);
    const entry = {
      ...composed.history_entry,
      school_ids: ["school-removed-in-new-bundle", ...composed.history_entry.school_ids],
      roles: ["anchor", ...composed.history_entry.roles],
    };
    const rendered = renderStoredRound(
      session({ round_history: [entry] }),
      bundle,
      entry,
    );
    expect(rendered.schools.map((s) => s.school.school_id)).toEqual(
      composed.history_entry.school_ids,
    );
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
