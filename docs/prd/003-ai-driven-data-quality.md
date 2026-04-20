<!-- /autoplan restore point: /Users/santhonys/.gstack/projects/bolewood-collegedata-fyi/main-autoplan-restore-20260417-091733.md -->

# PRD 003: AI-driven data-quality spike for Tier 4 extraction (M1 only)

**Status:** Historical planning artifact — approved for M1 exploration, but **not implemented directly**
**Author:** Anthony Showalter (with Claude)
**Date started:** 2026-04-17
**Updated:** 2026-04-20
**Related:** [PRD 001](001-collegedata-fyi-v1.md), [PRD 002](002-frontend.md), [PRD 006](006-llm-fallback.md), [ADR 0006](../decisions/0006-tiered-extraction-strategy.md), [ADR 0007](../decisions/0007-year-authority-moves-to-extraction.md)

> **Scope note:** /autoplan dual-voice review (both CEO and Eng phases) concluded that the original M1–M5 multi-milestone plan was over-scoped for a 2-day-old site with no user signal. Approved scope is **M1 only**, with an explicit kill-switch decision gate at the end of M1. M2–M5 are preserved as "conditional follow-ups" below but NOT committed work. See the Review Report section at the end of this document for the full analysis.

> **Implementation note (2026-04-20):** This PRD was **not** implemented directly. Keep it as the strategy/review record for the first LLM-fallback exploration, not as the active implementation spec.
>
> What is still worth keeping here:
> - the M1-only decision-gate framing
> - the alternatives table (`Reducto-only`, anomaly-only, top-N schools, "Ask the CDS")
> - ops/review-queue ideas like validator flags and maintainer workflow
> - prompt-eval guardrails such as deterministic confidence and prompt A/B regression testing
>
> What it does **not** own anymore:
> - the active fallback architecture
> - target-section ownership
> - subsection slicing / prompt / cache design
> - current validation and rollout plan
>
> Those moved into [PRD 006](006-llm-fallback.md), which is the in-flight implementation path. Read **PRD 003** for context and review history; read **PRD 006** for what is actually being built.

---

## Problem

The Tier 4 cleaner extracts ~25 of ~1,105 canonical CDS fields per document (~2% coverage per doc). After four iteration phases (`5951379` on main), GT scoring is 94.3% accuracy on the four hand-audited schools, and critical C1 admissions fields hit 50–59% coverage across the 443-doc corpus surveyed. But for consumers who want to see *all* the data a school published, we're showing them a sliver and calling the rest empty.

Rule-based extraction has a ceiling. Every new rule handles one label-shape variant; the long tail of community-college formats, OCR artifacts, wrapped cells, and year-over-year template drift means we'll never reach 100% with substring matching. The evidence from the Phase 4 corpus survey is clear: two-thirds of the fields the cleaner misses are structurally there in the markdown, just in shapes our rules don't recognize yet.

## Goal (M1 scope)

Ship a **falsifiable 2-week spike** that tests whether LLM gap-filling is a good investment. One question to answer at the decision gate: does LLM-filled CDS data have enough quality + audience demand to justify a corpus-wide rollout?

Concrete M1 deliverables:
1. An LLM gap-filler worker covering B1 enrollment only (the single most-used CDS section)
2. Hand-verified accuracy measurement on 10 ground-truth schools
3. Per-call cost measurement + cache-hit-rate measurement
4. A deterministic confidence score per extracted value (NOT LLM self-rated)
5. A decision-gate report: continue / kill / reframe

Stretch (only if M1 core is solid):
- Data-quality flags for blank-template and wrong-file archives
- Operator CLI with ack/dismiss for validator flags

## Non-goals

- Replacing the deterministic cleaner with an LLM. The cleaner stays; the LLM fills gaps.
- Extracting fields that aren't in the source document. We don't hallucinate values to boost coverage.
- Building a UI for human review of every LLM-extracted field. Review queue is a database table; frontend surfacing is a separate PRD if/when we need it.
- 100% accuracy. CDS documents themselves have internal inconsistencies; we can't be more accurate than the source.

## Approach — three layers + a closure loop

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: Deterministic cleaner (unchanged, runs first)  │
│   tier4_cleaner.py → values_cleaner                     │
│   Cost: free. Confidence: 1.0.                          │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 2: LLM gap-filler (section-scoped, cached)        │
│   For each CDS section (B1, B2, C1, C9, C10, H1-H7):    │
│     if cleaner filled all expected fields → skip        │
│     else → LLM prompt with schema subset + markdown     │
│     merge LLM values into result with provenance        │
│   Cost: ~$0.01 per section prompt with caching.         │
│   Confidence: 0.3–0.9 based on LLM self-rating.         │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ Layer 3: Cross-field validator (deterministic)          │
│   "men + women ≈ total"                                 │
│   "admit_count ≤ applied_count"                         │
│   "year-over-year values within 5x"                     │
│   Violations flag the values, don't discard them        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
       cds_artifacts.values {qn: {value, source, confidence,
                                  rationale, validator_flags}}
                           │
                           ▼
              ┌────────────────────────┐
              │ Layer 4: Closure loop  │
              │ For each LLM success:  │
              │  extract row pattern   │
              │  → propose cleaner     │
              │    rule                │
              │  → generate PR for     │
              │    human review        │
              │  Accepted rules make   │
              │  next pass cheaper.    │
              └────────────────────────┘
