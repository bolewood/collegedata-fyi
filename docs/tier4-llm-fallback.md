# Tier 4 LLM Fallback

*Last updated: 2026-04-28 (fallback/base compatibility contract added)*

Schema-aware LLM repair layer that runs after the deterministic Tier 4 cleaner
to fill in subsections the hand-coded resolvers can't reach. Scoped, cached,
validated, and cheap enough for a hobby open-source project.

Full design: [PRD 006](prd/006-llm-fallback.md). This doc is the operator
runbook and consumer integration guide.

---

## What it does

The deterministic Tier 4 cleaner (`tier4_cleaner.py`) extracts fields from
Docling markdown by parsing tables and matching row labels against schema
question text. It works well on sections where Docling preserves table
structure (B2 race/ethnicity, B5 graduation rates, I faculty, C7 selection)
but struggles where Docling flattens tables to paragraphs, merges rows, or
renders checkboxes in inconsistent dialects. Those gaps are concentrated in
financial aid (H5–H8), policy dates (C13–C22), transfer (D2–D16), and
estimated expenses (G5).

The LLM fallback:

1. Skips docs the cleaner already covered.
2. For each low-coverage document, slices the markdown by subsection.
3. Sends one prompt per target subsection with the schema's field list,
   known normalization rules, and a worked example — the cacheable glossary
   is identical across every call.
4. Validates every returned field deterministically (type, evidence
   substring, range, row-merge guard, no-synthesized-totals).
5. Caches responses in `cds_llm_cache` so re-runs on unchanged inputs cost
   `$0.00`.
6. Writes a separate `cds_artifacts` row with `producer='tier4_llm_fallback'`
   — the deterministic canonical artifact is never modified.

**Mode B (`fill_gaps`)** is the only shipped merge policy: the deterministic
cleaner always wins; the LLM only populates question numbers the cleaner
left blank.

**Compatibility gate:** a fallback artifact is only mergeable with the
selected `tier4_docling` base artifact it was generated against. New fallback
artifacts stamp `notes.base_artifact_id` and `notes.base_producer_version`.
Legacy fallback artifacts may still merge only when
`notes.markdown_sha256 == sha256(base.notes.markdown)` and
`notes.cleaner_version == base.producer_version`. If neither check passes, the
fallback is stale and must be ignored until re-run.

Measured on the 2024-25 corpus (244 docs backfilled 2026-04-20):
**mean 28.2 fields added per doc**, median 30, `$14.08` total spend
(`~$0.06/doc` at Haiku 4.5 with partial cache hits).

---

## Where the code lives

```
tools/extraction_worker/
├── subsection_slicer.py        # Six-strategy subsection locator
├── llm_client.py               # Anthropic SDK wrapper with prompt caching
├── tier4_llm_fallback.py       # Prompt builder + validator + merge policy
├── llm_fallback_bench.py       # Phase 0 harness (disk output, no DB writes)
└── llm_fallback_worker.py      # Phase 1 worker (writes cache + artifact rows)

supabase/migrations/
└── 20260420140000_cds_llm_cache.sql

tools/extraction-validator/
├── corpus_survey_tier4.py      # --include-fallback: two-producer delta
└── score_tier4.py              # --include-llm-artifact: regression check
```

---

## Eligibility gates

The worker picks a document up when a `tier4_docling` canonical artifact
exists and:

- `notes.stats.schema_fields_populated < --low-coverage-threshold` (default 200), OR
- the document's `data_quality_flag` is `low_coverage` (not `blank_template` or `wrong_file`), OR
- any of the target subsections is empty in the cleaner output

Per-subsection gate: if the cleaner already filled every field in a target
subsection, the worker skips that subsection entirely. Zero cost to call the
fallback on a doc the cleaner handled well.

Target subsections (default):

```
H5, H6, H7, H8       # Financial aid loans + nonresident aid
C13, C14, C15, C16, C17  # Application fee, closing dates, notification, reply
D13, D14, D15, D16   # Transfer credit policies
G5                   # Estimated expenses
```

These were chosen from the PRD 005 execution data (see
[`tier4-cleaner-learnings-for-llm-fallback.md`](research/tier4-cleaner-learnings-for-llm-fallback.md))
as the highest-leverage gaps where Docling's output is recoverable but the
deterministic parser can't handle it.

---

## Operator runbook

### One-time setup

```bash
cd tools/extraction_worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install anthropic
```

