// Client-side loader for the versioned evidence bundle. Fetched once per
// page lifetime from /public (CDN-cached, ~90KB gzipped) — only when the
// student actually reaches discovery rounds.

import type { EvidenceBundle } from "./types";

// Compile-time twin of the artifact's bundle_version — the fetch path below
// pins the same version, so a bundle bump changes both together.
export const EVIDENCE_BUNDLE_VERSION = "evidence-v1";

let cache: EvidenceBundle | null = null;
let inflight: Promise<EvidenceBundle> | null = null;

export function getCachedBundle(): EvidenceBundle | null {
  return cache;
}

export function loadBundle(): Promise<EvidenceBundle> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = fetch("/discovery/evidence-v1.json")
      .then((r) => {
        if (!r.ok) throw new Error(`evidence bundle: HTTP ${r.status}`);
        return r.json() as Promise<EvidenceBundle>;
      })
      .then((b) => {
        cache = b;
        return b;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}
