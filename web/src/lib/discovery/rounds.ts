// Deterministic round composition — the TypeScript implementation of
// discovery_policy_v1 §7-8, conformance-tested against the Python reference
// engine (tools/discovery/data_spike.py) via a committed fixture. Given
// identical evidence bundle, ontology, policy, constraints, and preferences,
// both engines must produce identical ordered rounds.

import { ONTOLOGY, POLICY } from "./content";
import { haversineMiles, matcher, SUPPORTED_KEYS } from "./matchers";
import type { EvidenceSchool, GeographyPreferenceLocal } from "./types";

const SCORING = POLICY.scoring;
const RC = POLICY.round_composition;
const MAX_PER_STATE = RC.diversity.max_per_state;
const MAX_PER_CONTROL = RC.diversity.max_per_control;

export interface RoundInput {
  pool: EvidenceSchool[];
  concepts: string[]; // empty = whole interest family
  geography: GeographyPreferenceLocal | null;
  origin: { lat: number; lon: number } | null;
  // key -> clamped aggregate (conflicted keys already zeroed upstream)
  aggregates: Record<string, number>;
  // schools never to show again / on cooldown (cross-round policy, applied
  // by the caller; the composer itself is stateless like the Python engine)
  excluded_school_ids?: Set<string>;
}

export interface Candidate {
  school: EvidenceSchool;
  score: number;
  distance: number | null;
  inPreferred: boolean;
  reasons: [string, string][]; // (kind, ref) — rendered separately
}

export interface ComposedRound {
  chosen: { candidate: Candidate; role: string }[];
  slots: Record<string, boolean>;
  diagnostics: Record<string, number | string>;
  eligible_candidates: number;
}

export function edgeSets(concepts: string[]): {
  direct: Set<string>;
  adjacent: Set<string>;
} {
  const direct = new Set<string>();
  const adjacent = new Set<string>();
  const filter = concepts.length > 0 ? new Set(concepts) : null;
  for (const e of ONTOLOGY.edges) {
    if (filter && !filter.has(e.from_concept_id)) continue;
    if (e.relationship === "direct") direct.add(e.to_cip);
    else if (e.relationship === "adjacent") adjacent.add(e.to_cip);
  }
  for (const cip of direct) adjacent.delete(cip);
  return { direct, adjacent };
}

export function scoreSchool(
  school: EvidenceSchool,
  aggregates: Record<string, number>,
  direct: Set<string>,
  adjacent: Set<string>,
  inPreferred: boolean,
): { score: number; reasons: [string, string][] } {
  let score = 0;
  const reasons: [string, string][] = [];
  const directHit = Object.keys(school.direct).some((c) => direct.has(c));
  if (directHit) {
    score += SCORING.academic_match.direct;
    reasons.push(["academic_direct", "program.recent_awards_direct"]);
  } else if (
    Object.keys(school.adjacent).some((c) => adjacent.has(c)) ||
    Object.keys(school.direct).some((c) => adjacent.has(c))
  ) {
    score += SCORING.academic_match.adjacent;
    reasons.push(["academic_adjacent", "program.recent_awards_adjacent"]);
  }
  for (const [key, agg] of Object.entries(aggregates)) {
    if (!SUPPORTED_KEYS.has(key)) continue;
    const m = matcher(key, school);
    if (m !== 0) {
      score += agg * m;
      if (agg * m > 0) reasons.push([key, `match:${key}`]);
    }
  }
  if (inPreferred) score += SCORING.inside_preferred_radius;
  return { score, reasons };
}

// Memoized per school object: the comparator runs O(n log n) times per sort
// and each evaluation runs all 37 matchers (measured ~28ms → ~3ms per round).
const dimensionsCache = new WeakMap<EvidenceSchool, number>();
function supportedDimensions(school: EvidenceSchool): number {
  const hit = dimensionsCache.get(school);
  if (hit !== undefined) return hit;
  let n = 0;
  for (const key of SUPPORTED_KEYS) if (matcher(key, school) !== 0) n += 1;
  dimensionsCache.set(school, n);
  return n;
}

// Tuple comparator mirroring Python's (-score, -direct_count, -dimensions,
// school_id) sort ordering.
function compareCandidates(a: Candidate, b: Candidate): number {
  if (a.score !== b.score) return b.score - a.score;
  const ad = Object.keys(a.school.direct).length;
  const bd = Object.keys(b.school.direct).length;
  if (ad !== bd) return bd - ad;
  const as_ = supportedDimensions(a.school);
  const bs = supportedDimensions(b.school);
  if (as_ !== bs) return bs - as_;
  return a.school.school_id < b.school.school_id ? -1 : 1;
}

function mismatchesExactlyOneInteresting(
  school: EvidenceSchool,
  aggregates: Record<string, number>,
): boolean {
  let interesting = 0;
  for (const [key, agg] of Object.entries(aggregates)) {
    if (!SUPPORTED_KEYS.has(key)) continue;
    const m = matcher(key, school);
    if (Math.abs(agg) >= SCORING.essential_threshold) {
      if ((agg > 0 && m === -1) || (agg < 0 && m === 1)) return false;
    } else if (agg !== 0) {
      if ((agg > 0 && m === -1) || (agg < 0 && m === 1)) interesting += 1;
    }
  }
  return interesting === 1;
}

