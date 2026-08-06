# S1.3/1.4 Taxonomies and existing controls

- Probe taxonomy already exists: `20260418230000_probe_outcome_categories.sql:15` (15-way). Audit measures unknown-rate + classification quality, does not re-invent.
- Loaded-but-unserved inventory: separate intentional out-of-scope/closed from accidental exclusions (50 migrations inventoried).
- Archive health: post-ledger cohort attempt durations via `archive_queue_attempts` (20260716010500+); enqueue idempotency invariants in 20260713215000.
