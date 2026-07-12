// Session-aware round composition: folds the cross-round policy (PRD 026 §8)
// and reaction-derived preference updates (§10) around the stateless
// composer. Pure functions — the UI supplies the session, this returns the
// round.

import { DECK_CARDS, resolveZip } from "./content";
import { renderReasons } from "./reasons";
import {
  composeRound,
  edgeSets,
  haversineDistance,
  scoreSchool,
  type ComposedRound,
} from "./rounds";
import { buildRoundAggregates } from "./signals";
import type {
  DiscoverySessionV1,
  EvidenceBundle,
  RoundHistoryEntry,
  RoundSchool,
} from "./types";

const COOLDOWN_ROUNDS = 2;

export interface NextRound {
  round_index: number;
  schools: RoundSchool[];
  diagnostics: Record<string, number | string>;
  eligible_candidates: number;
  // ZIP present but not resolvable: distance settings are disabled for this
  // round and the UI must say so (PRD failure state — never silently drop
  // only the maximum).
  zip_unresolved: boolean;
  // preference keys nudged by reactions since the previous round, for the
  // round change note
  changed_keys: { key: string; direction: "seek" | "avoid" }[];
  // what the session must persist so this round renders stably from history
  history_entry: RoundHistoryEntry;
}

export function roundExclusions(session: DiscoverySessionV1): {
  never: Set<string>;
  cooldown: Set<string>;
} {
  const never = new Set<string>();
  const reacted = new Set<string>();
  for (const r of session.reactions) {
    reacted.add(r.school_id);
    if (r.reaction === "research_next" || r.reaction === "not_for_me") {
      never.add(r.school_id);
    }
  }
  const cooldown = new Set<string>();
  const nextIndex = session.round_history.length;
  for (const h of session.round_history) {
    if (nextIndex - h.round_index <= COOLDOWN_ROUNDS) {
      for (const id of h.school_ids) {
        if (!never.has(id) && !reacted.has(id)) cooldown.add(id);
      }
    }
  }
  return { never, cooldown };
}

// Oldest shown-but-unreacted school ids, oldest round first — the only
// re-admission candidates (labeled Revisit).
function readmissionOrder(session: DiscoverySessionV1, never: Set<string>): string[] {
  const reacted = new Set(session.reactions.map((r) => r.school_id));
  const seen = new Set<string>();
  const out: string[] = [];
  for (const h of session.round_history) {
    for (const id of h.school_ids) {
      if (!never.has(id) && !reacted.has(id) && !seen.has(id)) {
        seen.add(id);
        out.push(id);
      }
    }
  }
  return out;
}

export function composeNextRound(
  session: DiscoverySessionV1,
  bundle: EvidenceBundle,
): NextRound {
  const aggregates = buildRoundAggregates(
    session.card_responses,
    DECK_CARDS,
    session.reactions,
  );

  const zip = session.geography?.zip ?? null;
  const origin = zip ? resolveZip(zip) : null;
  const zipUnresolved = Boolean(zip && !origin);
  // PRD failure state: an unresolved ZIP disables ALL distance settings for
  // the round (visibly), rather than silently dropping just the hard cap.
  const geography = zipUnresolved ? null : session.geography;

  const { never, cooldown } = roundExclusions(session);
  const excluded = new Set([...never, ...cooldown]);

  let result: ComposedRound = composeRound({
    pool: bundle.schools,
    concepts: session.concepts,
    geography,
    origin: zipUnresolved ? null : origin,
    aggregates,
    excluded_school_ids: excluded,
  });

  // Re-admission: if cooldowns starved the round below the minimum, re-admit
  // the oldest unreacted schools only — never saved or rejected ones.
  const revisitIds = new Set<string>();
  if (
    result.chosen.length < 4 &&
    cooldown.size > 0
  ) {
    for (const id of readmissionOrder(session, never)) {
      excluded.delete(id);
      revisitIds.add(id);
    }
    result = composeRound({
      pool: bundle.schools,
      concepts: session.concepts,
      geography,
      origin: zipUnresolved ? null : origin,
      aggregates,
      excluded_school_ids: excluded,
    });
  }

  const { direct, adjacent } = edgeSets(session.concepts);
  const schools: RoundSchool[] = result.chosen
    .map(({ candidate, role }) => ({
      school: candidate.school,
      role,
      score: candidate.score,
      distance_miles:
        candidate.distance === null ? null : Math.round(candidate.distance),
      reasons: renderReasons(candidate, session.concepts, direct, adjacent, aggregates),
      revisit: revisitIds.has(candidate.school.school_id),
    }))
    // Fail closed (§9): a school with no valid rendered reasons cannot enter
    // a round.
    .filter((s) => s.reasons.length > 0);

  // Reaction-driven changes since the previous round, for the change note.
  const lastRoundIndex = session.round_history.length - 1;
  const changedKeys = session.reactions
    .filter((r) => r.round_index === lastRoundIndex && r.key)
    .map((r) => ({
      key: r.key as string,
      direction: (r.reaction === "more_like_this" ? "seek" : "avoid") as
        | "seek"
        | "avoid",
    }));

  return {
    round_index: session.round_history.length,
    schools,
    diagnostics: result.diagnostics,
    eligible_candidates: result.eligible_candidates,
    zip_unresolved: zipUnresolved,
    changed_keys: changedKeys,
    history_entry: {
      round_index: session.round_history.length,
      school_ids: schools.map((x) => x.school.school_id),
      roles: schools.map((x) => x.role),
      revisit_ids: schools.filter((x) => x.revisit).map((x) => x.school.school_id),
    },
  };
}

