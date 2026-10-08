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

The hourly poller records current station lamps on first *fresh* snapshot without posting, so a deploy does not dump every station that is already red. Stale or seed responses (`as_of` older than 2 hours) never baseline or alert individual stations. After a fresh baseline it posts only transitions.

Not posted: pull-request CI, feature-branch workflow_dispatch, cancelled/skipped runs, `late`/`capped` board lamps, or successful scheduled ops jobs.

## `#deploys`

- Successful `CI` runs on `main`
- Successful `Deploy Edge Functions` runs on `main`
- Successful Vercel **production** `deployment_status` events, when Vercel's GitHub integration emits them

## Local check

```bash
python -m unittest tools.ops.test_notify_discord
```