Set `ANTHROPIC_API_KEY` in the repo-root `.env`. The Supabase env vars from
the main worker are reused.

### Phase 0: benchmark (no DB writes)

```bash
# Smoke test — single school, single subsection
python llm_fallback_bench.py \
    --school harvard --year 2024-25 --subsections H5 \
    --out-dir ../../scratch/llm-bench/

# Priority subsections across a benchmark slice
python llm_fallback_bench.py \
    --school harvard,dartmouth --year 2024-25 \
    --subsections H5,H6,H7,H8,C13,C14,C15,C16,C17,D13,D14,D15,D16,G5 \
    --max-cost-per-doc 0.10 \
    --out-dir ../../scratch/llm-bench/

# Dry-run (prompt sizes only, no API call)
python llm_fallback_bench.py --dry-run \
    --school yale --year 2024-25 --subsections H5 \
    --out-dir ../../scratch/llm-bench/
```

Each run writes `run-<timestamp>/_manifest.json` + `<school>.json` with
per-subsection costs, cache hit rates, acceptance counts, rejection reasons,
and the slicer strategy that located each subsection.

### Phase 1: production worker (writes to DB)

```bash
# Single school, one subsection (safe smoke test)
python llm_fallback_worker.py \
    --school harvard --year 2024-25 \
    --subsections H5 \
    --max-cost-per-doc 0.05

# Full 2024-25 backfill
python llm_fallback_worker.py \
    --year 2024-25 \
    --max-cost-per-run 15.00 \
    --max-cost-per-doc 0.12

# Shadow mode — write the artifact but don't expose merged values
# (caller must filter by producer to access the fallback values)
python llm_fallback_worker.py --mode shadow --year 2024-25
```

Per-doc JSON reports land in `scratch/llm-fallback-runs/run-<timestamp>/`.

Budget behavior: if a subsection's call would push the doc or run above the
cap, the worker writes a `status='budget_skipped'` cache row and skips the
LLM call. No silent overspend.

### Validation

```bash
# Regression check against the audited-school ground truth.
# Hard rule: the fallback must NOT regress existing cleaner GT pass rate.
python tools/extraction-validator/score_tier4.py \
    --ground-truth tools/extraction-validator/ground_truth/harvard-2024-25.yaml \
    --markdown tools/extraction-validator/runs/harvard-2024-25/baseline/output.md \
    --id-map tools/extraction-validator/id_maps/harvard-2024-25.yaml \
    --include-llm-artifact scratch/harvard-fallback.json

# Corpus coverage delta (cleaner-only vs cleaner+fallback).
python tools/extraction-validator/corpus_survey_tier4.py --include-fallback --limit 200
```

Post-2024-25 backfill: Harvard GT stays at 133/133 (100%) with the fallback
merged in — zero regression.

---

## Concurrency & retry

One worker at a time. The Phase 1 run on 2026-04-20 accidentally ran two
concurrent workers and produced duplicate `cds_artifacts` rows because both
wrote past each other's cache. Fixed by making the artifact insert
delete-then-insert for the same `(document_id, producer)` pair — but the
primary invariant is "one worker per year-window at a time."

Transient Supabase timeouts are handled by three-attempt retries with 2s/4s
backoff on `_cache_lookup` and `_cache_write`. Network glitches past that
window fail the run; cache state is preserved, so resume is cheap.

---

## Cache model

### Schema (`cds_llm_cache`)

The cache key columns are grounded in what actually persists today:

| Column | Source |
|---|---|
| `source_sha256` | `cds_documents.source_sha256` (the archived PDF bytes hash) |
| `markdown_sha256` | Hashed at runtime from `notes.markdown` on the `tier4_docling` artifact |
| `section_name` | Subsection code (`H5`, `C13`, ...) |
| `schema_version` | Derived from `cds_documents.detected_year` per ADR 0007 |
| `model_name` | `claude-haiku-4-5` (or override via `--model`) |
| `prompt_version` | Defined in `tier4_llm_fallback.PROMPT_VERSION` |
| `strategy_version` | Defined in `tier4_llm_fallback.STRATEGY_VERSION` |
| `cleaner_version` | Operator-supplied (`--cleaner-version`, default `0.3.0`) |
| `missing_fields_sha256` | sha256 of the sorted list of question numbers the cleaner left blank |

Uniqueness is enforced by a dedicated unique index (not a table UNIQUE
constraint) so `cleaner_version NOT NULL DEFAULT ''` avoids a `coalesce()`
expression in the key.

