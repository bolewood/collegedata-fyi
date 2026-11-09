# Dedup Plan — Lowercase-Dashed Slug vs Canonical Short-ID

**Generated:** 2026-04-20 | **Input:** `/tmp/dedup_plan.json`

## Context

34 cds_documents rows had `school_name` set to a lowercase-dashed string (the school_id fell through to display as the name), exposing duplicates where the same real school was archived under both a canonical short-id (`uf`, `unc`, `ucla`, …) and a full-name slug-id (`university-of-florida`, `university-of-north-carolina-at-chapel-hill`, …). Root cause: `archive-process` force_urls paths where `school_name` wasn't supplied and `schools.yaml` didn't have the slug-id, so the fallback `schoolName = entry?.name ?? schoolId` stuck the raw id into `school_name`.

**Already done in this session:**
- 10 display-only slug-names rewritten (Virginia Tech, Caltech, Univ. of Chicago, etc. — 130 rows touched)
- 3 no-year-overlap pairs merged (ohio-state-university → osu, university-of-california-davis → uc-davis, johns-hopkins-university → johns-hopkins)

**This plan covers:** 23 pairs with year-level overlap.

## Policy

1. **Canonical short-id wins** as the surviving `school_id` (e.g., `uf`, `umich`, `ucla`, `unc`).
2. **Slug-only years** → move slug-side row to canonical school_id + set school_name to canonical. No conflict.
3. **Canon-only years** → keep as-is. No work.
4. **Overlap years** → per-year decision:
   - Higher `schema_fields_populated` wins
   - On tie, canonical side wins
   - Loser's `cds_artifacts` rows are deleted (FK cascade), then loser's `cds_documents` row is deleted

**Per-row touched tables:** `cds_documents` (update or delete), `cds_artifacts` (delete on losers), `archive_queue` (dedupe by `enqueued_run_id`), `school_hosting_observations` (rebrand school_id).

**NOT touched:** `cds_artifacts.storage_path` keeps the old slug-id in the path string. Per prior dedup-migrate tooling convention — paths are string references; bytes already exist at the SHA-addressed location; a cosmetic path-rename is a separate follow-up.

## Summary

| Metric | Count |
|---|---:|
| Pairs | 23 |
| Overlap years (one doc deleted per) | 209 |
| — canonical side wins (slug row dropped) | 112 |
| — slug side wins (canon row dropped) | 97 |
| Slug-only years (moved to canonical id) | 60 |
| Canon-only years (no change) | 59 |
| **Total cds_documents rows deleted** | **209** |
| **Total cds_documents rows updated (school_id change)** | **60** |

## Per-pair breakdown

### `lehigh-university` → `lehigh`

