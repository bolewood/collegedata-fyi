import type { Metadata } from "next";
import Link from "next/link";
import { fetchUsageRows } from "@/lib/usage-data";
import {
  HEAVY_CLIENT_FILES_PER_DAY,
  METHOD_CHANGELOG,
  SPIKE_FLOOR,
  buildUsageModel,
  formatCount,
  formatDay,
  isUsageLaunched,
  type KindRow,
} from "@/lib/usage";
import { ApiBars, DownloadsChart } from "./UsageCharts";
import { UsageSchoolSearch } from "./UsageSchoolSearch";
import "./usage.css";

export const revalidate = 3600;

export function generateMetadata(): Metadata {
  const launched = isUsageLaunched();
  return {
    title: "Usage — collegedata.fyi",
    description:
      "How often people and programs download the Common Data Set reports in this archive, counted the way libraries count use, with bots kept out of the total.",
    alternates: { canonical: "/usage" },
    robots: launched ? undefined : { index: false, follow: false },
  };
}

function pct(part: number, whole: number): string {
  return whole > 0 ? `${Math.round((part / whole) * 100)}%` : "";
}

function KindBars({ rows, total, muted, max }: { rows: KindRow[]; total: number; muted: boolean; max: number }) {
  return (
    <>
      {rows.map((row) => (
        <div
          key={row.key}
          className={`usage-kind${row.key === "browser" ? " usage-kind--browser" : ""}${muted ? " usage-kind--muted" : ""}`}
        >
          <div className="usage-kind__label">
            {row.label}
            <small>{row.detail}</small>
          </div>
          <div className="usage-kind__track" aria-hidden="true">
            <div className="usage-kind__bar" style={{ width: `${max > 0 ? ((row.value / max) * 100).toFixed(1) : 0}%` }} />
          </div>
          <div className="usage-kind__num">{formatCount(row.value)}</div>
          <div className="usage-kind__pct">{muted ? "" : pct(row.value, total)}</div>
        </div>
      ))}
    </>
  );
}

