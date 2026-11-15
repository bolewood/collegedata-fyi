# Scholarship directory: annual review and monitor triage

PRD 036 M4. Two jobs: the August to September re-verification of every program for
the next entering class, and handling what the change monitor
(`tools/scholarships/monitor.py`, workflow `scholarships-monitor.yml`) flags.

## What the monitor does and does not do

- Fetches each source URL of each served version politely (robots.txt, crawl delay,
  no logins or CAPTCHAs), once per distinct URL per run, and writes one row per
  version to `scholarship_version_checks`. It never edits `data/scholarships/` and
  never publishes terms.
- **Only a detected change in terms sets `needs_review = true`**, which flips the
  public status to `current_cycle_unconfirmed`. A change counts when the extracted
  main text changed and the change touches an amount, a date, a year or a selection
  word (guaranteed, automatic, competitive, considered, required, deadline, no
  longer, and a few close relatives such as "not guaranteed" and "finalist"), or a
  number within four words of GPA or grade point, SAT, ACT, credits, hours,
  semesters, recipients, scholars or awards (a renewal GPA of 3.0 becoming 3.2, a
  minimum SAT, the number of awards). Banners, news teasers, "last updated" dates,
  markup, phone numbers and visitor counts, and wording that moves none of those
  are ignored on purpose: the monitor under-alerts rather than flip a record on
  noise. A rewording that moves no token, or a threshold stated without those
  words nearby, will not be caught here; the annual review is the backstop.
- **Never changes public status** (listed in the issue under "For information"):
  stale signals (heading or deadline years that look old, every dated milestone
  past with no next-cycle year), unreachable sources (robots block, robots
  unreachable, login or CAPTCHA wall, any HTTP error including 404, a host that
  throttled, a "suspect page" such as a maintenance or soft-404 page served with
  HTTP 200), pages with no readable text (script-rendered, scanned PDF), and raw-byte
  changes to a source with no readable text. A 404 never means the program ended;
  check the live site by hand.
- A flag set by a change is carried forward on every later run until a person clears
  it, and every run's issue comment lists each still-flagged version (marked "still
  flagged"), so a run that failed after writing rows cannot hide a flag.
- One GitHub issue ("Scholarship monitor: terms changed or stale, review needed")
  collects the findings, each with the diff and a "save page" link for Archive.org.
  Click it to snapshot the new page before you edit anything.
- Schedule: weekly July to January, monthly February to June, plus a daily run that
  rechecks versions with a required or priority dated milestone 0 to 30 days away
  that have not been checked since their 30-day mark (or, inside 7 days, their 7-day
  mark), so a missed run is caught up the next day. Dispatch the workflow with
  `dry_run` on to preview a run.

## Browser fallback

Some school sites answer a plain HTTP client with 403 or 404 while serving the same
public page to a browser; a source like that shows up as `unreachable` on every run.
The workflow runs the monitor with `--browser-fallback`, which retries such a page
once through headless Chromium (Playwright, installed for this workflow only; if the
install fails the run continues over plain HTTP).

- **It does not get past bot challenges.** The browser loads only the one document
  requested: no scripts, XHR, iframes or later redirects (meta refresh, JavaScript).
  A page that needs JavaScript, or a challenge or CAPTCHA wall, comes back as
  `unreachable` or as a page with little readable text, never as a change.
- **Triggers:** only after the plain request got 403, 404 or 406 for the page, and
  never for a login, SSO redirect, CAPTCHA or bot-challenge response. One browser
  attempt per URL per run. A host whose fallback worked is read through the browser
  for the rest of the run, except for a source whose last good read was plain HTTP,
  which tries plain HTTP first. Spacing and Crawl-delay apply as usual.
- **robots.txt:** a robots.txt the plain client cannot read (network error, 5xx, other
  non-2xx but not 404/410, never a 429) is read through the browser first. Its rules
  apply; a Disallow still blocks and the browser never fetches a disallowed path; a
  404/410 means allow-all. An HTML or challenge page is not robots.txt. If the
  browser cannot read it either: an unreachable robots.txt stays `robots_unreachable`;
  a plain 4xx keeps its allow-all reading for plain fetches, but the browser is not
  used on that origin.
- **Never bypassed:** a robots Disallow, a login or SSO redirect, a CAPTCHA.
- **Hashes:** a rendered page is not byte-stable, so for a browser fetch only the
  normalized text and its tokens are compared (`raw_sha256` is ignored, including
  against the YAML hash). When a source switches transport, equal text is `none`, a
  change that moves no token re-baselines (`transport_rebaseline`), and a change that
  moves a token keeps the previous baseline and is listed under "For information"
  with its diff (`transport_flip_diff`); none of them sets `needs_review`. Check
  those by hand. Each source's `detail` entry records its `transport`.
- **Limit:** the main document is fetched through Playwright's own HTTP client
  (`route.fetch`), not Chromium's network stack, so a site that judges clients by TLS
  fingerprint may still refuse it. It worked for aggie.tamu.edu.
- Run it locally with `pip install -r tools/scholarships/monitor-requirements.txt`,
  `python -m playwright install chromium`, then `monitor.py --browser-fallback`.

## Triage a finding

1. Open the source URLs from the issue. Compare against the version in
   `data/scholarships/programs/<program_id>/`.
2. Wording or layout change, terms the same: clear the flag (below).
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

Stale signals and the other informational findings carry no flag, so there is
nothing to clear; act on them in the next re-verification batch (below).

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
