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

// PRD 026 §3 PreferenceSignal — the slice-1 subset (card-sourced signals only;
// reflection, reactions, and explicit edits arrive with later slices).
export interface PreferenceSignal {
  signal_id: string;
  key: string;
  domain: string;
  direction: "seek" | "avoid";
  strength: "essential" | "interesting";
  magnitude: 1 | 3;
  source: "card";
  source_id: string;
  confidence: "explicit";
  active: boolean;
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
  schema_version: 1;
  created_at: string;
  expires_at: string;
  card_deck_version: string;
  card_library_version: string;
  policy_version: string;
  step: "intro" | "geography" | "sort" | "ledger";
  sort_index: number;
  geography: GeographyPreferenceLocal | null;
  card_responses: Record<string, Bucket>;
}
