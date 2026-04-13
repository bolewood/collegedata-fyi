# Backlog

Tactical work items for collegedata.fyi. Higher-level milestones (M0 scaffolding, M1 finder, M2 extraction pipeline, M3 public API, M4 first contributor integration) live in [`v1-plan.md`](v1-plan.md). This file tracks the smaller, between-milestone work that surfaces as we build.

Items are grouped by priority. Effort hints are rough estimates of CC-assisted time, not hand-coded human time.

---

## Next up

### 1. Checkbox value decoder for Tier 2 extractor
**Priority:** P1 (blocks Tier 2 from shipping with full output quality)
**Effort:** ~30 minutes
**Owner:** unassigned

The Tier 2 extractor at `tools/tier2_extractor/` reads AcroForm checkbox widgets and emits their raw PDF export values: `/VI`, `/X`, `/NON`, `/SAME`, `/P`, etc. These are not human-readable. Each checkbox field has a known set of possible values defined in the blank template's widget dictionary (the `/AP` and `/Opt` entries on the field object).

**What to build:** a one-time pass over `scratch/CDS-PDF-2025-2026_PDF_Template.pdf` that walks every Btn-type field, extracts its set of legal export values, and pairs each value with a human-readable label (from the adjacent text or the schema's question text). Bake the resulting decoder into `schemas/cds_schema_{year}.json` as a per-field `value_options` array, e.g.:

```json
{
  "question_number": "C.701",
  "pdf_tag": "Q111_1",
  "value_type": "x",
  "value_options": [
    {"export": "/VI", "label": "Very Important"},
    {"export": "/I",  "label": "Important"},
    {"export": "/SC", "label": "Somewhat Considered"},
    {"export": "/NC", "label": "Not Considered"}
  ]
}
```

The Tier 2 extractor then emits both the raw export value (for provenance) and the decoded label (for consumers).

**Why it matters:** without this, every checkbox field in Tier 2 output is a meaningless one- or two-letter code. Downstream consumers cannot use the data without writing their own per-field decoder, which defeats the canonical-schema promise.

**Cross-references:** `tools/tier2_extractor/README.md` known gap #1; `tools/schema_builder/build_from_xlsx.py`.

---

### 2. Full HMC regression test for Tier 2 against ground truth
**Priority:** P1 (validates the "Tier 2 is strictly better" claim with numbers)
**Effort:** ~45 minutes
**Owner:** unassigned

The Tier 2 extractor was verified against 13 hand-picked C1/C2/B1 spot checks from `tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml`. The full ground truth file has more fields (B2 race/ethnicity, B22 retention, C7 factor importance, C9 test scores, C10 class rank, C13 application fee, etc.) that were not checked.

**What to build:** a script (probably `tools/extraction-validator/score_tier2.py` so it sits next to the existing Docling-config validator) that:
1. Loads a school's ground-truth YAML
2. Loads the corresponding Tier 2 extract JSON
3. Builds a mapping from ground-truth field IDs (e.g. `b1_ft_firstyear_men`) to canonical question numbers (e.g. `B.101`) — this might require a small hand-edited map file because the ground truth uses homegrown IDs that don't directly join to the schema
4. For every ground-truth field, look up the Tier 2 value and compare
5. Emit `N/M match (X%)` plus a per-field diff table

Run it on HMC. Expected result: 100% match for any field that exists as a non-computed AcroForm value, with a small number of misses for fields that are derived from sub-values or that the school left blank.

**Why it matters:** the project's claim that Tier 2 is the right primary extraction path needs evidence beyond a 13-field spot check. A full regression score is the artifact a contributor can cite when defending the architecture decision in ADR 0006 or in a launch post.

**Stretch:** also score the existing Reducto reference extracts (`tools/extraction-validator/references/reducto/`) against the same ground truth using the same script. That gives a side-by-side: Tier 2 vs Reducto vs Docling, all on the same scale, all reading the same hand-verified YAML.

**Cross-references:** `tools/extraction-validator/README.md`; `tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml`; `tools/extraction-validator/references/reducto/observations-2026-04-13.md`.

---

### 3. ADR 0006: Tiered extraction strategy
**Priority:** P1 (captures the most important strategic decision the project has made so far)
**Effort:** ~45 minutes
**Owner:** unassigned

The project's extraction architecture has fundamentally changed in the last session and the change is not yet captured as an ADR. ADR 0002 ("Publish raw over clean") is still right in spirit but its framing assumes one extractor (Docling) and one artifact kind (raw Docling JSON). The reality is now:

- **Tier 1 (XLSX direct)** — possible but unobserved in the wild
- **Tier 2 (AcroForm direct)** — primary path for unflattened fillable PDFs, deterministic, ~100% accurate; HMC 2025-26 confirmed
- **Tier 3 (DOCX direct)** — possible, not yet observed
- **Tier 4 (flat-PDF layout extraction)** — Docling and/or Reducto + cleaner; required for Yale 2024-25, Harvard 2024-25
- **Tier 5 (image-only OCR)** — worst case

**What to write:** `docs/decisions/0006-tiered-extraction-strategy.md` following the format of the existing ADRs (Context / Decision / Why / Trade-offs accepted). It should:
1. Document the discovery that HMC was a fillable form the whole time and Docling was the wrong tool
2. Define the five tiers explicitly with detection logic
3. Specify that the scraper probes every PDF with `pypdf.get_fields()` before routing
4. Reference the data model columns that support the tier distinction (`source_format`, `producer`, `schema_version`) — these are now already documented in `docs/v1-plan.md`
5. Note that ADR 0002 is preserved (source files and artifacts are still immutable, multiple producers can coexist) but extended (each tier emits a different `producer` tag, all targeting the same canonical schema)
6. Acknowledge that the tier distribution across the wild corpus is still unmeasured and that the V1a finder needs to record `source_format` from day one so we can answer "what fraction of schools are Tier 2?" before deciding how much to invest in Tier 4

**Why it matters:** without an ADR, the next contributor will look at `tools/tier2_extractor/` and `tools/extraction-validator/` and have no idea why both exist or which one is "right." The ADR is the contract that explains the architecture.

**Cross-references:** `docs/decisions/0002-publish-raw-over-clean.md`; `tools/tier2_extractor/README.md`; `docs/known-issues/harvey-mudd-2025-26.md`.

---

### 4. Cross-year schema diff tool
**Priority:** P1 (cross-year time series cannot work without it, and the 2025-26 template has breaking changes)
**Effort:** ~45 minutes once a second schema year exists

The 2025-26 CDS template introduces three breaking changes versus prior years: gender categories collapsed from four (`Men, Women, Another Gender, Unknown`) to three (`Male, Female, Unknown`) with non-binary explicitly redistributed across binary; graduation rates B4-B21 now disaggregate by Pell recipient status; retention rate B22 now requires explicit numerator and denominator. A consumer asking "show me women's enrollment for school X across years 2022-2026" will hit a structural break where the data model genuinely changes, not just the column labels.

**What to build:** once we have `schemas/cds_schema_2024_25.json` alongside the 2025-26 file, write `tools/schema_builder/diff.py` that:
1. Loads two schema JSON files
2. For each question_number, categorizes the change: `unchanged` / `renamed` / `added` / `removed` / `semantics_changed`
3. For `semantics_changed`, emit a per-field note explaining what is different (e.g., B.101 in 2024-25 is `degree-seeking first-time men` but in 2025-26 is `degree-seeking first-time Male` — same-ish field but the gender value set is narrower)
4. Output `schemas/cds_schema_2024_25-to-2025_26.diff.json`

Downstream consumers reading cross-year data consult the diff file to decide how to handle each field. A "gender discontinuity" flag is probably the single most important output.

**Why it matters:** without this, cross-year queries silently lose or mis-merge data at the 2024-25 → 2025-26 boundary. The 2025-26 template is already in the wild and schools filing to it right now, so the discontinuity will exist in the dataset on day one of V1 launch.

**Dependency:** requires at least one prior year schema to diff against. Run `tools/schema_builder/build_from_xlsx.py` against the 2024-25 blank template first. The commondataset.org site archives prior-year templates; the URL pattern is `https://commondataset.org/wp-content/uploads/{year-1}/11/CDS-{year-1}-{year}-TEMPLATE.xlsx` or similar, verify exactly before downloading.

**Cross-references:** `tools/schema_builder/README.md`; `schemas/cds_schema_2025_26.json`; `docs/v1-plan.md` data model section ("Schema years are not interchangeable").

---

## Surfaced, not yet prioritized

Items raised in conversation or design notes that haven't been promoted to the priority queue yet. Move them up when you start working on them.

- **Probe the actual Tier 2 / Tier 4 distribution.** Pull 20-30 random school CDS PDFs from the wild, run `pypdf.get_fields()` on each, record the populated/empty split. Right now N=3 (HMC fillable, Yale + Harvard flat). The real distribution decides whether Tier 4 is the common case or the long tail, which decides how much to invest in Reducto / Docling cleaners.
- **Cross-table inconsistency notes.** Some schools' CDS files are internally inconsistent (Yale's C1 says women=772 enrolled, B1 says 769 enrolled; HMC's C1 enrollees-by-gender doesn't match the by-status sub-block). Decide whether to record these in `docs/known-issues/{school}.md`, in a per-extract `_notes` field, or both. They are not extraction bugs.
- **Reducto schema-constrained extraction mode.** The current reference extracts use free-form output, which is why the schema drifted between HMC and Yale. Re-running with Reducto's schema parameter pinned to the canonical CDS schema would close that drift and is worth testing if Tier 4 ends up being a meaningful fraction of the corpus.
- **Reducto citations enabled.** The reference extracts have `citations: null` because we did not request them. Re-running with citations enabled would give per-field bbox + page + source-text provenance, a real upgrade over Docling's bag-of-tokens output.
- **Reducto pricing investigation.** Per-page cost and corpus-scale viability are still unknown. Only matters if Tier 4 is a meaningful fraction of the corpus.
- **Header / metadata field fallback.** HMC's AcroForm has no value for `NAME` (school name, A.101) or respondent address fields, even though the visible PDF shows them. The Tier 2 extractor should probably mark these as "prefer external" so the manifest's `cds_documents.school_name` column is the canonical source for school identity.
- **Hand-mapping from ground-truth IDs to canonical question numbers.** The validator's `ground_truth/*.yaml` files use homegrown IDs (`b1_ft_firstyear_men`). The schema uses canonical question numbers (`B.101`). Building the join map is a one-time per-school task and unblocks both the regression test (P1 #2 above) and any cross-school query that wants to filter on schema-relative field IDs.
- **Test framework.** No tests exist yet. The project will eventually need pytest for at least the schema builder, the Tier 2 extractor, and any future cleaner code. Defer until the first piece of code accumulates a regression worth catching.
- **Periodic re-check job for preservation.** The `last_verified_at` / `removed_at` columns on `cds_documents` are useless without a scheduler that re-HEADs every known source URL on some cadence (weekly is probably fine) and flips `removed_at` when a URL starts 404ing. Build as a Supabase edge function cron once the manifest has more than a handful of rows.
- **`probe_urls.py` destroys schools.yaml formatting when it writes back.** It uses `yaml.dump()` with `sort_keys=False`, which preserves in-memory dict order but discards the section headers, comments, and section grouping that `build_school_list.py` produces. The idempotent fix is either (a) extract `build_school_list.py`'s `write_yaml()` into a shared helper both scripts import, or (b) have `probe_urls.py` write results to a side file like `tools/finder/probe_results.yaml` keyed by IPEDS ID, which `build_school_list.py` then reads during its next run. Option (b) is cleaner because it makes `probe_urls.py` purely additive and leaves `schools.yaml` generated-only from `build_school_list.py`.
- **`probe_urls.py` does GET where HEAD would be faster.** The probe loop issues a GET with `read_bytes=5000` for every pattern attempt, even though most attempts will 404. A HEAD-first strategy (check status + content-type from headers, only GET-sniff the HTML body when the HEAD returns 200 text/html) would cut probe time roughly in half. Minor optimization, matters more if we run against the full 2,400-school corpus.

