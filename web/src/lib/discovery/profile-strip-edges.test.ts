import { describe, expect, it } from "vitest";
import { AGGREGATE_CLAMP } from "./content";
import { buildProfileStripModel } from "./profile-strip";
import { newSession } from "./session";
import type { DiscoverySessionV1, SchoolReaction } from "./types";

// Edge coverage for the profile-strip model: group ordering, mixed
// supported/unsupported inline selection, the away/unsupported kind
// combination, the fresh-session state, and clamp interplay. Companion to
// profile-strip.test.ts (grouping, glosses, drift guards).

const NOW = new Date("2026-07-12T12:00:00Z");

function session(over: Partial<DiscoverySessionV1> = {}): DiscoverySessionV1 {
  return { ...newSession(NOW), step: "rounds", concepts: ["environment-climate"], ...over };
}

function reaction(over: Partial<SchoolReaction>): SchoolReaction {
  return {
    school_id: "s1",
    reaction: "more_like_this",
    key: "cost.low_debt",
    saved_reason_text: null,
    familiarity: null,
    round_index: 0,
    ...over,
  };
}

describe("buildProfileStripModel ordering", () => {
  it("orders the away group most-negative first, then key ascending on ties", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "big-school-energy": "not_for_me", // scale.large -3
          "city-as-campus": "not_for_me", // place.big_city -3 (key tie with above)
        },
        // Reaction-only avoid: out.retention -1, weaker than the -3 pair.
        reactions: [reaction({ reaction: "not_for_me", key: "out.retention" })],
      }),
    );
    expect(m.away.map((e) => e.key)).toEqual([
      "place.big_city",
      "scale.large",
      "out.retention",
    ]);
    expect(m.away.map((e) => e.total)).toEqual([-3, -3, -1]);
  });

  it("orders the gentle group strongest first, then key ascending on ties", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "graduate-low-debt": "interesting", // +1 card
          "students-return": "interesting", // +1
          "four-year-finish": "interesting", // +1
        },
        // One more_like_this lifts cost.low_debt to +2 — still under the
        // essential threshold, so it stays gentle but leads the group.
        reactions: [reaction({})],
      }),
    );
    expect(m.gentle.map((e) => e.key)).toEqual([
      "cost.low_debt",
      "out.four_year_grad",
      "out.retention",
    ]);
    expect(m.gentle.map((e) => e.total)).toEqual([2, 1, 1]);
  });
});

describe("buildProfileStripModel kind/group edges", () => {
  it("non-actionable entries go to recorded; inline comes from actionable positives", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "collaborative-culture": "essential", // spirit.collaborative +3, no matcher
          "graduate-low-debt": "interesting", // cost.low_debt +1, actionable
        },
      }),
    );
    // Non-actionable keys never inflate the steering groups or counts —
    // scoreSchool ignores them, so "Steering strongly" would be a lie.
    expect(m.strong).toEqual([]);
    expect(m.counts.strong).toBe(0);
    expect(m.recorded.map((e) => e.key)).toEqual(["spirit.collaborative"]);
    expect(m.inline.map((e) => e.key)).toEqual(["cost.low_debt"]);
    expect(m.inline[0].kind).toBe("spotlight");
  });

  it("a negative non-actionable key is recorded, not away", () => {
    // The away copy "shapes scoring" would overstate what an unmatched key
    // does — it shapes nothing until its evidence ships.
    const m = buildProfileStripModel(
      session({ card_responses: { "collaborative-culture": "not_for_me" } }),
    );
    expect(m.away).toEqual([]);
    expect(m.counts.away).toBe(0);
    expect(m.recorded.map((e) => e.key)).toEqual(["spirit.collaborative"]);
    expect(m.recorded[0].kind).toBe("unsupported");
  });

  it("a tension entry carries total 0 and appears in no steering group", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: { "students-return": "essential" },
        reactions: [reaction({ reaction: "not_for_me", key: "out.retention" })],
      }),
    );
    expect(m.tensions.map((e) => e.key)).toEqual(["out.retention"]);
    expect(m.tensions[0].total).toBe(0);
    expect(m.strong).toEqual([]);
    expect(m.gentle).toEqual([]);
    expect(m.away).toEqual([]);
  });
});

describe("buildProfileStripModel boundary states", () => {
  it("a fresh session (no responses, no reactions) is empty with zeroed counts", () => {
    const m = buildProfileStripModel(session());
    expect(m.empty).toBe(true);
    expect(m.counts).toEqual({ strong: 0, away: 0, tensions: 0 });
    expect(m.inline).toEqual([]);
    expect(m.glosses).toEqual({});
  });

  it("entry totals respect the policy aggregate clamp", () => {
    // Essential card (+3) plus three more_like_this reactions on distinct
    // schools (+1 each) sums to 6 raw; the strip must show the clamped
    // steering value the engine actually uses, not the raw sum.
    const [, hi] = AGGREGATE_CLAMP;
    const m = buildProfileStripModel(
      session({
        card_responses: { "graduate-low-debt": "essential" },
        reactions: [
          reaction({ school_id: "s1" }),
          reaction({ school_id: "s2" }),
          reaction({ school_id: "s3" }),
        ],
      }),
    );
    const entry = m.strong.find((e) => e.key === "cost.low_debt");
    expect(entry).toBeTruthy();
    expect(entry!.total).toBe(hi);
  });
});