```

### Why this shape

- **LLM as fallback, not replacement.** Cleaner runs deterministically and stays auditable. LLM fills only what's missing. Consumers who want "deterministic only" can filter by `source=cleaner`.
- **Section-scoped prompts, not whole-doc.** 10–15 focused prompts per doc × ~10KB each with prompt caching on the schema. Much cheaper and easier to audit than one giant prompt. Prompt caching cuts ~80% of input tokens since schema fragments are reused across all docs.
- **Per-field provenance, not per-doc.** Today's `values[qn] = {value, source}` becomes `{value, source, confidence, rationale, extractor_version}`. Consumers can filter by confidence, trust-tier, or extractor.
- **Caching keyed by (doc_sha256, section, schema_version, model, prompt_version).** Same doc + same prompt = same result forever. Reproducibility is free; re-runs after cleaner changes only re-do the sections that would actually change.
- **Closure loop is the cost curve.** Every LLM success that matches a reusable pattern graduates to the cleaner via a proposed PR. The LLM works itself out of a job for well-understood patterns. LLM cost decays over time for a stable corpus.

## Milestones

### M1 — Committed scope (~1.5–2 weeks CC)

**M1 absorbs every eng + DX resolution from the review. The spike can't just "ship LLM gap-filling"; it must ship LLM gap-filling with the safety, test, and operability scaffolding that M2+ would otherwise retrofit.**

**M1a — Data model + safety scaffolding (~3 days CC)**

- **Two-artifact-row design (per finding D1).** LLM output writes a NEW `cds_artifacts` row with `producer = 'tier4_llm_gap_filler'`, `kind = 'canonical'`. **Do NOT merge into the tier4_docling notes jsonb** — that's a race. Existing `cds_artifacts.producer` field already supports multi-producer coexistence.
- `values[qn]` shape becomes `{value, source, confidence, rationale, verification, extractor_version}` for BOTH producers. Backfill existing rows with `confidence=1.0, source="cleaner", verification="deterministic"`.
- New `cds_llm_cache` table keyed by `(doc_sha256, cleaner_version, gap_set_sha, section, schema_version, model, prompt_version)`. **`cleaner_version` and `gap_set_sha` are mandatory** so the cache invalidates when the cleaner improves (per Codex finding).
- New `cds_validator_flags` table: `(artifact_id, rule, severity, status, fields, values, reviewed_at, reviewed_by, notes)`. Status enum: `open | acknowledged | dismissed | false_positive`.
- Migration is DO-block guarded with `WHERE values[qn]->>'confidence' IS NULL` for idempotency.

**M1b — Gap-filler worker skeleton (~3 days CC)**

- `tools/extraction_worker/quality_worker.py` polls for docs where `tier4_docling` artifact exists but no `tier4_llm_gap_filler` artifact exists yet.
- Uses `FOR UPDATE SKIP LOCKED` leasing (mirrors existing `worker.py` pattern — per Codex finding).
- CLI: `python -m tools.extraction_worker.quality_worker --once|--daemon --doc-sha=<hash>|--dry-run`. Exit codes: `0=done, 2=budget_tripped, 3=claim_failure`. Structured logs with `event=...` prefix.
- Budget enforcement: hard cap `$1.00/doc/day`, global daily cap `$50`. Enforcement queries `cds_llm_cache` aggregate (NOT in-memory counter — crash-safe).
- In-flight tracking: record cache entry with `status=in_flight` before HTTP call; reconcile on restart.

**M1c — B1 section prompt (the actual LLM work) (~2 days CC)**

- Section-scoped prompt for B1 enrollment only. Input: schema subset (B.101–B.176) + Docling markdown.
- **Prompt injection defense:** wrap markdown in `<document>untrusted</document>` tags; primary defense is source-text verification (next bullet).
- LLM returns `{question_number, value, source_text_quote}` for each field. Source text is verbatim — a post-process step verifies it appears in the markdown. If not, field is nulled with `verification="source_not_found"`.
- **Deterministic confidence** (NOT LLM self-rating):
  - `1.0` = source text found verbatim + cross-field validator passes
  - `0.7` = source text found + no cross-field check available
  - `0.3` = source text found approximately (fuzzy match within edit distance N)
  - `0.0` = source text not found → value nulled, flag raised

**M1d — Test harness + golden regression (~2 days CC)**

- Expand `score_tier4.py` with `--include-llm` mode that merges LLM output before scoring.
- Build 10 ground-truth YAMLs for B1 fields on 10 schools (6 new beyond existing Harvard/Yale/Dartmouth/HMC). Target: 3 Ivies, 3 state schools, 4 community colleges.
- `tools/extraction-validator/llm_prompt_ab.py`: when `prompt_version` changes, re-run golden set, diff new vs cached old, require explicit sign-off.
- Unit tests: gap-set computation, source-text verification (pos+neg), cache hit/miss, cross-field validators, worker concurrency (2 parallel workers on same doc).

**M1e — Decision-gate report (~1 day CC)**

- Run against 20 low-B1-coverage docs from corpus survey.
- Report: accuracy on 10 GT schools (should be ≥95%), cost per doc (target <$0.05), cache-hit rate on second run (target >90%), number of values with `verification="source_not_found"` (hallucination rate).
- **Decision gate questions:**
  - Is accuracy ≥95% across all 10 GT schools? (technical viability)
  - Is cost per doc < $0.05? (economic viability)
  - Has any user said "I need B1 fields for schools X, Y, Z that you don't have"? (demand viability)
- **Outcomes:** continue to M2 / reframe (different scope or section priority) / kill (extraction isn't the moat).

### Conditional follow-ups (NOT committed)

Below is the original M2–M5 plan. These stay in the doc as reference material. **Nothing here is approved work** — each becomes committable only if the M1 decision gate passes AND specific criteria below are met.

#### M2 — Full section coverage (~2 weeks)

**Gate:** M1 accuracy ≥95% AND cost per doc <$0.05 AND a named user has said they need fields outside B1.

- Section-scoped prompts for every major CDS section: A (metadata), B1, B2, B3, B4, B11, B22, C1, C2, C7, C8, C9, C10, C11, C12, C13–C22 (admission policies), D (transfer), E (academic offerings), F (student life), G (cost), H1–H7 (financial aid), I (athletic).
- Each prompt pulls the relevant schema subset. Total ~15 prompts per doc.
- Worker: `tools/extraction_worker/quality_worker.py` polls `cds_artifacts` where `producer=tier4_docling` and needs gap-filling, runs the pipeline, writes back.
- Budget guard: hard cap on LLM calls per doc per day, configurable.
- Run against the full corpus (~1,675 docs × 15 prompts × $0.01 = ~$250 one-time).

#### M3 — Validator + anomaly flagging (~1 week)

**Gate:** either M2 passed AND review-queue fatigue is manageable, OR user signal specifically asks for quality flags on existing extracted data.

- Cross-field validator rules in code: men+women≈total, admit≤applied, enrolled≤admitted, percentages sum to 100, test scores in valid ranges, etc.
- Cross-year validator: flag any value that's > 5× neighboring years (catches decimal errors and Docling scrape misalignments).
- Cross-school validator: flag values > 3σ outside IPEDS peer-group median (catches blank-template scenarios like Cal Poly SLO).
- Violations populate `notes.validator_flags[]`. Visible via a new `cds_manifest.quality_flags` view column.

#### M4 — Closure loop (CSV + human-authored rules) (~1 week)

**Gate:** M2 passed AND patterns emerging from LLM successes show clustering signal in informal review.

**Scope reduction from original PRD:** no clustering research. M4 = a nightly `propose_cleaner_rules.py` script that exports captured LLM-success patterns (label, question_number, value, context) to `docs/proposals/YYYY-MM-DD-rule-NNN.md`. Operator reviews the CSV/markdown, hand-authors any rule updates, opens a PR manually. Rule threshold: N=10+ schools sharing a pattern (not N=3 — per Codex finding).

- Pattern extractor: for each LLM success, capture the exact row/block of markdown the value came from, plus the label structure, plus the section context.
- Rule proposer: cluster captured patterns by label shape. When N+ schools share a new pattern (threshold = 3), propose a new `_FIELD_MAP` entry in a draft PR.
- PR includes: (a) the proposed rule diff, (b) scorer regression run showing GT still green, (c) corpus-survey delta showing how many docs gain coverage.
- Human reviews and merges. Accepted rules close the loop.

#### M5 — Continuous operation (~ongoing)

**Gate:** M2 + M3 shipped AND operator is actively managing the review queue.

- Integration with the existing extraction worker: quality-worker runs after tier4_docling writes a new artifact. Incremental.
- Re-process triggers: when the cleaner bumps version, mark affected artifacts for re-processing in the background.
- Quality trends dashboard: per-section coverage over time, LLM cost trend, pattern-proposal acceptance rate.
- Weekly review-queue digest for the operator.

## Data-model changes

### `cds_artifacts.notes.values` (shape update)

Before:
```json
{"B.101": {"value": "764", "source": "tier4_cleaner"}}
```

After:
```json
{
  "B.101": {
    "value": "764",
    "source": "tier4_cleaner",
    "confidence": 1.0,
    "rationale": null,
    "extractor_version": "0.1.0"
  },
  "B.102": {
    "value": "3",
    "source": "llm_gap_filler",
    "confidence": 0.85,
    "rationale": "Row labeled 'Other first-year, degree-seeking' in the B1 Full-Time table, Men column.",
    "extractor_version": "claude-sonnet-4-6-2026-04"
  }
}
```

### New table: `cds_llm_cache`

```sql
create table public.cds_llm_cache (
  id             uuid primary key default gen_random_uuid(),
  doc_sha256     text not null,
  section        text not null,
  schema_version text not null,
  model          text not null,
  prompt_version text not null,
  response       jsonb not null,
  input_tokens   integer,
  output_tokens  integer,
  cost_cents     integer,
  created_at     timestamptz not null default now(),
  unique (doc_sha256, section, schema_version, model, prompt_version)
);
```

No RLS public-read (this is worker-only state). Backfill: empty on creation.

### New column: `cds_artifacts.notes.validator_flags` (array)

```json
{"validator_flags": [
  {"rule": "men_plus_women_eq_total",
   "fields": ["B.101", "B.126", "B.104"],
   "values": [764, 877, 1640],
   "severity": "warning"}
]}
```

### New manifest exposure

`cds_manifest.quality_score` — 0.0–1.0 derived from (fields-populated / expected-fields) × (1 − weighted-validator-flags). Surfaced to the API.

## Cost envelope (M1 only)

| Line | Cost |
|---|---|
| M1 pilot: 20 docs × 1 section (B1) | ~$0.20 |
| M1 hand-verification of 10 GT schools | your time, ~2 hours |
| M1 CC implementation time | ~1.5–2 weeks |
| M1 total cash | **~$2, negligible** |

Prompt-caching assumption: schema subset (~5KB) is cached per section across docs; document markdown (~5KB) is fresh per call. **M1 measures cache-hit rate directly** — if < 50% we renegotiate the prompt structure before any corpus-wide run.

**Conditional M2–M5 cost** (only spent if gates pass, shown for reference):
- M2 full corpus: ~$250 one-time
- Steady state: ~$15/month
- **Annual M2+ steady state:** ~$500/year

## Risks

1. **Hallucination.** LLM fabricates a plausible number not present in the source. **Mitigation:** require the prompt to return both the extracted value AND the verbatim source text it came from. A post-process step verifies the source text appears in the markdown. If not, the field is null'd and logged.
2. **Cost runaway.** Worker loop + LLM failures + retries → unbounded spend. **Mitigation:** hard budget cap per doc per day (default: $1.00), global daily cap ($50), alerting on threshold.
3. **Model drift.** Future Claude updates produce different outputs for the same prompt. **Mitigation:** cache key includes model ID. Old cache entries stay; new model creates new entries; we compare and evolve. Consumer-facing `extractor_version` lets users pin.
4. **Feedback-loop mis-generalization.** Rule proposer generates a regex that matches wrong rows in other schools. **Mitigation:** proposed rules are human-reviewed. Scorer regression must stay green. Proposal includes a corpus-wide impact diff.
5. **Review-queue fatigue.** Validator flags accumulate faster than humans can triage. **Mitigation:** severity tiers; only critical severity blocks the field from the API. Warnings are metadata.
6. **Prompt-cache miss.** If prompt-caching implementation is wrong, costs balloon. **Mitigation:** M1 verifies cache-hit rate before scaling.

## Open questions

- **Model choice.** Claude Sonnet 4.6 is the default. Haiku might be 3x cheaper and good enough for most sections. Should we stratify: Haiku for simple sections (B2, C13), Sonnet for complex (H financial aid)?
- **Validator rule source.** Hardcode rules in Python, or schema-annotate (add `relations: [{expr: "men + women == total"}]` to the canonical schema JSON)? Schema-annotation is more reusable but requires a schema-builder change.
- **Review-queue UX.** How do operators actually review proposed rules and flagged values? CLI? Web admin? Issue-tracker integration? Out of scope for this PRD but needs a follow-up.
- **Multi-producer coexistence.** Do we always store both cleaner-only and cleaner+LLM as separate artifacts (two rows), or single artifact with merged values (one row)? Single-row keeps consumers simple but loses the ability to compare.

## Success criteria

### M1 (committed)

All three must be true to advance beyond M1:

1. **Technical:** ≥95% accuracy across all 10 ground-truth B1 schools. Zero `verification="source_not_found"` values shipped (they must be nulled, not ignored).
2. **Economic:** < $0.05 per doc for one section. Cache-hit rate ≥90% on second run.
3. **Demand:** at least one named user has explicitly asked for B1 coverage for schools currently missing it, OR the operator has a specific use case in mind they can articulate in a Slack/email thread before the gate.

If all three: M2 gate opens.
If technical + economic but not demand: **reframe** — this is where the review said the biggest risk lives. Do user research before M2.
If technical fails: **kill** — LLM gap-filling isn't the answer here.
If economic fails: **optimize** — switch to Haiku for this section or change prompt structure.

### Conditional M2–M5 (only if gates pass)

- M2: Full corpus median fields-populated rises from 25 → 100+ per doc. No GT regression.
- M3: Validator catches all three known blank-template / wrong-file docs at `severity=critical`.
- M4: ≥5 accepted cleaner rules in first month. LLM call rate drops ≥20% per accepted rule.
- M5: Operator spends < 30 min/week on review queue.

## Out of scope (and where it goes)

- Frontend exposure of confidence/provenance → separate PRD when we need it
- Cleaner authoring UX for non-engineers → future work, backlog item
- Reducto integration (would share this pipeline if sponsorship materializes) → not this PRD
- Tier 5 OCR fallback for image-only PDFs → separate milestone
- Multi-model consensus (Sonnet + GPT + verify) → defer to M6 if quality ever becomes the bottleneck

---

*Initial draft generated from the Phase 4 corpus-survey learnings. Reviewed via `/autoplan` on 2026-04-17, approved with scope reduction to M1-only + all eng/DX resolutions folded in. Original scope archived in restore file referenced at top of this document.*

---

## Decision Audit Trail (from /autoplan)

| # | Phase | Decision | Classification | Principle | Rationale |
|---|---|---|---|---|---|
| 1 | CEO | Accept premise 1 (rule ceiling) | Mechanical | P6 | Evidence: 4 phases of tuning only hit 2% |
| 2 | CEO | Accept premise 5 (per-field provenance) | Mechanical | P1 | Minor jsonb cost for meaningful capability |
| 3 | CEO | Challenge premise 3 (cost decay via closure loop) | Taste (at gate) | P6 | Both voices disagree; surfaced to user |
| 4 | CEO | Challenge premise 4 (consumer demand) | User Challenge (at gate) | P6 | Both voices strongly disagree with user's stated direction |
| 5 | CEO | Mode = SELECTIVE EXPANSION with kill-switch | Mechanical | P2 | Scope cannot expand without evidence |
| 6 | CEO | Add 4 new alternatives (E, F, G) to table | Mechanical | P1 | Both voices flagged alternatives as missing |
| 7 | Eng | Two-artifact-row design (not merged jsonb) | Mechanical | P3 | Both voices identify as race condition |
| 8 | Eng | Cache key includes cleaner_version + gap_set_sha | Mechanical | P3 | Codex finding; stale cache otherwise |
| 9 | Eng | Budget enforcement via DB aggregate | Mechanical | P5 | Crash-safe requires this; no in-memory counters |
| 10 | Eng | Prompt-injection defense in M1 | Mechanical | P1 | Hostile markdown is plausible; defense is cheap |
| 11 | Eng | Confidence = deterministic (verification-based) | Mechanical | P5 | Both voices reject LLM self-rating |
| 12 | Eng | 10 GT schools for M1 (not 3) | Mechanical | P1 | n=3 is statistical noise |
| 13 | Eng | A/B harness in M1 | Mechanical | P1 | Prompt changes otherwise untestable |
| 14 | Eng | Validator fails loud, not silent | Mechanical | P1 | L3 silent failure is worst-case |
| 15 | Eng | M4 = CSV + human-authored rules | Mechanical | P5 | Clustering is research; defer or simplify |
| 16 | Eng | Rule threshold = 10+ schools (not 3) | Mechanical | P4 | 3 is too low for production rule change |
| 17 | Eng | Manifest view via CREATE OR REPLACE additively | Mechanical | P5 | Avoids downtime; staging test required |
| 18 | Eng | Worker uses FOR UPDATE SKIP LOCKED | Mechanical | P3 | Mirrors existing `worker.py` pattern |
| 19 | DX | Worker CLI with exit codes + structured logs | Mechanical | P5 | Operability table-stakes |
| 20 | DX | `cds_validator_flags` table + review CLI | Mechanical | P1 | Target is fiction without this |
| 21 | DX | `docs/runbooks/quality-worker.md` + operator README | Mechanical | P5 | Docs discoverability, onboarding |
| 22 | Phase 4 | Accept scope reduction to M1-only | **User decision** | Option A | Chosen via AskUserQuestion at final gate |

22 decisions total: 20 auto-decided + 1 user challenge (resolved to scope reduction) + 1 explicit user choice.

---

## /autoplan Review Report

The review findings are preserved below for reference.



---

# Review Report (via /autoplan)

## Phase 1 — CEO Review

### 0A Premise challenge

| # | Premise | Challenge | Verdict |
|---|---|---|---|
| 1 | Rule-based extraction has a ceiling | Evidence: 4 phases, 2% corpus-wide coverage. | ACCEPT |
| 2 | LLM can bridge the gap reliably | Untested. M1's 20-doc sample is the validation gate. | ACCEPT with gate |
| 3 | Cost will decay via closure loop | **CHALLENGED** by both voices. Long-tail patterns (OCR, wrapped cells, community-college variants) don't generalize. Closure loop may produce rules matching 3 schools, not 30. | CHALLENGE |
| 4 | Consumers want 80% coverage | **CHALLENGED** by both voices. Site is 2 days old. Zero user signals. | CHALLENGE (critical) |
| 5 | Per-field provenance is the right abstraction | Consumers who don't need it pay a tiny jsonb tax. | ACCEPT |

### 0B Existing-code leverage

~60% of the plan extends existing infrastructure: `tier4_cleaner._parse_markdown_tables`, `cds_artifacts.notes` jsonb, `worker.py`, `score_tier4.py`, `corpus_survey_tier4.py`. Net-new: LLM cache table, anomaly validator, rule proposer.

### 0C Dream state

```
CURRENT                        THIS PLAN (M5)                   12-MONTH IDEAL
─────────────                  ──────────────                   ────────────────
25 fields/doc                  100+ fields/doc                  200+ fields/doc
Implicit confidence 1.0        Per-field confidence             Multi-producer consensus
No quality signal              Quality score + flags            Cross-year time series
No user signal                 ???                              Named audience served
```

The missing box is "named audience served." Both voices flagged this gap.

### 0C-bis Implementation alternatives (expanded per Codex flag that this was missing)

| # | Approach | Effort | Risk | Pros | Cons |
|---|---|---|---|---|---|
| A | **PRD as drafted** (M1–M5) | 6 weeks | Medium | Full coverage; cleaner improves | Over-scoped; premise #4 unvalidated |
| B | **M1 only, then stop** (20-doc spike + decision) | 1 week | Low | Cheap learning; respects user-signal absence | Doesn't fix the coverage gap yet |
| C | **Reducto-only** (drop LLM gap-filler, pay for hosted) | 1 week | Low if funded | Offload quality problem | Sponsorship risk; cost per doc ongoing |
| D | **Community-cleaners first** (publish raw, invite PRs, ADR 0002) | 2 weeks | High | Distributed labor; free | Requires community; may never materialize |
| E | **Anomaly detection only** (Layer 3 without Layer 2) | 2 weeks | Low | Flags data quality without expanding extraction | Doesn't expand coverage |
| F | **Top-N schools only** (hand-verify aid+admissions for ~50 popular schools) | 2 weeks | Low | High value per unit effort; serves a real audience | Manual; doesn't scale |
| G | **"Ask the CDS" conversational UI** (LLM over raw PDF per query) | 3 weeks | Medium | Directly serves the user question, not the field extraction | On-demand LLM cost per query; no quality gate |

### 0D Mode — SELECTIVE EXPANSION (revised per review)

The revised mode is tighter than the initial "hold scope + expand closure loop." Both voices argue for **SCOPE REDUCTION to M1 only** with M2+ conditional on user signal OR a clear falsifiable success criterion.

### 0E Temporal — revised

- Week 1: M1 pilot. 20-doc B1 extraction + hand-verify. Publish cost, accuracy, cache-hit rate.
- Week 1 end: **decision gate** — does the evidence justify M2-M5? User-signal check.
- Conditional weeks 2-8: M2-M5 only if gate passes; otherwise loop back to "what do users actually want?"

### 0F Mode — REVISED

Mode is now **SELECTIVE EXPANSION with hard gate after M1**. Default: ship M1 only. Expand to M2-M5 only if M1 evidence + user-signal evidence both land.

### Dual voices — CEO consensus

**CLAUDE SUBAGENT (CEO — strategic independence)**

> 1. Wrong problem framing (CRITICAL) — consumer demand is assumed. 10x reframe: interview 5 potential users first.
> 2. Unstated premises (HIGH) — closure loop is load-bearing and unverified. Cache-hit rate unverified.
> 3. 6-month regret scenario (CRITICAL) — "the plan produces a prettier grave." 26 hours/year volunteer time for review queue.
> 4. Alternatives table missing from doc (MEDIUM) — document didn't actually preserve the options.
> 5. Competitive risk (HIGH) — IPEDS/Scorecard + frontier models; moat is archive not extraction.
> 6. Scope calibration (CRITICAL) — **collapse to M1 only, make M2+ conditional on a named user asking.**

**CODEX SAYS (CEO — strategy challenge)**

> - Main demand premise is asserted, not proven. Product vanity unless you name the user and job.
> - Closure loop is weakest premise, presented as established. Long tail (OCR, wrapped cells, template drift) doesn't collapse into durable `_FIELD_MAP` entries. "LLM self-rated confidence" is not credible.
> - M2 is reckless for this stage. 6 weeks of platform-building for a 2-day-old site with no paying users.
> - Alternatives section literally missing — strategy failure.
> - Moat is provenance + archive + ugly-source handling, not extraction breadth. PRD spends ambition on the easiest thing for bigger players to copy.
> - Budget is fine ($500/yr). Founder-weeks is the issue.

**CEO DUAL VOICES — CONSENSUS TABLE**

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Premises valid? | NO | NO | **DISAGREE with PRD** |
| 2. Right problem to solve? | NO | NO | **DISAGREE with PRD** |
| 3. Scope calibration correct? | NO | NO | **DISAGREE with PRD** |
| 4. Alternatives sufficiently explored? | NO | NO | **DISAGREE with PRD** |
| 5. Competitive/market risks covered? | NO | NO | **DISAGREE with PRD** |
| 6. 6-month trajectory sound? | NO | NO | **DISAGREE with PRD** |

**6 of 6 dimensions: both models disagree with the PRD's original scope.** This is a **USER CHALLENGE** — surfaced at the final gate, never auto-decided.

### User Challenge — scope reduction

- **What the user said (in the /autoplan args):** design a multi-milestone pipeline (M1-M5) with closure loop, validator framework, and continuous operation.
- **What both models recommend:** collapse to M1 only. Gate M2+ on either (a) named-user evidence that missing fields block a real use case, or (b) a falsifiable hypothesis about which audience is underserved.
- **Why:** site is 2 days old with no user signal; LLM closure loop is the weakest premise; extraction breadth is the easiest thing for frontier labs to copy; moat is the archive itself.
- **What context we might be missing:** the user has direct knowledge of the audience they're building for (perhaps IR professionals, journalists, CDS nerds) and may have a specific information-completeness target in mind that the models don't see.
- **If we're wrong, the cost is:** if the user has validated demand we don't know about and we scope down, they ship the coverage expansion 5 weeks later than they could have.

### Mandatory outputs

**NOT in scope** (from the PRD as-written):
- Frontend UX for review queue (separate PRD)
- Multi-model consensus (deferred to M6)
- Cleaner-authoring UI for non-engineers (backlog)
- Tier 5 OCR fallback
- Reducto integration (separate if sponsorship)

**What already exists** (reuse):
- `tier4_cleaner._parse_markdown_tables` — the markdown parser
- `tools/extraction_worker/worker.py` — polling pattern
- `tools/extraction-validator/score_tier4.py` — regression gate
- `tools/extraction-validator/corpus_survey_tier4.py` — coverage gauge
- `cds_artifacts.notes` jsonb — field-level storage
- `schemas/cds_schema_2025_26.json` — canonical field list

**Error & Rescue Registry**

| # | Error | Trigger | Rescue |
|---|---|---|---|
| 1 | LLM hallucinates value | Source text not in markdown | Null the field + log |
| 2 | Cost runaway | Per-doc LLM cap exceeded | Stop + alert operator |
| 3 | Proposed rule fails scorer | New `_FIELD_MAP` entry breaks GT | PR blocked by CI |
| 4 | Cache poisoning | Model ID mismatch in cache key | New entry, old retained |
| 5 | Validator false positive | Cross-field rule triggers on legit value | Severity = warning, not blocking |

**Failure Modes Registry**

| # | Failure | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Closure loop produces no durable rules | High (per both voices) | Cost stays flat forever | M1 measures rule-acceptance rate; kill if < 5 in first month |
| 2 | Prompt cache hit rate < 50% | Medium | Budget 2x planned | M1 verifies cache behavior |
| 3 | Review-queue fatigue | High | Operator abandons | Severity tiers; critical-only blocks API |
| 4 | Frontier model ships competing extractor | High (within 12 months) | Our pipeline becomes irrelevant | Acknowledged; moat must be archive+provenance not extraction |
| 5 | No one uses the expanded coverage | Unknown | Wasted 6 weeks + $250 | **M1 gate decision** |

**Dream state delta**

The PRD moves the "current" → M5 delta significantly, but both voices argue **it moves the wrong axis.** The high-leverage gap is not "fields per doc" but "named audience served." M5 as written still doesn't have users. The revised recommendation: spend the gap on audience validation, not extraction breadth.

### Phase 1 completion summary

| Item | Status |
|---|---|
| Premises | 2 of 5 challenged by both voices |
| Alternatives | 7 now in doc (was 4 referenced but missing) |
| Scope | 6/6 dimensions flagged for reduction |
| Dual voices | Both ran, both agreed |
| User Challenge | **Raised for final gate** |

---

## Phase 2 — Design Review

**SKIPPED.** No UI scope detected in PRD 003 (1 match, threshold 2+). This is a backend pipeline; UX for review queue is explicitly out-of-scope.

---

## Phase 3 — Eng Review

### Architecture ASCII diagram

```
                   ┌─────────────────────┐
                   │ tier4_docling       │  existing
                   │ writes artifact     │  producer=tier4_docling
                   │ notes: {markdown,   │  kind=canonical
                   │        values}      │
                   └──────────┬──────────┘
                              │
                              ▼  listens for new rows
                   ┌─────────────────────┐
                   │ quality_worker      │  NEW — runs AFTER tier4_docling
                   │ 1. read markdown    │  uses FOR UPDATE SKIP LOCKED
                   │ 2. compute gap set  │  (concurrent-safe)
                   │ 3. LLM per section  │
                   │ 4. validate output  │
                   └──────────┬──────────┘
                              │
                              ▼  writes SEPARATE row (see finding D1)
                   ┌─────────────────────┐
                   │ new cds_artifacts   │
                   │ producer=           │
                   │   llm_gap_filler    │
                   │ notes.values        │
                   └─────────────────────┘

                   ┌─────────────────────┐
                   │ cds_llm_cache       │  NEW — keyed on
                   │ (sha, cleaner_ver,  │  cleaner_version too
                   │  gap_set, section,  │  (per Codex finding)
                   │  model, prompt_ver) │
                   └─────────────────────┘
