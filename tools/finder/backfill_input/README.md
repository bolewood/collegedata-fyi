Operational input and review output for the review-only IR hub backfill (not a product dataset).

`missing_in_scope.csv` is a 2026-11-20 snapshot of in-scope
`institution_cds_coverage` rows with no live CDS artifact
(`no_public_cds_found`, `not_checked`, `source_not_automatically_accessible`).

`batch-0N.csv` are crawl slices of that list. Coverage is set to `not_checked`
so `backfill_ir_hubs.py` crawls every missing school, not only homepage
`no_pdfs_found` seeds.

`review.csv` is the completed review-only crawl of all 2,273 UNITIDs
(sequential, 0.5 rps, `published=false`): **56 yes / 1,771 no / 446 unclear**.
GitHub `workflow_dispatch` returned 403 from this agent, so the crawl ran
locally against main `51d476a`. Nothing was archived, enqueued, or written
to `schools.yaml`. Unclear is almost entirely homepage timeout/DNS from this
VM, not a confirmed missing CDS.

See `summary.json`, `yes.md`, and `unclear.md` for the rollup.
