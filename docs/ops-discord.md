# Discord ops notifications

CollegeData.fyi posts concise Discord embeds to the Bolewood server so humans (or bots) can act on breaks without watching GitHub.

Webhooks already exist on that server, both named **CollegeData.fyi**. Store the URLs as GitHub Actions **repository secrets** (Settings → Secrets and variables → Actions). This repo never commits them, and the notifier never prints them.

| Secret | Channel | When it is used |
|---|---|---|
| `DISCORD_ALERTS_WEBHOOK_URL` | `#alerts` | Something broke and needs action, plus the matching recovery |
| `DISCORD_DEPLOYS_WEBHOOK_URL` | `#deploys` | Routine FYI for successful production-shaped deploys |

If a secret is missing or empty, that channel is skipped and the job still succeeds.

Implementation: [`tools/ops/notify_discord.py`](../tools/ops/notify_discord.py), triggered by [`.github/workflows/ops-discord-notify.yml`](../.github/workflows/ops-discord-notify.yml). Embeds are red on failure and green on recovery or success. They always include the project name **CollegeData.fyi**, what happened, workflow/job or station, branch/commit when GitHub has one, and a link.

`workflow_run` listeners only fire from the default-branch copy of this workflow. Adding or changing the notifier does nothing in Discord until it is merged to `main`.

## `#alerts`

Failures and recoveries only. Repeat posts of the same ongoing failure are suppressed (first failure, then recovery).

