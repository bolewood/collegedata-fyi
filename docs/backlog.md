# Backlog

Tactical work items for collegedata.fyi. Higher-level milestones (M0 scaffolding, M1 finder, M2 extraction pipeline, M3 public API, M4 first contributor integration) live in [`v1-plan.md`](v1-plan.md). This file tracks the smaller, between-milestone work that surfaces as we build.

Items are grouped by priority. Effort hints are rough estimates of CC-assisted time, not hand-coded human time.

---

## Next up

### 1. Cross-year schema diff tool
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
- **Score Reducto reference extracts against the HMC ground truth.** `tools/extraction-validator/score_tier2.py` already handles the join against `harvey-mudd-2025-26.yaml` via the committed id map. Adapting the scorer to read Reducto's free-form output (nested by section, not keyed by question_number) would produce the first real apples-to-apples Tier 2 vs Reducto vs Docling comparison. The HMC ground truth has 31 fields — a meaningful sample, not a spot check. Useful for the "when is Reducto worth paying for?" decision on Tier 4 coverage.
- **`probe_urls.py` destroys schools.yaml formatting when it writes back.** It uses `yaml.dump()` with `sort_keys=False`, which preserves in-memory dict order but discards the section headers, comments, and section grouping that `build_school_list.py` produces. The idempotent fix is either (a) extract `build_school_list.py`'s `write_yaml()` into a shared helper both scripts import, or (b) have `probe_urls.py` write results to a side file like `tools/finder/probe_results.yaml` keyed by IPEDS ID, which `build_school_list.py` then reads during its next run. Option (b) is cleaner because it makes `probe_urls.py` purely additive and leaves `schools.yaml` generated-only from `build_school_list.py`.
- **`probe_urls.py` does GET where HEAD would be faster.** The probe loop issues a GET with `read_bytes=5000` for every pattern attempt, even though most attempts will 404. A HEAD-first strategy (check status + content-type from headers, only GET-sniff the HTML body when the HEAD returns 200 text/html) would cut probe time roughly in half. Minor optimization, matters more if we run against the full 2,400-school corpus.
- **Python extraction worker skeleton (M2 scope).** The Python worker is specified in ADR 0006 and v1-plan.md but has not been written. Its job: poll `cds_documents WHERE extraction_status = 'extraction_pending'`, download the archived source from Storage, run `pypdf.get_fields()` to detect format, route to the appropriate tier extractor, write a `canonical` artifact back. Starting point: `tools/extraction_worker/worker.py` using `supabase-py` for Postgres access and `pypdf` for format detection. Tier 2 routing uses the existing `tools/tier2_extractor/extract.py`. Tier 4 routing is a stub for now (record `extraction_status = failed` with `notes.reason = "tier 4 not implemented"`). M1b's output (schools.yaml → Storage uploads) is what feeds this worker.
- **`schemas/README.md`** documenting the canonical schema structure, the `value_options` decoder format, the year-versioning convention, and the relationship between `question_number`, `pdf_tag`, `word_tag`, and the XLSX Answer Sheet's columns. One-pager. Makes the schema artifact self-documenting for new contributors who don't want to read `build_from_xlsx.py` to understand the format.
- **ADR 0007: Takedown process for archived documents.** ADR 0006 mentions this as a future ADR. The PRD's risks section mentions "a school's legal counsel sends a takedown request" without documenting the response protocol. The protocol should cover: who to contact inside the project, how to verify the request (school IR office confirmation vs random person claiming to represent the school), what counts as compliance (flip `cds_documents.participation_status = withdrawn`, optionally revoke public access on the Storage blob while keeping the archive in cold storage), and how we publicly disclose takedowns in a transparency log. 30 minutes of pure-docs work, worth doing before launch.

---

## Strategic context (V2 and V3 ideas worth not losing)

Ideas bigger than a single backlog item, captured here so they don't get dropped. These are not scheduled.

### Join CDS with College Scorecard via IPEDS unit ID

The College Scorecard provides post-graduation earnings, federal debt loads, and other outcome data that the CDS completely ignores. The CDS captures admissions granularity (C7 factor weighting, C9 test distributions, C21 demonstrated interest tracking) that Scorecard completely ignores. Both can be joined to every school in the US higher-ed universe via IPEDS unit ID. A V2 or V3 that exposes the joined dataset through the same PostgREST API would give consumers the strongest public ROI-per-admissions-tier comparison available anywhere: "schools where early decision matters but 4-year-out earnings don't justify the premium," "schools whose admissions emphasize demonstrated interest and whose 10-year-out debt-to-earnings ratios are worst," etc. The join is trivial technically. The value is high because nobody currently offers this.

### Cross-year time series as a first-class query

Once multiple years of data exist for each school, cross-year time series become the most interesting consumer query: "show me Yale's SAT 50th percentile from 2015 to 2025," "which schools' acceptance rates dropped fastest during the test-optional period." This requires the schema year-diff tooling (P1 #4 above) plus a data model extension that lets consumers ask for "the same field across years" in the face of known schema discontinuities. Park for V2.

### Launch the "preservation archive" story to IR professionals

The preservation angle is a stronger story than the data-library angle for at least three audiences: institutional research professionals (who are the ones getting blamed when schools manipulate numbers), investigative journalists covering higher ed (who are currently losing access to historical CDS files as WCAG-driven removals accelerate), and IPEDS-adjacent academics (who use historical CDS for admissions equity research). An HN launch post framed around "we're archiving the public-accountability documents of American higher education at the moment they're being deleted" will land much harder than a generic open-data announcement. The CDS Initiative's own endorsement of machine-readable formats is written cover; a launch post that quotes their 2025-26 Word template instructions directly is very hard to argue against.
