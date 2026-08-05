# PRD 027: Endowment health facts (IPEDS Finance Part H)

**Status:** Draft (revised after adversarial review, 2026-08-03)
**Created:** 2026-08-03
**Author:** Anthony Showalter (with Claude)
**Related:** PRD 021 (IPEDS coverage layer — this extends its open item "Broader IPEDS field-family coverage beyond the MVP mappings", in 021's "Still open from the original PRD" section)

---

## Executive summary

The WSJ reported (Aug 2, 2026, "The Struggling Colleges Raiding Their Endowments to Pay the Bills")
that ~200 private colleges are borrowing from restricted endowments, and that the share of private
nonprofits drawing down endowments faster than 7%/year nearly doubled between 2016 and 2025. Our
database currently carries exactly one endowment number per school:
`scorecard_summary.endowment_end`, a single-vintage snapshot with no history, no payout detail, and
no restricted/unrestricted split.

Federal data can do much better. Starting with **fiscal year 2020** (2020-21 collection), the IPEDS
Finance survey's Part H reports not just endowment beginning/end values but the **components of the
change**: new gifts, investment return, spending distribution for current use, and a residual
"other changes" line. From those we can compute a per-school, per-year endowment draw rate — the
same *kind* of metric behind the WSJ statistic — using the loader pipeline PRD 021 already
shipped, with **no schema migration in Phase 1** (Phase 2's derived view is a migration) and
roughly 6 new `FactMapping` rows plus targeted loader fixes (enumerated below; the
"mappings-only" version of this plan did not survive review).

Phases:

1. **Phase 0 (spike):** pull the FY2023 F2 file + dictionary, verify variable codes, valuesets, and
   sign conventions, and run a new small analysis script over the fixture schools. Go/no-go.
2. **Phase 1:** map and load Part H endowment facts for FASB filers (form F2), FY2020–FY2024
   (5 releases; FY2024 and FY2023-final are Access-DB-only — see Backfill).
3. **Phase 2:** `school_endowment_health` SQL view with derived metrics (sign-normalized draw
   rate, per-student endowment, trend) and a school-page endowment panel.
4. **Phase 3:** an **endowment draw-rate recipe** at `/recipes/` — an *independent estimate from
   public federal data* of the draw-rate distribution, FY2020→latest, built from a checked-in
   dataset precomputed from the public API (matching the existing recipe pattern).
5. **Beyond (separately justified):** GASB publics (F1A — has the same Part H detail from FY2020),
   balance-sheet net-asset splits (UNAEP-style liquidity proxy), FSA composite scores.

What federal data **cannot** show — and this PRD does not promise — is restricted-endowment
borrowing itself. That lives in audited financial statements, Form 990 footnotes, and
attorney-general filings. Perspective Data Science's WSJ-cited numbers are built from audited
statements; our IPEDS-based figures are a different estimate of a related quantity and must never
be framed as a reproduction of theirs.

## What we have today (measured)

- `scorecard_summary.endowment_end` (Scorecard `ENDOWEND`), latest vintage only. **Review
  finding:** the live values (Baldwin Wallace $179.9M, Quincy $18.1M, Averett $5.7M, Lake Erie
  $31.5M) match the June 2026 Scorecard file's **FY2024** values, while our
  `scorecard_data_year` column says "2022-23" for every row — the vintage label appears stale
  relative to the finance elements. Investigate separately in the scorecard pipeline; do not
  trust `scorecard_data_year` for fiscal-year alignment in this project.
- The CDS schema (1,105 fields) has **no finance section**. The only endowment-adjacent field is
  the Section H2 aid line "Institutional: Endowed scholarships, annual gifts and tuition funded
  grants" — an aid-spending amount, not an endowment measure.
- The PRD 021 mapping set (`tools/ipeds/mappings.py`) covers HD/IC/ADM/EF/GR/SFA-type tables only.
  No `F` (Finance) tables are downloaded or loaded today, for any release year.
- `institution_directory` (Scorecard-sourced) contains **no row at all** for closed schools that
  have dropped out of Scorecard (e.g. Notre Dame College, unitid 204468 — absent, not
  `in_scope=false`; separately, 125 directory rows are closed and all excluded). Since
  `school_facts_unified` inner-joins the directory, closed-school facts can load into
  `ipeds_facts` but cannot reach school pages without a design change (see Design).

## Official-source findings

All variable codes, availability years, and sign conventions below were verified against the
actual NCES complete data files and dictionaries (`F1819_F2`, `F1920_F2`, `F2021_F2`, `F2122_F2`,
`F2223_F2`, `F1920_F1A`, HD2023) during adversarial review — not inferred.

### IPEDS Finance survey, Part H (endowment)

Three forms split by control/accounting standard — **F1A** (public, GASB), **F2** (private
nonprofit FASB — the MVP scope; the F2 file also includes some FASB-reporting publics), **F3**
(for-profit). Data-file naming uses the fiscal-year pair: FY2023 → `F2223_F2`, FY2021 →
`F2021_F2`, FY2015 → `F1415_F2`.

| Line | Official variable title | Variable | Available since |
|---|---|---|---|
| 01 | Value of endowment net assets, beginning of FY | `F2H01` | long history (decades) |
| 02 | Value of endowment net assets, end of FY | `F2H02` | long history (decades) |
| 03 | Change in value (calculated, 02 − 01) | `F2H03` | **FY2020** |
| 03a | New gifts and additions | `F2H03A` | **FY2020** |
| 03b | Endowment net investment return | `F2H03B` | **FY2020** |
| 03c | Spending distribution for current use | `F2H03C` | **FY2020** |
| 03d | Other changes in value of endowment net assets | `F2H03D` | **FY2020** |

Ground truths that shape the design:

- **Component detail starts FY2020, not FY2021.** `F1920_F2` (FY2020 final) already carries
  F2H03A–D for 1,350 reporters; `F1819_F2` (FY2019) has only F2H01/F2H02. The backfill floor for
  components is FY2020 — which also captures the COVID year.
- **Sign conventions are messy in early years.** In FY2023, `F2H03C` ≤ 0 for **all** 1,318
  reporters and the identity `F2H03 = F2H03A + F2H03B + F2H03C + F2H03D` holds for 1318/1318.
  But FY2020 has **194 positive** F2H03C values and FY2021 has **184** (~15% of reporters used
  the opposite sign), and since 03d is the balancing residual, **the residual is contaminated in
  exactly those years**. Raw facts load verbatim (PRD 021 contract); all sign normalization and
  residual re-derivation happens in the derived layer, per-row, with the FY2020–21 caveat.
- **Draw rate** = `−F2H03C / F2H01` after normalization. Note this is *not* the UPMIFA test (see
  thresholds below).
- **Imputation is essentially absent from Part H.** Actual X-flag counts: FY2020 {R:1350, A:469},
  FY2023 {R:1317, A:448, P:1}. Zero-to-one imputed institutions per year. The 'A' codes are
  schools answering "no endowment" on the screener (~25% of F2 filers). Their Part H value
  cells are typically blank, and the current projection emits **no fact at all** for blank
  values — so the expected representation is *absent rows*, not not-applicable status facts
  (a school with no endowment simply has no Endowment section, which is the accepted design).
  M0 records the actual representation observed in the data.
- **Coverage:** the F2 file has ~1,770–1,820 rows per year (including FASB-reporting publics);
  ~75% report Part H. Our in-scope private-nonprofit directory population is 1,364, of which
  1,112 have a non-null Scorecard endowment today.
- **File availability lags differ by release.** `F2324_F2` (FY2024) is **not yet downloadable as
  a complete data file** (404 as of 2026-08-03); FY2024 finance exists only inside the 2024-25
  provisional **Access database** (March 2026). FY2023's *final* revision is likewise
  Access-DB-only today. The loader's `--access-fallback` path is therefore required for the
  **newest** data, not just pre-2020 history.
- GASB form F1A gained the same Part H detail in the same year (F1H03A–D confirmed in
  `F1920_F1A`); publics remain out of MVP scope.

### Thresholds and the UPMIFA caveat

UPMIFA's 7% presumption of imprudence is an **optional bracketed provision (§4(d))** adopted by
only a minority of states, and it is computed against endowment fair market value **averaged over
≥3 years**, not against beginning-of-year value — so `−F2H03C / F2H01` above 7% does not establish
the UPMIFA presumption anywhere, and in most states no such presumption exists at all. Any UI copy
must say something like: *"Some states' UPMIFA statutes presume imprudence above a 7% spending
rate (measured against a multi-year average value); typical endowment payout policies target
4–5%."* Never "UPMIFA presumes imprudence above 7%" unqualified, and never as a per-school claim.

Note also that `F2H03C` does not distinguish donor-restricted from quasi-endowment
(board-designated) spending: a board-approved quasi-endowment spend-down can push the rate above
7% with zero imprudence. High draw rate ≠ misconduct; single-year spikes (especially FY2021) will
be common.

### FSA Financial Responsibility composite scores — future candidate

Federal Student Aid publishes annual composite scores (−1.0 to +3.0; ≥1.5 passes) derived from
**audited financial statements** — the only federal dataset that sees what auditors see. Multi-year
publication lag, keyed by OPEID (not in our schema; would come from the HD table), ad-hoc Excel
distribution. Real value, real integration cost; separate decision.

### What federal data cannot show

Restricted-vs-unrestricted **endowment** composition, internal borrowing against restricted funds,
and donor-intent violations are visible only in audit footnotes, Form 990s, and litigation.
Reclassifications and interfund loans need not move Part H at all (they can be pure Part A /
asset-composition events). Any UI copy must not imply otherwise. We present labeled federal values
and clearly marked derived metrics; we do not compute a distress verdict.

## Product goals

1. A school page answers: how big is the endowment, which direction is it moving, and how fast is
   the school drawing from it — with full provenance (source table/variable, release type,
   status), consistent with PRD 021 principles.
2. **Student/family relevance is the design driver:** "will this school exist in four years?" is a
   live question for applicants and counselors (Notre Dame College closed mid-degree for its
   students). Panel and recipe copy must be comprehensible to non-CFO readers.
3. The draw-rate metric is computable from our public API by anyone, per school, per year, with
   the arithmetic published.
4. History is queryable (the fact table keeps every data year), so sector-level trend claims can
   be independently checked against our data for FY2020+.

## Non-goals

- No "financial health grade" or composite score of our own.
- No claim about restricted-fund borrowing for any specific school — and no annotation language
  that implies an *event* occurred (see Derived metrics).
- No GASB/for-profit coverage in MVP.
- No pre-FY2020 draw rates: they are not computable from federal data (no spending-distribution
  variable), and we will not approximate them from value changes (which conflate market return,
  gifts, and spending).
- No CDS crosswalk: every fact in this family is `definition_alignment = "not_cds_equivalent"`.

## Design

### New fact mappings (Phase 1)

Appended to `MVP_FACT_MAPPINGS` in `tools/ipeds/mappings.py`, with `value_kind="number"`,
`display_group="Endowment"`, `unit="usd"`, `definition_alignment="not_cds_equivalent"`. Field
keys deliberately avoid shadowing
the Scorecard column `endowment_end` — resolved now, not deferred: the IPEDS family uses a
`_value_` naming pair, `scorecard_summary.endowment_end` stays unchanged, and the API docs
cross-reference the two.

| field_key | label (from official titles) | var |
|---|---|---|
| `endowment_value_begin` | Endowment net assets, beginning of fiscal year | `F2H01` |
| `endowment_value_end` | Endowment net assets, end of fiscal year | `F2H02` |
| `endowment_new_gifts` | Endowment new gifts and additions | `F2H03A` |
| `endowment_investment_return` | Endowment net investment return | `F2H03B` |
| `endowment_spending_distribution` | Endowment spending distribution for current use | `F2H03C` |
| `endowment_other_change` | Other changes in endowment net assets | `F2H03D` |

- Baseline `table_name` is the newest complete-data-file name at implementation time (`F2223_F2`
  today); `table_name_for_data_year` translates per year.
- `F2H03` (change in value) is deliberately **not mapped** — it is a calculated field equal to
  `F2H02 − F2H01`. Every identity check in this PRD is stated in the `(F2H02 − F2H01)` form so
  it is computable from the loaded fact set.
- The F2 file includes a small number of FASB-reporting **public** institutions. Phase 1 loads
  all F2 filers (the form, not control, determines the data) — provenance columns make the
  source visible either way. Control-based gating applies only to Phase 2 panel copy.
- `definition_note` on `endowment_spending_distribution`: reported as a negative value
  (funds leaving the endowment); FY2020–21 filings mix sign conventions. On
  `endowment_other_change`: residual line; absorbs transfers, reclassifications, and reporting
  noise — not a borrowing measure.
- **Projection hazard (spike must clear):** `project.py:121-136` converts any negative numeric
  that has a matching value label into a status fact with `value_numeric=NULL`. Endowment
  components are legitimately negative — including the draw-rate numerator itself. The spike
  must confirm the F2 valuesets define **no** value labels on `F2H03*` (only the `X*` status
  codes); if any exist, the projection rule needs a per-mapping escape hatch before Phase 1.

### Loader changes (revised — "mappings-only" did not survive review)

1. **`table_name_for_data_year`**: bespoke Finance branch mirroring the SFA fiscal-year-pair
   formula: data year Y → `F{Y-1 mod 100}{Y mod 100}_F2` (2024→`F2324_F2`, 2021→`F2021_F2`,
   2015→`F1415_F2`; verified against live NCES file names). Must be a dedicated branch —
   F-table names match none of the existing prefixes, so the function currently falls through
   and returns the baseline table name **unchanged**, which on backfill silently loads the
   wrong year's table.
2. **`_best_table_candidate` cannot handle F tables** — its digit-stripping fallback turns
   `F1516_F2` into prefix `F_F`, which can never match. Contrary to the earlier draft, existing
   rename resolution does *not* cover finance; add an F-table candidate rule + tests.
3. **Targeted-backfill provenance bug**: `load_release.py` `apply_to_supabase` builds
   `ipeds_tables` payloads for **every** Tablesdoc table; on a `--display-groups Endowment`
   rerun against an already-loaded release, all other tables get re-upserted with null
   `data_url`/`row_count`/`source_sha256`/`loaded_at`, wiping load provenance, and release
   `notes` are overwritten wholesale (dropping `release_date_text`/`release_probe_due_on` unless
   the date flags are re-passed). **Fix the loader before any backfill**: scope `ipeds_tables`
   upserts to tables actually loaded in this run, and merge rather than replace notes (or
   require the date flags and document it).
4. **Access-fallback gating**: `download_release.py` only routes a table to `--access-fallback`
   when it appears in Tablesdoc but 404s from the data generator; a table name absent from an
   old Tablesdoc is silently skipped. Backfill needs a loud failure (or explicit skip report)
   for expected-but-missing finance tables. Additionally, the data-generator URL pins `HasRV=0`
   (original, non-revised values) and the fallback fires only on 404 — so a **revised final**
   release whose provisional CSV still returns 200 (FY2023 today) is unreachable by the
   documented mechanism. Add an explicit revised-final path (release-type selector routing to
   the Access DB) or the backfill will silently load provisional values under whatever
   release-type label the operator passes.
5. **Release selection**: `download_release.py` silently falls back to the newest release when
   `--collection-year` doesn't match; for a 5-release backfill this turns a typo into loading
   the wrong year. Add strict matching (or at minimum a confirmation line in the manifest).
6. The `--tables` flag already exists on `download_release.py` — use it for the spike; no CLI
   work needed there.
7. No SQL migration for Phase 1 stands: constraints, RLS, browser flags, and view plumbing are
   all group-agnostic (verified against both migrations).

### Derived metrics (Phase 2) — SQL view, not synthetic facts

Raw `ipeds_facts` rows stay verbatim federal values (signs included). The
`school_endowment_health` view (migration, applied from main post-merge) computes, per
`(ipeds_id, data_year)`, FASB filers, FY2020+:

- `draw_rate` = `abs(F2H03C) / nullif(F2H01, 0)` with per-row sign normalization; for FY2020–21
  rows where the identity `(F2H02 − F2H01) = 03A+03B+03C+03D` fails under the modern
  convention, re-derive or null out rather than guess. `draw_rate` is **not** floored by
  endowment size — small distressed endowments are precisely the population of interest; the
  panel carries a volatility note for endowments under ~$5M instead.
- `other_change_share` = normalized `F2H03D / nullif(F2H01, 0)` — **nulled for FY2020–21**
  (residual contamination) and **nulled when `F2H01` < $5M** (small-denominator volatility; one
  gift swings the ratio by points). The floor applies to this metric only.
- `endowment_per_student`, `value_change_1yr`, `value_change_5yr` (value series only).
- Rows with imputed or non-reported inputs produce NULL metrics — provenance must not leak away
  one layer up (PRD 021's imputation principle applies to derived layers too, even though Part H
  imputation is empirically rare).

**Annotation policy (revised).** No annotation may assert an event. Banned: "large unexplained
withdrawal." Allowed: descriptive-neutral, e.g. *"Other/residual change exceeded 5% of
beginning-of-year value"* and *"Spending rate above 7% for N consecutive years"* — threshold
annotations require **multi-year persistence**, never a single-year spike, never on imputed or
sign-ambiguous inputs. UI copy uses the qualified UPMIFA language from Official-source findings.
The exact annotation strings get a human review pass (owner sign-off) before Phase 2 ships, and
the site's contact path must be referenced near the panel so a school can dispute a figure
(see Open questions).

### Frontend and API surface

- **Automatic:** the new `display_group` renders as its own section in `FederalBaselineTable.tsx`
  (data-driven grouping; `display_group asc` ordering in `web/src/lib/queries.ts:842`).
  `unit="usd"` formats via `formatCurrency`. Within-group ordering is `field_label asc`; the
  labels in the mapping table already yield an acceptable order (net-asset values first —
  beginning, then end — then investment return, gifts, spending distribution, with the "Other
  changes" residual sorting last). No code change and no label rework needed.
- **Required changes (fuller list than the first draft):**
  - `web/src/lib/public-data.ts`: `federalCategory` branch + new `PublicFactCategory` member
    (`"finance"`) — otherwise endowment facts land under `"identity"` in the public JSON API.
  - `web/src/app/api/schools/[school_id]/facts/route.ts`: the hardcoded `CATEGORIES` set silently
    drops unknown categories — `?categories=finance` returns nothing until this file is updated.
  - `web/src/app/api/page.tsx`: examples + cross-reference between
    `scorecard_summary.endowment_end` and the IPEDS `endowment_value_*` series.
  - Known, accepted gaps (pre-existing, documented not fixed here): snapshots exclude IPEDS
    facts entirely; `/api/fields` and `field_dictionary.json` list only the static friendly
    fields; `/api/compare` cannot select IPEDS fields.
- **Phase 2 panel:** compact endowment card on the school page — end value, 5-year sparkline or
  delta, draw rate with the qualified threshold copy — per `web/DESIGN_SYSTEM.md` and dataviz
  guidance. Private nonprofits only until F1A lands; publics get a "reports under different
  accounting standards" note.

### Recipe: endowment draw-rate tracker (Phase 3)

A fourth entry in `/recipes/`, following the **actual** existing pattern: all three current
recipes ship static, checked-in datasets ("seeded with hand-verified data, extendable to the full
corpus via the public API") — none fetch at runtime. This recipe does the same:

- A small script (checked in, shown in the writeup) pulls `ipeds_facts` via the public PostgREST
  API, computes sign-normalized draw rates, and emits a static dataset module. "Just the raw
  data" is preserved — the writeup shows the exact queries and arithmetic — without inventing a
  client-side-corpus-fetch pattern or fighting PostgREST pagination.
- **Charts:** (1) sector-wide distribution of draw rates by fiscal year, **FY2020→latest** (share
  above 5% / 7% / 15%) — framed as *"an independent estimate from public federal data"*, with a
  methodology-differences section explaining why it will not equal Perspective Data Science's
  audited-statement-based figures (different source, population, and years) and stating both
  numbers without asserting equivalence. The FY2016→2025 window in the WSJ is **not
  reproducible** from IPEDS (no spending variable before FY2020; FY2025 unpublished until
  ~late 2027) and the recipe must say so.
  (2) per-school endowment value + draw-rate view via a school picker. **Default view is
  selection-neutral** (corpus distribution / deciles); WSJ-named schools are internal QA
  fixtures, not the public default cast.
- Closed schools **can** be included here (raw `ipeds_facts` is publicly queryable and keeps
  them) even though school pages cannot show them yet — the recipe is the archive's first
  closed-school surface, which is worth a line in the writeup.
- Sequencing: requires Phase 1 only. Can land before the Phase 2 panel and de-risk its design.

#### Amendment (2026-08-05): threshold bucket membership lists

User feedback after launch: the sector table shows counts ("Above 7%: N schools") without
saying which schools — while the underlying facts are publicly queryable in our own API. An
aggregate that won't name its members reads as deliberate obfuscation, which is the opposite
of the archive's mission. The threshold cells become clickable and reveal their member lists.

**Spec:**

- Each `Above 5% / Above 7% / Above 15%` cell in the threshold table becomes a disclosure
  control that expands the full member list for that (fiscal year, threshold): school name,
  state, and that school's draw rate for that year, sorted by rate descending. Buckets stay
  cumulative, matching the existing counts (a school above 15% appears in all three lists).
- Membership is derived in the frontend from the existing checked-in dataset
  (`endowment-draw-rate-recipe-data.ts` already carries every school's per-year rate) using
  the same eligibility rule the build script uses for the summary counts. **Consistency
  gate:** a unit test asserts the derived list length equals the rendered
  `above{5,7,15}Count` for every year — if they ever diverge, the derivation is wrong, never
  the counts.
- Schools with `hasCurrentSchoolPage` link to their school page; schools without one (closed
  or out-of-directory institutions) render unlinked with a "no longer operating /
  not in directory" marker — their inclusion is deliberate archive value, not an error.
- Schools with beginning value under ~$5M carry a small-endowment volatility marker in the
  list (consistent with the derived-metrics floor rationale; the rate still shows).
- **Disclaimer, rendered above the table and repeated inside each expanded list** (must
  survive on its own when screenshotted):

  > Many things put a school on these lists besides financial stress: board-approved
  > spending of unrestricted quasi-endowment funds, drawing down a completed capital
  > campaign, deploying a large one-time gift, or ordinary volatility in a small endowment,
  > where a single transfer can swing the rate by whole percentage points. Appearing here is
  > not evidence of fiscal irresponsibility. Rates come from each school's own federal IPEDS
  > filing. Some states' UPMIFA statutes presume imprudence only above a 7% rate measured
  > against a multi-year average value — a different measure than the single-year rate shown
  > here.

- **Annotation-policy boundary (unchanged):** these lists are factual query renderings — the
  school's own reported number shown next to its name — not editorial annotations. The
  school-page annotation policy (descriptive-neutral strings, multi-year persistence, owner
  sign-off) still governs school pages and is not relaxed by this amendment.
- Accessibility: disclosure pattern must be keyboard/screen-reader native (`<details>` or
  equivalent), not hover-only; lists render as real DOM content.
- The methodology writeup (`docs/recipes/endowment-draw-rate.md`) gains a short section on
  bucket membership and the disclaimer rationale.

### Closed schools (promoted from open question to design decision)

Verified: closed schools that have left Scorecard have **no `institution_directory` row**, so
`school_facts_unified`'s inner join excludes them permanently; the 125 closed schools still in
the directory are all `in_scope=false`. Their IPEDS facts load fine. Decision needed in Phase 2
planning: (a) augment the directory from IPEDS HD for closed institutions (new `exclusion_reason`
handling, slug strategy, "closed" banner on school pages), or (b) serve closed-school history
only through raw API + recipes for now. Recommendation: (b) for this PRD, with (a) as its own
small follow-up PRD — school pages for closed institutions have UX and identity questions
(matching, aliasing, "this school no longer exists" framing) that deserve their own scope.

## Backfill plan

- **Phase 1: FY2020–FY2024** (5 releases — the FY2020 floor is where components begin; the first
  draft's FY2021 floor was off by one and would have dropped the COVID year).
  - FY2020–FY2022: complete data files from the datacenter (per-table ZIPs).
  - FY2023: provisional CSV exists; the **final** revision is Access-DB-only today.
  - FY2024: **Access-DB-only** (2024-25 provisional, March 2026) — `--access-fallback` from day
    one. Note the WSJ narrative events (Quincy's borrowing, Baldwin Wallace's reclassification,
    Averett's depletion) are FY2024 events: without the Access path, Phase 1 shows none of them.
- **Phase 2: values-only (`F2H01`/`F2H02`) back to FY2015** for a 10-year value trend (no draw
  rates pre-FY2020). `fact_mappings_for_data_year` applies all mappings to every year with no
  min-year gating — pre-FY2020 component vars simply resolve to nothing; backfill reports will
  show them missing, which is expected, not drift.
- Operational reality (measured, not assumed): no artifacts on disk; every release is a fresh
  download; `--access-fallback` re-downloads the full Access ZIP per invocation (tens–hundreds
  of MB); the downloader has no retry/resume. Budget a **full day** for the Phase 1+2 backfill,
  more if pre-2020 Tablesdoc naming drifts.
- Finance rides along automatically on future loads (download set derives from mappings; probe
  workflow unchanged).

## Pipeline commands

Spike (Phase 0) — FY2023 complete data file (exists today), dictionary check, fixture analysis.
**Phase 0 runs from the feature-branch worktree**: the draft Endowment mappings and the new
`analyze_endowment` script must exist on the branch before these commands run (they are not on
`main` during the spike; with zero Endowment mappings the dry run "passes" vacuously with 0
facts — that is a failed spike, not a passing one).

```bash
cd /Users/santhonys/Projects/Owen/colleges/collegedata-fyi   # or your checkout of the feature branch
source .env

# 1. Download the 2023-24 collection's F2 table + Tablesdoc (the --tables flag already exists).
#    The output directory is scratch/ipeds/<collection-year>-<release-type>/ where release-type
#    comes from the live NCES page — 2023-24 is now listed as Final (March 2026), so expect
#    scratch/ipeds/2023-24-final/. Take the directory, release type, release date text, and
#    metadata URL from the emitted release.json manifest; do NOT assume the values below.
python -m tools.ipeds.download_release --collection-year 2023-24 --tables F2223_F2
cat scratch/ipeds/2023-24-*/release.json
RELEASE_DIR=scratch/ipeds/2023-24-final    # substitute from the manifest

# 2. Confirm Part H variable codes AND valuesets (projection hazard: any value label on F2H03*
#    negative values would be silently converted to status facts)
python - "$RELEASE_DIR" <<'EOF'
import sys
from pathlib import Path
from tools.ipeds.metadata import parse_tablesdoc
meta = parse_tablesdoc(next(Path(sys.argv[1]).glob("*ablesdoc*.xlsx")))
for c in meta.columns:
    if c.table_name.upper().endswith("_F2") and c.var_name.upper().startswith("F2H"):
        print("VAR", c.table_name, c.var_name, "|", c.var_title)
for v in meta.value_labels:
    if v.var_name.upper().startswith("F2H"):
        print("VALUESET", v.var_name, v.code_value, "->", v.value_label)
EOF

# 3. Dry run (default) — writes scratch/ipeds/ipeds-<collection>-<type>-report.json.
#    --metadata-url is REQUIRED by load_release.py; take it (and release type/date text)
#    from release.json. GATE: the report must show F2223_F2 read with >0 projected
#    Endowment facts.
python -m tools.ipeds.load_release \
  --metadata-xlsx "$RELEASE_DIR"/<tablesdoc>.xlsx \
  --metadata-url "<metadata_url from release.json>" \
  --data-dir "$RELEASE_DIR" \
  --collection-year 2023-24 --data-year 2023 \
  --release-type "<release_type from release.json>" \
  --release-date-text "<release_date_text from release.json>" \
  --display-groups Endowment

# 4. NEW TOOLING (in scope for M0, does not exist yet): a fixture/identity analysis script —
#    per-school Part H values for named unitids, corpus-wide sign audit (count of positive
#    F2H03C per year), accounting-identity residuals, and draw-rate distribution. The current
#    dry-run report only emits counts + the first 20 facts and cannot do any of this.
#    Unitids: 201195 Baldwin Wallace, 148131 Quincy, 231420 Averett, 203580 Lake Erie,
#    152080 Notre Dame.
python -m tools.ipeds.analyze_endowment \
  --data-dir "$RELEASE_DIR" \
  --unitids 201195,148131,231420,203580,152080 \
  --out scratch/ipeds/endowment-spike-analysis.json
```

Load + backfill (Phase 1, after PR merge and after the loader fixes land). One
download+dry-run+apply cycle per release row; all flag values come from that release's
`release.json` manifest:

| FY (`--data-year`) | `--collection-year` | F2 table | Source path |
|---|---|---|---|
| 2020 | 2020-21 | `F1920_F2` | datacenter CSV |
| 2021 | 2021-22 | `F2021_F2` | datacenter CSV |
| 2022 | 2022-23 | `F2122_F2` | datacenter CSV |
| 2023 | 2023-24 | `F2223_F2` | CSV serves provisional values; revised final needs the Access path (loader fix 4) |
| 2024 | 2024-25 | `F2324_F2` | Access DB only — `--access-fallback` |

```bash
cd /Users/santhonys/Projects/Owen/colleges/collegedata-fyi
source .env
# Per release row above (example shown for FY2020; repeat for each row, substituting from
# that release's release.json). Add --access-fallback for 2024-25. Dry-run first (omit
# --apply), review the report + analyze_endowment output, then re-run with --apply.
python -m tools.ipeds.download_release --collection-year 2020-21 --tables F1920_F2
python -m tools.ipeds.load_release \
  --metadata-xlsx scratch/ipeds/2020-21-<type>/<tablesdoc>.xlsx \
  --metadata-url "<metadata_url from release.json>" \
  --data-dir scratch/ipeds/2020-21-<type> \
  --collection-year 2020-21 --data-year 2020 \
  --release-type "<release_type from release.json>" \
  --release-date-text "<release_date_text from release.json>" \
  --display-groups Endowment --apply
```

## QA plan

Fixture schools — expectations rewritten as **observations to record**, not outcomes to confirm
(the first draft treated WSJ claims as ground truth; review showed reclassifications and
interfund loans need not move Part H at all):

| School (unitid) | What to record |
|---|---|
| Baldwin Wallace (201195) | FY2020–24 Part H series. Note: the $20M restricted→unrestricted reclassification may legitimately not appear in Part H (Part A event). FY2023 F2H02 = $167.8M (verified). |
| Quincy University (148131) | FY2024 values via Access path. Note: a $6M interfund loan is an asset-composition swap; determine whether FY2024 03c/03d moved at all. FY2023 F2H02 = $22.7M (review-verified by school name; re-verify against unitid in M0). |
| Averett University (231420) | Draw-rate series FY2020–24 and which line the depletion shows in (03c vs 03d). Correction from first draft: FY2022 endowment was $26.7M; the $5.7M figure is FY2024. Re-verify against unitid in M0. |
| Lake Erie College (203580 — OH, not LECOM) | Full series; record draw rate, no threshold asserted. |
| University of Notre Dame (152080) | Control: FY2023 F2H02 = $16.96B (verified); expect ~4-5% draw, all components populated, identity holds. |
| Notre Dame College (204468) | Loads into `ipeds_facts` for FY≤2022 (absent from F2223 provisional onward); confirm it is queryable via raw API and correctly absent from school pages. |

Validation checks:

- **Reconciliation (re-specified; runs in M1 once facts are loaded):** note that our
  `scorecard_summary` table persists only `endowment_end` — Scorecard's `ENDOWBEGIN` is **not
  in our database**, so the gate compares against the **raw Scorecard institution file**
  (`Most-Recent-Cohorts-Institution_*.zip`, which carries both `ENDOWBEGIN` and `ENDOWEND`)
  joined to loaded `ipeds_facts` by UNITID. One Scorecard CSV download + one PostgREST query
  (`$SUPABASE_URL/rest/v1/ipeds_facts?...` with `apikey` + `Authorization` headers — the bare
  `https://api.collegedata.fyi/<table>` form returns "requested path is invalid"). Alignment
  discovered *empirically*: scan match rate across candidate data years over the **full
  population** of in-scope private nonprofits with non-null Scorecard endowment (1,112 schools;
  no 20-school samples, which cannot measure a 99% threshold). Verified during review: 5/5
  fixtures match exactly under FY-correct alignment (Scorecard's current file is FY2024).
  Gate: ≥99% exact match over the full correctly-aligned FASB population, with the discovered
  alignment documented.
  **Observed after the Phase 1 production backfill (June 10, 2026 Scorecard file):** the best
  alignment is FY2024. There are 1,110 in-scope private-nonprofit Scorecard rows with both
  values; 1,079 have complete F2 beginning/end fact pairs. Direct UNITID matches account for
  1,060. Of 19 reporting entities needing consolidation, 16 reconcile through exact OPEID6
  allocation rollups and two through unique exact beginning-and-ending residual matches.
  The Chicago School remains the one unreconciled entity because its Dallas branch has `NA`
  Scorecard values. Correct reporting-entity result: 1,078/1,079 = 99.907% (pass); the 31
  in-scope rows without F2 pairs are reported separately, not counted as independent F2
  reporters. That is 97.207% coverage of the in-scope Scorecard population, above the tool's
  95% anti-sparsity floor. All five corrected fixtures match both values exactly. The
  reproducible command is `tools/ipeds/reconcile_endowment_scorecard.py`; its JSON output lists
  every member UNITID and method and does not use fuzzy names.
- **Accounting identity:** `(F2H02 − F2H01) = F2H03A+F2H03B+F2H03C+F2H03D` per year via the
  analysis script (`F2H03` itself is not loaded — it is the calculated difference). Verified
  FY2023 baseline: identity holds 1318/1318. FY2020–21 checks run per-release during the M1
  backfill; expect failures ≈ the positive-03C population (~194 and ~184 rows at review time —
  treat these as tolerance bands, not exact gates; revisions move counts). Those failures
  drive the sign-normalization rules.
- **Coverage:** ~75% of F2 filers report Part H (rest are screener-'A' no-endowment schools).
  Record counts per year; expect ~1,300–1,350 reporters.
- **Status handling:** expect ~25% of filers to produce **no Part H facts at all**
  (screener-'A' no-endowment schools; blank values project to nothing) and near-zero
  imputations (first draft's "frequently imputed" was wrong — do not assert imputed counts).
  M0 confirms the representation; absence is the accepted design.

Success gates — M0 (FY2023 scope): variable codes confirmed; F2H valuesets empty (or a
projection escape hatch designed); dry run projects >0 Endowment facts; FY2023 sign audit and
identity within tolerance of the review baselines (≈0 positive `F2H03C`, identity holding for
essentially all reporters — treat material divergence as investigate, not auto-fail); fixture
dollar values re-verified against the corrected unitids. M1: per-release FY2020–21 sign audits;
reconciliation ≥99% under documented alignment; no regression in existing
`school_facts_unified` consumers.

## Risks and mitigations

- **Annotation as accusation.** Any event-asserting string ("unexplained withdrawal") is banned;
  descriptive-neutral copy, multi-year persistence requirement, small-denominator floor,
  imputed/ambiguous-input exclusion, human sign-off on final strings, dispute path. Caveats
  don't survive screenshots — the annotation text itself must be safe standalone.
- **Sign-convention contamination (FY2020–21).** ~15% opposite-sign filers; residual metric
  nulled for those years; normalization rules set from the M0 corpus audit, not per-school
  guesses.
- **Loader collateral damage on backfill.** The `ipeds_tables` provenance wipe and notes
  overwrite are fixed (or explicitly guarded) before any `--apply` rerun.
- **Access-DB dependency for the newest data.** FY2024 (and FY2023-final) only via
  `--access-fallback`/mdbtools; the provisional→final supersession in `ipeds_current_facts_cache`
  handles revisions once loaded.
- **Divergence from published figures.** Our sector numbers will differ from Perspective Data
  Science's audited-statement figures; framing is "independent estimate," with an explicit
  methodology-differences section. Decide acceptable-divergence handling before publishing the
  sector chart (open question).
- **Provisional revisions moving the sector chart.** FY2024 is provisional; the recipe dataset
  is versioned (regenerate + note on final release) rather than silently mutated.

## Rollout

- **M0 (spike, ~1 day, on the feature branch):** write the draft mappings and the **new
  `analyze_endowment` script** first (both must exist before the commands run), then FY2023
  download + dictionary/valueset probe + dry-run (gate: >0 projected Endowment facts) +
  fixture/sign/identity analysis. Go/no-go on: variable codes; F2H valuesets empty (or escape
  hatch designed); FY2023 results within tolerance of review baselines; fixture values
  re-verified against corrected unitids.
- **M1:** loader fixes (F-table year branch + candidate rule, backfill provenance fix,
  access-fallback loudness, strict release selection) + mappings + tests +
  `public-data.ts`/facts-route category plumbing; load FY2020–FY2024 (Access path for FY2024);
  ship the auto-appearing Endowment section.
- **M2:** values-only backfill to FY2015; `school_endowment_health` view (migration from main,
  post-merge apply per CLAUDE.md); school-page panel with reviewed annotation copy; API docs.
- **M3:** `/recipes/endowment-draw-rate` — precompute script + checked-in dataset + writeup with
  methodology-differences section; selection-neutral default view. Can swap order with M2's
  panel.
- **Beyond (separate decisions):** F1A publics; Part A / UNAEP proxy; FSA composite scores
  (needs OPEID); closed-school directory augmentation (own PRD); scorecard
  `scorecard_data_year` vintage-label investigation (separate bug, noted above).

## Open questions

1. **Dispute/correction channel:** what is the process when a school disputes a figure or
   annotation? (Currently nothing site-wide; needed before the Phase 2 panel ships.)
2. **Acceptable divergence:** if our sector estimate differs materially from
   WSJ/Perspective-published figures, do we publish with the difference explained, or hold?
3. **Closed-school serving path:** confirm recommendation (b) — raw API + recipe only for now,
   directory augmentation as a follow-up PRD — or pull (a) forward.
4. **Panel scope:** private nonprofits only until F1A lands, or render for publics with an
   accounting-standards note?

---

## Adversarial review log (2026-08-03)

Four independent adversarial reviews (federal-data verification against actual NCES files;
pipeline claims against repo code; product/editorial/legal exposure; QA-gate testability with
live production queries) were run before execution handoff. Material corrections folded in above:
component availability FY2020 not FY2021; FY2024 is Access-DB-only; F2H03C sign conventions and
FY2020–21 contamination; "reproduce the WSJ statistic" replaced with "independent estimate"
(reproduction is impossible from IPEDS); reconciliation gate re-specified (population, alignment,
full-population scan); Part H imputation expectation inverted (near-zero, not frequent);
"~1,600 filers" corrected; fixture expectations rewritten as observations (reclassifications and
interfund loans need not touch Part H); Averett FY2022 value corrected ($26.7M); loader gaps
promoted into M1 scope (backfill provenance wipe, F-table rename resolution, access-fallback
gating, release selection); projection hazard on negative values flagged for M0; recipe aligned
to the real static-dataset pattern; annotation policy rewritten (no event-asserting language,
persistence requirement, denominator floor); UPMIFA copy qualified (optional §4(d), minority
states, 3-yr-average denominator); `endowment_value_*` naming resolved now instead of deferred;
closed-school question resolved into a design decision (directory absence, not `in_scope`).

A ship-stage review pass (two specialist reviewers plus three cross-model adversarial
reviewers over the final diff) then corrected: two wrong fixture unitids in the spike command
(206349/231688 were Ursuline College and a VA nursing school — Quincy is 148131, Averett is
231420); the missing required `--metadata-url` flag; hardcoded release directory/type/date
assumptions (now taken from `release.json`); M0 sequencing (draft mappings must exist before
the spike commands, with a >0-facts gate against vacuous passes); the unreachable
revised-final path (`HasRV=0` + 404-only fallback); the `F2H03` identity restated as
`(F2H02 − F2H01)`; the reconciliation gate repointed at the raw Scorecard file (our DB lacks
`ENDOWBEGIN`); the 'A'-screener representation (absent rows, not status facts); exact-count
gates loosened to tolerance bands; the $5M floor scoped to `other_change_share` only; and the
Phase 1 apply command expanded to the full per-release table.
