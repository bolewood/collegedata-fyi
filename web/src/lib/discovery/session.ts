// Browser-local discovery session (PRD 026 §12). Default state never leaves
// the device: no account, no server persistence, ZIP included only here.
// Sessions expire after 30 days; a session written by an incompatible deck,
// library, or policy version is discarded rather than silently migrated.

import {
  CARD_LIBRARY_VERSION,
  DECK_VERSION,
  POLICY_VERSION,
} from "./content";
import type { DiscoverySessionV1 } from "./types";

export const SESSION_STORAGE_KEY = "cdfyi.discovery.session.v1";
const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

export function newSession(now: Date): DiscoverySessionV1 {
  return {
    schema_version: 1,
    created_at: now.toISOString(),
    expires_at: new Date(now.getTime() + THIRTY_DAYS_MS).toISOString(),
    card_deck_version: DECK_VERSION,
    card_library_version: CARD_LIBRARY_VERSION,
    policy_version: POLICY_VERSION,
    step: "intro",
    sort_index: 0,
    geography: null,
    card_responses: {},
  };
}

export function isCompatible(
  session: DiscoverySessionV1,
  now: Date,
): boolean {
  return (
    session.schema_version === 1 &&
    session.card_deck_version === DECK_VERSION &&
    session.card_library_version === CARD_LIBRARY_VERSION &&
    session.policy_version === POLICY_VERSION &&
    new Date(session.expires_at).getTime() > now.getTime()
  );
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
  try {
    const raw = s.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DiscoverySessionV1;
    if (!isCompatible(parsed, now)) {
      s.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
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
