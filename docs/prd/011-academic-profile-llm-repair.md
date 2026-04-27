# PRD 011: Academic profile browser fields and DeepSeek-OCR repair

**Status:** Draft for later implementation
**Created:** 2026-04-26
**Author:** Codex + Anthony
**Related:** [PRD 010](010-queryable-data-browser.md), [PRD 006](006-llm-fallback.md), [PRD 005](005-full-schema-extraction.md), [Extraction Quality](../extraction-quality.md), [Queryable Browser Backend Notes](../queryable-browser-backend.md)

---

## Context

The queryable school browser MVP shipped with a deliberately narrow certified field
set:

- applications
- admits
- first-year enrolled
- derived acceptance rate
- derived yield rate
- Scorecard enrollment, retention, net price, and Pell rate

That was the right launch cut. It avoided exposing fields whose current extraction
answerability is too weak to support a public filtering workflow.

The next obvious product request is an "academic profile" browser slice:

- GPA profile
- SAT profile
- ACT profile

These fields are high-value for students, parents, counselors, and analysts. They
also sit in one of the current Tier 4 weak spots. The extraction-quality snapshot
shows:

- C9 test scores: low corpus-wide fill rate
- C11 GPA profile: highly school-dependent format
- flattened-PDF extraction failures caused mostly by table-to-paragraph flattening,
  row merge, header ambiguity, and school-specific layout variants

The question is not whether these fields are useful. They are. The question is
whether the project can expose them without making weak extracted values look more
authoritative than they are.

This PRD proposes a measured v1.1 path:

1. add a narrow academic-profile field set internally
2. measure answerability without default UI exposure
3. pilot DeepSeek-OCR as an evidence-bound local repair path
4. promote only values that pass deterministic validation
5. expose browser filters once answerability clears a published gate

## Problem

### User problem

The browser cannot yet answer common academic-profile queries:

- show schools where SAT composite 75th percentile is at least 1450
- show schools where ACT composite median is at least 32
- show schools where average high-school GPA is above 3.8
- compare selectivity alongside test-score profile

These are natural follow-ons to the admissions and enrollment filters already live.

### Data problem

The relevant CDS fields exist in the canonical schema, but their current extraction
quality is uneven:

- SAT/ACT percentile tables are sometimes readable but often layout-fragmented.
- Test-policy fields require companion semantics such as reported, test optional,
  not used, not applicable, or missing extraction.
- GPA profile can appear as average GPA, distribution buckets, submitted-rate rows,
  or school-specific variants.
- Docling can lose table structure even when the underlying page is visually clear.

### Cost problem

The project cannot spend proprietary API tokens across roughly 4,000 PDFs as a
standing workflow. A viable repair path must support:

- small paid API pilots
- local overnight batch runs on Apple Silicon
- targeted page/crop repair rather than whole-document VLM processing

## Goals

1. Add a useful academic-profile field set to the browser-serving model.
2. Keep public browser semantics honest and reproducible.
3. Use DeepSeek-OCR or a similar local-capable document VLM only as a repair layer,
   not as a replacement for deterministic extraction.
4. Require deterministic validation before repaired values can become browser data.
5. Produce reusable repair-candidate records so failed/uncertain repairs are auditable.

## Non-goals

- Full arbitrary SAT/ACT/GPA field exposure.
- Full replacement of Docling or the existing Tier 4 cleaner.
- Running a VLM across every page of every PDF.
- Confidence scoring.
- Accepting LLM values directly into `cds_fields` or `school_browser_rows` without
  validation.
- Building a human correction CMS in the first pass.

## Recommended browser field set

Start with fields that users naturally filter or sort on and that can be validated
with relatively strong deterministic rules.

### SAT / ACT submission fields

| Browser field | CDS field | Type | Storage |
|---|---:|---|---|
| `sat_submit_rate` | `C.901` | percent/rate | fractional `0..1` |
| `act_submit_rate` | `C.902` | percent/rate | fractional `0..1` |
| `sat_submit_count` | `C.903` | integer | integer |
| `act_submit_count` | `C.904` | integer | integer |

### SAT percentile fields

| Browser field | CDS field | Type | Valid range |
|---|---:|---|---:|
| `sat_composite_p25` | `C.905` | integer | `400..1600` |
| `sat_composite_p50` | `C.906` | integer | `400..1600` |
| `sat_composite_p75` | `C.907` | integer | `400..1600` |
| `sat_ebrw_p25` | `C.908` | integer | `200..800` |
| `sat_ebrw_p50` | `C.909` | integer | `200..800` |
| `sat_ebrw_p75` | `C.910` | integer | `200..800` |
| `sat_math_p25` | `C.911` | integer | `200..800` |
| `sat_math_p50` | `C.912` | integer | `200..800` |
| `sat_math_p75` | `C.913` | integer | `200..800` |

