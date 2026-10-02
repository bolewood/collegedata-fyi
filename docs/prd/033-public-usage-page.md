# PRD 033: Public usage page

**Status:** Draft rev 1 (2026-10-01). Not started.
**Author:** Anthony Showalter (with Claude)
**URL (planned):** `https://www.collegedata.fyi/usage` and `/usage.json`
**Related:** [PRD 032](032-api-usage-capture.md) (gateway usage capture, the data source), [PRD 030](030-pipeline-observation.md) (public pipeline board, the serving pattern), [PRD 013](013-analytics-and-abuse-signal.md), [`docs/api-usage-attribution.md`](../api-usage-attribution.md), [privacy page](../../web/src/app/privacy/page.tsx), [design system](../../web/DESIGN_SYSTEM.md), [voice](../../web/VOICE.md)

---

## One-line job

A public page that shows, honestly, how much the archive is used: how many
CDS documents people and programs download, how much the API is used by
others, and which schools' documents are in demand.

## Why

- **The archive is a public good, so its use should be public too.** The
  data is open; the evidence that it matters should be as well.
- **Leverage with schools.** "Your Common Data Set was downloaded 1,400
  times in the last year" is a concrete reason for a school to keep
  publishing, or to put back a PDF it took down.
- **Credibility with press, funders, and contributors.** A number with a
  published method beats an anecdote.
- **Reassurance for API users** that the service is alive and used.

## Prior art

