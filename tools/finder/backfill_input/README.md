Operational input for the review-only IR hub backfill (not a product dataset).

`missing_in_scope.csv` is a 2026-11-20 snapshot of in-scope
`institution_cds_coverage` rows with no live CDS artifact
(`no_public_cds_found`, `not_checked`, `source_not_automatically_accessible`).

`batch-0N.csv` are crawl slices of that list. Coverage is set to `not_checked`
so `backfill_ir_hubs.py` crawls every missing school, not only homepage
`no_pdfs_found` seeds. The workflow writes a review CSV only.
