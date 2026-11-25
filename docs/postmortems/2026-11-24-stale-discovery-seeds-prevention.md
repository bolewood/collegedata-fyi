# Prevention ledger: stale discovery seeds

**Date:** 2026-11-25
**For:** [the stale-seeds postmortem](2026-11-24-stale-discovery-seeds.md)
**Question:** can the archive fall behind on what schools publish, with every check looking fine, and no person told within a month?

This ledger maps each of the postmortem's ten causes to five things: the control that now catches it, how a person is told, the test that proves it, the evidence, and what is still not covered. Run logs and raw outputs from the overnight run are summarized where they are used.

## How a person is told

| Channel | Fires when | Reaches | Live today? |
|---|---|---|---|
| **Alarm issue** (label `alarm:discovery-renewal`; one per scope: `renewal:<Y>` and `arrivals:<Y>`, so up to two per CDS year) | Checked daily. It opens when current-year, two-year or next-year renewal is below its floor, or (its own `arrivals:<Y>` issue) when a year's arrivals fall below 0.4 of what the curve predicts (D17). While still below, it is superseded by a new assigned issue every 30 days and at once on a 5-point worsening (D16). It closes only when that year recovers; years two or more cycles old are retired | Assigned to the owner | From the first scheduled run, 2026-11-25 13:41 UTC (the assigned path has not run for real yet). It will open one, because renewal is 74.9% against a floor of 82.5% |
| **Discord #alerts, direct** | An alarm issue opens, is superseded (every 30 days or on a 5-point worsening), recovers, or is retired | Channel | Yes. The end-to-end test posted both kinds |
| **Discord #alerts, `workflow_run`** | The renewal workflow fails (short read, too few schools in the denominator, a floor mismatch, the alarm step failing) | Channel | Yes |
| **Discord #alerts, hourly scheduled-run check** | The renewal workflow has no scheduled run newer than 36 h (the hand check: 35 days) | Channel | From the first scheduled run; with no scheduled run ever seen it records nothing |
| **Discord #alerts, hourly board poll** | A board lamp turns `down`: Renewal (below a floor, no scheduled heartbeat in 36 h, an error, a hung run) or Stuck PDFs (90% or more still stuck) | Channel | Stuck PDFs: yes. Renewal: only after migration #469 is applied (slate until then) |
| **Monthly hand-check issue** | The 3rd of each month | Assigned to the owner | From the first scheduled run on 2026-12-03; shown once by dispatch (`[test]` #498) |

## The headline number and its floor

**Definition** (as in the postmortem): of schools with a live document filed under the previous CDS year, the share that also have one filed under the current year. `unknown` years don't count, and a school that has only the current year is not in the denominator. It is computed in one place, `tools/ops/discovery_renewal.py`. The PRD 040 snapshot imports it.

**Floor:** the posting curve read by months since the CDS year's fall. The points are 3% at 4 months, 18% at 6, 46% at 8, 68% at 10, 81% at 12 and 88% at 15, flat after that.
- **Current year:** curve − 5 points. That is 76% at the September switch and about 82.5% in late November.
- **Two-year:** of schools with either of the two previous years, the share that have the current one. Floor = current-year floor − 8.
- **Next year:** curve × 0.75, tracked once the curve reaches 18% (March 1).

The floor's calibration is an owner decision (D1). A healthy year likely sits near the raw curve each fall.

**Backtest** (reproduced independently by Fable). It replays the daily check at each month end, using `discovered_at` and `removed_at` on today's filed years:

| Date | Check | Renewal | Floor | Fires? |
|---|---|---:|---:|---|
| 2026-04-30 | next (2025-26) | 25.7% | 34.1% | **yes** |
| 2026-05-31 | next (2025-26) | 33.6% | 42.5% | **yes** |
| 2026-06-30 | next | 39.0% | 50.7% | **yes** |
| 2026-07-31 | next | 42.0% | 55.7% | **yes** |
| 2026-08-31 | next | 46.6% | 60.6% | **yes** |
| 2026-09-30 | current (2025-26) | 50.6% | 78.3% | **yes** |
| 2026-10-31 | current | 52.7% | 80.6% | **yes** |
| 2026-11-30 | current | 76.0% | 82.9% | **yes** |

The alarm would have opened an issue at the end of April 2026, from the next-year check. Under #493 alone that one issue would then have stayed open and silent through November (Fable's round-2 replay). The re-notification rule (D16) supersedes it every 30 days and on each 5-point worsening.

**Caveats:**
- It uses today's filed years. The 22 documents re-filed to 2025-26 by #455 count as 2025-26 in past months, so the real history was lower, which strengthens the conclusion.
- The archive began in April 2026 (about 350 of the live 2024-25 documents were first seen that month: 346 of 471 by `cds_year` in the local snapshot).
- 118 rows have no `discovered_at` and are treated as always present.
- The first backtest table in #474 was wrong: a timestamp parser silently returned None on Python 3.9. Fable caught it, and the parser now raises.

## Causes

### 1. A one-file seed finds a new year only if the file is in one of two places

- **Control:**
  - The renewal alarm (#474) measures the outcome whatever the seed is.
  - The stuck-seed sweep (#472) flags every one-file seed behind the cycle (122 when it merged; 95 after #495 moved seeds).
  - Seed dating (#490, #462) counts every seed whose newest year is behind, of any kind (403 on the final dry run: 93 one-file, 310 listing pages).
  - The monthly hand check (#471, #461) samples from outside the pipeline.
- **Told:**
  - The alarm issue and Discord, when renewal falls below its floor.
  - The Stuck PDFs lamp and Discord, at 90% or more still stuck.
  - The hand-check issue, monthly.
- **Test:** `test_every_stale_one_file_seed_is_flagged` runs on the real `schools.yaml` and a committed archive snapshot. The renewal snapshot test checks 364/479.
- **Evidence:**
  - Backtest: it fires from 2026-04-30.
  - Reinsertion 1: put the two-year cap back and 6 tests fail.
- **Not covered:**
  - The resolver mechanism itself is unchanged (`resolve.ts` parent walk, then standard paths). A one-file seed is still found stale, not fixed.
  - Listing-page seeds behind the cycle are counted and listed, not re-probed (D9).

### 2. The August fix fixed the shape, not the mechanism

- **Control:**
  - Sweeps account for every school, and `flagged + fresh + skipped == total` is enforced in code (#472).
  - Years are parsed as integers everywhere in the new code.
  - An every-copy sweep across Python, SQL and TypeScript found the remaining copies. Fixed: the Edge `fetchMostRecentDocumentForSchool` (#473); `probe_urls` cooldown stamping, headless caps and exit code, `published_years`, `kids_worklist`, `force_resolve_missing`, `fetch_known_years`, and the hardcoded years in `directory_enqueue_autopilot` and `top100_coverage` (#476).
  - One fixture of freshness-floor cases is tested from Python and TypeScript (#487).
- **Told:** CI, when the identity fails; the job, which errors.
- **Test:** `test_every_school_lands_in_exactly_one_bucket`, `test_unknown_year_is_not_the_newest` and `test_an_inconsistent_count_raises`.
- **Evidence:** reinsertions 1, 2a, 6 and 7a fail their tests. Trial 6 drops schools before counting, so the totals stay consistent, and it is still caught.
- **Not covered:**
  - Serving copies of the `unknown`-first sort (#479).
  - Directory re-seeding of unknown-only schools (#475, pulled from #473 after review).
  - Coverage SQL keys on `cds_year`, not `canonical_year` (#478).
  - The `cds_freshness_floor` rule now has four copies (SQL, `discovery_renewal`, `stuck_pdf_seeds`, web `freshness.ts`). The renewal job checks SQL against Python on every run, and a shared fixture checks Python against TypeScript. `discovery_renewal`'s copy is not yet in the shared fixture.

### 3. The re-probe's results swung, and November's status didn't show it

- **Control:**
  - `reprobe_outcome.py` (#472) counts a school as fixed only when its new seed reaches a CDS year newer than the archive's and at or past the floor (no section files, CDS evidence in the URL), or when it is a listing page that matches. Otherwise it is still stuck.
  - The Stuck PDFs lamp (#470) is `late` above 50% still stuck and `down` at 90% or more.
  - A heartbeat history table keeps each finished run (migration #469, open).
- **Told:** the lamp, then Discord at 90% or more. On deploy it went down on November's 71/78.
- **Test:** pipeline-lamps "71 of 78 still stuck is down", plus `test_old_file_is_not_a_fix_even_when_the_archive_has_nothing`, `test_section_file_is_never_a_fix` and `test_a_year_on_a_non_cds_link_is_ignored`.
- **Evidence:** reinsertion 3 (lamp ignores its result) fails 6 tests.
- **Not covered:**
  - Between 50% and 90% the lamp is only `late`, which Discord does not post. The renewal alarm is the push for that range.
  - History is kept only once #469 is applied.

### 4. An alarm existed, and no one acted on it

- **Control:**
  - One issue per breach, found by label and assigned to the owner (#474). Its body and title update while it stays below the floor. It is never commented on. It closes with one comment on recovery. While still below, it is superseded by a new assigned issue every 30 days and on a 5-point worsening (D16).
  - The monthly comment on standing issue #136 is removed (#472).
- **Told:** an issue assignment plus Discord.
- **Test:** `tools/ops/test_renewal_alarm.py` (create, update with no comment and no post, close, supersede, test-label isolation).
- **Evidence:** end-to-end on 2026-11-25:
  - Run 45551257009 opened `[test]` #489 and posted to #alerts.
  - Run 45551423155 closed it with one comment and posted the recovery.
- **Not covered:**
  - A person can still ignore an assigned issue, or mute Discord.
  - The alarm floor may be noisy each fall (D1). A noisy alarm is the #136 failure in another form. Re-derive the curve from snapshots after a year (#460).

### 5. The 2025-26 form prints last year's title

- **Control:**
  - The year reader fix (#455).
  - Same-year duplicates (#491, #467): every school with two or more live documents in one filed year, classified, reported in the renewal summary and report, and in the scoreboard.
- **Told:** the renewal report (alarm issue and step summary), the board detail line, and the scoreboard.
- **Test:** `test_year_detection.StaleTitleTest` and `test_same_year_duplicates`.
- **Evidence:**
  - Reinsertion 4 (stale-title correction disabled) fails.
  - 43 groups on the final dry run. At #491's live read there were 38: 22 `year_conflict` (4 look like #455 residue), 14 `same_file` and 2 `duplicate`.
- **Not covered:** the duplicates count is reported, not alarmed. A rise in duplicates does not post anywhere by itself.

### 6. Fetch failures had no owner

- **Control:** `fetch_failures.py` (#488, #468) lists schools whose listing is known and whose current-year file is missing, by cause from `archive_queue`. The counts go in the renewal summary and the board detail line. The list goes in the run summary and in the monthly hand-check issue (#497).
- **Told:** the board detail line, the monthly issue, and the renewal report.
- **Test:** `test_fetch_failures`.
- **Evidence:**
  - 160 failures on the final dry run: blocked 27, viewer 7, dead link 18, other 108 (at #488: 158, with 93 of the `other` being `no_pdfs_found`).
  - It agrees 6 of 6 with #452's blocked list.
- **Not covered:**
  - Viewer and section-file causes are poorly detected: 1 of 8 and 0 of 3 agree with #452, because the archive records no evidence for them.
  - `other` is the largest bucket.

### 7. The tests checked the code's choices, not the goal

- **Control:**
  - Goal-level tests over real data: every stale one-file seed in the real `schools.yaml` is flagged, and renewal on the snapshot is 364/479.
  - Every PR was reviewed for "does the test fail when the bug returns".
  - The overnight reinsertion pass put back all seven original bugs, as 8 trials.
- **Told:** CI.
- **Evidence:** see [Bug reinsertion](#bug-reinsertion). All 8 trials fail on 054b2b7, b9895cc1 and the final b429c142.
- **Not covered:** the snapshot fixtures go stale. They prove the mechanism, not today's corpus.

### 8. The pipeline page measures whether jobs run, not what they achieve

- **Control:**
  - The Renewal station's lamp is the outcome (#470). It fails closed on missing or malformed figures. An overridden test run can turn it red, never green.
  - The Stuck PDFs lamp is its result.
  - The heartbeat history table (#469).
  - Watching the watcher: three paths; see [Watching the watcher](#watching-the-watcher).
- **Told:** the board, then Discord.
- **Test:** pipeline-lamps (20+ renewal and stuck cases) and `test_discovery_renewal_staleness_alerts_once_then_recovers`.
- **Not covered:**
  - The Renewal lamp is slate until #469 is applied.
  - Other stations still report `ok` from completion, filed as #480 (refresh jobs ok on empty or partial counts).

### 9. The coverage page showed the symptom one school at a time

- **Control:**
  - The renewal number, on the board and in the alarm issue with a worklist grouped by seed kind.
  - The PRD 040 "This year's reports on file" tile from the snapshot's renewal block (#487, M2).
- **Told:** the issue and the board. The tile is a page, not a push.
- **Test:** the renewal tile test equals `renewal.both / renewal.previous` (#487).
- **Not covered:** the Coverage tile appears only once the first snapshot is committed (M0).

### 10. The project's goals never named this outcome

- **Control:**
  - The headline number is defined once (postmortem, PRD 040 amendment, `CLAUDE.md` data quality loop).
  - It is computed by one module and alarmed daily.
- **Told:** n/a.
- **Not covered:** PRD 001's success criteria are unchanged. Updating them is an owner edit.


## Bug reinsertion

Each original bug was put back in a throwaway worktree at `origin/main` 054b2b7 again on b9895cc1, and on the final `main` b429c142 (after all red-team fixes, including #505), the guarding tests were run, and the worktree was discarded.

| # | Bug put back | Test that fails |
|---|---|---|
| 1 | The stuck sweep skips schools with more than 2 archived years | `test_every_stale_one_file_seed_is_flagged`, `test_many_archived_years_do_not_hide_a_stale_one_file_seed` and 4 more |
| 2 | `unknown` is counted as the newest year (text sort) | `test_unknown_year_is_not_the_newest`, `test_an_undated_document_does_not_make_a_school_look_fresh` |
| 3 | The Stuck PDFs lamp ignores its result (`ok` at 71 of 78 still stuck) | pipeline-lamps "71 of 78 still stuck is down" and 5 more (vitest) |
| 4 | A 2025-26 form is filed as 2024-25 (the #455 correction disabled) | `test_year_detection.StaleTitleTest.*` |
| 5 | Relative links are resolved without `<base href>` (#457 reverted) | `resolve.test.ts` "relative links resolve against `<base href>`" and 5 more |
| 6 | The sweep silently drops no-seed schools before counting (totals stay consistent) | `test_every_school_lands_in_exactly_one_bucket` |
| 7a | Renewal accepts `unknown` as a year | `test_unknown_and_malformed_years_are_not_years` |
| 7b | Renewal counts schools that have only the current year | `test_a_school_with_only_the_current_year_is_not_in_the_denominator` |

## Watching the watcher

| If the renewal workflow… | Caught by | Test |
|---|---|---|
| fails (short read, too few schools, a floor mismatch, the alarm step) | the `workflow_run` post to #alerts. From #493, day after day too: every 7th consecutive failure posts | `test_scheduled_failure_on_default_branch_alerts`, `test_consecutive_failures` |
| stops running (disabled, deleted, schedule broken) | the hourly poll: no scheduled run in 36 h posts to #alerts | `test_discovery_renewal_staleness_alerts_once_then_recovers`, `test_first_poll_alerts_on_a_stale_run_and_baselines_a_fresh_one` |
| runs but heartbeats nothing, errors, or hangs | the station's SLA lamp (36 h), then the board poll. **Once #469 is applied.** The poll posts only on a change to down, so while the lamp is already down for a below-floor result a silent heartbeat failure (rejected write, warning, exit 0) is not alarmed by itself. The alarm issue and its monthly re-notify don't depend on the heartbeat, so a below-floor year is still pushed | pipeline-lamps "scheduled heartbeat older than 36h is down", "last scheduled error is down", "a hung run is a clock failure" |
| goes quiet because GitHub disabled schedules (60 days) | the optional outside check-in (D14), **once set up** | workflow test: the step is schedule-only and the URL is never printed |

## End-to-end test (2026-11-25)

| Run | Inputs | Result |
|---|---|---|
| 45551072276 | dry run (default) | It read 5,836 live rows and the floor 2025-26 agrees with SQL. 365/479 = 76.2% (two-year 379/536) against a floor of 82.5%. It printed the issue it would open, unassigned for a test. No heartbeat |
| 45551257009 | test mode, floor override 99 | It opened `[test]` #489, unassigned, and posted to #alerts. The heartbeat was rejected with a warning (the station is unregistered until #469) |
| 45551423155 | test mode, floor override 10 | It closed #489 with one comment ("Recovered: … 365 of 479 (76.2%) … Closing.") and posted the recovery to #alerts |
| 45580532234 | final code (after #502), test mode, override 99 | `alarm renewal:2025-26: create`. It opened `[test]` #504, unassigned, and posted to #alerts |
| 45580731560 | final code, test mode, override 10 | `alarm renewal:2025-26: close`. It closed #504 and posted "[test] Discovery renewal recovered: one-year 74.9%…" |

The lamp part could not be shown in production: the Renewal tile is slate until #469 is applied. It is covered by the web tests above. The first three runs used the alarm as merged in #474. The last two ran the final per-year, separate-scope model (#493, #499, #502) on `main`.

## Red team

Four rounds. In round 1, Gemini 4 Neon (xhigh) and Fable each answered, independently: "Describe three concrete ways the archive could fall behind again without a human being told within a month. For each, show where these controls fail to catch it." Fable checked each scenario against the code, ran simulations, and made one production read.

| # | Scenario (round 1) | Found by | Outcome |
|---|---|---|---|
| R1 | An open alarm issue swallows every later breach. A next-year collapse only edits the body for up to six months, and the September switch can close the issue while the old gap stays open | both | **Fixed** in #493 (D13): one issue per breaching year, each re-evaluated against its own floors until it recovers; an earlier year still short is shown on the board (`outstanding_below_floor`, #494) |
| R2 | The numerator counts flagged documents (change sheets, blank templates, section-only files, the wrong school's file): 9 of 422 2025-26 rows | both | **Fixed** in #493 (D12): flagged documents don't count, and they are listed in the report |
| R3 | A sub-program filing masks a missing main-campus CDS | Gemini | **Fixed** in #493: sub-institutional rows are excluded, and the count is reported |
| R4 | A daily failure goes quiet after the first `workflow_run` post | Fable | **Fixed** in #493: a consecutive-failure counter posts on every 7th day running |
| R5 | A Stuck PDFs move from down to late posts "recovered", and so does a run lamp | both | **Fixed** in #493: only `ok` posts a recovery |
| R6 | A Discord post that fails on the alarm's first day is never retried | Gemini | **Fixed** in #493: a marker in the issue body, retried on every run |
| R7 | GitHub disables scheduled workflows after 60 days with no repository activity, which silences every in-GitHub alert | Gemini | **Built, needs the owner:** an optional outside check-in (`RENEWAL_DEADMAN_URL`, D14) |
| R8 | The snapshot test always skips in CI | Fable | **Fixed** in #493: it now uses the committed fixture |
| R9 | A loss smaller than the margins (3–8 points mature; next year at 0.75 of the curve) never trips | both | **Accepted risk** (below) |
| R10 | Listing-page rot (CMS moves, WAF rules, viewers): seeds are counted, not re-probed | Gemini | **Accepted risk** (below) |
| R11 | Re-probe "fixes" are judged before the seed PR merges and before an archive run | Fable | **Accepted risk**: renewal still catches the outcome a day after the archive runs |
| R12 | Schools outside every denominator: no document, undated only, or the newest year 2022-23 or older | both | **Partly addressed**: #495 searched the 156 older schools and moved 38 seeds; the rest stay accepted |

### Round 2 (on the controls after #493)

| # | Scenario | Found by | Outcome |
|---|---|---|---|
| R13 | **The alarm latches per year.** Once a year's issue is open, nothing more is pushed for that year. Replaying 2026, the issue opens on 2026-04-19, then seven silent months follow while the gap grows from 8 to 28 points | both | **Fixed** in #499 (D16): an open issue below the floor is superseded by a new assigned issue and a Discord post every 30 days, and at once on a 5-point worsening. The 2026 replay now gives 8 notifications for 2025-26 between April and November |
| R14 | **A total stop takes 35–135 days to cross a floor**: the next-year check is off from September to February, and its margin widens in summer | both | **Fixed** in #499 (D17): an arrivals check. It fires when schools gaining a current- or next-year document in 30 days fall below a quarter of what the curve predicts, over 60 days in winter. The arrivals measure itself would have gone below on 2026-08-14 to 08-22. Under #499 that was only a body edit on an already-open issue, and a frozen archive took 38–49 days. An open arrivals breach is held until 30-day arrivals really recover. Round 3 found the gaps; see R21–R23 |
| R15 | An old year's issue that never reaches the mature floor keeps the lamp red forever and mutes later board alerts | Gemini | **Fixed** in #499: years two or more cycles old are retired with one post and never count as outstanding |
| R16 | A real-mode test dispatch reads `outstanding` from the test label and can turn the lamp green | Gemini | **Fixed** in #499: it always reads the real label |
| R17 | A crash in a `continue-on-error` step leaves the job green | Gemini | **Fixed** in #499: a final step fails the job |
| R18 | Unknown `data_quality_flag` values count as renewing | Gemini | **Fixed** in #499: any non-null flag doesn't count |
| R19 | Unextracted current-year documents count as renewing (21 today; a broken extractor would stay green) | both | **Reported**, not fixed: `unextracted_current_docs` is in the summary and on the board. Extraction is downstream (#477, #480) |
| R20 | The hand-check workflow has no staleness watch | Fable | **Fixed** in #499: 35 days |

### Round 3 (on the controls after #499)

| # | Scenario | Found by | Outcome |
|---|---|---|---|
| R21 | An arrivals breach is silent behind an already-open renewal issue: only body edits, 96 days for a total stop from today | both | **Fixed** in #502: arrivals has its own issue per year (`arrivals:<Y>`), so it is never hidden behind a renewal issue. A frozen archive from today opens a distinct `arrivals:2026-27` issue on 2027-01-05 on the final code (2027-01-06 on #502), when that year's check becomes active. Notifications are never more than 31 days apart |
| R22 | Pooled arrivals let hand catch-up of last year mask a dead pipeline for the new year | both | **Fixed** in #502: arrivals are judged per year, against each year's own cohort, on first documents |
| R23 | Losing 50–70% of arrivals is silent for 2–4 months at a 0.25 ratio | both | **Improved** in #502: the ratio is 0.4, the highest value that wouldn't have false-alarmed September–November 2026 per year. Partial stops removing 60–70% of arrivals took up to 38 days and 50% up to 118 (Fable round 4, before #505); total stops are covered in R26. Losses under about 60% of arrivals remain an accepted risk (below) |
| R24 | #502's first design, a "join" state machine, had 4 bugs: self-feeding debounce, reverting titles, the wrong year blamed, a swallowed alert | Gemini | **Removed**: the separate-scope design makes them impossible, and each scenario is a test |
| R25 | An `arrivals:<current>` issue could never close once the year's curve flattens, and the 60-day window had no hysteresis | Gemini | **Fixed** in #502: retire once uncheckable; the 60-day close needs `count_60 ≥ 0.5 × expected` |

### Round 4 (final, scoped against the declared accepted risks below)

| # | Scenario | Found by | Outcome |
|---|---|---|---|
| — | Re-ran R21–R23 by simulation on `main`. A frozen archive with the renewal issue open has a longest notification gap of 30 days. Hand catch-up still opens `arrivals:2026-27` on January 4 or 5. Partial loss is as stated | Fable | **Holds.** Fable: "NOTHING NEW AND CREDIBLE" |
| R26 | Moving from the 30-day to the 60-day window pulls in a month of pre-stop arrivals, and a cohort of 428 schools or fewer uses the 60-day window all autumn (2025-26's cohort was 417 on the 2026-11-24 snapshot; 435 on the final dry run). A 100% stop is then silent for 37–53 days | Gemini | **Fixed** in #505: both windows are judged every day (30-day from 6 expected, 60-day from 10), and a year is short if either is. Gemini's three scenarios now fire within 22 days. Total stops on the 1st of a month: median 20 days, max 34. Healthy-year noise is unchanged |

**Verification of #505 (Fable, simulating the code on `main` b429c142):**
- Gemini's scenarios: 22 days or less.
- Total stops on the 1st of each month: 4–25 days, except December 1 (34–35).
- Every stop date from September 2026 to August 2027, on the curve: 15 of 365 dates at a cohort of 417 (at most 46 days) and 12 of 365 at 480 (at most 43) take more than 31 days. They all start between about November 20 and December 4. After December 1 the current year's curve is flat, and the next year expects fewer than 6 arrivals a month until about January 4, so neither window is judged until then.
- No close deadlock in 288 outage-and-recovery cases. An issue that is held, not below, can still re-notify, and an autumn arrivals issue can't close by recovery after December 1 (the retire rule closes it in early January).

**Healthy-year noise** (a simulation of a full year, 5 seeds, the current year maturing at 87%, the next year at 0.9× the curve): a mean of 0.4 issues and 0.8 Discord posts a year. All of it is in one seed (a January arrivals dip and a March next-year check on its floor). This sits beside D1's warning that the raw curve runs close to a healthy year. Fable's earlier control, with different assumptions, tripped the two-year floor on 2027-09-01, and Fable's healthy controls: synthetic archives at 0.95–1.0 × the curve gave 0 issues over three years. A control built on the real manifest gave 0 issues through August 2027, then 13 `renewal:2026-27` issues (the two-year check at 73% against a 75% floor, re-notified monthly) from September 2027 to August 2028. Those come from schools that lapsed in 2025-26 and never return in the control. So expect several autumn issues a year in a healthy year under the current floors; that is the main reason D1 is the owner's call.

## Accepted risks (what is still not covered)

1. **Partial losses.** The mature floors (83% one-year, 75% two-year) allow a steady loss of about 13% a year indefinitely (0.866² ≈ 0.75, and lapsed schools leave both denominators after two years). The arrivals check (ratio 0.4) catches most total stops within 25 days (#505), except stops starting November 20 – December 4, which take up to 46 (risk 8), and a stop removing 60% or more of a year's arrivals within about 38 days. A mechanism that removes less than that, mid-season, can stay under every floor for months. The control for it is the monthly hand check.
2. **Rot inside listing pages.** 310 listing seeds are behind the cycle today. They are counted on the board and listed in the alarm report, but no job tries to fix them (D9). Only the renewal number pushes.
3. **Hand-check discipline.** The monthly issue depends on a person filling it in. An unanswered issue is reported next month as "N unanswered", with no escalation.
4. **Discord and GitHub as the only channels.** There is no outside channel until the D14 check-in is set up.
5. **Until migration #469 is applied:** the Renewal lamp is slate, heartbeat history is not kept, and new summary keys are dropped from stored heartbeats. The alarm issue, Discord and the scheduled-run staleness check all work without it.
6. **Renewal is not gated on extraction.** Renewal and arrivals count archived files, whether or not they have been read. A broken extractor leaves renewal green while school pages show nothing new; `unextracted_current_docs` and `unextracted_next_docs` are reported, not alarmed. Extraction is a separate lane (#477, #480).
7. **Floor calibration (D1, D7).** The raw posting curve probably puts a healthy year near the floor each fall, and the two-year floor trips too (in a healthy simulated control, 68% against 68% on 2027-09-01). With re-notification (D16) that means monthly issues for a healthy year in autumn. The owner may prefer the scaled curve.
8. **The December arrivals gap.** A total stop that starts between about November 20 and December 4 waits 32–46 days for its first notification (15 of 365 stop dates a year). The current year's curve has flattened and the next year's expected arrivals are too few to judge. In practice an open `renewal:<Y>` issue in that season is still re-notified every 30 days. **Why accept:** the fix would mean judging windows with fewer than 6 expected arrivals, where noise is high, and this run had used its review rounds. A pooled "anything arrived at all" check over both years would close it; that is the suggested follow-up (#506).

## Corrections to earlier drafts

Fable checked the round-1 draft against the code. These are fixed in this version:
- PRs that were open at the time were described as live.
- The snapshot test was described as running in CI; it was skipped.
- The scheduled alarm was described as having run; the first scheduled run is 2026-11-25 13:41 UTC.
- Discord was described as posting on every failure; it posts on a change of state.
- The backtest was described as opening a second issue at the September switch. That was false under #474 and under #493 alike: one issue, then silence. The re-notification rule (D16) is the fix.
- "Live today" for the alarm issue and the scheduled-run check is corrected: both start with the first scheduled run.

## Decisions taken overnight (for the owner)

The defaults taken, each reversible. The full text, with the alternatives, is in the overnight report on #452.

| ID | Decision |
|---|---|
| D1 | The alarm floor is the raw posting curve less 5 points, not a curve scaled by mature renewal. The scaled alternative is about 68% in September; the raw curve likely puts a healthy year near the floor each fall |
| D2 | The next-year floor is the curve × 0.75, tracked from March 1 |
| D3 | The migration (#469) is left open for the owner to apply from `main` |
| D4 | Real alarm issues are assigned to `santhonys`; test issues are not |
| D5 | The Stuck PDFs lamp is down at 90% or more still stuck and late above 50%, once 10 or more are flagged |
| D6 | No version bump; the changelog entries are collected in this PR |
| D7 | A two-year cohort check guards against denominator erosion. Its floor is the current-year floor − 8. `MIN_PREV_SCHOOLS` = 350 |
| D8 | Test runs can turn the Renewal lamp red, never green. Dry runs send no heartbeat |
| D9 | Listing-page seeds behind the cycle are counted and listed, not re-probed |
| D10 | Changelog entries land in one docs PR |
| D11 | The PRD 040 CSV downloads wait for the launch gate (an untested `#` comment block) |
| D12 | Flagged documents don't count as renewing: any non-null `data_quality_flag`, failing closed (#499); today's values are `wrong_file`, `blank_template` and `low_coverage` |
| D13 | One alarm issue per breaching CDS year |
| D14 | Optional outside check-in (`RENEWAL_DEADMAN_URL`) against GitHub's 60-day schedule disable. It needs an account, which is the owner's call |
| D16 | A standing alarm re-notifies: a new assigned issue every 30 days while still below, and at once on a 5-point worsening |
| D17 | Arrivals check: per year, its own issue scope (`arrivals:<Y>`), ratio 0.4. The 30-day and 60-day windows are both judged every day (from 6 and 10 expected), and a year is short if either is; there is hysteresis on close (#505) |
| D15 | The first data-quality snapshot PR (#496) is held, because it would publish the ungated `/coverage` tile under the old renewal definition |
