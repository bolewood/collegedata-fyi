// Browser-local discovery session (PRD 026 §12). Default state never leaves
// the device: no account, no server persistence, ZIP included only here.
// Sessions expire after 30 days; a session written by an incompatible deck,
// library, or policy version is discarded rather than silently migrated.

import {
  CARD_LIBRARY_VERSION,
  DECK_VERSION,
  POLICY_VERSION,
} from "./content";
import { BUCKETS, type DiscoverySessionV1 } from "./types";

export const SESSION_STORAGE_KEY = "cdfyi.discovery.session.v1";
export const SESSION_TTL_DAYS = 30;
const SESSION_TTL_MS = SESSION_TTL_DAYS * 24 * 60 * 60 * 1000;

export function newSession(now: Date): DiscoverySessionV1 {
  return {
    schema_version: 2,
    created_at: now.toISOString(),
    expires_at: new Date(now.getTime() + SESSION_TTL_MS).toISOString(),
    card_deck_version: DECK_VERSION,
    card_library_version: CARD_LIBRARY_VERSION,
    policy_version: POLICY_VERSION,
    step: "intro",
    sort_index: 0,
    geography: null,
    card_responses: {},
    concepts: [],
    reactions: [],
    current_round: 0,
    round_history: [],
  };
}

export function isCompatible(
  session: DiscoverySessionV1,
  now: Date,
): boolean {
  return (
    session.schema_version === 2 &&
    session.card_deck_version === DECK_VERSION &&
    session.card_library_version === CARD_LIBRARY_VERSION &&
    session.policy_version === POLICY_VERSION &&
    new Date(session.expires_at).getTime() > now.getTime()
  );
}

const STEPS = new Set(["intro", "geography", "sort", "ledger", "interests", "rounds", "shelf"]);
const BUCKET_SET = new Set<string>(BUCKETS);

// A version-stamped session can still be shape-corrupted (tampered or
// half-written storage). Without this guard a bad step/sort_index/bucket
// crashes the flow on every reload — a permanent dead end.
export function hasValidShape(session: DiscoverySessionV1): boolean {
  if (typeof session !== "object" || session === null) return false;
  if (!STEPS.has(session.step)) return false;
  if (
    !Number.isInteger(session.sort_index) ||
    session.sort_index < 0 ||
    session.sort_index > 10_000
  ) {
    return false;
  }
  if (
    typeof session.card_responses !== "object" ||
    session.card_responses === null ||
    Array.isArray(session.card_responses) ||
    !Object.values(session.card_responses).every((b) => BUCKET_SET.has(b))
  ) {
    return false;
  }
  const geo = session.geography;
  if (geo !== null) {
    if (typeof geo !== "object") return false;
    if (geo.zip !== null && typeof geo.zip !== "string") return false;
    if (geo.preferred_miles !== null && typeof geo.preferred_miles !== "number") return false;
    if (geo.maximum_miles !== null && typeof geo.maximum_miles !== "number") return false;
    if (typeof geo.allow_wildcards !== "boolean") return false;
  }
  if (!Array.isArray(session.concepts) || !session.concepts.every((c) => typeof c === "string")) {
    return false;
  }
  if (!Array.isArray(session.reactions) || !Array.isArray(session.round_history)) {
    return false;
  }
  if (!Number.isInteger(session.current_round) || session.current_round < 0) {
    return false;
  }
  return true;
}

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function storage(): StorageLike | null {
  // localStorage can throw under private-mode/quota policies; the session is
  // an enhancement, never a requirement.
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadSession(now: Date, store?: StorageLike): DiscoverySessionV1 | null {
  const s = store ?? storage();
  if (!s) return null;
  let raw: string | null = null;
  try {
    raw = s.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as DiscoverySessionV1;
    if (!isCompatible(parsed, now) || !hasValidShape(parsed)) {
      s.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    // Corrupt payloads are cleared like incompatible ones, so a bad write
    // cannot be re-parsed forever.
    try {
      s.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // storage rejected the cleanup too — nothing more to do
    }
    return null;
  }
}

export function saveSession(session: DiscoverySessionV1, store?: StorageLike): void {
  const s = store ?? storage();
  if (!s) return;
  try {
    s.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Storage full or blocked — the in-memory session still works for the tab.
  }
}

export function clearSession(store?: StorageLike): void {
  const s = store ?? storage();
  if (!s) return;
  try {
    s.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // nothing to clean
  }
}
