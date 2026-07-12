// Types for the guided discovery runtime (PRD 026). The content shapes mirror
// the versioned CC BY-SA artifacts under data/discovery/.

export type Bucket = "essential" | "interesting" | "not_important" | "not_for_me";

export const BUCKETS: Bucket[] = [
  "essential",
  "interesting",
  "not_important",
  "not_for_me",
];

export const BUCKET_LABELS: Record<Bucket, string> = {
  essential: "Essential",
  interesting: "Interesting",
  not_important: "Not important",
  not_for_me: "Not for me",
};

export type EvidenceStatus = "data" | "proxy" | "reflection_only";

export interface DiscoveryCard {
  card_id: string;
  version: number;
  group: string;
  domain: string;
  evidence_status: EvidenceStatus;
  statement: string;
  explanation: string;
  preference_keys: string[];
  evidence_keys: string[];
  limitation_id: string;
}

// PRD 026 §3 PreferenceSignal — card-sourced and school-reaction signals
// (reflection-derived signals and explicit ledger edits arrive with later
// slices).
export interface PreferenceSignal {
  signal_id: string;
  key: string;
  domain: string;
  direction: "seek" | "avoid";
  strength: "essential" | "interesting";
  // Absolute policy bucket weight (discovery_policy_v1 scoring); school
  // reactions contribute magnitude 1 (PRD 026 §3).
  magnitude: number;
  source: "card" | "school_reaction";
  source_id: string;
  confidence: "explicit";
  active: boolean;
}

// --- policy / ontology / evidence shapes (mirrors of the CC artifacts) ---

export interface MatcherSpec {
  kind:
    | "numeric_band"
    | "numeric_band_inverted"
    | "count_band"
    | "category_set"
    | "offering_any"
    | "checklist_membership";
  evidence_keys: string[];
  seek?: Record<string, number>;
  opposite?: Record<string, number>;
  seek_set?: (string | number)[];
  opposite_set?: (string | number)[];
  members?: string[];
  min_members?: number;
  aggregation?: "max";
  unit?: string;
  limitation_id: string;
}

export interface DiscoveryPolicy {
  policy_version: string;
  scoring: {
    academic_match: { direct: number; adjacent: number };
    preference_aggregate_clamp: [number, number];
    bucket_weights: Record<string, number>;
    inside_preferred_radius: number;
    essential_threshold: number;
  };
  matchers: Record<string, MatcherSpec>;
  unsupported_keys: { keys: string[] };
  round_composition: {
    round_size: number;
    minimum_size: number;
    diversity: { max_per_state: number; max_per_control: number };
  };
  reason_templates: Record<string, { text: string; limitation_id: string } | string>;
}

export interface InterestConcept {
  concept_id: string;
  label: string;
  aliases: string[];
}

export interface InterestEdge {
  edge_id: string;
  from_concept_id: string;
  to_cip: string;
  cip_label: string;
  relationship: "direct" | "adjacent" | "exploratory";
  explanation: string;
}

export interface InterestOntology {
  ontology_version: string;
  concepts: InterestConcept[];
  edges: InterestEdge[];
}

export interface EvidenceSchool {
  school_id: string;
  ipeds_id: string;
  name: string;
  city: string | null;
  state: string;
  control: number;
  lat: number | null;
  lon: number | null;
  enrollment: number | null;
  direct: Record<string, number>;
  adjacent: Record<string, number>;
  scorecard: {
    locale: number | null;
    avg_net_price: number | null;
    net_price_0_30k: number | null;
    median_debt_completers: number | null;
    retention_rate_ft: number | null;
    graduation_rate_4yr: number | null;
    graduation_rate_6yr: number | null;
    earnings_10yr_median: number | null;
    pell_grant_rate: number | null;
    scorecard_data_year: string | null;
  };
}

export interface EvidenceBundle {
  bundle_version: string;
  policy_version: string;
  ontology_version: string;
  completions_release: string;
  completions_data_year: number;
  school_count: number;
  schools: EvidenceSchool[];
}

export interface RoundReason {
  kind: string; // "academic_direct" | "academic_adjacent" | preference key
  ref: string;
  text: string;
  evidence_class: "program" | "directory" | "scorecard";
  data_year: string;
  limitation: string;
  // preference key this reason can tune via reactions; null for academic
  // interest matches (nothing to tune).
  tunable_key: string | null;
}

export interface RoundSchool {
  school: EvidenceSchool;
  role: string;
  score: number;
  distance_miles: number | null;
  reasons: RoundReason[];
  revisit: boolean;
}

export interface SchoolReaction {
  school_id: string;
  reaction: "research_next" | "more_like_this" | "not_for_me";
  // preference key of the chosen reason, when one was chosen
  key: string | null;
  saved_reason_text: string | null;
  familiarity: "yes" | "name_only" | "no" | null;
  round_index: number;
}

export interface KeyAggregate {
  key: string;
  domain: string;
  total: number; // clamped per policy
  conflicted: boolean;
  signal_ids: string[];
}

// Soft distance settings (PRD 026 §3 GeographyPreference). The ZIP itself is
// browser-local only and must never leave the device (PRD §12); centroid
// resolution is deferred until the ZIP-centroid source is selected (PRD Q5).
export interface GeographyPreferenceLocal {
  zip: string | null;
  preferred_miles: number | null;
  maximum_miles: number | null;
  allow_wildcards: boolean;
}

export interface DiscoverySessionV1 {
  schema_version: 2;
  created_at: string;
  expires_at: string;
  card_deck_version: string;
  card_library_version: string;
  policy_version: string;
  step: "intro" | "geography" | "sort" | "ledger" | "interests" | "rounds" | "shelf";
  sort_index: number;
  geography: GeographyPreferenceLocal | null;
  card_responses: Record<string, Bucket>;
  // rounds-slice state (schema v2)
  concepts: string[];
  reactions: SchoolReaction[];
  // Index of the round currently displayed. Shown rounds render from
  // round_history (never recomposed — their own cooldown entries would
  // exclude them); composition happens only when current_round advances
  // past the recorded history.
  current_round: number;
  round_history: RoundHistoryEntry[];
  // Evidence bundle version the stored rounds were composed against. A bundle
  // bump resets round history (stale school ids/reasons) but keeps the
  // student's own work.
  bundle_version: string;
}

export interface RoundHistoryEntry {
  round_index: number;
  school_ids: string[];
  roles: string[];
  revisit_ids: string[];
}