// Re-render an already-shown round from its history entry. Shown rounds are
// NEVER recomposed — recording them creates cooldown entries that would
// exclude their own members. Reason rendering is pure and deterministic, so
// rebuilding presentation from stored ids is stable.
export function renderStoredRound(
  session: DiscoverySessionV1,
  bundle: EvidenceBundle,
  entry: RoundHistoryEntry,
): NextRound {
  const aggregates = buildRoundAggregates(
    session.card_responses,
    DECK_CARDS,
    session.reactions,
  );
  const zip = session.geography?.zip ?? null;
  const origin = zip ? resolveZip(zip) : null;
  const zipUnresolved = Boolean(zip && !origin);
  const useOrigin = zipUnresolved ? null : origin;
  const prefMi = zipUnresolved ? null : session.geography?.preferred_miles ?? null;

  const byId = new Map(bundle.schools.map((s) => [s.school_id, s]));
  const { direct, adjacent } = edgeSets(session.concepts);
  const revisit = new Set(entry.revisit_ids);

  const schools: RoundSchool[] = [];
  entry.school_ids.forEach((id, i) => {
    const school = byId.get(id);
    if (!school) return; // bundle version changed underneath — skip cleanly
    let distance: number | null = null;
    if (useOrigin && school.lat !== null && school.lon !== null) {
      distance = haversineDistance(useOrigin.lat, useOrigin.lon, school.lat, school.lon);
    }
    const inPreferred = Boolean(prefMi && distance !== null && distance <= prefMi);
    const { score, reasons } = scoreSchool(school, aggregates, direct, adjacent, inPreferred);
    const rendered = renderReasons(
      { school, score, distance, inPreferred, reasons },
      session.concepts,
      direct,
      adjacent,
      aggregates,
    );
    if (rendered.length === 0) return;
    schools.push({
      school,
      role: entry.roles[i] ?? "exploration",
      score,
      distance_miles: distance === null ? null : Math.round(distance),
      reasons: rendered,
      revisit: revisit.has(id),
    });
  });

  const changedKeys = session.reactions
    .filter((r) => r.round_index === entry.round_index - 1 && r.key)
    .map((r) => ({
      key: r.key as string,
      direction: (r.reaction === "more_like_this" ? "seek" : "avoid") as
        | "seek"
        | "avoid",
    }));

  return {
    round_index: entry.round_index,
    schools,
    diagnostics: {},
    eligible_candidates: schools.length,
    zip_unresolved: zipUnresolved,
    changed_keys: changedKeys,
    history_entry: entry,
  };
}

export function cardStatementForKey(key: string): string | null {
  const card = DECK_CARDS.find((c) => c.preference_keys.includes(key));
  return card?.statement ?? null;
}