export function composeRound(input: RoundInput): ComposedRound {
  const { direct, adjacent } = edgeSets(input.concepts);
  const geo = input.geography;
  const maxMi = geo?.maximum_miles ?? null;
  const prefMi = geo?.preferred_miles ?? null;
  const useGeo = input.origin !== null && Boolean(maxMi || prefMi);
  const excluded = input.excluded_school_ids ?? new Set<string>();

  const diagnostics: Record<string, number> = {};
  const bump = (k: string) => {
    diagnostics[k] = (diagnostics[k] ?? 0) + 1;
  };

  const candidates: Candidate[] = [];
  for (const s of input.pool) {
    if (excluded.has(s.school_id)) {
      bump("excluded_by_cooldown");
      continue;
    }
    const directHit = Object.keys(s.direct).some((c) => direct.has(c));
    const adjacentHit =
      Object.keys(s.direct).some((c) => adjacent.has(c)) ||
      Object.keys(s.adjacent).some((c) => adjacent.has(c));
    if (!directHit && !adjacentHit) {
      bump("outside_selected_concepts");
      continue;
    }
    let distance: number | null = null;
    if (useGeo && input.origin) {
      if (s.lat === null || s.lon === null) {
        if (maxMi) {
          bump("missing_coordinates_under_hard_radius");
          continue;
        }
      } else {
        distance = haversineMiles(input.origin.lat, input.origin.lon, s.lat, s.lon);
        if (maxMi && distance > maxMi) {
          bump("beyond_maximum");
          continue;
        }
      }
    }
    const inPreferred = Boolean(
      prefMi && distance !== null && distance <= prefMi,
    );
    const { score, reasons } = scoreSchool(
      s, input.aggregates, direct, adjacent, inPreferred,
    );
    candidates.push({ school: s, score, distance, inPreferred, reasons });
  }

  candidates.sort(compareCandidates);

  const chosen: { candidate: Candidate; role: string }[] = [];
  const stateCount: Record<string, number> = {};
  const controlCount: Record<number, number> = {};

  const diversityOk = (s: EvidenceSchool) =>
    (stateCount[s.state] ?? 0) < MAX_PER_STATE &&
    (controlCount[s.control] ?? 0) < MAX_PER_CONTROL;

  const pick = (c: Candidate, role: string) => {
    chosen.push({ candidate: c, role });
    stateCount[c.school.state] = (stateCount[c.school.state] ?? 0) + 1;
    controlCount[c.school.control] = (controlCount[c.school.control] ?? 0) + 1;
  };

  const isChosen = (c: Candidate) =>
    chosen.some((x) => x.candidate.school.school_id === c.school.school_id);

  const take = (pred: (c: Candidate) => boolean, role: string): boolean => {
    for (const c of candidates) {
      if (isChosen(c)) continue;
      if (!pred(c)) continue;
      if (!diversityOk(c.school)) {
        bump(`diversity_rejected:${role}`);
        continue;
      }
      pick(c, role);
      return true;
    }
    return false;
  };

  const isDirect = (c: Candidate) =>
    Object.keys(c.school.direct).some((cip) => direct.has(cip));

  const slots: Record<string, boolean> = {};
  slots.anchor = take(isDirect, "anchor");

  // Flexible path: highest related-CIP count among remaining direct matches,
  // counted within the selected concepts' edge sets.
  slots.flexible = (() => {
    let best: Candidate | null = null;
    let bestRelated = -1;
    const scoped = new Set([...direct, ...adjacent]);
    for (const c of candidates) {
      if (isChosen(c) || !isDirect(c)) continue;
      if (!diversityOk(c.school)) {
        bump("diversity_rejected:flexible");
        continue;
      }
      const related = [
        ...Object.keys(c.school.direct),
        ...Object.keys(c.school.adjacent),
      ].filter((cip) => scoped.has(cip)).length;
      if (related > bestRelated) {
        bestRelated = related;
        best = c;
      }
    }
    if (best) {
      pick(best, "flexible");
      return true;
    }
    return false;
  })();

  slots.contrast = take(
    (c) => mismatchesExactlyOneInteresting(c.school, input.aggregates),
    "contrast",
  );

  // Affordability context: lowest non-missing avg_net_price.
  slots.affordability = (() => {
    let best: Candidate | null = null;
    let bestPrice = Infinity;
    for (const c of candidates) {
      if (isChosen(c)) continue;
      const np = c.school.scorecard.avg_net_price;
      if (np === null) continue;
      if (!diversityOk(c.school)) {
        bump("diversity_rejected:affordability");
        continue;
      }
      if (np < bestPrice) {
        bestPrice = np;
        best = c;
      }
    }
    if (best) {
      pick(best, "affordability");
      return true;
    }
    return false;
  })();

  slots.wildcard =
    geo?.allow_wildcards && prefMi
      ? take((c) => c.distance !== null && c.distance > prefMi, "wildcard")
      : false;

  slots.exploration = take(() => true, "exploration");

  while (chosen.length < RC.round_size && take(() => true, "additional_exploration")) {
    // backfill
  }

  // §8 relaxation: level 1 drops the control cap (state cap kept); level 2
  // drops both. Recorded only when it actually adds schools.
  if (chosen.length < RC.minimum_size) {
    const levels: (number | null)[] = [MAX_PER_STATE, null];
    for (let level = 1; level <= levels.length; level++) {
      const stateCap = levels[level - 1];
      let added = 0;
      for (const c of candidates) {
        if (chosen.length >= RC.minimum_size) break;
        if (isChosen(c)) continue;
        if (stateCap !== null && (stateCount[c.school.state] ?? 0) >= stateCap) continue;
        pick(c, "additional_exploration_relaxed");
        added += 1;
      }
      if (added) {
        diagnostics["relaxation_level"] = level;
        diagnostics[`relaxation_added_l${level}`] = added;
      }
      if (chosen.length >= RC.minimum_size) break;
    }
  }

  return {
    chosen,
    slots,
    diagnostics,
    eligible_candidates: candidates.length,
  };
}