- Failed runs of `ci.yml`, `deploy-edge-functions.yml`, `ipeds-release-probe.yml`, and `ops-*.yml` when the run is on `main` or was started by `schedule`
- Recoveries of those same runs (the next successful run after a failure)
- Failed Vercel **production** GitHub `deployment_status` events (Preview deploys are ignored)
- Public pipeline-board lamps that go `down` (hourly poll of [`/pipeline-observation.json`](https://www.collegedata.fyi/pipeline-observation.json)): missed or errored heartbeats for enqueue, archive-process, coverage, serving caches, finder, headless archive, extraction, IPEDS probe, and the yearly schema/scorecard stations if they actually go down
- Board-health: `as_of` older than 2 hours, `activity_load_error: true`, or a failed JSON fetch. The poller waits 12s and re-fetches before deciding (Vercel SWR can return the build-time seed as `STALE`; a query-string cache-bust does not bypass that). It posts only after two consecutive unhealthy polls, then once on recovery
- API usage ingest scheduled-run staleness (no scheduled run newer than 8 hours), matching `tools/ops/automation_health.py`
- Ops discovery renewal scheduled-run staleness (no scheduled run newer than 36 hours). This catches the workflow being disabled or deleted, when nothing runs to report it. Posts on the first miss and once on recovery; a workflow that has never had a scheduled run is not announced until it has one
- Ops discovery renewal failed run (a short or empty read of the archive, a denominator under 200 schools, or a freshness floor that disagrees with the database)
- A station whose lamp is down while its clock is fresh (the job ran on time and reported a bad result, such as `discovery_renewal` below its floor) posts with a result title, for example "Discovery renewal below floor", and the station's result line, instead of "heartbeat missed"
- Discovery is behind: current-year, two-year or next-year renewal fell below its floor (any one of the three). Posted by `tools/ops/renewal_alarm.py` when it opens the alarm issue (label `alarm:discovery-renewal`), and a green recovery post when it closes it. A standing issue gets its body updated and no further posts. Manual test runs post with a `[test]` title prefix

The hourly poller records current station lamps on first *fresh* snapshot without posting, so a deploy does not dump every station that is already red. Stale or seed responses (`as_of` older than 2 hours) never baseline or alert individual stations. After a fresh baseline it posts only transitions.

Not posted: pull-request CI, feature-branch workflow_dispatch, cancelled/skipped runs, `late`/`capped` board lamps, or successful scheduled ops jobs.

## `#deploys`

- Successful `CI` runs on `main`
- Successful `Deploy Edge Functions` runs on `main`
- Successful Vercel **production** `deployment_status` events, when Vercel's GitHub integration emits them

## Outside check-in for the renewal check (dead man's switch)

Every alert above lives in GitHub. GitHub disables scheduled workflows after 60 days without repository activity, and then the renewal check, the Discord poll and the failure notifier all go quiet together, with nothing to say so. The renewal workflow can therefore check in with an outside service, which alerts when the check-in stops.

Setup, once:

1. Create one free check at [healthchecks.io](https://healthchecks.io) (or any service with the same URL convention). Schedule: every 1 day, grace time 2 days. Send the alert email to the owner.
2. Copy the check's ping URL into the repository secret `RENEWAL_DEADMAN_URL` (Settings, Secrets and variables, Actions).

What it does: scheduled runs of `Ops discovery renewal` end with `curl -fsS -m 10 --retry 3 "$RENEWAL_DEADMAN_URL"` when the job succeeded, and with `"$RENEWAL_DEADMAN_URL/fail"` when an earlier step failed. Manual runs never check in. If the secret is unset the step prints `RENEWAL_DEADMAN_URL not set; no outside check-in (see docs/ops-discord.md)` and the job passes. The URL is never printed.

## Discovery renewal alarm: what posts, and when again

Alarm issues carry the label `alarm:discovery-renewal`, one per scope (see below). A year's renewal issue opens when any of its renewal checks is below its floor: one-year, two-year, or next-year (from March). Arrivals open separately. The arrivals check counts schools that gained a usable current- or next-year document in the last 30 days and compares with what the posting curve expects for a month; under a quarter of that, with at least 10 expected, is a breach. Both windows are judged every day, each from its own expectation: 30 days when the curve expects at least 6 new documents in that time, 60 days when it expects at least 10. A year is short when EITHER judgeable window is under 40% of what is expected, so a stop cannot hide behind the 60-day window, which still holds a month of arrivals from before it. If neither window can be judged (a small archive, or the year's curve has run out), the report says "not checked" and that year cannot open an alarm.

The arrivals check judges the current year and the next year each on their own (hand-archiving one year cannot hide a stopped pipeline for the other), counting only schools in that year's cohort, once, on their earliest live document for the year. A year is short when its arrivals are under 40% of what the curve expects (the highest ratio that did not false-alarm on the Sep to Nov 2026 replay; 25% left a loss of half the arrivals unseen for months). Both years' counts are in the summary (`arrivals_current_*`, `arrivals_next_*`).

There are two kinds of alarm issue, each with its own scope marker in the body. `renewal:<Y>` is the renewal numbers of CDS year Y (one-year, two-year, and the next year's early-curve check). `arrivals:<Y>` is that year's arrivals, for the current year and the next year only (the older `year:<Y>` markers read as `renewal:<Y>`). They open, re-notify (every 30 days; renewal also when its gap grows by 5 points) and close independently, so arrivals stopping is announced as its own issue, titled "Almost nothing new arrived for 2026-27: 1 schools in 60 days (expected 11)", even while the renewal issue is open.

An arrivals issue closes only when that year's own 30-day arrivals are back to at least the larger of 3 and half the expected 30-day arrivals (it opens under 40%, so a count on the boundary cannot open and close it every day). A change of window, or a window too small to judge, never closes it. Its year is out of scope once it is no longer the current or next year, and then it is closed as "No longer tracked". The heartbeat summary's `outstanding_years` covers both kinds and `arrivals_years` lists the years with an arrivals issue.

An open issue is not a latch. While it stays below its floor it is replaced by a new assigned issue and a new Discord post after 30 days, or when the gap to the floor has grown by 5 points since it opened (the gap at open is in the `alarm-gap` marker). The old one is closed with "Superseded by #N: still behind". It closes for good only when its year is back above its floors (a recovery post).

A year two or more cycles old is retired: its issue is closed with "No longer tracked: final one-year X%, two-year Y%", and it never counts as outstanding. `Ops monthly hand check` is watched like the daily workflows, with a limit of 35 days since its last scheduled run.

## Repeated failures

The notifier posts the first failure of a run of failures only. When a scheduled `Ops discovery renewal` run fails and the one before it failed too, the run prints `::error::renewal check has failed N days running` (a red annotation on the run), and every 7th consecutive failure also posts to `#alerts` directly (`tools/ops/consecutive_failures.py`).

## Local check

```bash
python -m unittest tools.ops.test_notify_discord
```
