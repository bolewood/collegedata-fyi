// Deterministic card-to-preference mapping (PRD 026 §3, executed per
// discovery_policy_v1 bucket weights). Pure functions: same responses in,
// same ledger out — no clock, no randomness.

import { AGGREGATE_CLAMP, BUCKET_WEIGHTS, ESSENTIAL_THRESHOLD } from "./content";
import type {
  Bucket,
  DiscoveryCard,
  KeyAggregate,
  PreferenceSignal,
  SchoolReaction,
} from "./types";

// Bucket → signal mapping per the PRD table. "not_important" retains the
// card response for UI state only and writes no signal.
export function buildSignals(
  responses: Record<string, Bucket>,
  cards: DiscoveryCard[],
): PreferenceSignal[] {
  const signals: PreferenceSignal[] = [];
  for (const card of cards) {
    const bucket = responses[card.card_id];
    if (!bucket || bucket === "not_important") continue;
    const weight = BUCKET_WEIGHTS[bucket] ?? 0;
    if (weight === 0) continue;
    for (const key of card.preference_keys) {
      const magnitude = Math.abs(weight);
      signals.push({
        signal_id: `card:${card.card_id}:${key}`,
        key,
        domain: card.domain,
        direction: weight > 0 ? "seek" : "avoid",
        strength: magnitude >= ESSENTIAL_THRESHOLD ? "essential" : "interesting",
        magnitude,
        source: "card",
        source_id: card.card_id,
        confidence: "explicit",
        active: true,
      });
    }
  }
  return signals;
}

// Sum signed magnitudes per key and clamp per policy. A key carrying both
// active seek and avoid signals is conflicted: it contributes zero to
// candidate relevance but stays visible (PRD §3). Opposing signals never
// disappear merely because their numeric sum is zero.
export function aggregateKeys(signals: PreferenceSignal[]): KeyAggregate[] {
  const [lo, hi] = AGGREGATE_CLAMP;
  const byKey = new Map<string, PreferenceSignal[]>();
  for (const s of signals) {
    if (!s.active) continue;
    const list = byKey.get(s.key) ?? [];
    list.push(s);
    byKey.set(s.key, list);
  }
  const out: KeyAggregate[] = [];
  for (const [key, list] of byKey) {
    const conflicted =
      list.some((s) => s.direction === "seek") &&
      list.some((s) => s.direction === "avoid");
    const raw = list.reduce(
      (sum, s) => sum + (s.direction === "seek" ? s.magnitude : -s.magnitude),
      0,
    );
    out.push({
      key,
      domain: list[0].domain,
      total: conflicted ? 0 : Math.max(lo, Math.min(hi, raw)),
      conflicted,
      signal_ids: list.map((s) => s.signal_id).sort(),
    });
  }
  return out.sort((a, b) => a.key.localeCompare(b.key));
}

// School reactions become preference signals of magnitude 1 (PRD 026 §3,
// §10). Only one active reaction signal may exist per (school, key): a later
// reaction on the same pair supersedes the earlier one.
export function buildReactionSignals(
  reactions: SchoolReaction[],
): PreferenceSignal[] {
  const latest = new Map<string, SchoolReaction>();
  for (const r of reactions) {
    if (!r.key) continue;
    if (r.reaction !== "more_like_this" && r.reaction !== "not_for_me") continue;
    latest.set(`${r.school_id}:${r.key}`, r);
  }
  return [...latest.entries()].map(([pair, r]) => ({
    signal_id: `reaction:${pair}`,
    key: r.key as string,
    domain: "community",
    direction: r.reaction === "more_like_this" ? ("seek" as const) : ("avoid" as const),
    strength: "interesting" as const,
    magnitude: 1,
    source: "school_reaction" as const,
    source_id: r.school_id,
    confidence: "explicit" as const,
    active: true,
  }));
}

// Combined card + reaction aggregates for round composition: conflicted keys
// contribute zero (but stay visible in the ledger).
export function buildRoundAggregates(
  responses: Record<string, Bucket>,
  cards: DiscoveryCard[],
  reactions: SchoolReaction[],
): Record<string, number> {
  const signals = [
    ...buildSignals(responses, cards),
    ...buildReactionSignals(reactions),
  ];
  const out: Record<string, number> = {};
  for (const agg of aggregateKeys(signals)) {
    out[agg.key] = agg.conflicted ? 0 : agg.total;
  }
  return out;
}

export interface LedgerRow {
  card: DiscoveryCard;
  bucket: Bucket;
}

// Plain-language ledger grouped by bucket, preserving deck order within each.
export function buildLedger(
  responses: Record<string, Bucket>,
  deckCards: DiscoveryCard[],
): Record<Bucket, LedgerRow[]> {
  const grouped: Record<Bucket, LedgerRow[]> = {
    essential: [],
    interesting: [],
    not_important: [],
    not_for_me: [],
  };
  for (const card of deckCards) {
    const bucket = responses[card.card_id];
    // Unknown bucket strings (tampered/corrupt storage) are dropped rather
    // than crashing the ledger.
    if (bucket && grouped[bucket]) grouped[bucket].push({ card, bucket });
  }
  return grouped;
}
