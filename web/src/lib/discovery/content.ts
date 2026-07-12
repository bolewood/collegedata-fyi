// Build-time binding to the versioned discovery content artifacts
// (data/discovery/, CC BY-SA 4.0). Importing at build time keeps sessions
// reproducible: a deployed build serves exactly one deck/library/policy
// version, and the session records which.

// Mirrors of the canonical CC BY-SA artifacts under data/discovery/ —
// see ./content/README.md; content-sync.test.ts enforces they never drift.
import libraryJson from "./content/cards.v1.json";
import deckJson from "./content/deck.opening-v1.json";
import ontologyJson from "./content/ontology.v1.json";
import policyJson from "./content/policy.v1.json";
import zip3Json from "./content/zip3-centroids.v1.json";
import type { DiscoveryCard, DiscoveryPolicy, InterestOntology } from "./types";

const library = libraryJson as unknown as {
  card_library_version: string;
  limitations: Record<string, string>;
  cards: DiscoveryCard[];
};

const deck = deckJson as unknown as {
  deck_version: string;
  card_library_version: string;
  display_order: string[];
};

const policy = policyJson as unknown as DiscoveryPolicy;

const cardsById = new Map(library.cards.map((c) => [c.card_id, c]));

// The opening deck in versioned display order. An unresolved deck id is a
// content bug: fail closed at module init (surfaces in build/tests) rather
// than silently serving a shorter deck.
const unresolved = deck.display_order.filter((id) => !cardsById.has(id));
if (unresolved.length > 0) {
  throw new Error(
    `Deck ${deck.deck_version} references unknown cards: ${unresolved.join(", ")}`,
  );
}
export const DECK_CARDS: DiscoveryCard[] = deck.display_order.map(
  (id) => cardsById.get(id) as DiscoveryCard,
);

export const CARD_LIBRARY_VERSION = library.card_library_version;
export const DECK_VERSION = deck.deck_version;
export const POLICY_VERSION = policy.policy_version;
export const LIMITATIONS = library.limitations;

export const AGGREGATE_CLAMP = policy.scoring.preference_aggregate_clamp;
export const BUCKET_WEIGHTS = policy.scoring.bucket_weights;
export const ESSENTIAL_THRESHOLD = policy.scoring.essential_threshold;

export function getCard(cardId: string): DiscoveryCard | undefined {
  return cardsById.get(cardId);
}

export const POLICY = policy;
export const ONTOLOGY = ontologyJson as unknown as InterestOntology;

const zip3 = zip3Json as unknown as {
  zip3_centroid_version: string;
  centroids: Record<string, [number, number]>;
};
export const ZIP3_CENTROID_VERSION = zip3.zip3_centroid_version;

// PRD Q5 v1 resolution: a coarse 3-digit-prefix centroid lookup that runs
// entirely in the browser — the full ZIP never leaves the device. Returns
// null when the prefix is unknown (the UI's ZIP-no-match state applies).
export function resolveZip(zip: string): { lat: number; lon: number } | null {
  const m = /^(\d{3})\d{2}$/.exec(zip.trim());
  if (!m) return null;
  const hit = zip3.centroids[m[1]];
  return hit ? { lat: hit[0], lon: hit[1] } : null;
}
