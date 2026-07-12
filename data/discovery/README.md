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

- `cards/v1.json` — versioned experience-card library (54 cards). The
  opening sort deck is drawn from this library; deck selection is a
  separate versioned artifact (pending).
- `ontology/` — reviewed interest-concept graph (pending, Milestone 0).
- `scenarios/` — synthetic geography/preference fixtures for the
  feasibility gate (pending, Milestone 0).

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
