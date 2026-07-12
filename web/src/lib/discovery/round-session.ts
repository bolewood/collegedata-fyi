// Session-aware round composition: folds the cross-round policy (PRD 026 §8)
// and reaction-derived preference updates (§10) around the stateless
// composer. Pure functions — the UI supplies the session, this returns the
// round.

import { DECK_CARDS, LIMITATIONS, POLICY, resolveZip } from "./content";
import { haversineMiles } from "./matchers";
import { renderReasons } from "./reasons";
import { composeRound, edgeSets, scoreSchool, type ComposedRound } from "./rounds";
import {
  aggregateKeys,
  buildReactionSignals,
  buildSignals,
} from "./signals";
import type {
  DiscoverySessionV1,
  EvidenceBundle,
  RoundHistoryEntry,
  RoundReason,
  RoundSchool,
  SchoolReaction,
} from "./types";

// Machine-readable in discovery_policy_v1 round_composition.cooldowns.
const COOLDOWN_ROUNDS = (POLICY.round_composition as unknown as {
  cooldowns: { shown_unreacted_rounds: number };
}).cooldowns.shown_unreacted_rounds;
const MINIMUM_SIZE = POLICY.round_composition.minimum_size;

// Shared session context so composeNextRound and renderStoredRound cannot
// drift (stored-round stability depends on them agreeing).
function sessionContext(session: DiscoverySessionV1) {
  const signals = [
    ...buildSignals(session.card_responses, DECK_CARDS),
    ...buildReactionSignals(session.reactions),
  ];
  const aggregates: Record<string, number> = {};
  const conflictedKeys = new Set<string>();
  for (const agg of aggregateKeys(signals)) {
    aggregates[agg.key] = agg.conflicted ? 0 : agg.total;
    if (agg.conflicted) conflictedKeys.add(agg.key);
  }
  const zip = session.geography?.zip ?? null;
  const origin = zip ? resolveZip(zip) : null;
  const zipUnresolved = Boolean(zip && !origin);
  return {
    aggregates,
    conflictedKeys,
    origin: zipUnresolved ? null : origin,
    zipUnresolved,
    geography: zipUnresolved ? null : session.geography,
  };
}

// The round change note derives only from reactions that actually write
// signals (more_like_this / not_for_me with a key). Saving to the shelf
// never changes preferences and must never read as a lean. A reaction whose
// key ended up conflicted is reported as a tension, not a lean the engine
// silently neutralized.
function changedKeysForRound(
  reactions: SchoolReaction[],
  priorRoundIndex: number,
  conflictedKeys: Set<string>,
): { key: string; direction: "seek" | "avoid"; conflicted: boolean }[] {
  return reactions
    .filter(
      (r) =>
        r.round_index === priorRoundIndex &&
        r.key &&
        (r.reaction === "more_like_this" || r.reaction === "not_for_me"),
    )
    .map((r) => ({
      key: r.key as string,
      direction: (r.reaction === "more_like_this" ? "seek" : "avoid") as
        | "seek"
        | "avoid",
      conflicted: conflictedKeys.has(r.key as string),
    }));
}

// The affordability slot's selection evidence (lowest reported average net
// price) must itself be shown (policy slot rule + PRD §9).
function affordabilityReason(school: RoundSchool["school"]): RoundReason | null {
  const tpl = POLICY.reason_templates["tpl.affordability_slot.v1"];
  if (!tpl || typeof tpl === "string") return null;
  const np = school.scorecard.avg_net_price;
  if (np === null) return null;
  const year = school.scorecard.scorecard_data_year ?? "recent";
  const text = tpl.text
    .replaceAll("{value}", `$${Math.round(np).toLocaleString("en-US")}`)
    .replaceAll("{population}", "students receiving federal aid")
    .replaceAll("{data_year}", year);
  const limitation = LIMITATIONS[tpl.limitation_id];
  if (!limitation || /\{[a-z_]+\}/.test(text)) return null;
  return {
    kind: "affordability_slot",
    ref: "scorecard.avg_net_price",
    text,
    evidence_class: "scorecard",
    data_year: year,
    limitation,
    tunable_key: null,
  };
}

export interface NextRound {
  round_index: number;
  schools: RoundSchool[];
  eligible_candidates: number;
  // ZIP present but not resolvable: distance settings are disabled for this
  // round and the UI must say so (PRD failure state — never silently drop
  // only the maximum).
  zip_unresolved: boolean;
  // preference keys nudged by reactions since the previous round; conflicted
  // means the reaction now opposes a card signal and the key counts for
  // nothing until resolved (surfaced, never silent — PRD §3).
  changed_keys: { key: string; direction: "seek" | "avoid"; conflicted: boolean }[];
  // what the session must persist so this round renders stably from history
  history_entry: RoundHistoryEntry;
}