- Overlap years: 11 (11 canon wins, 0 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 1

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2014-15 | overlap | 27 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2015-16 | overlap | 22 (tier4_docling, pdf_flat) | 22 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2016-17 | overlap | 24 (tier4_docling, pdf_flat) | 24 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2017-18 | overlap | 30 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2018-19 | overlap | 26 (tier4_docling, pdf_flat) | 26 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 36 (tier4_docling, pdf_flat) | 36 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 35 (tier4_docling, pdf_flat) | 35 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2021-22 | overlap | 40 (tier4_docling, pdf_flat) | 40 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 40 (tier4_docling, pdf_flat) | 40 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 30 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 733 (tier2_acroform, pdf_fillable) | 733 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| unknown | slug-only | 55 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `vanderbilt-university` → `vanderbilt`

- Overlap years: 10 (10 canon wins, 0 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 1

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2012-13 | overlap | 275 (tier1_xlsx, xlsx) | 275 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2013-14 | overlap | 3 (tier1_xlsx, xlsx) | 3 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2014-15 | overlap | 276 (tier1_xlsx, xlsx) | 276 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2017-18 | overlap | 281 (tier1_xlsx, xlsx) | 281 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2019-20 | overlap | 291 (tier1_xlsx, xlsx) | 291 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2020-21 | overlap | 398 (tier1_xlsx, xlsx) | 398 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2021-22 | overlap | 386 (tier1_xlsx, xlsx) | 386 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2022-23 | overlap | 392 (tier1_xlsx, xlsx) | 392 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2023-24 | overlap | 251 (tier1_xlsx, xlsx) | 251 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2024-25 | overlap | 482 (tier1_xlsx, xlsx) | 482 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| unknown | slug-only | 274 (tier1_xlsx, xlsx) | — | MOVE slug→canon |

### `bowdoin-college` → `bowdoin`

- Overlap years: 8 (7 canon wins, 1 slug wins)
- Slug-only years (to move): 17
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2001-02 | slug-only | 8 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2002-03 | slug-only | 8 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2003-04 | slug-only | 8 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2004-05 | slug-only | 10 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2005-06 | slug-only | 10 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2006-07 | slug-only | 12 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2007-08 | slug-only | 16 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2008-09 | slug-only | 16 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2009-10 | slug-only | 16 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2010-11 | slug-only | 19 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2011-12 | slug-only | 19 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2012-13 | slug-only | 19 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2013-14 | slug-only | 18 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2014-15 | slug-only | 18 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2015-16 | slug-only | 18 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2016-17 | slug-only | 18 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2017-18 | slug-only | 21 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2018-19 | overlap | 21 (tier4_docling, pdf_flat) | 21 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 23 (tier4_docling, pdf_flat) | 23 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 40 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 40 (tier4_docling, pdf_flat) | 40 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 48 (tier4_docling, pdf_flat) | 48 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 58 (tier4_docling, pdf_flat) | 58 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 631 (tier2_acroform, pdf_fillable) | 633 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| 2025-26 | overlap | 633 (tier2_acroform, pdf_fillable) | 633 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |

### `brandeis-university` → `brandeis`

- Overlap years: 4 (0 canon wins, 4 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 3

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2021-22 | overlap | 46 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 54 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 65 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 47 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |

### `wake-forest-university` → `wake-forest`

- Overlap years: 7 (5 canon wins, 2 slug wins)
- Slug-only years (to move): 5
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2014-15 | slug-only | 115 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2015-16 | slug-only | 104 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2016-17 | slug-only | 125 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2017-18 | slug-only | 174 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2018-19 | overlap | 125 (tier4_docling, pdf_flat) | 125 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 122 (tier4_docling, pdf_flat) | 123 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 314 (tier4_docling, pdf_flat) | 314 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2021-22 | overlap | 306 (tier4_docling, pdf_flat) | 260 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 340 (tier4_docling, pdf_flat) | 331 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 364 (tier4_docling, pdf_flat) | 365 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 631 (tier2_acroform, pdf_fillable) | 631 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| unknown | slug-only | 83 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `university-of-florida` → `uf`

- Overlap years: 2 (2 canon wins, 0 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 4

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2023-24 | overlap | 56 (tier4_docling, pdf_flat) | 61 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 59 (tier4_docling, pdf_flat) | 59 (tier4_docling, pdf_flat) | DROP slug row, keep canon |

### `swarthmore-college` → `swarthmore`

- Overlap years: 6 (6 canon wins, 0 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 20

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2000-01 | overlap | 0 (None, other) | 0 (None, other) | DROP slug row, keep canon |
| 2015-16 | overlap | 0 (None, other) | 0 (None, other) | DROP slug row, keep canon |
| 2016-17 | overlap | 0 (None, other) | 0 (None, other) | DROP slug row, keep canon |
| 2021-22 | overlap | 0 (None, other) | 0 (None, other) | DROP slug row, keep canon |
| 2024-25 | overlap | 1 (tier2_acroform, pdf_fillable) | 1 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| 2025-26 | overlap | 614 (tier2_acroform, pdf_fillable) | 614 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| unknown | slug-only | 0 (None, other) | — | MOVE slug→canon |

### `university-of-north-carolina-at-chapel-hill` → `unc`

- Overlap years: 25 (0 canon wins, 25 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2000-01 | overlap | 128 (tier4_docling, pdf_flat) | 19 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2001-02 | overlap | 114 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2002-03 | overlap | 112 (tier4_docling, pdf_flat) | 19 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2003-04 | overlap | 130 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2004-05 | overlap | 126 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2005-06 | overlap | 109 (tier4_docling, pdf_flat) | 20 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2006-07 | overlap | 137 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2007-08 | overlap | 114 (tier4_docling, pdf_flat) | 15 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2008-09 | overlap | 134 (tier4_docling, pdf_flat) | 28 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2009-10 | overlap | 114 (tier4_docling, pdf_flat) | 29 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2010-11 | overlap | 98 (tier4_docling, pdf_flat) | 24 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2011-12 | overlap | 113 (tier4_docling, pdf_flat) | 35 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2012-13 | overlap | 140 (tier4_docling, pdf_flat) | 38 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2013-14 | overlap | 84 (tier4_docling, pdf_flat) | 31 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2014-15 | overlap | 106 (tier4_docling, pdf_flat) | 36 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2015-16 | overlap | 113 (tier4_docling, pdf_flat) | 26 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2016-17 | overlap | 138 (tier4_docling, pdf_flat) | 29 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2017-18 | overlap | 119 (tier4_docling, pdf_flat) | 35 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2018-19 | overlap | 35 (tier4_docling, pdf_flat) | 9 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2019-20 | overlap | 168 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2020-21 | overlap | 233 (tier4_docling, pdf_flat) | 28 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 238 (tier4_docling, pdf_flat) | 28 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 222 (tier4_docling, pdf_flat) | 17 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 70 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 325 (tier4_docling, pdf_flat) | 51 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| unknown | slug-only | 48 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `university-of-wisconsin-madison` → `uw-madison`

- Overlap years: 1 (1 canon wins, 0 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 6

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2024-25 | overlap | 760 (tier2_acroform, pdf_fillable) | 760 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| unknown | slug-only | 0 (None, pdf_flat) | — | MOVE slug→canon |

### `university-of-pittsburgh` → `upitt`

- Overlap years: 1 (1 canon wins, 0 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 7

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2022-23 | overlap | 143 (tier4_docling, pdf_flat) | 143 (tier4_docling, pdf_flat) | DROP slug row, keep canon |

### `university-of-california-los-angeles` → `ucla`

- Overlap years: 1 (1 canon wins, 0 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 7

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2019-20 | overlap | 0 (None, pdf_flat) | 0 (None, pdf_flat) | DROP slug row, keep canon |

### `tufts-university` → `tufts`

- Overlap years: 10 (9 canon wins, 1 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2015-16 | overlap | 25 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2016-17 | overlap | 27 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2017-18 | overlap | 33 (tier4_docling, pdf_flat) | 33 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2018-19 | overlap | 32 (tier4_docling, pdf_flat) | 32 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 26 (tier4_docling, pdf_flat) | 26 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 36 (tier4_docling, pdf_flat) | 36 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2021-22 | overlap | 25 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 42 (tier4_docling, pdf_flat) | 42 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 25 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 53 (tier4_docling, pdf_flat) | 31 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |

### `claremont-mckenna-college` → `claremont-mckenna`

- Overlap years: 13 (0 canon wins, 13 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 1

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2012-13 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2013-14 | overlap | 26 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2014-15 | overlap | 18 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2015-16 | overlap | 26 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2016-17 | overlap | 21 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2017-18 | overlap | 27 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2018-19 | overlap | 35 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2020-21 | overlap | 42 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 44 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 42 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 31 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 56 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2025-26 | overlap | 59 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| unknown | slug-only | 42 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `university-of-michigan` → `umich`

- Overlap years: 7 (0 canon wins, 7 slug wins)
- Slug-only years (to move): 20
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2000-01 | slug-only | 118 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2001-02 | slug-only | 123 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2002-03 | slug-only | 115 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2003-04 | slug-only | 121 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2004-05 | slug-only | 108 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2005-06 | slug-only | 132 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2006-07 | slug-only | 84 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2007-08 | slug-only | 131 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2008-09 | slug-only | 114 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2009-10 | slug-only | 146 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2010-11 | slug-only | 128 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2011-12 | slug-only | 171 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2012-13 | slug-only | 115 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2013-14 | slug-only | 85 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2014-15 | slug-only | 98 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2015-16 | slug-only | 139 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2016-17 | slug-only | 183 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2017-18 | slug-only | 116 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2018-19 | overlap | 134 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2019-20 | overlap | 136 (tier4_docling, pdf_flat) | 32 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2020-21 | overlap | 166 (tier4_docling, pdf_flat) | 32 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 166 (tier4_docling, pdf_flat) | 32 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 158 (tier4_docling, pdf_flat) | 35 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 180 (tier4_docling, pdf_flat) | 34 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 90 (tier4_docling, pdf_flat) | 33 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2025-26 | slug-only | 367 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| unknown | slug-only | 74 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `purdue-university` → `purdue`

- Overlap years: 7 (1 canon wins, 6 slug wins)
- Slug-only years (to move): 5
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2014-15 | slug-only | 260 (tier1_xlsx, xlsx) | — | MOVE slug→canon |
| 2015-16 | slug-only | 261 (tier1_xlsx, xlsx) | — | MOVE slug→canon |
| 2016-17 | slug-only | 264 (tier1_xlsx, xlsx) | — | MOVE slug→canon |
| 2017-18 | slug-only | 264 (tier1_xlsx, xlsx) | — | MOVE slug→canon |
| 2018-19 | overlap | 260 (tier1_xlsx, xlsx) | 301 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2019-20 | overlap | 258 (tier1_xlsx, xlsx) | 36 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2020-21 | overlap | 260 (tier1_xlsx, xlsx) | 34 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 249 (tier1_xlsx, xlsx) | 29 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 270 (tier1_xlsx, xlsx) | 27 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 278 (tier1_xlsx, xlsx) | 36 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 287 (tier1_xlsx, xlsx) | 63 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2025-26 | slug-only | 419 (tier1_xlsx, xlsx) | — | MOVE slug→canon |

### `george-washington-university` → `gwu`

- Overlap years: 7 (6 canon wins, 1 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2018-19 | overlap | 37 (tier4_docling, pdf_flat) | 37 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 37 (tier4_docling, pdf_flat) | 37 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 32 (tier4_docling, pdf_flat) | 18 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 39 (tier4_docling, pdf_flat) | 39 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 50 (tier4_docling, pdf_flat) | 50 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 62 (tier4_docling, pdf_flat) | 62 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 62 (tier4_docling, pdf_flat) | 62 (tier4_docling, pdf_flat) | DROP slug row, keep canon |

### `barnard-college` → `barnard`

- Overlap years: 8 (0 canon wins, 8 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 4

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2017-18 | overlap | 19 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2018-19 | overlap | 23 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2019-20 | overlap | 36 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2020-21 | overlap | 22 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 24 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 37 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 50 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 2 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |

### `drexel-university` → `drexel`

- Overlap years: 7 (5 canon wins, 2 slug wins)
- Slug-only years (to move): 4
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2015-16 | slug-only | 32 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2016-17 | slug-only | 35 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2017-18 | slug-only | 29 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2018-19 | overlap | 26 (tier4_docling, pdf_flat) | 28 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 36 (tier4_docling, pdf_flat) | 37 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 35 (tier4_docling, pdf_flat) | 17 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 39 (tier4_docling, pdf_flat) | 39 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 50 (tier4_docling, pdf_flat) | 50 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 46 (tier4_docling, pdf_flat) | 46 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 27 (tier4_docling, pdf_flat) | 1 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2025-26 | slug-only | 18 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `bates-college` → `bates`

- Overlap years: 25 (2 canon wins, 23 slug wins)
- Slug-only years (to move): 1
- Canon-only years (no change): 2

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 1999-00 | overlap | 8 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2000-01 | overlap | 1 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2001-02 | overlap | 15 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2002-03 | overlap | 20 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2003-04 | overlap | 19 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2004-05 | overlap | 14 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2007-08 | overlap | 11 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2008-09 | overlap | 17 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2009-10 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2010-11 | overlap | 17 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2011-12 | overlap | 16 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2012-13 | overlap | 17 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2013-14 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2014-15 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2015-16 | overlap | 27 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2016-17 | overlap | 23 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2017-18 | overlap | 25 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2018-19 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2019-20 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2020-21 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 28 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2022-23 | overlap | 37 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 34 (tier4_docling, pdf_flat) | 0 (None, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2024-25 | overlap | 638 (tier2_acroform, pdf_fillable) | 638 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| 2025-26 | overlap | 618 (tier2_acroform, pdf_fillable) | 618 (tier2_acroform, pdf_fillable) | DROP slug row, keep canon |
| unknown | slug-only | 11 (tier4_docling, pdf_flat) | — | MOVE slug→canon |

### `rice-university` → `rice`

- Overlap years: 16 (16 canon wins, 0 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2008-09 | overlap | 23 (tier4_docling, pdf_flat) | 23 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2009-10 | overlap | 22 (tier4_docling, pdf_flat) | 22 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2010-11 | overlap | 23 (tier4_docling, pdf_flat) | 23 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2011-12 | overlap | 23 (tier4_docling, pdf_flat) | 23 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2012-13 | overlap | 31 (tier4_docling, pdf_flat) | 31 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2014-15 | overlap | 33 (tier4_docling, pdf_flat) | 33 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2015-16 | overlap | 28 (tier4_docling, pdf_flat) | 28 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2016-17 | overlap | 37 (tier4_docling, pdf_flat) | 37 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2017-18 | overlap | 32 (tier4_docling, pdf_flat) | 32 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2018-19 | overlap | 38 (tier4_docling, pdf_flat) | 38 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 38 (tier4_docling, pdf_flat) | 38 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 24 (tier4_docling, pdf_flat) | 24 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2021-22 | overlap | 41 (tier4_docling, pdf_flat) | 41 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 44 (tier4_docling, pdf_flat) | 44 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 44 (tier4_docling, pdf_flat) | 44 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 58 (tier4_docling, pdf_flat) | 58 (tier4_docling, pdf_flat) | DROP slug row, keep canon |

### `northeastern-university` → `northeastern`

- Overlap years: 5 (4 canon wins, 1 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 2

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2020-21 | overlap | 43 (tier4_docling, pdf_flat) | 43 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2021-22 | overlap | 38 (tier4_docling, pdf_flat) | 38 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2022-23 | overlap | 48 (tier4_docling, pdf_flat) | 48 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 30 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 60 (tier4_docling, pdf_flat) | 33 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |

### `georgetown-university` → `georgetown`

- Overlap years: 22 (21 canon wins, 1 slug wins)
- Slug-only years (to move): 2
- Canon-only years (no change): 0

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2001-02 | slug-only | 30 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2002-03 | slug-only | 30 (tier4_docling, pdf_flat) | — | MOVE slug→canon |
| 2003-04 | overlap | 30 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2004-05 | overlap | 25 (tier4_docling, pdf_flat) | 25 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2005-06 | overlap | 23 (tier4_docling, pdf_flat) | 23 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2006-07 | overlap | 31 (tier4_docling, pdf_flat) | 31 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2007-08 | overlap | 0 (None, pdf_fillable) | 0 (None, pdf_fillable) | DROP slug row, keep canon |
| 2008-09 | overlap | 0 (None, pdf_fillable) | 0 (None, pdf_fillable) | DROP slug row, keep canon |
| 2009-10 | overlap | 0 (None, pdf_fillable) | 0 (None, pdf_fillable) | DROP slug row, keep canon |
| 2010-11 | overlap | 0 (None, pdf_fillable) | 0 (None, pdf_fillable) | DROP slug row, keep canon |
| 2011-12 | overlap | 27 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2012-13 | overlap | 21 (tier4_docling, pdf_flat) | 21 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2013-14 | overlap | 29 (tier4_docling, pdf_flat) | 29 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2014-15 | overlap | 27 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2015-16 | overlap | 26 (tier4_docling, pdf_flat) | 26 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2016-17 | overlap | 27 (tier4_docling, pdf_flat) | 27 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2017-18 | overlap | 30 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2018-19 | overlap | 40 (tier4_docling, pdf_flat) | 40 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2019-20 | overlap | 42 (tier4_docling, pdf_flat) | 42 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 36 (tier4_docling, pdf_flat) | 36 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2021-22 | overlap | 40 (tier4_docling, pdf_flat) | 40 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2023-24 | overlap | 53 (tier4_docling, pdf_flat) | 53 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 63 (tier4_docling, pdf_flat) | 63 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2025-26 | overlap | 57 (tier4_docling, pdf_flat) | 0 (None, docx) | DROP canon row, MOVE slug (rare) |

### `new-york-university` → `nyu`

- Overlap years: 6 (4 canon wins, 2 slug wins)
- Slug-only years (to move): 0
- Canon-only years (no change): 1

| Year | Kind | Slug fields (producer, format) | Canon fields (producer, format) | Action |
|---|---|---|---|---|
| 2019-20 | overlap | 34 (tier4_docling, pdf_flat) | 34 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2020-21 | overlap | 36 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2021-22 | overlap | 0 (None, pdf_flat) | 405 (tier1_xlsx, xlsx) | DROP slug row, keep canon |
| 2022-23 | overlap | 38 (tier4_docling, pdf_flat) | 32 (tier4_docling, pdf_flat) | DROP canon row, MOVE slug (rare) |
| 2023-24 | overlap | 30 (tier4_docling, pdf_flat) | 30 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
| 2024-25 | overlap | 52 (tier4_docling, pdf_flat) | 54 (tier4_docling, pdf_flat) | DROP slug row, keep canon |