### Invalidation

Cache entries are invalidated by bumping any of:

- `PROMPT_VERSION` (prompt text changed)
- `STRATEGY_VERSION` (slicer or validator behavior changed)
- `--cleaner-version` (deterministic cleaner shrunk the gap set)
- The underlying `markdown_sha256` (Docling re-run produced new markdown)

Bump `PROMPT_VERSION` in `tools/extraction_worker/tier4_llm_fallback.py` and
re-run the worker to regenerate. The old cache rows stay (they're cheap to
keep) and the new `(prompt_version, ...)` key forces fresh LLM calls.

### Artifact compatibility

Cache correctness and consumer merge correctness are related but separate:

- `cds_llm_cache` prevents re-billing the same model call.
- `cds_artifacts` controls what public consumers can merge.

The public merge contract is stricter than "latest fallback for document":

1. Choose the selected deterministic base artifact by producer precedence.
2. If the base producer is not `tier4_docling`, do not merge LLM fallback.
3. If the base producer is `tier4_docling`, merge only a fallback artifact
   compatible with that exact base:
   - preferred: `fallback.notes.base_artifact_id == base.id`
   - legacy: `fallback.notes.markdown_sha256 == sha256(base.notes.markdown)`
     and `fallback.notes.cleaner_version == base.producer_version`
4. If no compatible fallback exists, expose cleaner-only values.

This matters after a Docling/cleaner re-drain. A fallback generated from old
markdown may still be the newest `tier4_llm_fallback` row for that document,
but it is no longer evidence-compatible with the selected base artifact. It
must not be overlaid onto v0.3 values.

Implementation surfaces that must share this rule:

- `public.cds_selected_extraction_result`
- `tools/browser_backend/project_browser_data.py`
- `web/src/lib/queries.ts::fetchExtract`

---

## Consumer integration

The frontend merges cleaner + fallback values via `fetchExtract()` in
`web/src/lib/queries.ts`. Any consumer hitting `api.collegedata.fyi` can do
the same with two parallel requests:

```bash
DOC=0e482995-83a3-4dcf-92f1-296ca4e8cf94   # harvard 2024-25

# Cleaner (canonical) artifact
curl -sH "apikey: $ANON" \
  "https://api.collegedata.fyi/rest/v1/cds_artifacts?document_id=eq.$DOC&producer=eq.tier4_docling&kind=eq.canonical"

# Fallback artifact
curl -sH "apikey: $ANON" \
  "https://api.collegedata.fyi/rest/v1/cds_artifacts?document_id=eq.$DOC&producer=eq.tier4_llm_fallback"
```

Merge rule for Mode B: after the compatibility gate passes, start with the
fallback `notes.values` as the base, overlay the cleaner `notes.values` on
top. Cleaner wins on any collision.

`cds_llm_cache` is not publicly readable — it's an internal response cache,
not consumer-facing data.

---

## Current status

As of 2026-04-20:

| Metric | Value |
|---|---|
| Docs with fallback artifact | 244 (2024-25) |
| Fields added (total) | 6,871 |
| Mean fields added per doc | 28.2 |
| Median fields added per doc | 30 |
| Total Anthropic spend | `$14.08` |
| Cache hit rate on re-run | 100% (same prompt/model/cleaner) |
| GT regression on audited schools | 0 |

Next expansions (not yet done):

- Backfill earlier years (2023-24, 2022-23, ...). Cost scales linearly with
  doc count and is dominated by per-call output tokens, not the cached glossary.
- Expand the target subsection list as `corpus_survey_tier4.py
  --include-fallback` surfaces sections where the fallback pays for itself.
- Batch multiple small subsections (C15, D15, D16) into one call to reduce
  the per-call overhead on thin subsections.

---

## Cross-references

- [PRD 006](prd/006-llm-fallback.md) — full design, decision gate, phasing
- [PRD 005](prd/005-full-schema-extraction.md) — hand-coded Tier 4 cleaner expansion (complementary path)
- [Tier 4 cleaner learnings](research/tier4-cleaner-learnings-for-llm-fallback.md) — what the 6-phase PRD 005 execution taught us about where the LLM earns its keep
- [ADR 0006](decisions/0006-tiered-extraction-strategy.md) — the tiered extraction strategy this fallback sits inside
- [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md) — why `schema_version` derives from `detected_year`, not the URL year
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — how the fallback fits the overall data flow