| Project | What it publishes | What we borrow |
|---|---|---|
| Wikimedia ([stats.wikimedia.org](https://stats.wikimedia.org), [Pageviews](https://pageviews.wmcloud.org)) | Project and per-article pageviews, split into user, spider, and automated agents; open dumps and an API | Agent-type split; open data next to the page; a public methodology |
| Wikimedia [country-project-page dataset](https://analytics.wikimedia.org/published/datasets/country_project_page/00_README.html) | Per-country per-page daily counts with differential privacy and a release threshold (90+ views for lower-risk countries) | Release thresholds on fine-grained cells |
| [analytics.usa.gov](https://analytics.usa.gov) | Live aggregate traffic for federal sites, plus downloads | Public dashboard with open data |
| arXiv, PyPI ([pypistats.org](https://pypistats.org)), npm | Monthly downloads per paper or package | Per-item download counts as the headline |
| [COUNTER Code of Practice for Research Data](https://coprd.countermetrics.org/en/1.0.1/10-processing.html) (Zenodo, DataCite repositories) | Standard for dataset usage counts | Exclude crawlers; count scripts but label them "machine"; collapse repeat requests; unique requests per one-hour session |

## What the data says today

From the PRD 032 backfill. Almost all of it predates site tagging, so
attribution is partly inferred.

- **Raw requests are dominated by our own site.** About 82% of the 11.6M
  requests in the 89-day backfill were the site's own server rendering. A
  raw request count would be a vanity number. The page must not lead with
  it.
- **Archive downloads by others, last 30 days:** about 72K. Declared bots
  and crawlers 32.8K, browsers 18.3K, other integrations 11.5K, scripts
  4.9K, AI agents 4.9K. These are raw downloads, before repeat requests are
  collapsed.
- **Per school, monthly works; daily doesn't.** In 30 days, 798 schools had archive
  downloads; 733 had at least 10. Per school per day the median is 3.
- **Per-school API reads are too thin to publish.** 3,014 schools were
  queried by `school_id`, but only 548 reached 10 in a month.

## Metrics

Definitions follow COUNTER where it applies.

1. **CDS downloads** (headline). Successful archive PDF downloads, collapsed
   to **unique downloads**: one per client, per file, per UTC hour (the
   COUNTER one-hour session). Split by access method:
   - **People:** browsers, including clicks from our own school pages.
   - **Machines:** scripts, integrations, and AI agents acting for a user
     (`ChatGPT-User`, `Claude-User`, `Perplexity-User`, and similar).
   - **Search crawlers:** shown separately, and excluded from the headline,
     as COUNTER requires.
2. **API use by others.** Third-party PostgREST and Edge Function requests
   per day, and **distinct clients per day**. Client hashes use a daily
   salt, so distinct counts are valid within a day only; weekly and monthly
   views show the average daily count, never a sum.
3. **Who is using it, by kind.** Share of downloads and API requests by
   client family (browser, script, integration, AI agent, crawler). Named
   clients only from an allowlist of declared products and common libraries
   (for example `ChatGPT-User`, `Googlebot`, `python-requests`, `curl`).
   Everything else is "Other".
4. **Most-downloaded schools.** Top schools by unique people-plus-machine
   downloads over the last 30 days and the last 12 months.
5. **Our own serving load** as a footnote: requests made by the site and the
   friendly API, so readers can see what the headline excludes.

## Privacy rules

These rules are enforced in the publish step, not in the page.

- **Aggregates only, with a lag.** Whole-archive metrics are daily totals
  through the end of the previous UTC day. Nothing hourly is published.
- **Per-school numbers are 30-day and 12-month totals only.** Any cell under
  10 shows as "fewer than 10".
- **Never published:** client hashes, network organizations, countries, IP
  ranges, user-agent versions, query strings, or any per-client row.
  Organizations are the main risk: an organization name can identify one
  university or company.
- **Client names come only from the allowlist,** and only when the name has
  at least 50 requests in the period.
- **No differential privacy in v1.** Wikimedia needs it because per-page,
  per-country views can reveal what people in a small place read. We publish
  no geography and no per-client rows, and per-school cells are monthly with
  a floor of 10. Revisit if we ever add geography.
- **Update the privacy page** to say that we publish aggregate, anonymous
  usage counts, and link to `/usage`.

## Honesty rules

- **Lead with unique downloads, never raw requests.**
- **Label estimates.** Hours before site tagging (before 2026-10-01 20:00
  UTC) use inference. They are shaded and marked "estimated".
- **Version the method.** Each published row carries a `method_version`.
  When classification rules change, the methodology section gets a dated
  note, and the chart marks the change.
- **Retention limit.** Supabase keeps gateway logs for 90 days. History
  before 2026-07-04 does not exist and can't be recomputed. Any new metric
  can only be backfilled 90 days, which is why M0 comes first.

## Architecture

Builds on PRD 032. No new log source.

### M0: capture what the page needs (start now)

The 90-day retention clock argues for adding these before anything is
displayed.

- Add `unique_downloads` to `api_gateway_rollups_hourly` and
  `api_gateway_schools_hourly`. It is computed in the logs query as
  distinct (client key, file path) per hour among successful GET downloads.
  The client key is used inside ClickHouse only; nothing new is stored.
- Add `access_method` (`people`, `machine`, `crawler`, `first_party_serving`)
  to the schools table's primary key. Today it has only `classification`, so
  crawler downloads can't be separated from people per school.
- Compare `BOT_PATTERN` with the [COUNTER-Robots](https://github.com/atmire/COUNTER-Robots)
  list. Adopt missing crawler patterns, but never flag general research
  tools (`python`, `curl`, `wget`, `java`), as COUNTER requires.
- Re-run the 89-day backfill. It took about 2 hours 45 minutes last time.

### M1: publish layer

- New tables `usage_public_daily` (day, metric, access_method,
  client_family, client_name, value, estimated, method_version) and
  `usage_public_schools` (period, school_id, access_method, unique_downloads
  or null when under 10, method_version).
- `api_usage_publish(p_day date)`, security definer and service-role only,
  rebuilds those rows from the private tables and applies every privacy
  rule above. The ingest job calls it after a UTC day closes.
- Grant anon `select` on the two public tables only. The private tables
  stay private. Exposing a separate table means a view bug can't leak a
  private column.
- Tests: no published cell under 10; no client name off the allowlist; no
  hash, organization, or country column in any public table.

### M2: page and open data

- `/usage`: server-rendered, revalidated hourly, following
  `web/DESIGN_SYSTEM.md` and `web/VOICE.md`. Sections: headline downloads
  (12 months, people/machines, crawlers shown separately), API use by
  others, use by client kind, most-downloaded schools, our own serving
  load, and a methodology section.
- `/usage.json`: the same published rows, CC0, like
  `/pipeline-observation.json`.
- Link from `/api`, `/about`, and the footer.
- **Launch gate:** at least 30 days of tagged data, so no earlier than
  2026-11-01.

### M3: per-school demand

- A small "Downloaded N times in the last 12 months" line on each school's
  page, shown only at 10 or more.
- A reusable sentence for outreach to schools that stopped publishing.

## Success

- The page launches with no cell that breaks the privacy rules, verified by
  tests and a review of `/usage.json`.
- Headline unique downloads reconcile with the private rollups for any
  closed day.
- At least one outside citation (press, a counselor resource, or a funder
  application) within six months.
- At least one school outreach message uses the M3 number.

## Open questions

1. Should search-crawler downloads appear at all, or only in the
   methodology? Proposed: a separate, muted line. Crawlers are how people
   find the PDFs through search.
2. Does a per-school download count read as a popularity ranking? Proposed:
   show it on the school page without a rank, and show the top-schools list
   only on `/usage`.
3. Should first-party PDF clicks count as "people"? Proposed: yes. A visitor
   on a school page clicking the PDF is real use. Only the site's own
   server-side API reads are excluded.
4. Should we name the top integrations by product token (for example
   `Go-http-client`), or keep them all as "Other"? Proposed: allowlisted
   generic libraries only.