export function roundExclusions(session: DiscoverySessionV1): {
  never: Set<string>;
  cooldown: Set<string>;
} {
  const never = new Set<string>();
  for (const r of session.reactions) {
    if (r.reaction === "research_next" || r.reaction === "not_for_me") {
      never.add(r.school_id);
    }
  }
  // ALL shown schools cool down — including more_like_this reactions, whose
  // boosted key would otherwise bounce the very same school straight back
  // (policy cooldowns.shown_note).
  const cooldown = new Set<string>();
  const nextIndex = session.round_history.length;
  for (const h of session.round_history) {
    if (nextIndex - h.round_index <= COOLDOWN_ROUNDS) {
      for (const id of h.school_ids) {
        if (!never.has(id)) cooldown.add(id);
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
  const ctx = sessionContext(session);
  const { never, cooldown } = roundExclusions(session);
  const excluded = new Set([...never, ...cooldown]);

  const compose = (): ComposedRound =>
    composeRound({
      pool: bundle.schools,
      concepts: session.concepts,
      geography: ctx.geography,
      origin: ctx.origin,
      aggregates: ctx.aggregates,
      excluded_school_ids: excluded,
    });

  let result = compose();

  // Re-admission: if cooldowns starved the round below the policy minimum,
  // re-admit oldest unreacted schools one at a time — only as many as the
  // minimum requires, never saved or rejected ones.
  const revisitIds = new Set<string>();
  if (result.chosen.length < MINIMUM_SIZE && cooldown.size > 0) {
    for (const id of readmissionOrder(session, never)) {
      if (result.chosen.length >= MINIMUM_SIZE) break;
      if (!excluded.has(id)) continue;
      excluded.delete(id);
      revisitIds.add(id);
      result = compose();
    }
  }

  const { direct, adjacent } = edgeSets(session.concepts);
  const schools: RoundSchool[] = result.chosen
    .map(({ candidate, role }) => {
      const reasons = renderReasons(
        candidate, session.concepts, direct, adjacent, ctx.aggregates,
      );
      if (role === "affordability") {
        const r = affordabilityReason(candidate.school);
        if (r && !reasons.some((x) => x.kind === "affordability_slot")) {
          reasons.push(r);
        }
      }
      return {
        school: candidate.school,
        role,
        score: candidate.score,
        distance_miles:
          candidate.distance === null ? null : Math.round(candidate.distance),
        reasons: reasons.slice(0, 3),
        revisit: revisitIds.has(candidate.school.school_id),
      };
    })
    // Fail closed (§9): a school with no valid rendered reasons cannot enter
    // a round.
    .filter((s) => s.reasons.length > 0);

  return {
    round_index: session.round_history.length,
    schools,
    eligible_candidates: result.eligible_candidates,
    zip_unresolved: ctx.zipUnresolved,
    changed_keys: changedKeysForRound(
      session.reactions,
      session.round_history.length - 1,
      ctx.conflictedKeys,
    ),
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
  const ctx = sessionContext(session);
  const prefMi = ctx.geography?.preferred_miles ?? null;

  const byId = new Map(bundle.schools.map((s) => [s.school_id, s]));
  const { direct, adjacent } = edgeSets(session.concepts);
  const revisit = new Set(entry.revisit_ids);

  const schools: RoundSchool[] = [];
  entry.school_ids.forEach((id, i) => {
    const school = byId.get(id);
    if (!school) return; // bundle version changed underneath — skip cleanly
    let distance: number | null = null;
    if (ctx.origin && school.lat !== null && school.lon !== null) {
      distance = haversineMiles(ctx.origin.lat, ctx.origin.lon, school.lat, school.lon);
    }
    const inPreferred = Boolean(prefMi && distance !== null && distance <= prefMi);
    const { score, reasons } = scoreSchool(school, ctx.aggregates, direct, adjacent, inPreferred);
    const role = entry.roles[i] ?? "exploration";
    const rendered = renderReasons(
      { school, score, distance, inPreferred, reasons },
      session.concepts,
      direct,
      adjacent,
      ctx.aggregates,
    );
    if (role === "affordability") {
      const r = affordabilityReason(school);
      if (r && !rendered.some((x) => x.kind === "affordability_slot")) {
        rendered.push(r);
      }
    }
    if (rendered.length === 0) return;
    schools.push({
      school,
      role,
      score,
      distance_miles: distance === null ? null : Math.round(distance),
      reasons: rendered.slice(0, 3),
      revisit: revisit.has(id),
    });
  });

  return {
    round_index: entry.round_index,
    schools,
    eligible_candidates: schools.length,
    zip_unresolved: ctx.zipUnresolved,
    changed_keys: changedKeysForRound(
      session.reactions,
      entry.round_index - 1,
      ctx.conflictedKeys,
    ),
    history_entry: entry,
  };
}

export function cardStatementForKey(key: string): string | null {
  const card = DECK_CARDS.find((c) => c.preference_keys.includes(key));
  return card?.statement ?? null;
}