### ACT percentile fields

| Browser field | CDS field | Type | Valid range |
|---|---:|---|---:|
| `act_composite_p25` | `C.914` | integer | `1..36` |
| `act_composite_p50` | `C.915` | integer | `1..36` |
| `act_composite_p75` | `C.916` | integer | `1..36` |

### GPA fields

| Browser field | CDS field | Type | Storage |
|---|---:|---|---|
| `avg_high_school_gpa` | `C.1201` | numeric | numeric, usually `0..4.5` |
| `gpa_submit_rate` | `C.1202` | percent/rate | fractional `0..1` |

### Explicitly out of first pass

Do not expose these in the first academic-profile browser iteration:

- ACT subject percentiles (`C.917-C.931`)
- SAT/ACT score-band distributions (`C.932-C.987`)
- full GPA distribution buckets (`C.1101-C.1130`)
- C8 test-policy text fields
- GPA/test fields as default homepage marketing stats

Those are valuable later, but they increase surface area and ambiguity. The first
pass should prove the pipeline on the smaller field set above.

## Data model changes

### `cds_metric_aliases`

Add direct aliases for the field set above. These are direct field aliases, not
derived metrics.

Examples:

```text
sat_composite_p25 -> C.905
act_composite_p75 -> C.916
avg_high_school_gpa -> C.1201
```

`acceptance_rate` and `yield_rate` remain derived serving-layer metrics and do not
belong in `cds_metric_aliases`.

### `school_browser_rows`

Add nullable columns for the recommended browser fields.

Percent/rate columns must use the same fractional `0..1` convention as the existing
browser model.

### Repair candidate table

Add a new internal table for model-generated candidates. The key design point:
repair candidates are not the source of truth until validation promotes them.

Suggested shape:

```sql
create table public.cds_field_repair_candidates (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.cds_documents(id) on delete cascade,
  schema_version text not null,
  field_id text not null,
  canonical_metric text,

  candidate_value_text text,
  candidate_value_num numeric,
  candidate_value_bool boolean,
  candidate_value_kind text not null,

  model_name text not null,
  model_provider text not null,
  prompt_version text not null,
  input_artifact_sha256 text,
  input_page integer,
  input_crop_path text,

  evidence_text text,
  evidence_json jsonb not null default '{}'::jsonb,
  repaired_markdown text,
  output_kind text not null,
  raw_response jsonb not null,

  validation_status text not null,
  validation_errors jsonb not null default '[]'::jsonb,
  promoted_at timestamptz,
  created_at timestamptz not null default now()
);
```

Initial access should be service-role only. If repair provenance is exposed publicly,
do it through a curated view after the semantics settle.

## Repair selection policy

Projection should resolve field values in this order:

1. valid deterministic extraction value
2. promoted repair candidate
3. null / missing

The repair layer must not overwrite valid deterministic values. If a repair candidate
disagrees with a valid deterministic value, record a conflict and keep the deterministic
value.

## Deterministic validation

Validation does not prove the model "saw" the PDF correctly. It decides whether a
candidate is safe enough to publish.

### Common validators

All repaired values must pass:

- field is in the requested repair set
- value parses into the expected type
- value is within the field's allowed range
- candidate is section-local to C9, C11, or C12 as appropriate
- evidence text or repaired markdown supports the returned value
- candidate does not conflict with a stronger deterministic value

### SAT validators

- `400 <= sat_composite_p25 <= sat_composite_p50 <= sat_composite_p75 <= 1600`
- `200 <= sat_ebrw_p25 <= sat_ebrw_p50 <= sat_ebrw_p75 <= 800`
- `200 <= sat_math_p25 <= sat_math_p50 <= sat_math_p75 <= 800`
- for matching percentiles, `sat_composite` should roughly equal `sat_ebrw + sat_math`
  with a generous tolerance, for example `±40`
- `0 <= sat_submit_rate <= 1`
- `sat_submit_count >= 0`

`sat_submit_count <= enrolled_first_year` should be warning-only. Reporting bases can
vary and some schools report counts in ways that do not map cleanly to the browser's
first-year enrolled field.

### ACT validators

- `1 <= act_composite_p25 <= act_composite_p50 <= act_composite_p75 <= 36`
- `0 <= act_submit_rate <= 1`
- `act_submit_count >= 0`

