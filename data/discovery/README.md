# Discovery content (PRD 026)

Curated, versioned content for the guided college discovery experience
([PRD 026](../../docs/prd/026-guided-college-discovery.md)): the
experience-card library, the interest-to-CIP ontology, explanation
templates, and discovery policy definitions.

## Licensing — read before contributing

**This directory is CC BY-SA 4.0, not MIT.** See [`LICENSE`](LICENSE).
The code that consumes these files stays MIT like the rest of the repo;
the content here is authored editorial synthesis and carries its own
license so it stays inspectable (the product's trust model requires the
policy and ontology to be public) while requiring attribution and
share-alike from reuse.

**Contribution gate:** outside contributions to this directory are not
accepted without a signed contribution agreement. This preserves the
maintainer's ability to relicense or dual-license the content layer
later. Code contributions elsewhere in the repo are unaffected.

## Files

- `cards/v1.json` — versioned experience-card library (54 cards;
  25 data / 12 proxy / 17 reflection-only).
- `decks/opening-v1.json` — the 24-card opening sort deck drawn from the
  library (approved, revision 2).
- `ontology/v1.json` — reviewed interest-concept graph for the
  environment/climate/sustainability lake (6 concepts, 45 edges,
  approved 2026-07-12).
- `scenarios/v1.json` — versioned synthetic geography/preference
  fixtures for the feasibility gate (5 origins x 4 profiles).
- `geo/zip3-centroids-v1.json` — 3-digit ZIP prefix centroids (Census
  gazetteer, public domain) for browser-local, coarse distance resolution
  (PRD Q5 v1 answer: the full ZIP never leaves the device). Regenerated
  bit-identically by `tools/discovery/build_zip3_centroids.py`.
- `policy/v1.json` — `discovery_policy_v1`: eligibility predicate,
  scoring constants, evidence matchers for every data/proxy preference
  key (thresholds are initial calibration pending pilot evidence), slot
  composition, diversity + relaxation, tie-breaks, cooldowns,
  diagnostics schema, and reason templates. Executed by
  `tools/discovery/data_spike.py`; invariants pinned by
  `tools/discovery/test_policy.py`.

## Web runtime mirrors

The web app consumes committed mirrors of the runtime artifacts — the card
library, opening deck, policy, ontology, and ZIP3 centroids (not the scenario
fixtures) — under `web/src/lib/discovery/content/` (the Vercel project root is
`web/`, so it cannot import across the repo root).
`web/src/lib/discovery/content-sync.test.ts` fails the suite whenever a
mirror drifts from its canonical source here.

## Versioning rules

- Files are immutable once referenced by a shipped policy version: fix
  forward by publishing `v2`, never by editing `v1` in place.
- Every card carries `card_id` + `version`; preference-key and
  evidence-key mappings are part of the versioned definition
  (PRD 026 §2).
- `evidence_status` values: `data` (verified evidence can support a
  recommendation reason), `proxy` (supportable with a mandatory
  limitation caveat), `reflection_only` (shapes the ledger and AI
  reflection; can never generate a school recommendation reason).
- Evidence keys are declarative pointers; the binding to concrete
  matchers and thresholds happens in `discovery_policy_v1` and may
  rename keys before first ship.
