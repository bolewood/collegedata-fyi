# PRD 033: Public usage page

**Status:** Rev 4 (2026-10-02). M0 shipped in v0.6.16.0 and backfilled (2026-07-06 to 2026-10-01). M1 and M2 built in v0.6.17.0; `/usage` launched 2026-10-03 (v0.6.17.1).
**Author:** Anthony Showalter (with Claude)
**URL (planned):** `https://www.collegedata.fyi/usage` and `/usage.json`
**Related:** [PRD 032](032-api-usage-capture.md) (gateway usage capture, the data source), [PRD 030](030-pipeline-observation.md) (public pipeline board, the serving pattern), [PRD 013](013-analytics-and-abuse-signal.md), [`docs/api-usage-attribution.md`](../api-usage-attribution.md), [privacy page](../../web/src/app/privacy/page.tsx), [design system](../../web/DESIGN_SYSTEM.md), [voice](../../web/VOICE.md)

---

## What changed in rev 4

M1 and M2 are built. Differences from the rev 3 plan:

- **No `client_name` column.** Named clients are deferred; every public row
  carries a client kind only, and unknown families publish as `unknown`.
- **Publishing is one call, `api_usage_publish_pending()`,** which finds
  ready days, publishes them, and rebuilds the months they touch. A day is
  ready when the daily count and every hour have run successfully.
- **Storage folders resolve through artifact ownership first.** 21 download
  folders are not current school ids. Most resolve through
  `institution_slug_crosswalk`; a few (`university-of-michigan`,
  `purdue-university`) only through the school that owns their files.
- **The API section counts both surfaces:** third-party PostgREST and Edge
  Function requests, plus calls to the simple `/api` routes and MCP server.
  Self-declared bots and AI crawlers are left out of the API headline.
- **School cells are rounded in the table and small schools are left out.**
  Review found that exact values with null rows under 10 could be recovered
  by subtracting listed schools from the daily totals. The school table now
  holds only schools at 10 or more, rounded to the nearest 10, and
  `usage_public_months` publishes just the count of schools under 10.
- **Spikes** are days with at least 2,000 machine downloads and four times
  the median machine day.
- **Launch gate.** The page and JSON shipped with `noindex` and no links
  until `USAGE_LAUNCH_DATE`. Planned for 2026-11-01; moved up to 2026-10-03,
  leading with September 2026, whose API attribution is inferred (the API
  section says so). Footer, sitemap, `/api`, and `/about` links appear on
  the first build on or after that date.

## What changed from rev 1

A red-team review found that rev 1's headline split didn't match the shipped
classifier, that our own tools would inflate it, and that per-school
suppression could be undone. Rev 2:

- **Splits AI clients in two.** The shipped `ai_agent` family includes
  training crawlers (GPTBot, ClaudeBot) alongside agents fetching for a user
  (ChatGPT-User). Rev 2 separates `ai_user` from `ai_crawler`.
- **Renames "search crawlers" to "self-declared bots and crawlers."**
  `declared_bot` is any self-declared bot token, including commercial
  integrations.
- **Defines unique downloads precisely** and computes them in a dedicated
  daily query, not by summing per-group counts.
- **Publishes one rounded number per school per calendar month.** No
  per-method rows, no rolling windows, no top-schools list.
- **Uses "browser downloads," not "people,"** and adds a heavy-client rule so
  one script with a browser user agent can't inflate a school's count.
- **Freezes the rules before the one backfill** that can still cover all
  history.
- **Drops "last 12 months"** until 12 complete months exist.

## One-line job

A public page that shows, honestly, how much the archive is used: how many
CDS documents browsers and programs download, how much others use the API,
and how demand is spread across schools.

## Why

- **The archive is a public good, so its use should be public too.**
- **Leverage with schools.** "Your Common Data Set was downloaded about 140
  times since July 2026" is a concrete reason for a school to keep
  publishing, or to put back a PDF it took down.
- **Credibility with press, funders, and contributors.** A number with a
  published method beats an anecdote.
- **Reassurance for API users** that the service is alive and used.

## Prior art

