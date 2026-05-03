# PRD 018 Section H Audit

Generated: `2026-05-03T03:43:15.092512+00:00`

## Summary

- Rows audited: `365`
- Rows with >=60% core merit metrics: `236` (`64.7%`)
- Average core answerability: `66.2%`
- Top-100 average core answerability: `80.2%`
- Rows with >=60% all target metrics: `234` (`64.1%`)
- Effective first-year merit answerability before redrain: `200` (`54.8%`)
- Effective first-year merit answerability after H2A redrain: `252` (`69.0%`)

Note: top-100 in this audit means the 100 latest primary 2024+ rows with the
largest reported applicant counts, not the 100 most selective institutions.

## Decision

The initial audit showed PRD 018 should not jump straight to the public
`school_merit_profile` projection: broad H-section fields cleared the rough 60%
line, but the load-bearing merit field did not. First-year institutional
non-need scholarship/grant aid was only `52.3%` directly answerable and `54.8%`
answerable after treating reported zero recipients or zero non-need grant
dollars as a defensible no-merit signal.

The H2A cleanup and targeted redrain moved direct `H.2A02` coverage to `66.8%`
and effective merit answerability to `69.0%`. The next PRD 018 decision is
whether to ship the public merit profile with explicit missing-data caveats, or
do a second H2A pass first.

## H2A Cleaner Follow-up

Spot audit of high-application misses found a deterministic Docling split-table
case, not a source-data absence. UC Irvine 2024-25 reported H2A values in the
stored markdown, but Docling emitted row `N` without its letter and moved rows
`O`-`Q` into a headerless continuation table. The Tier 4 cleaner only accepted
explicit `N`-`Q` row labels in a single cohort-header table, so all H2A values
were missed.

Cleaner patch:

- Infer H2A row letters from stable row text for `N`-`Q`.
- Treat headerless `O`-`Q` continuation tables as first-year/full-time,
  all full-time, and less-than-full-time columns.
- Repair the adjacent H2 split-table shape where Docling drops row `J` and
  combines `K`/`L` values into the same cells, because PRD 018 also uses
  average aid package and need-grant metrics.
- Bump `tier4_docling` to `0.3.2` so future redrains write fresh canonical
  artifacts instead of colliding with existing `0.3.1` rows.

Measured against current latest 2024+ Tier 4 browser rows:

- Tier 4 latest rows: `272`
- Direct `H.2A02` misses before cleaner patch: `155`
- Misses recovered by rerunning the patched cleaner on stored markdown: `57`
- Still missing after deterministic re-clean: `98`

Top recovered schools include UC Irvine, UC Santa Barbara, Binghamton,
Northwestern, Buffalo, Notre Dame, Tulane, Hofstra, TCU, Montana State, Lehigh,
American, and Kansas State.

Targeted redrain applied: `57` candidate documents re-extracted as
`tier4_docling` `0.3.2` and refreshed projection successfully.

- Direct `H.2A01` after redrain: `248 / 365` (`67.9%`)
- Direct `H.2A02` after redrain: `244 / 365` (`66.8%`)

This clears the rough 60% gate, but it is not enough to treat the public merit
profile as uniformly complete.

## Remaining Misses

The remaining `98` documents should be a separate follow-up, not mixed into the
first deterministic cleanup commit. Two plausible next paths:

- Spot-audit the remaining misses for a second dominant layout pattern, then add
  another narrow deterministic cleaner fixture if one exists.
- Extend the Tier 4 LLM fallback to target H2A specifically if the remaining
  misses are visibly present in markdown but too varied for reliable layout
  parsing.

Use the post-redrain audit to decide whether to ship the public merit profile at
the new coverage level with explicit missing-data caveats, or push for a second
H2A cleanup pass first.

## Target Metrics

| Metric | Field IDs | Answerable | Pct |
|---|---:|---:|---:|
| H1 need-based total scholarships/grants | `H.109` | 274 | 75.1% |
| H1 non-need-based total scholarships/grants | `H.121` | 289 | 79.2% |
| H2 first-year/full-time students awarded aid | `H.204` | 239 | 65.5% |
| H2 all full-time students awarded aid | `H.217` | 243 | 66.6% |
| H2 average financial-aid package, first-year/full-time | `H.210` | 236 | 64.7% |
| H2 average financial-aid package, all full-time | `H.223` | 254 | 69.6% |
| H2 average need-based scholarship/grant, first-year/full-time | `H.211` | 237 | 64.9% |
| H2 average need-based scholarship/grant, all full-time | `H.224` | 240 | 65.8% |
| H2 average need-based self-help, first-year/full-time | `H.212` | 236 | 64.7% |
| H2 average need-based self-help, all full-time | `H.225` | 239 | 65.5% |
| H2A students with non-need institutional grant aid, first-year/full-time | `H.2A01` | 248 | 67.9% |
| H2A average non-need institutional grant aid, first-year/full-time | `H.2A02` | 244 | 66.8% |
| H2A students with non-need institutional grant aid, all full-time | `H.2A05` | 204 | 55.9% |
| H2A average non-need institutional grant aid, all full-time | `H.2A06` | 202 | 55.3% |
| H6 institutional need-based aid for nonresidents | `H.601` | 121 | 33.2% |
| H6 institutional non-need aid for nonresidents | `H.602` | 171 | 46.8% |
| H6 average institutional aid to nonresidents | `H.605` | 168 | 46.0% |
| H14 institutional aid awarded for academics | `H.1401, H.1411` | 208 | 57.0% |
