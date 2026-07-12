import { describe, expect, it } from "vitest";
import { DECK_CARDS } from "./content";
import {
  aggregateKeys,
  buildLedger,
  buildReactionSignals,
  buildRoundAggregates,
  buildSignals,
} from "./signals";
import type { Bucket, DiscoveryCard, SchoolReaction } from "./types";

const card = (id: string, keys: string[], domain = "community"): DiscoveryCard => ({
  card_id: id,
  version: 1,
  group: "g",
  domain,
  evidence_status: "data",
  statement: `statement ${id}`,
  explanation: "",
  preference_keys: keys,
  evidence_keys: ["directory.enrollment"],
  limitation_id: "lim.size_proxy",
});

describe("buildSignals (PRD 026 §3 deterministic mapping)", () => {
  const cards = [card("a", ["k.one"]), card("b", ["k.two"]), card("c", ["k.three"])];

  it("maps buckets to the policy weights", () => {
    const signals = buildSignals(
      { a: "essential", b: "interesting", c: "not_for_me" },
      cards,
    );
    const byId = Object.fromEntries(signals.map((s) => [s.source_id, s]));
    expect(byId.a).toMatchObject({ direction: "seek", strength: "essential", magnitude: 3 });
    expect(byId.b).toMatchObject({ direction: "seek", strength: "interesting", magnitude: 1 });
    expect(byId.c).toMatchObject({ direction: "avoid", strength: "essential", magnitude: 3 });
  });

  it("writes no signal for not_important or unsorted cards", () => {
    const signals = buildSignals({ a: "not_important" }, cards);
    expect(signals).toHaveLength(0);
  });

  it("writes one signal per preference key on multi-key cards", () => {
    const multi = card("m", ["k.x", "k.y"]);
    const signals = buildSignals({ m: "essential" }, [multi]);
    expect(signals.map((s) => s.key).sort()).toEqual(["k.x", "k.y"]);
  });

  it("is deterministic: same responses, same signals", () => {
    const responses = { a: "essential" as Bucket, b: "not_for_me" as Bucket };
    expect(buildSignals(responses, cards)).toEqual(buildSignals(responses, cards));
  });
});

describe("aggregateKeys", () => {
  it("sums signed magnitudes and clamps to the policy range", () => {
    const cards6 = Array.from({ length: 6 }, (_, i) => card(`c${i}`, ["k.same"]));
    const responses = Object.fromEntries(cards6.map((c) => [c.card_id, "essential"]));
    const [agg] = aggregateKeys(buildSignals(responses as Record<string, Bucket>, cards6));
    expect(agg.total).toBe(5); // 6 x +3 clamped to +5
    expect(agg.conflicted).toBe(false);
  });

  it("marks seek+avoid on one key conflicted and zeroes its contribution", () => {
    const two = [card("p", ["k.same"]), card("q", ["k.same"])];
    const [agg] = aggregateKeys(
      buildSignals({ p: "essential", q: "not_for_me" }, two),
    );
    expect(agg.conflicted).toBe(true);
    expect(agg.total).toBe(0);
    expect(agg.signal_ids).toHaveLength(2); // opposing signals never disappear
  });

  it("clamps the avoid side to the negative policy bound", () => {
    const cards3 = Array.from({ length: 3 }, (_, i) => card(`n${i}`, ["k.same"]));
    const responses = Object.fromEntries(cards3.map((c) => [c.card_id, "not_for_me"]));
    const [agg] = aggregateKeys(buildSignals(responses as Record<string, Bucket>, cards3));
    expect(agg.total).toBe(-5); // 3 x -3 clamped to -5
    expect(agg.conflicted).toBe(false);
  });

  it("mixes essential and interesting magnitudes on one key", () => {
    const two = [card("p", ["k.same"]), card("q", ["k.same"])];
    const [agg] = aggregateKeys(
      buildSignals({ p: "essential", q: "interesting" }, two),
    );
    expect(agg.total).toBe(4); // +3 +1, same direction — not conflicted
    expect(agg.conflicted).toBe(false);
  });

  it("excludes inactive signals from aggregation", () => {
    const signals = buildSignals({ a: "essential", b: "essential" }, [
      card("a", ["k.one"]),
      card("b", ["k.two"]),
    ]);
    const deactivated = signals.map((s) =>
      s.key === "k.two" ? { ...s, active: false } : s,
    );
    const aggs = aggregateKeys(deactivated);
    expect(aggs.map((a) => a.key)).toEqual(["k.one"]);
  });

  it("returns aggregates sorted by key for stable rendering", () => {
    const cards = [card("z", ["k.zeta"]), card("a", ["k.alpha"]), card("m", ["k.mid"])];
    const responses = { z: "essential", a: "interesting", m: "interesting" } as Record<
      string,
      Bucket
    >;
    const aggs = aggregateKeys(buildSignals(responses, cards));
    expect(aggs.map((a) => a.key)).toEqual(["k.alpha", "k.mid", "k.zeta"]);
  });
});

