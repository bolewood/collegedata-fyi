# IR hub backfill audit — 2026-11-22

Review-only crawl of every in-scope school with no live CDS artifact, after
PR #385 landed IR-hub discovery on `main` (`51d476a`). Nothing was archived,
enqueued, written to `schools.yaml`, or sent through the WAF/headless path.

## Counts

| Outcome | Count |
| --- | ---: |
| yes (CDS listing found) | 56 |
| no | 1,771 |
| unclear | 446 |
| **UNITIDs crawled** | **2,273** |

`published=false`. Sequential, 0.5 requests/second.

Unclear is **not** “confirmed no CDS”:

- 429 homepage timeout / connection failure from the crawl VM
- 15 DNS miss
- 2 `InvalidURL` (paths with spaces: Cerro Coso 111896, Normandale 174428)

That is 444 unreachable-from-this-VM rows plus 2 parser errors. A slower
re-crawl from GitHub Actions (or another network that can actually reach
`.edu` homepages) should happen before treating those schools as misses.

## Method

1. Snapshot `institution_cds_coverage` on 2026-11-20 for in-scope schools
   with `no_public_cds_found`, `not_checked`, or
   `source_not_automatically_accessible` → `missing_in_scope.csv` (2,273
   UNITIDs).
2. `tools/finder/backfill_ir_hubs.py` only selects homepage
   `no_pdfs_found` seeds plus never-checked rows. To cover the full missing
   list, the crawl CSV set `coverage_status=not_checked` and blanked
   `archive_last_outcome`.
3. For each school: fetch the homepage (8s HTTP timeout), follow at most one
   About page plus at most six IR/IE/fact-book URLs (`MAX_IR_HUB_URLS=6`,
   `MAX_ABOUT_PAGES=1`), classify `yes` / `no` / `unclear`.
4. GitHub `workflow_dispatch` on `ops-ir-hub-backfill.yml` returned 403 from
   the agent that ran this, so the crawl ran locally against `main` at the
   documented 0.5 rps. Same script, same politeness.

`review.csv` columns: `school_id,name,ipeds_id,cds,url,notes`.

## Caveats

- Yes means “this page looks like it lists a Common Data Set,” not “we
  archived a PDF.” Several homepage yeses were later false positives
  (`cds.benedict.edu` Career Development, Maranatha “CDs & Music”, New River
  `/cds/` Disability Services).
- Shared-system IR pages (Kent State regionals, Miami OH regionals,
  Embry-Riddle Prescott/Worldwide, BGSU-Firelands, SJU-Lancaster, Springfield
  ROCE, East Georgia → Georgia Southern) are parent collisions. The existing
  `dedupe_identical_seeds` / `shared_parent_seed` rules already refuse a
  second owner of the same URL.
- 24 of the 56 yes rows already had a `discovery_seed_url` in `schools.yaml`.
- Colorado Northwestern CC (126748) and UMass Dartmouth (167987) are in this
  coverage snapshot but not in `schools.yaml`. Do not expand corpus scope
  from this file; use `build_school_list.py --append-missing` separately.
- Mott’s IR page says the CDS is available upon request / behind sign-in.

## How to re-run

Polite, sequential, review-only. Do not pass `--apply` anywhere; the script
has no publish path.

```bash
# GitHub Actions (preferred network): Ops IR hub backfill
#   from_csv: tools/finder/audits/ir-hub-backfill-2026-11/missing_in_scope.csv
#   limit: 0
#   rps: 0.5
# Batch if the job would exceed the 240-minute timeout (~570 schools/batch).

# Local (same flags the workflow uses)
python tools/finder/backfill_ir_hubs.py \
  --from-csv tools/finder/audits/ir-hub-backfill-2026-11/missing_in_scope.csv \
  --out scratch/ir-hub-backfill/review.csv \
  --summary-json scratch/ir-hub-backfill/summary.json \
  --limit 0 \
  --rps 0.5
```

To crawl every missing school rather than only homepage-`no_pdfs_found`
seeds, set `coverage_status=not_checked` and blank `archive_last_outcome`
on the input CSV first (see `select_backfill_rows` in
`tools/finder/backfill_ir_hubs.py`). Resume/dedupe must key on UNITID, not
display name — several campuses share names.

A follow-up seed PR should only write `discovery_seed_url` for yes rows
verified as the same institution’s CDS listing.

## Timeout recrawl — 2026-11-22

The 446 unclear rows were recrawled the same day with a 25s timeout, one
retry, https/http and www/non-www variants, and a per-request process
kill. Record: `recrawl-timeouts/`.

| Outcome | Count |
| --- | ---: |
| yes | 0 |
| no | 13 |
| still unclear | 433 |

399 of the remaining unclears are HTTP 403 from this VM, not confirmed
misses. No new same-institution CDS listings, so nothing to add to the
seed PR. Re-run command is in `recrawl-timeouts/README.md`.
