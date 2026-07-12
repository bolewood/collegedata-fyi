// Build-time binding to the versioned discovery content artifacts
// (data/discovery/, CC BY-SA 4.0). Importing at build time keeps sessions
// reproducible: a deployed build serves exactly one deck/library/policy
// version, and the session records which.

// Mirrors of the canonical CC BY-SA artifacts under data/discovery/ —
// see ./content/README.md; content-sync.test.ts enforces they never drift.
import libraryJson from "./content/cards.v1.json";
import deckJson from "./content/deck.opening-v1.json";
import policyJson from "./content/policy.v1.json";
import type { DiscoveryCard } from "./types";

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

const policy = policyJson as unknown as {
  policy_version: string;
  scoring: {
    preference_aggregate_clamp: [number, number];
    bucket_weights: Record<string, number>;
    essential_threshold: number;
  };
};

const cardsById = new Map(library.cards.map((c) => [c.card_id, c]));

// The opening deck in versioned display order. A deck id that fails to
// resolve is a content bug the artifact tests catch pre-merge; the runtime
// filter is defense in depth.
export const DECK_CARDS: DiscoveryCard[] = deck.display_order
  .map((id) => cardsById.get(id))
  .filter((c): c is DiscoveryCard => Boolean(c));

export const CARD_LIBRARY_VERSION = library.card_library_version;
export const DECK_VERSION = deck.deck_version;
export const POLICY_VERSION = policy.policy_version;
export const LIMITATIONS = library.limitations;

export const AGGREGATE_CLAMP = policy.scoring.preference_aggregate_clamp;
export const BUCKET_WEIGHTS = policy.scoring.bucket_weights;

export function getCard(cardId: string): DiscoveryCard | undefined {
  return cardsById.get(cardId);
}