`act_submit_count <= enrolled_first_year` is warning-only for the same reason as SAT.

### GPA validators

- `0 <= avg_high_school_gpa <= 4.5`
- `0 <= gpa_submit_rate <= 1`

If GPA distribution buckets are added later, their total should be close to `100%`
with a small tolerance for rounding.

## DeepSeek-OCR repair approach

The repair path should be document-image-first, but narrow.

### Why DeepSeek-OCR

DeepSeek-OCR is interesting because it is document/OCR/layout oriented rather than
just a general chat VLM. The desired behavior is not "reason about college admissions."
It is:

- read a visually clear but structurally mangled CDS table
- reconstruct the table or reading order as markdown
- preserve enough text/layout evidence for deterministic parsing and validation

The important design revision: DeepSeek-OCR should first be treated as a targeted
**page-to-markdown/table repair** engine, not a canonical-field extractor. Direct
strict JSON extraction is useful as a fallback and benchmark, but the default trust
boundary should be:

```text
DeepSeek-OCR: page image/crop -> repaired markdown table
project code: repaired markdown -> canonical fields -> validation
```

This is easier to audit than asking the model to jump straight from pixels to
`C.905`, `C.916`, or `C.1201`.

### What not to do

Do not send entire PDFs to the model.

That is too slow, too expensive, and unnecessary. The target fields live in a small
part of Section C.

Do not assume bounding boxes are always present. Some demos show useful boxes for
section detection, but other document modes return no boxes. Boxes should be stored
when available, never required for promotion.

### Targeted repair flow

1. Select eligible documents:
   - `2024-25+`
   - Tier 4 or Tier 5 source path
   - academic-profile browser fields missing, parse-error, or validation-failed
2. Locate likely pages:
   - prefer existing markdown section markers
   - search page text for `C9`, `SAT`, `ACT`, `C11`, `GPA`, `C12`
   - include one neighboring page when uncertain
3. Render pages or crops:
   - `200-300 DPI`
   - stable crop/page artifact path
   - record page number and crop coordinates
4. Call DeepSeek-OCR in ordered modes:
   - primary: markdown table reconstruction
   - secondary: free OCR reading-order text
   - fallback/benchmark: strict JSON field extraction
5. Parse repaired output:
   - run deterministic C9/C11/C12 parsers over repaired markdown first
   - use free-OCR text only for evidence/locality support or fallback parsing
   - use strict JSON only when markdown parsing fails, and still validate hard
6. Validate candidates:
   - parse/type/range checks
   - monotonic percentile checks
   - evidence and section-locality checks
   - no overwrite of deterministic values
7. Store all candidates:
   - promoted and rejected
   - repaired markdown/free OCR/JSON raw output
   - validation errors included
8. Re-run projection:
   - deterministic value wins
   - promoted repair fills gaps

### Prompt/mode matrix

Every pilot document should run the same crop through three modes so the project can
measure which output shape is most reliable.

#### Mode A: markdown table repair

Ask for markdown only:

```text
Convert this CDS page region into markdown. Preserve tables, row labels, column
headers, and numbers exactly. Do not summarize. Do not infer missing cells.
```

Then parse the markdown with project code.

#### Mode B: free OCR / reading order

Ask for text only:

```text
Transcribe all visible text in logical reading order. Preserve line breaks and
numbers exactly. Do not summarize.
```

Use this mainly for evidence matching and section-locality checks.

#### Mode C: strict JSON extraction

Ask for canonical fields only:

```json
{
  "section": "C9",
  "fields": {
    "sat_composite_p25": null,
    "sat_composite_p50": null,
    "sat_composite_p75": null,
    "act_composite_p25": null,
    "act_composite_p50": null,
    "act_composite_p75": null
  },
  "evidence": []
}
```

This mode is a fallback, not the preferred promotion path.

## API pilot

Before local installation, run a small paid API pilot if DeepSeek-OCR is available
through DeepSeek API or OpenRouter at implementation time.

### Pilot corpus

Use 25-50 documents:

- 10 where deterministic extraction already has SAT/ACT/GPA values
- 10 where SAT/ACT fields are missing
- 10 where GPA fields are missing
- 5 scanned or visually ugly cases
- optional: 5 elite/private schools users are likely to search first

### Pilot metrics

Measure:

- exact match against existing deterministic values where available
- manual-audit accuracy on missing cases
- markdown table parse success rate
- free-OCR evidence match rate
- strict-JSON parse success rate
- valid repaired fields per dollar
- valid repaired fields per minute
- rejection rate by validator
- conflict rate against deterministic extraction
- page/crop localization success rate
- whether full page or cropped table performs better