describe("opening deck integration", () => {
  it("deck cards resolve and carry unique preference keys (no sort-only conflicts)", () => {
    expect(DECK_CARDS).toHaveLength(24);
    const keys = DECK_CARDS.flatMap((c) => c.preference_keys);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("a full essential sort of the real deck yields no conflicts", () => {
    const responses = Object.fromEntries(
      DECK_CARDS.map((c) => [c.card_id, "essential"]),
    ) as Record<string, Bucket>;
    const aggregates = aggregateKeys(buildSignals(responses, DECK_CARDS));
    expect(aggregates.every((a) => !a.conflicted)).toBe(true);
  });
});

const reaction = (over: Partial<SchoolReaction> = {}): SchoolReaction => ({
  school_id: "s1",
  reaction: "more_like_this",
  key: "k.one",
  saved_reason_text: null,
  familiarity: null,
  round_index: 0,
  ...over,
});

describe("buildReactionSignals (PRD 026 §10)", () => {
  it("maps more_like_this/not_for_me to magnitude-1 seek/avoid signals", () => {
    const signals = buildReactionSignals([
      reaction(),
      reaction({ school_id: "s2", reaction: "not_for_me", key: "k.two" }),
    ]);
    expect(signals).toHaveLength(2);
    const byKey = Object.fromEntries(signals.map((s) => [s.key, s]));
    expect(byKey["k.one"]).toMatchObject({
      direction: "seek",
      magnitude: 1,
      strength: "interesting",
      source: "school_reaction",
      source_id: "s1",
    });
    expect(byKey["k.two"]).toMatchObject({ direction: "avoid", magnitude: 1 });
  });

  it("ignores research_next and keyless reactions — saving never tunes preferences", () => {
    expect(
      buildReactionSignals([
        reaction({ reaction: "research_next", key: "k.one" }),
        reaction({ key: null }),
        reaction({ reaction: "not_for_me", key: null }),
      ]),
    ).toEqual([]);
  });

  it("keeps only the latest reaction per (school, key) pair", () => {
    const signals = buildReactionSignals([
      reaction({ reaction: "more_like_this" }),
      reaction({ reaction: "not_for_me", round_index: 2 }),
    ]);
    expect(signals).toHaveLength(1);
    expect(signals[0].direction).toBe("avoid");
  });

  it("keeps distinct schools' reactions on the same key separate", () => {
    const signals = buildReactionSignals([
      reaction({ school_id: "s1" }),
      reaction({ school_id: "s2" }),
    ]);
    expect(signals).toHaveLength(2);
  });
});

describe("buildRoundAggregates", () => {
  it("adds reaction magnitude on top of card signals for the same key", () => {
    const aggs = buildRoundAggregates(
      { a: "interesting" },
      [card("a", ["k.one"])],
      [reaction({ key: "k.one" })],
    );
    expect(aggs["k.one"]).toBe(2); // +1 card, +1 reaction
  });

  it("zeroes a key conflicted between a card and a reaction (both stay visible upstream)", () => {
    const aggs = buildRoundAggregates(
      { a: "essential" },
      [card("a", ["k.one"])],
      [reaction({ reaction: "not_for_me", key: "k.one" })],
    );
    expect(aggs["k.one"]).toBe(0);
  });

  it("reaction-only keys enter the aggregates without any card response", () => {
    const aggs = buildRoundAggregates({}, [card("a", ["k.one"])], [
      reaction({ key: "k.solo", reaction: "not_for_me" }),
    ]);
    expect(aggs["k.solo"]).toBe(-1);
    expect(aggs["k.one"]).toBeUndefined();
  });
});

describe("buildLedger", () => {
  it("groups by bucket preserving deck order", () => {
    const cards = [card("a", ["k.1"]), card("b", ["k.2"]), card("c", ["k.3"])];
    const grouped = buildLedger(
      { a: "interesting", b: "essential", c: "interesting" },
      cards,
    );
    expect(grouped.essential.map((r) => r.card.card_id)).toEqual(["b"]);
    expect(grouped.interesting.map((r) => r.card.card_id)).toEqual(["a", "c"]);
    expect(grouped.not_for_me).toEqual([]);
  });
});