---

## Strategic context (V2 and V3 ideas worth not losing)

Ideas bigger than a single backlog item, captured here so they don't get dropped. These are not scheduled.

### Join CDS with College Scorecard via IPEDS unit ID

The College Scorecard provides post-graduation earnings, federal debt loads, and other outcome data that the CDS completely ignores. The CDS captures admissions granularity (C7 factor weighting, C9 test distributions, C21 demonstrated interest tracking) that Scorecard completely ignores. Both can be joined to every school in the US higher-ed universe via IPEDS unit ID. A V2 or V3 that exposes the joined dataset through the same PostgREST API would give consumers the strongest public ROI-per-admissions-tier comparison available anywhere: "schools where early decision matters but 4-year-out earnings don't justify the premium," "schools whose admissions emphasize demonstrated interest and whose 10-year-out debt-to-earnings ratios are worst," etc. The join is trivial technically. The value is high because nobody currently offers this.

### Cross-year time series as a first-class query

Once multiple years of data exist for each school, cross-year time series become the most interesting consumer query: "show me Yale's SAT 50th percentile from 2015 to 2025," "which schools' acceptance rates dropped fastest during the test-optional period." This requires the schema year-diff tooling (P1 #4 above) plus a data model extension that lets consumers ask for "the same field across years" in the face of known schema discontinuities. Park for V2.

### Launch the "preservation archive" story to IR professionals

The preservation angle is a stronger story than the data-library angle for at least three audiences: institutional research professionals (who are the ones getting blamed when schools manipulate numbers), investigative journalists covering higher ed (who are currently losing access to historical CDS files as WCAG-driven removals accelerate), and IPEDS-adjacent academics (who use historical CDS for admissions equity research). An HN launch post framed around "we're archiving the public-accountability documents of American higher education at the moment they're being deleted" will land much harder than a generic open-data announcement. The CDS Initiative's own endorsement of machine-readable formats is written cover; a launch post that quotes their 2025-26 Word template instructions directly is very hard to argue against.