| Project | What it publishes | What we borrow |
|---|---|---|
| Wikimedia ([stats.wikimedia.org](https://stats.wikimedia.org), [Pageviews](https://pageviews.wmcloud.org)) | Project and per-article pageviews, split into user, spider, and automated agents; open dumps and an API | Agent-type split; open data next to the page; a public methodology |
| Wikimedia [country-project-page dataset](https://analytics.wikimedia.org/published/datasets/country_project_page/00_README.html) | Per-country per-page daily counts with differential privacy and a release threshold | Release thresholds on fine-grained cells |
| [analytics.usa.gov](https://analytics.usa.gov) | Live aggregate traffic for federal sites, plus downloads | Public dashboard with open data |
| arXiv, PyPI ([pypistats.org](https://pypistats.org)), npm | Monthly downloads per paper or package | Per-item download counts |
| [COUNTER Code of Practice for Research Data](https://coprd.countermetrics.org/en/1.0.1/10-processing.html) | Standard for dataset usage counts | Exclude robots; count scripts as "machine"; collapse repeats per client and item |

## What the data says today

From `api_usage_downloads_daily` after the M0 backfill (method version 1),
for the 30 days from 2026-09-02 to 2026-10-01. Repeats are collapsed, bots
are split out, and the heavy-client rule is applied.

- **Raw requests are dominated by our own site.** About 82% of the 11.6M
  requests in the 89-day PRD 032 backfill were the site's own server
  rendering, which is why the headline counts downloads, not requests.
- **Unique downloads, 30 days:**

  | Access method | Unique | Raw fetches |
  |---|---|---|
  | Browser | 8,729 | 9,472 |
  | Machine | 26,383 | 27,883 |
  | Self-declared bots and crawlers | 36,267 | 36,684 |

  Collapsing repeats removes only about 4%; the big correction is splitting
  out bots (half of all downloads) and machines.
- **Machine is mostly integrations and scripts:** integrations 11.1K,
  scripts 8.2K, heavy browser keys 3.8K, AI agents fetching for a person
  3.3K. Bots split into declared bots 29.5K and AI crawlers 6.8K.
- **The heavy-client rule matters.** Browser keys over 30 files a day moved
  3.8K downloads (30% of browser-shaped downloads) to Machine. Day-level
  histograms show real browser keys rarely pass 10 files, so 30 stays.
- **Our school pages drive about 9% of browser downloads** (764 with a
  collegedata.fyi referer).
- **Per school, monthly works; daily doesn't.** Counting browser and machine
  together, 760 schools had downloads, 596 had at least 10 and 71 had at
  least 100. The median school had 29 in the month (max 682). Per school per
  day the median is 2. The floor of 10 hides about a fifth of schools with
  any downloads.
- **Our pipeline shows up as zero.** No archive downloads in the window were
  `excluded`; pipeline tools read Storage through authenticated paths.
- **Per-school API reads are too thin to publish.** 3,014 schools were
  queried by `school_id`, but only 548 reached 10 in a month.

## Decisions

| Question | Decision |
|---|---|
| Bot and crawler downloads | A separate muted line, "self-declared bots and crawlers," never in the headline |
| Per-school demand | No top-schools list. `/usage` shows the spread across schools plus a school search; each school page shows its own number |
| Per-school precision | One combined number per school per calendar month, rounded to the nearest 10; schools under 10 not listed, only counted |
| PDF clicks from our school pages | Count as browser downloads |
| Client names | Major public products and generic libraries only, from an allowlist |
| Human bucket label | "Browser downloads" |
| Inflation by one client | Heavy browser clients become machines; spikes are annotated |
| School objects to its number | No opt-out. The number is aggregate, rounded, and floored |
| Capture bugs and rule changes | Fixed and frozen before one backfill (M0) |

## Metrics

### 1. CDS downloads (headline)

A **unique download** is one client fetching one archive file on one UTC
day, where:

- **The client key is IP address plus full user agent,** the COUNTER
  fallback for sites without cookies. JA4 is left out; it makes the key
  stricter in ways that are hard to explain.
- **A fetch is a GET that returns 200 or 206.** PDF viewers often load in
  ranges (206), so counting only 200s would miss them. Repeats collapse
  regardless of how many range requests a viewer makes.
- **A client counts once per file per day.** That covers COUNTER's
  double-click rule, and caps what a loop can add.

Each unique download gets one access method:

| Access method | Who | In headline |
|---|---|---|
| Browser | Browser user agents, including clicks from our own school pages | Yes |
| Machine | Scripts, integrations, `ai_user` agents fetching for a person, unknown clients, and heavy browser clients | Yes, shown separately |
| Self-declared bots and crawlers | `declared_bot` and `ai_crawler` | No; a muted line |
| Excluded | Our pipeline and tools | Never published |

**Heavy-client rule:** a browser client key that fetches more than 30
distinct archive files in a day is counted as a machine for that day. M0
checks the threshold against real distributions before the backfill.

### 2. API use by others

Third-party PostgREST and Edge Function requests per day. "Approximate
distinct non-browser clients per day" is a secondary line: client hashes
cover only non-browser third parties on `edge_logs`, use a daily salt, and
are skipped in overflow hours. Longer periods show the average daily count,
never a sum.

### 3. Who is using it, by kind

Share of unique downloads and API requests by client kind (browser, script,
integration, AI on a user's behalf, AI crawler, other bots). Named clients
come only from an allowlist of major public products (`ChatGPT-User`,
`Claude-User`, `Perplexity-User`, `Googlebot`, `bingbot`, `GPTBot`,
`ClaudeBot`) and generic libraries (`python-requests`, `curl`, `wget`,
`node`, `Go-http-client`), with at least 50 requests in the calendar month.
Everything else is "Other". Adding a name that identifies a company needs a
written review in the PR.

### 4. Demand across schools

- **On `/usage`:** the spread across schools for the last complete month
  (median, share of schools at 10 or more, share at 100 or more) and a
  school search. No ranked list.
- **On school pages (M3):** "Downloaded about N times since July 2026",
  rounded to the nearest 10, hidden under 10. After 12 complete months,
  "in the last 12 months".

### 5. Our own serving load

A footnote with requests made by the site and the friendly API, so readers
can see what the headline leaves out.

## Privacy rules

These are enforced in the publish step and checked by tests, not left to the
page.

- **Daily whole-archive totals only, published after the day closes.**
  Nothing hourly.
- **Per school: one combined number per calendar month, rounded to the
  nearest 10 in the table itself.** A school is listed for a month only at
  10 or more; schools under 10 have no row at all, and a separate monthly
  summary publishes only how many there were. The daily totals sum every
  school, so a hidden-but-listed row (or an exact value) would let anyone
  recover small schools by subtracting the listed ones; rounding and
  leaving them out entirely closes that. No per-method rows. Totals "since
  July 2026" are sums of listed months, so they don't reveal anything finer
  than a month.
- **Never published:** client hashes, network organizations, countries, IP
  ranges, user-agent versions, query strings, or any per-client row.
- **IP addresses stay inside the logs query.** The daily query uses IP plus
  user agent as the client key inside ClickHouse and returns only counts.
  This is the first query to read IPs for counting, so PRD 032 and the
  attribution doc are updated to say so.
- **No differential privacy in v1.** Wikimedia needs it because per-page,
  per-country views can reveal what people in a small place read. We publish
  no geography and no per-client rows, and per-school cells are monthly,
  floored, and rounded. Revisit if we ever add geography or finer periods.
- **Privacy page, updated in M0** because PRD 032 already measures usage:
  - usage is measured from gateway logs;
  - IP addresses are read in passing to count unique downloads and are not
    stored;
  - non-browser API clients get a daily-salted hash, kept 400 days;
  - aggregate counts are published at `/usage`;
  - a new effective date.

## Honesty rules

- **Lead with unique browser and machine downloads, never raw requests.**
- **Mark changes on the charts.** The T0 cutover (2026-10-01 20:00 UTC)
  mainly affects API attribution; browser downloads are comparable across
  it. Each `method_version` change gets a dated marker and a methodology
  note.
- **Annotate spikes** where one client or event drives a day, instead of
  silently dropping it.
- **Retention limit.** Gateway logs keep 90 days. History before 2026-07-04
  doesn't exist, and any rule change can only be reprocessed 90 days back.
  That is why M0 freezes the rules first.
- **Accessibility.** Every chart has a table alternative, and estimated or
  annotated data is marked by more than color.

## Architecture

### M0: fix capture, freeze rules, backfill once (done, v0.6.16.0)

Shipped as planned, plus: a `daily` workflow mode, a `from_site` column for
clicks from our pages, hourly runs that recount any of the last 7 days
without a successful count, and user-agent bucketing for days too large to
page. Details in `docs/api-usage-attribution.md`.

Capture fixes that also correct PRD 032 data:

1. **Split `ai_agent`** into `ai_user` (ChatGPT-User, Claude-User,
   Perplexity-User, and similar) and `ai_crawler` (GPTBot, ClaudeBot,
   OAI-SearchBot, PerplexityBot, CCBot, Google-Extended, and similar), in
   `classify.py` and the matching SQL. `client_family` has no value
   constraint, so no migration is needed for it.
2. **Tag every tool that reads public Storage** with a `collegedata-pipeline`
   user agent (for example `tools/data_quality/cleanup_bad_html_sources.py`
   and `probe_source_corpus.py`), plus a test that fails on untagged HTTP
   fetches under `tools/`.
3. **Compare `BOT_PATTERN` with [COUNTER-Robots](https://github.com/atmire/COUNTER-Robots)**
   and adopt missing crawler patterns, never flagging general research tools
   (`python`, `curl`, `wget`, `java`).

New daily capture:

4. **`api_usage_downloads_daily`** (day, school_id, access_method,
   client_family, unique_downloads, raw_downloads, method_version), private,
   service-role only. It is written by a daily query over the closed UTC
   day:
   - collapse archive GETs with status 200 or 206 to one row per (client
     key, file);
   - flag client keys over the heavy-client threshold;
   - return counts grouped by school, user agent, and the first-party
     referer flag, which Python classifies with the same rules as the
     hourly job.
5. **Spike check first.** Confirm the query shape works on the logs
   endpoint (subqueries, distinct counts, paging) and size it: rows per day,
   pages, total backfill time.
6. **Recompute "What the data says"** with repeats and robots removed, and
   confirm the floor of 10 and the heavy-client threshold.
7. **Privacy page and PRD 032 updates** as listed under Privacy rules.
8. **Backfill once:** the hourly rollups (for the AI split and tool
   tagging) and the new daily table, 89 days, as `method_version` 1. The
   hourly job waits in its concurrency group while the backfill runs.

### M1: publish layer (built, v0.6.17.0)

- Public tables `usage_public_daily` (day, metric, access_method,
  client_kind, value, method_version), `usage_public_school_months`
  (month, school_id, school_name, unique_downloads, method_version; only
  schools at 10 or more, rounded to the nearest 10), and
  `usage_public_months` (month, schools_with_downloads,
  schools_under_floor, method_version). They contain only publishable rows,
  so a view bug can't leak a private column. Anon gets `select` on these
  three only. Metric definitions are in `docs/api-usage-attribution.md`.
- `api_usage_publish_pending(p_method_version, p_limit)`, service-role
  only, publishes ready days through `api_usage_publish_day()` and rebuilds
  their months through `api_usage_publish_month()`.
  `api_usage_publish_days` (private) records each day's source run time.
- **Timing:** a day is published only when the daily query has run and all
  24 hours are covered by successful windows. A day is republished when a
  later run touching it finishes. Publish is its own workflow step with its
  own alert issue, run after the ingest heartbeat. A day still unready two
  days after it closes counts as stuck and opens a separate alert issue;
  past 80 days it can no longer be recounted from the logs. GitHub's late
  cron only delays publishing.
- **Checks:** `usage_public_violations()` runs after every publish and fails
  the step on a school cell under 10 or not a multiple of 10, an incomplete
  month, a school month without a summary, a published day without a
  publish record, an unexpected public column, or anon access to any
  private usage table. A throwaway-Postgres harness covered the migration before
  merge (alias merging, the floor, incomplete months, republishing, grants).
- Retired and older school ids in storage paths resolve through artifact
  ownership and `institution_slug_crosswalk` (which carries the identity
  manifest's retired aliases).

### M2: page and open data (built, v0.6.17.0)

- `/usage`: server-rendered, revalidated hourly, following
  `web/DESIGN_SYSTEM.md` and `web/VOICE.md`. Sections: headline downloads
  (browser and machine, with bots and crawlers as a muted line), API use by
  others, use by client kind, demand across schools with school search, our
  own serving load, and a methodology section with a worked example of one
  request going through the rules.
- `/usage.json`: the published rows plus the method-version changelog and
  the T0 timestamp, CC0, like `/pipeline-observation.json`.
- Link from `/api`, `/about`, and the footer.
- **Launch gate:** planned as at least 30 days of tagged data after the M0
  backfill (2026-11-01). Launched early on 2026-10-03 once all 89 days were
  published; download counts don't depend on site tagging, and the API
  section notes the inferred attribution before 2026-10-01
  (`isUsageLaunched()` in `web/src/lib/usage.ts`).

### M3: per-school demand

- The rounded line on each school's page, hidden under 10.
- A reusable sentence for outreach to schools that stopped publishing.

## Success

- **Correct:** a spot check of one sample day against a direct raw-log count
  matches unique downloads within 1%.
- **Private:** the suppression scan over the full `/usage.json` history
  passes on every publish.
- **Used:** at least one outside citation (press, a counselor resource, or a
  funder application) within six months.
- **Useful:** at least one school outreach message uses the M3 number.

## Remaining open questions

1. **Integrations are the largest Machine group (11.1K a month).** Check
   whether one client dominates before launch, and annotate it if so.
2. **Named clients.** Deferred from M1. Adding them needs a `client_name`
   column, the allowlist above, and a written review.

Resolved in M0: the heavy-client threshold stays at 30 distinct files per
client key per day (see "What the data says"). Resolved in M2: the Machine
headline is not split; AI on a user's behalf appears only in "by kind".