export default async function UsagePage() {
  const rows = await fetchUsageRows();
  const model = buildUsageModel(rows.daily, rows.schoolMonths);

  if (!model) {
    return (
      <div className="usage-page mx-auto max-w-5xl px-4 sm:px-6 py-8">
        <header className="usage-hero">
          <div className="meta">§ Usage</div>
          <h1>
            Who uses <em>the archive.</em>
          </h1>
        </header>
        <p className="usage-empty-state cd-card">
          Usage numbers have not been published yet. They appear here once the
          first full day of downloads is counted.
        </p>
      </div>
    );
  }

  const { period, headline, kinds, api, spread } = model;
  const since = formatDay(model.firstDay, { year: true });
  const sinceShort = formatDay(model.firstDay);
  const counted = headline.browser + headline.machine;
  const kindMax = Math.max(...kinds.counted.map((k) => k.value), ...kinds.bots.map((k) => k.value));
  const histMax = spread ? Math.max(1, ...spread.buckets.map((b) => b.schools)) : 1;
  const markers = METHOD_CHANGELOG.filter((entry) => entry.from > model.firstDay).map((entry) => ({
    day: entry.from,
    label: `Rules v${entry.version}`,
  }));
  const spikeList = model.spikes.map((s) => `${formatDay(s.day)} (${formatCount(s.machine)})`).join(", ");

  return (
    <div className="usage-page mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <header className="usage-hero">
        <div className="meta">§ Usage · updated hourly · through {formatDay(model.lastDay, { year: true })}</div>
        <h1>
          Who uses <em>the archive.</em>
        </h1>
        <p className="usage-lede">
          How often people and programs download the reports in this archive.
          Counted the same way libraries count use, with bots kept out of the
          total.
        </p>
      </header>

      <div className="usage-ledger rule-2">
        <div className="usage-accent">
          <span className="meta">Browser downloads · {period.label}</span>
          <strong>{formatCount(headline.browser)}</strong>
          <small>
            People opening reports in a web browser. {formatCount(headline.browserSinceStart)} since {sinceShort}.
          </small>
        </div>
        <div>
          <span className="meta">Machine downloads · {period.label}</span>
          <strong>{formatCount(headline.machine)}</strong>
          <small>
            Scripts, integrations, and AI assistants fetching for a person.{" "}
            {formatCount(headline.machineSinceStart)} since {sinceShort}.
          </small>
        </div>
        <div>
          <span className="meta">Schools with downloads</span>
          <strong>{spread ? formatCount(spread.schools) : "—"}</strong>
          <small>Schools whose reports were downloaded at least once in {period.label}.</small>
        </div>
      </div>
      <p className="usage-bots-line">
        Search engines and AI crawlers fetched another <b>{formatCount(headline.bots)}</b> files in{" "}
        {period.label}. They keep the archive findable, but we don&rsquo;t count them as use.
      </p>

      <section className="usage-band" aria-labelledby="usage-over-time">
        <div className="meta">§ 1 · Downloads over time</div>
        <h2 id="usage-over-time">Every day since {sinceShort}</h2>
        <p className="usage-copy">
          A download counts once per person or program, per file, per day.
          Reopening the same report on the same day does not add to the count.
          {headline.siteShare !== null
            ? ` In ${period.label}, ${pct(headline.siteShare, 1)} of browser downloads started from a link on this site.`
            : ""}
        </p>
        <div className="usage-chart-card cd-card">
          <div className="usage-chart-head">
            <span className="meta">Unique downloads per day, 7-day average</span>
            <div className="usage-key" aria-hidden="true">
              <span>
                <i style={{ borderColor: "var(--browser)", borderTopWidth: 3 }} />
                Browser
              </span>
              <span>
                <i style={{ borderColor: "var(--ink)", borderTopWidth: 1.25 }} />
                Machine
              </span>
              <span>
                <i style={{ borderColor: "var(--ink-4)", borderTopStyle: "dashed" }} />
                Bots and crawlers
              </span>
            </div>
          </div>
          <DownloadsChart averages={model.averages} spikes={model.spikes} markers={markers} />
          {model.spikes.length ? (
            <p className="usage-chart-note">
              ▼ marks days when machine downloads jumped, usually one program
              fetching many files at once. {model.spikes.length === 1 ? "One day" : `${model.spikes.length} days`}{" "}
              had at least {formatCount(SPIKE_FLOOR)} machine downloads and four times a typical day: {spikeList}.
            </p>
          ) : null}
          <details className="usage-data">
            <summary>Show the numbers by week</summary>
            <div className="usage-tbl-wrap">
              <table className="usage-table">
                <thead>
                  <tr>
                    <th scope="col">Week of</th>
                    <th scope="col">Browser</th>
                    <th scope="col">Machine</th>
                    <th scope="col">Bots and crawlers</th>
                  </tr>
                </thead>
                <tbody>
                  {model.weeks.map((week) => (
                    <tr key={week.start}>
                      <td>
                        {formatDay(week.start)}
                        {week.days < 7 ? ` (${week.days} days)` : ""}
                      </td>
                      <td>{formatCount(week.browser)}</td>
                      <td>{formatCount(week.machine)}</td>
                      <td>{formatCount(week.bots)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </section>

      <section className="usage-band" aria-labelledby="usage-by-kind">
        <div className="meta">§ 2 · By kind · {period.label}</div>
        <h2 id="usage-by-kind">Who is downloading</h2>
        <p className="usage-copy">
          We sort each download by what the program says it is. Programs that
          open more than {HEAVY_CLIENT_FILES_PER_DAY} files in a day move from
          browser to machine, even if they look like a browser.
        </p>
        <div className="usage-kinds">
          <div className="usage-kinds-sub">Counted · {formatCount(counted)} downloads</div>
          <KindBars rows={kinds.counted} total={counted} muted={false} max={kindMax} />
          <div className="usage-kinds-sub">Not counted · {formatCount(headline.bots)} fetches</div>
          <KindBars rows={kinds.bots} total={0} muted max={kindMax} />
        </div>
      </section>

      <section className="usage-band" aria-labelledby="usage-api">
        <div className="meta">§ 3 · The API · {period.label}</div>
        <h2 id="usage-api">Use of the open API</h2>
        <div className="usage-api-row">
          <div>
            <strong>{formatCount(api.total)}</strong>
            <small>
              requests to the public API by people and programs other than this
              site, in {period.label}: {formatCount(api.postgrest)} to the full
              API and {formatCount(api.simple)} to the simple API and MCP server.
            </small>
          </div>
          <ApiBars daily={api.daily} highlight={period} />
        </div>
        <p className="usage-copy">
          API requests are not downloads. One program can ask for a thousand
          fields in an afternoon, so this number swings more than the download
          count.
          {api.topThreeShare !== null
            ? ` In ${period.label}, the three busiest days made up ${pct(api.topThreeShare, 1)} of the requests.`
            : ""}
          {api.botsExcluded > 0
            ? ` Bots and crawlers made another ${formatCount(api.botsExcluded)} requests, left out here.`
            : ""}{" "}
          Before October 1, 2026 we inferred which requests came from this site;
          since then the site labels its own.
        </p>
      </section>

      <section className="usage-band" aria-labelledby="usage-schools">
        <div className="meta">§ 4 · Across schools · {period.label}</div>
        <h2 id="usage-schools">Demand is spread wide</h2>
        {spread ? (
          <>
            <p className="usage-copy">
              Downloads are not concentrated on a few famous names. In {period.label}{" "}
              {spread.median !== null
                ? `the typical school's reports were downloaded about ${formatCount(spread.median)} times, and `
                : ""}
              {pct(spread.atLeast10, spread.schools)} of schools with any downloads had 10 or more.
            </p>
            <div className="usage-stats4">
              <div>
                <span>Schools with downloads</span>
                <strong>{formatCount(spread.schools)}</strong>
                <small>{period.label}</small>
              </div>
              <div>
                <span>Median per school</span>
                <strong>{spread.median !== null ? formatCount(spread.median) : "<10"}</strong>
                <small>downloads in the month</small>
              </div>
              <div>
                <span>10 or more</span>
                <strong>{formatCount(spread.atLeast10)}</strong>
                <small>{pct(spread.atLeast10, spread.schools)} of schools</small>
              </div>
              <div>
                <span>100 or more</span>
                <strong>{formatCount(spread.atLeast100)}</strong>
                <small>{pct(spread.atLeast100, spread.schools)} of schools</small>
              </div>
            </div>
            <div className="usage-hist" role="img" aria-label="Number of schools by downloads in the month">
              {spread.buckets.map((bucket, i) => (
                <div className="usage-hist__col" key={bucket.label}>
                  <span className="usage-hist__val">{formatCount(bucket.schools)}</span>
                  <span
                    className={`usage-hist__bar${i === 0 ? " usage-hist__bar--hidden" : ""}`}
                    style={{ height: `${((bucket.schools / histMax) * 150).toFixed(0)}px` }}
                  />
                </div>
              ))}
            </div>
            <div className="usage-hist__labels" aria-hidden="true">
              {spread.buckets.map((bucket) => (
                <div key={bucket.label}>{bucket.label} downloads</div>
              ))}
            </div>
            <p className="usage-chart-note">
              Schools by browser and machine downloads in {period.label}. We
              don&rsquo;t publish a ranked list of schools.
            </p>
          </>
        ) : (
          <p className="usage-copy">School numbers appear after the first full month is counted.</p>
        )}
        <UsageSchoolSearch schools={model.schools} periodLabel={period.label} sinceLabel={since} />
      </section>

      <section className="usage-band" aria-labelledby="usage-how" id="how-we-count">
        <div className="meta">§ 5 · How we count</div>
        <h2 id="usage-how">One request, start to finish</h2>
        <p className="usage-copy">Here is what happens to a single request for a report file.</p>
        <ol className="usage-steps">
          <li>
            <div>
              Someone opens a school&rsquo;s 2024&ndash;25 report in Chrome at 9:14 a.m. UTC.
              The file loads in three range requests, all answered with <code>206</code>.
            </div>
          </li>
          <li>
            <div>
              We pair the IP address with the browser&rsquo;s user-agent string to tell one
              visitor from another. The IP address stays inside the log system and is never
              stored.
            </div>
          </li>
          <li>
            <div>The three requests are for one file on one day, so they become one unique download.</div>
          </li>
          <li>
            <div>
              The user agent reads as an ordinary browser, and that visitor opened fewer than{" "}
              {HEAVY_CLIENT_FILES_PER_DAY} files that day, so it counts as a <b>browser</b> download.
            </div>
          </li>
          <li>
            <div>
              If the same visitor opens that report again at 4 p.m., the count does not change.
              Tomorrow it would count again.
            </div>
          </li>
          <li>
            <div>
              If the user agent had named a crawler, such as Googlebot or GPTBot, the download
              would go into bots and crawlers instead and stay out of the headline.
            </div>
          </li>
        </ol>
        <p className="usage-copy">
          Requests from our own pipeline and from this website&rsquo;s servers are left out
          entirely. A day appears here once every hour of it has been counted. School numbers
          are published once a month is complete, and a month with fewer than 10 downloads is
          hidden. The counting rules are versioned; when they change, we note the date and the
          change below. Read the <Link href="/privacy">privacy page</Link> for what we keep.
        </p>
      </section>

      <div className="usage-footnote">
        <span className="meta">Our own serving load</span>
        In {period.label} this website and its simple API made {formatCount(model.serving)} requests
        to the database to serve pages and answers. That is our own cost of running the site, not
        use by others, so it stays out of every count above.
      </div>

      <section className="usage-band" aria-labelledby="usage-open-data">
        <div className="meta">§ Open data</div>
        <h2 id="usage-open-data">Take the numbers with you</h2>
        <p className="usage-copy">
          Every number on this page is in a public file, free to reuse under CC0. It holds the
          daily totals, the monthly school counts, and the history of the counting rules.
        </p>
        <div className="usage-open-data">
          <a className="cd-btn" href="/usage.json">
            Download usage.json
          </a>
          <a className="cd-btn cd-btn--ghost" href="#how-we-count">
            Read the method
          </a>
        </div>
        <div className="usage-tbl-wrap" style={{ maxWidth: 640, marginTop: 22 }}>
          <table className="usage-table">
            <thead>
              <tr>
                <th scope="col">Rules version</th>
                <th scope="col">From</th>
                <th scope="col" style={{ textAlign: "left" }}>
                  Change
                </th>
              </tr>
            </thead>
            <tbody>
              {METHOD_CHANGELOG.map((entry) => (
                <tr key={entry.version}>
                  <td>{entry.version}</td>
                  <td>{formatDay(entry.from, { year: true })}</td>
                  <td className="usage-wrap">{entry.change}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
