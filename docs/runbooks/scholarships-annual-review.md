# Scholarship directory: annual review and monitor triage

PRD 036 M4. Two jobs: the August to September re-verification of every program for
the next entering class, and handling what the change monitor
(`tools/scholarships/monitor.py`, workflow `scholarships-monitor.yml`) flags.

## What the monitor does and does not do

- Fetches each source URL of each served version politely (robots.txt, crawl delay,
  no logins or CAPTCHAs) and writes one row per version to
  `scholarship_version_checks`. It never edits `data/scholarships/` and never
  publishes terms.
- `needs_review = true` on the latest row flips the public status to
  `current_cycle_unconfirmed`. That happens for a changed page (normalized text
  differs from the last check) and for a stale signal.
- A robots block, unreachable robots.txt, login or CAPTCHA wall, or a 404 is
  recorded as `unreachable` and does not set `needs_review`. A 404 never means the
  program ended; check the live site by hand.
- One GitHub issue ("Scholarship monitor: terms changed or stale, review needed")
  collects new findings, each with the diff and a "save page" link for
  Archive.org. Click the link to snapshot the new page before you edit anything.
- Schedule: weekly July to January, monthly February to June, plus a daily run that
  only rechecks versions with a required or priority dated milestone 30 or 7 days
  away. Dispatch the workflow with `dry_run` on to preview a run.

## Triage a finding

1. Open the source URLs from the issue. Compare against the version in
   `data/scholarships/programs/<program_id>/`.
2. Pure wording or layout change, terms the same: clear the flag (below).
3. Terms changed for the same entering class: it is a correction. Add a new version
   with `supersedes` (published versions are immutable), re-verify with evidence
   locators, merge, then run the loader from `main`. The new version has no
   check history, so it starts clean.
4. A new cycle opened: add a new version for the new `entry_year`; do not edit the
   old one.
5. Page gone or program ended: set `status` on the program, or add a
   `historical_only` version; do not infer it from a 404.

### Clear a flag

Only after re-verifying. This inserts a cleared row that keeps the stored baseline
(hashes and tokens), so the next check diffs against the page you just reviewed.
Replace the ids and note; run it with the service role.

```sql
insert into public.scholarship_version_checks (program_id, version_id, result, needs_review, detail)
select program_id, version_id, 'unchanged', false,
       (detail - 'review' - 'stale_signals' - 'needs_review_carried')
         || jsonb_build_object('cleared_note', 'reviewed 2026-09-12: wording only')
from public.scholarship_version_checks
where program_id = 'PROGRAM_ID' and version_id = 'VERSION_ID'
order by checked_at desc, id desc
limit 1;
select public.refresh_scholarship_directory_cache();
```

A stale signal comes back on the next run if the page still has it; fix the cause
(a new version, or a corrected page) rather than clearing it repeatedly.

## August to September: re-verify for the next entering class

Early deadlines start in October and November, so the work finishes before then.

1. **Batch by deadline month.** List served versions with
   `select program_id, deadline_months from scholarship_directory_cache`, or from
   the YAML. Work earliest first: programs with an October or November deadline in
   the first batch, December next, then January to March, then the rest.
2. **Per program, an agent re-verifies for the next entering class.** Same process
   as M5 drafting: fetch the official pages through `polite_fetch`, draft a new
   version with `field_evidence` locators, run the validator, no sum totals, no
   inferred "automatic". Last year's dates are never copied forward: a deadline is
   entered only when the new cycle's page states it.
3. **Owner spot-check each batch** (about an hour per batch): open the cited
   locators for a sample, confirm terms and dates against the live page, record the
   check in the PR checklist and set `owner_spot_checked`.
4. Merge, then load from `main` (`python tools/scholarships/load.py --apply`).

### The 30-day rule

A program that is still unconfirmed 30 days before its likely early deadline is
shown as past-cycle and its dates are never carried forward.

- Last year's version needs nothing from you: from 1 July the freshness rule already
  shows it as `past_cycle`, and nothing publishes a guessed replacement.
- At the 30-day mark (30 days before the previous cycle's earliest required or
  priority deadline, from `deadline_months`), list programs with no verified version
  for the next entering class. Leave them unverified. Do not copy last year's version
  forward and do not set `cycle_through_date` or any milestone to a guessed date.
- Nothing automatic enforces the rest. A current-cycle version still flagged
  `needs_review` at that mark shows as `current_cycle_unconfirmed`, not past-cycle.
  The reviewer re-verifies it or, if the official page is gone or unchanged from
  last cycle, adds a `historical_only` version (or sets the program `status`) so it
  stops reading as current.
