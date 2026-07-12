import { describe, expect, it } from "vitest";
import { DECK_CARDS, ESSENTIAL_THRESHOLD } from "./content";
import { SUPPORTED_KEYS } from "./matchers";
import { buildProfileStripModel } from "./profile-strip";
import { newSession } from "./session";
import type { DiscoverySessionV1, SchoolReaction } from "./types";

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

describe("buildProfileStripModel grouping", () => {
  it("groups by steering strength, direction, and conflict", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "small-school-known": "essential", // +3 -> strong
          "graduate-low-debt": "interesting", // +1 -> gentle
          "big-school-energy": "not_for_me", // -3 -> away
          "students-return": "essential", // +3, opposed by reaction -> tension
        },
        reactions: [
          reaction({ reaction: "not_for_me", key: "out.retention" }),
        ],
      }),
    );
    expect(m.strong.map((e) => e.key)).toEqual(["scale.small"]);
    expect(m.gentle.map((e) => e.key)).toEqual(["cost.low_debt"]);
    expect(m.away.map((e) => e.key)).toEqual(["scale.large"]);
    expect(m.tensions.map((e) => e.key)).toEqual(["out.retention"]);
    expect(m.counts).toEqual({ strong: 1, away: 1, tensions: 1 });
    expect(m.empty).toBe(false);
  });

  it("an Interesting-sorted card pushed past the threshold by reactions lands in Steering strongly", () => {
    // Weight 1 from the card + two more_like_this reactions (+1 each,
    // distinct schools) = 3 = ESSENTIAL_THRESHOLD. The group is steering
    // language on purpose — the student never marked this card Essential.
    const m = buildProfileStripModel(
      session({
        card_responses: { "graduate-low-debt": "interesting" },
        reactions: [
          reaction({ school_id: "s1" }),
          reaction({ school_id: "s2" }),
        ],
      }),
    );
    const entry = m.strong.find((e) => e.key === "cost.low_debt");
    expect(entry).toBeTruthy();
    expect(entry!.total).toBe(ESSENTIAL_THRESHOLD);
    expect(m.gentle).toEqual([]);
  });

  it("marks unsupported keys non-toggle even when steering positively", () => {
    const m = buildProfileStripModel(
      session({ card_responses: { "collaborative-culture": "essential" } }),
    );
    const entry = m.strong.find((e) => e.key === "spirit.collaborative");
    expect(entry).toBeTruthy();
    expect(entry!.kind).toBe("unsupported");
    // Non-toggle entries never reach the collapsed inline chips.
    expect(m.inline).toEqual([]);
  });

  it("away and tension entries are never spotlight toggles", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "big-school-energy": "not_for_me",
          "students-return": "essential",
        },
        reactions: [reaction({ reaction: "not_for_me", key: "out.retention" })],
      }),
    );
    expect(m.away.every((e) => e.kind === "away")).toBe(true);
    expect(m.tensions.every((e) => e.kind === "tension")).toBe(true);
  });

  it("inline chips are the strongest supported positives, capped at 3", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "small-school-known": "essential", // scale.small +3
          "students-return": "essential", // out.retention +3
          "four-year-finish": "essential", // out.four_year_grad +3
          "graduate-low-debt": "interesting", // cost.low_debt +1
        },
      }),
    );
    expect(m.inline).toHaveLength(3);
    // total desc, then key asc: three +3 keys sort alphabetically.
    expect(m.inline.map((e) => e.key)).toEqual([
      "out.four_year_grad",
      "out.retention",
      "scale.small",
    ]);
    expect(m.inline.every((e) => e.kind === "spotlight" && SUPPORTED_KEYS.has(e.key))).toBe(true);
  });

  it("is empty when nothing steers (all cards Not important, no reactions)", () => {
    const responses: Record<string, "not_important"> = {};
    for (const c of DECK_CARDS) responses[c.card_id] = "not_important";
    const m = buildProfileStripModel(session({ card_responses: responses }));
    expect(m.empty).toBe(true);
  });

  it("fails closed on keys without a card statement", () => {
    const m = buildProfileStripModel(
      session({ reactions: [reaction({ key: "no.such_key" })] }),
    );
    const everywhere = [...m.strong, ...m.gentle, ...m.away, ...m.tensions];
    expect(everywhere.find((e) => e.key === "no.such_key")).toBeUndefined();
  });
});

describe("attribution glosses", () => {
  it("quotes the card while an active card signal exists", () => {
    const m = buildProfileStripModel(
      session({ card_responses: { "small-school-known": "essential" } }),
    );
    expect(m.glosses["scale.small"]).toMatch(/^Because you said: “/);
    expect(m.glosses["scale.small"]).toMatch(/small enough/);
  });

  it("uses the reaction wording when the aggregate is reaction-only", () => {
    // Ledger edit moved the card to "Not important" (writes no signal); a
    // prior More-like-this reaction keeps the key alive. Quoting the card
    // would misstate what the student currently says.
    const m = buildProfileStripModel(
      session({
        card_responses: { "graduate-low-debt": "not_important" },
        reactions: [reaction({})],
      }),
    );
    expect(m.glosses["cost.low_debt"]).toBe("Because you asked for more like this.");
  });

  it("writes no gloss for away or conflicted keys", () => {
    const m = buildProfileStripModel(
      session({
        card_responses: {
          "big-school-energy": "not_for_me",
          "students-return": "essential",
        },
        reactions: [reaction({ reaction: "not_for_me", key: "out.retention" })],
      }),
    );
    expect(m.glosses["scale.large"]).toBeUndefined();
    expect(m.glosses["out.retention"]).toBeUndefined();
  });
});

describe("content-drift guards", () => {
  it("every deck card maps to exactly one key and no two cards share one", () => {
    // The strip dedupes chips by key; today that path is vacuously safe
    // because the deck is strictly 1 card : 1 key. This pins that fact so a
    // future content change re-opens the design question consciously.
    const seen = new Map<string, string>();
    for (const c of DECK_CARDS) {
      expect(c.preference_keys).toHaveLength(1);
      const key = c.preference_keys[0];
      expect(seen.has(key), `${c.card_id} shares ${key} with ${seen.get(key)}`).toBe(false);
      seen.set(key, c.card_id);
    }
  });
});
