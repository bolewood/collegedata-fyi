# PRD 033: Public usage page

**Status:** Rev 2 (2026-10-01), after red-team review. Decisions locked; M0 next.
**Author:** Anthony Showalter (with Claude)
**URL (planned):** `https://www.collegedata.fyi/usage` and `/usage.json`
**Related:** [PRD 032](032-api-usage-capture.md) (gateway usage capture, the data source), [PRD 030](030-pipeline-observation.md) (public pipeline board, the serving pattern), [PRD 013](013-analytics-and-abuse-signal.md), [`docs/api-usage-attribution.md`](../api-usage-attribution.md), [privacy page](../../web/src/app/privacy/page.tsx), [design system](../../web/DESIGN_SYSTEM.md), [voice](../../web/VOICE.md)

---

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

From the PRD 032 backfill. Almost all of it predates site tagging, and none
of it has repeats collapsed or our own tools removed, so treat it as an
upper bound.

- **Raw requests are dominated by our own site.** About 82% of the 11.6M
  requests in the 89-day backfill were the site's own server rendering.
- **Archive downloads by others, last 30 days:** about 72K raw. Self-declared
  bots and crawlers 32.8K, browsers 18.3K, integrations 11.5K, scripts 4.9K,
  AI clients 4.9K (training crawlers and user agents mixed).
- **Per school, monthly works; daily doesn't.** In 30 days, 798 schools had
  archive downloads and 733 had at least 10, but that includes bots (about
  45% of downloads). Per school per day the median is 3. M0 recomputes these
  after repeats and robots are removed, and the floor is confirmed then.
- **Per-school API reads are too thin to publish.** 3,014 schools were
  queried by `school_id`, but only 548 reached 10 in a month.

## Decisions

| Question | Decision |
|---|---|
| Bot and crawler downloads | A separate muted line, "self-declared bots and crawlers," never in the headline |
| Per-school demand | No top-schools list. `/usage` shows the spread across schools plus a school search; each school page shows its own number |
| Per-school precision | One combined number per school per calendar month; hidden under 10; rounded to the nearest 10 on school pages |
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
- **Per school: one combined number per calendar month.** No per-method
  rows, so a hidden cell can't be recovered by subtraction. Totals "since
  July 2026" are sums of completed months, so publishing them doesn't
  reveal anything finer than a month. A month under 10 is hidden, and a
  school page shows the total rounded to the nearest 10.
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

### M0: fix capture, freeze rules, backfill once (start now)

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

### M1: publish layer

- Public tables `usage_public_daily` (day, metric, access_method,
  client_kind, client_name, value, method_version) and
  `usage_public_school_months` (month, school_id, unique_downloads or null
  under 10, method_version). They contain only publishable rows, so a view
  bug can't leak a private column. Anon gets `select` on these two only.
- `api_usage_publish(p_day date)`, security definer and service-role only,
  rebuilds the public rows from the private tables and applies every privacy
  rule.
- **Timing:** a day is published only when the daily query has run and all
  24 hourly windows have reconciled. Any day a backfill rewrites is
  republished. Publish is its own workflow step, so a publish failure and an
  ingest failure are reported separately. GitHub's late cron only delays
  publishing.
- **Tests:** no published per-school cell under 10; no per-method school
  rows; no client name off the allowlist; no hash, organization, or country
  column in any public table; a full scan of the published history on every
  run.
- Retired school ids in storage paths map through the identity manifest's
  `retired_aliases`, with a test.

### M2: page and open data

- `/usage`: server-rendered, revalidated hourly, following
  `web/DESIGN_SYSTEM.md` and `web/VOICE.md`. Sections: headline downloads
  (browser and machine, with bots and crawlers as a muted line), API use by
  others, use by client kind, demand across schools with school search, our
  own serving load, and a methodology section with a worked example of one
  request going through the rules.
- `/usage.json`: the published rows plus the method-version changelog and
  the T0 timestamp, CC0, like `/pipeline-observation.json`.
- Link from `/api`, `/about`, and the footer.
- **Launch gate:** at least 30 days of tagged data after the M0 backfill, so
  no earlier than 2026-11-01.

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

1. **Heavy-client threshold.** Proposed 30 distinct files per client per
   day; confirm against the M0 distribution.
2. **Does the "Machine" headline line need a split** between AI on a user's
   behalf and scripts, or is that only in the "by kind" section? Proposed:
   only in "by kind," to keep the headline simple.