### Success gate

Proceed to local overnight pipeline only if:

- at least 90% exact match on fields where deterministic values already exist
- at least 80% manually accepted values on missing-field cases
- markdown repair produces parseable tables often enough to be the default path
- validator catches obvious page/column/scale mistakes
- output is stable enough to parse without human cleanup

These thresholds are intentionally high because the browser makes values look
canonical.

### Local feasibility note

Informal public demos claim the newer DeepSeek-OCR model is under 7 GB and consumes
roughly 7.5 GB of VRAM on an NVIDIA GPU. Treat that as directional, not a guarantee
for Apple Silicon. The implementation should keep the local runner behind a provider
interface so the operator can try MLX, a model-specific server, or an API-compatible
local HTTP wrapper without rewriting validation/projection logic.

## Local overnight pipeline

If the API pilot succeeds, build an operator script:

```bash
python tools/browser_backend/repair_academic_profile.py \
  --limit 500 \
  --model deepseek-ocr \
  --render-dir scratch/repair-pages \
  --write-candidates \
  --apply-promoted
```

Required modes:

- `--dry-run`
- `--document-id <uuid>`
- `--limit <n>`
- `--only-missing`
- `--only-invalid`
- `--write-candidates`
- `--apply-promoted`
- `--provider api`
- `--provider local`
- `--output-mode markdown`
- `--output-mode free_ocr`
- `--output-mode json`
- `--output-mode all`

The local provider should be designed so the operator can install and configure the
actual model runner separately. The project script should own batching, page rendering,
prompt construction, markdown parsing, JSON parsing, validation, and database writes.

## Browser rollout plan

### Phase 0: internal projection only

- add aliases and projection support
- do not expose UI filters yet
- compute answerability for academic-profile fields
- write a report into `.context` or a committed docs snapshot

### Phase 1: API pilot

- run DeepSeek-OCR API/OpenRouter pilot on 25-50 docs
- compare markdown, free-OCR, and strict-JSON modes on the same crops
- store repair candidates in dry-run artifacts
- manually audit results

### Phase 2: local batch script

- implement local/provider abstraction
- process a larger sample overnight
- measure repair yield and runtime

### Phase 3: hidden browser columns

- populate `school_browser_rows` fields
- expose via API only
- keep UI filters off
- verify answerability and validation behavior

### Phase 4: UI enablement

Enable public browser filters only if answerability is good enough.

Suggested minimum gate:

- at least 150 primary schools can answer SAT composite percentile filters, or
  a documented lower threshold if the corpus is genuinely sparse
- validation rejection/conflict rates are low and understood
- no known systematic scale errors
- provenance available in exports

## UX implications

The browser should avoid making repaired values look magical.

Suggested display semantics:

- table cells look normal when values pass promotion
- source/export metadata includes provenance:
  - deterministic CDS extraction
  - repaired from page image
  - College Scorecard
- answerability metadata remains prominent
- no confidence badges

Exports should include provenance columns before the UI does.

## Risks

### False precision

SAT/ACT/GPA fields are emotionally salient and easy to over-trust. Mitigation:
promote only validated values and keep answerability counts visible.

### Model output instability

Open-source/local model serving can drift by quantization, runner, and prompt format.
Mitigation: persist raw response, model name, prompt version, and input artifact hash.

### Runtime too slow

Full-PDF VLM repair will not scale locally. Mitigation: page/crop targeting only.

### API availability changes

DeepSeek-OCR API/OpenRouter availability may change. Mitigation: keep provider
interface separate from validation and projection logic.

### Weak validation for some fields

Composite percentiles validate better than policy text. Mitigation: exclude C8
policy text and distribution buckets from the first public browser slice.

## Open questions

1. What answerability threshold is high enough to expose SAT/ACT/GPA filters publicly?
2. Should repaired values appear in `cds_fields` as ordinary rows with provenance, or
   only in `school_browser_rows` for the browser slice?
3. Should repair candidates be public through a read-only provenance view?
4. Which local runner should the operator script target first: MLX, llama.cpp,
   a model-specific runner, or a small local HTTP contract?
5. Do we need a tiny manual review UI before public exposure, or is a CSV/report
   enough for v1.1?

## Acceptance criteria

This PRD is ready to ship when:

- academic-profile aliases are documented and projected internally
- DeepSeek-OCR pilot results are measured against a small audited sample
- rejected and promoted repair candidates are persisted with validation details
- browser rows include academic-profile fields only after validation
- `/browse` exposes academic-profile filters only after answerability gate review
- docs/backlog records remaining operational work