```

### Scope challenge

The PRD layers (1 cleaner + 2 LLM + 3 validator + 4 closure loop) are correctly scoped at the *functional* level, but the **implementation coupling across layers is not**. L4 needs structured provenance from L2 (not prose rationale); L3's failure is silent (should fail loud); L2 and L1 must write separate artifact rows (not merge into one jsonb field — races).

### Dual voices — Eng consensus

**CLAUDE SUBAGENT (eng — independent review)**

Highlights:
- **A1 (HIGH):** L4 needs structured provenance `{table_id, row_label_raw, column_header, char_span}`, not prose rationale.
- **E1 (HIGH):** Malformed JSON from LLM not handled. Retry-once + fail-closed.
- **E4 (HIGH):** Closure-loop rule threshold N=3 is far too low. Raise to 10+, require full GT scorer pass, add control set.
- **T1 (HIGH):** n=3 hand-verification is not a statistic. Need ground-truth YAMLs for 10 of the 20 sample docs.
- **T2 (HIGH):** No A/B harness for prompt-version changes. Must exist at M1.
- **S1 (HIGH):** Prompt injection via hostile CDS markdown. Sanitize + XML-delimit + source-text verification.
- **D1 (HIGH):** Concurrent writers racing on `cds_artifacts.notes`. **Two artifact rows, not one.**
- **H4:** LLM self-rated confidence is not credible. Derive from verification signals.

**CODEX SAYS (eng — architecture challenge)**

Highlights:
- **Artifact model unresolved** — PRD conflates "single row with merged values" vs "two rows, one per producer." Must choose two-row before M2.
- **Cache key wrong** — must include cleaner_version; stale when cleaner improves.
- **Concurrent workers bypass budget caps** — caps must be DB-aggregated (`SELECT sum(cost_cents) FROM cds_llm_cache WHERE created_at > now() - '1 day'`), not in-memory.
- **Prompt injection** — public `notes.markdown` is school-authored; feeding directly to LLM is unsafe without sanitization.
- **Manifest complexity understated** — `cds_manifest` view doesn't expose `notes` today; adding flags needs `CREATE OR REPLACE VIEW` with staging test.
- **M4 clustering is research, not glue** — either prototype in M1 or scope M4 to CSV-export + human-authored rules.

**ENG DUAL VOICES — CONSENSUS TABLE**

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Architecture sound? | NO (D1 race) | NO (artifact model) | **DISAGREE** |
| 2. Test coverage sufficient? | NO (n=3, no prompt A/B) | NO (no golden regression) | **DISAGREE** |
| 3. Performance risks addressed? | NO (cache growth) | NO (cache key wrong) | **DISAGREE** |
| 4. Security threats covered? | NO (prompt injection) | NO (RLS + keys thin) | **DISAGREE** |
| 5. Error paths handled? | NO (malformed JSON) | NO (lease/claim) | **DISAGREE** |
| 6. Deployment risk manageable? | NO (concurrent write) | NO (rollback unspec) | **DISAGREE** |

### Resolutions (must be incorporated into M1)

| # | Finding | Resolution |
|---|---|---|
| R1 | Two workers race on notes jsonb | Write LLM output as **separate artifact row** with `producer=llm_gap_filler`. No merge. |
| R2 | Cache key stale when cleaner improves | Cache key includes `cleaner_version` AND the gap-set (SHA of missing question numbers). |
| R3 | Budget cap bypass | Budget enforcement queries `cds_llm_cache` aggregate, not in-memory counter. |
| R4 | Prompt injection | Wrap markdown in `<document>untrusted</document>`, sanitize `(ignore\|system:\|assistant:)` patterns, primary defense is source-text verification. |
| R5 | LLM self-rated confidence | Remove. Derive confidence from source-text verification (binary) + cross-field validator (binary) + peer-school plausibility (3σ). |
| R6 | n=3 M1 gate | Require 10 ground-truth YAMLs. Reuse `score_tier4.py` with an `--include-llm` mode. |
| R7 | Prompt regression non-determinism | Golden-set A/B harness: new `prompt_version` reruns 10 GT docs, diffs vs cached old, operator sign-off required. Must exist at M1. |
| R8 | L3 silent failure | Validator failure marks artifact `validation_pending` until next run; doesn't silently pass. |
| R9 | Pattern clustering research | Scope M4 down to "CSV export of (label, qn, value, pattern) + human-authored rules." Defer actual clustering. |
| R10 | Manifest view migration | Use `CREATE OR REPLACE VIEW` additively; test in staging; coordinate with web/ frontend queries. |
| R11 | Worker concurrency | Use Postgres `FOR UPDATE SKIP LOCKED` on a new `cds_llm_jobs` lease table, or reuse existing pending-queue pattern from `worker.py`. |
| R12 | Backfill idempotency | Migration DO-block guarded by `WHERE values[qn]->>'confidence' IS NULL`. |

### Test diagram (NEW UX flows / data flows / codepaths)

| Codepath | Test type | Exists? | Gap |
|---|---|---|---|
| Gap-detection (what's missing per section) | Unit, schema-driven | NO | Add `tests/test_gap_set.py` |
| LLM section prompt (B1) | Golden test vs 10 GT docs | NO | Add `tests/test_llm_b1_golden.py` with cached responses |
| Source-text verification | Unit, pos + neg cases | NO | Add `tests/test_source_verify.py` |
| Cache hit/miss | Unit with mocked supabase | NO | Add `tests/test_llm_cache.py` |
| Validator rules (men+women≈total) | Unit, pos + neg + edge | NO | Add `tests/test_validators.py` |
| Worker lease/claim under concurrency | Integration with 2 parallel workers | NO | Add `tests/test_worker_concurrency.py` |
| Backfill migration idempotency | Integration, re-run | NO | Add to migration suite |
| Prompt-version A/B harness | Command-line script + golden diff | NO | Add `tools/extraction-validator/llm_prompt_ab.py` |

**Test plan artifact written to:** `~/.gstack/projects/bolewood-collegedata-fyi/main-test-plan-20260417.md` (inlined here to avoid writing another file).

### Failure modes (critical gaps)

| # | Failure | Severity | Blocks M1? |
|---|---|---|---|
| D1 | Two workers race on notes jsonb | CRITICAL | YES — must ship two-row design |
| E1 | Malformed JSON not handled | HIGH | YES — must have retry + fail-closed |
| S1 | Prompt injection | HIGH | YES — must have sanitize + source-verify |
| T1 | n=3 hand-verify | HIGH | YES — must require 10 GT |
| H4 | LLM self-rated confidence | HIGH | YES — must use deterministic signals |
| A1 | Structured provenance | MEDIUM | No (only blocks M4) |
| R9 | Clustering as glue | MEDIUM | No (M4 rescope) |

**Five of seven must be addressed in M1**, not deferred.

### Eng completion summary

The PRD's layered architecture is directionally right but **M1 as drafted is underspecified on safety, concurrency, and testing.** Before M1 ships:
- Two-artifact-row design must replace "merge into one jsonb"
- Cache keying must include cleaner_version
- Budget enforcement must be DB-aggregated
- Prompt injection defense must be in the first prompt
- Confidence must be deterministic, not LLM-self-rated
- 10 GT docs + A/B harness must exist before M1 evaluation

These are 1-2 days of additional M1 scope. Worth doing because they're table stakes, not bells.

---

## Phase 3.5 — DX Review [subagent-only]

Codex call stalled; proceeded with Claude subagent only. Output tagged per degradation matrix.

### Developer journey (operator persona)

The "developer" here is the maintainer/operator (one person). The worker is internal tooling, not a shipped developer product.

| Stage | Today | After M5 as drafted | Target |
|---|---|---|---|
| Start worker | `python worker.py` (documented) | `quality_worker.py ?` (undefined) | `python -m tools.extraction_worker.quality_worker --once\|--daemon` |
| See budget status | n/a | mentioned, no command | `psql -c "SELECT sum(cost_cents) ..."` or worker status subcommand |
| Review proposed rules | n/a | "generates a PR" (by what?) | `docs/proposals/YYYY-MM-DD-rule-NNN.md` files + `gh pr create` one-liner |
| Triage queue | n/a | "< 30 min/week" (how?) | `quality_worker review --next` CLI with ack/dismiss |
| Understand failure | n/a | unclear | Structured log events + heartbeat row |
| Debug one doc | n/a | undefined | `--dry-run --doc-sha=<hash>` flag |
| Onboard new maintainer | n/a | undefined | Runbook at `docs/runbooks/quality-worker.md` |

### Dual voices

**CLAUDE SUBAGENT (DX — independent review)**

All 5 findings were HIGH/SEVERE except #4 and #5 (MEDIUM):
- **DX1 (HIGH):** Worker start/stop/observe unspecified. No exit codes, no log format, no "why did it stop" distinguishability.
- **DX2 (HIGH):** PR proposer contract unspecified — GitHub App? Local script? CSV? M4 body and R9 resolution contradict.
- **DX3 (HIGH):** Review queue target "< 30 min/week" has zero mechanism; no table, no CLI, no ack/dismiss.
- **DX4 (MEDIUM):** Docs discoverability — where is `README.md`? Runbook? Cost dashboard?
- **DX5 (MEDIUM):** Second-maintainer handoff has no credentials checklist, no `--dry-run`, no local smoke test.

**CODEX:** call did not return in time window. Not run. Findings are subagent-only. Recommend operator re-run DX voice during implementation if a second opinion is wanted.

**DX DUAL VOICES — CONSENSUS TABLE** (subagent-only)

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| 1. Getting started < 5 min? | NO | — | N/A (single voice, flagged) |
| 2. CLI naming guessable? | NO | — | N/A |
| 3. Error messages actionable? | NO | — | N/A |
| 4. Docs findable & complete? | NO | — | N/A |
| 5. Upgrade path safe? | NO | — | N/A |
| 6. Dev environment friction-free? | NO | — | N/A |

### DX scorecard (subagent ratings)

| Dimension | Score 0-10 |
|---|---|
| Getting started | 3 (undefined) |
| CLI ergonomics | 3 |
| Error actionability | 4 |
| Docs | 2 |
| Upgrade path | N/A |
| Escape hatches | 3 |
| Second-maintainer handoff | 2 |
| **Overall DX** | **~3/10** |

Low score reflects that the PRD specifies *what the worker does* thoroughly but almost nothing about *how a human lives with it*.

### DX resolutions (to be incorporated into M1)

| # | Finding | Resolution |
|---|---|---|
| DX-R1 | Worker CLI | `python -m tools.extraction_worker.quality_worker --once\|--daemon --doc-sha=<hash>\|--dry-run`. Exit codes: 0=done, 2=budget, 3=claim failure. Structured logs with `event=...` prefix. |
| DX-R2 | PR proposer | Nightly `propose_cleaner_rules.py` writes `docs/proposals/*.md` (patch + summary). Operator runs `gh pr create` manually with proposal as template. No GitHub App in M4. |
| DX-R3 | Review-queue | New `cds_validator_flags` table with `(artifact_id, rule, severity, status, reviewed_at, reviewed_by, notes)`. CLI: `quality_worker review next\|ack <id>\|dismiss <id> --reason=...`. |
| DX-R4 | Docs location | `tools/extraction_worker/README.md` + `docs/runbooks/quality-worker.md`. Cost dashboard = `cds_llm_cost_daily` SQL view + one-liner in README. |
| DX-R5 | Onboarding | Env-var table + 10-min smoke test + scratch-schema toggle, in the runbook. |

### DX completion summary

M1 + M5 must ship DX alongside functionality. The < 30 min/week review-queue target (a success criterion) is **fiction without the review CLI + validator-flags table.** This is in scope for M1, not M5.

---

## Cross-phase themes

Three themes surfaced in 2+ phases independently (high-confidence signal):

1. **M1 is load-bearing for the whole plan.** CEO says "gate M2+ on M1 evidence + user signal." Eng says "M1 must already include two-row design, 10 GT, prompt injection defense, deterministic confidence, A/B harness." DX says "review CLI and runbook are M1 scope." Converging message: **make M1 substantially tighter and larger, kill M2-M5 as automatic follow-ons.**
2. **"LLM self-rated confidence" is not a real signal.** Flagged in CEO dual voices AND eng dual voices AND independently by subagent. Replace with deterministic signals (source verification + cross-field validator + peer plausibility).
3. **Moat is archive + provenance, not extraction breadth.** CEO phase (both voices). Eng phase independently surfaces the multi-producer precedence problem. DX phase surfaces missing ops story. All roads point toward: **publish the raw markdown well, trust users/community for long-tail extraction.**

---

## NOT in scope (revised after review)

From the original PRD:
- Frontend UX for review queue
- Multi-model consensus
- Cleaner-authoring UI for non-engineers
- Tier 5 OCR fallback
- Reducto integration

Added during review:
- Closure-loop clustering (M4) — rescope to CSV-export + human-authored rules
- Prompt injection red-team exercise — deferred until post-M1 decision
- Cross-school anomaly via IPEDS peer groups — M3 only after M1 gate passes

## What already exists (updated)

As in Phase 1, plus:
- `worker.py` uses `FOR UPDATE SKIP LOCKED` pattern (per Codex finding) — quality_worker should mirror this; don't reinvent
- `cds_artifacts.producer` field supports multi-producer coexistence (per D1 resolution) — no schema change needed for two-row design

---

## Phase 4 — Final Approval Gate

See below.

---
