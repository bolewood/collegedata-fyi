import type { Metadata } from "next";
import Link from "next/link";
import { fetchPipelineObservation } from "@/lib/pipeline-observation";
import type { ExtractionActivityItem } from "@/lib/pipeline-observation";
import type { Lamp } from "@/lib/pipeline-lamps";
import "./pipeline-observation.css";

export const revalidate = 60;

export const metadata: Metadata = {
  title: "Pipeline observation — collegedata.fyi",
  description:
    "Every dispatch station on collegedata.fyi, when it last ran on schedule, and what it found. Missing heartbeats are red.",
  alternates: { canonical: "/pipeline-observation" },
};

const LAMP_WORD: Record<Lamp, string> = {
  capped: "Daily Cap Reached",
  down: "DOWN",
  late: "LATE",
  ok: "OK",
  run: "RUN",
  slate: "SLATE",
};

const FORMAT_LABEL: Record<ExtractionActivityItem["source_format"], string> = {
  pdf_fillable: "fillable PDF",
  pdf_flat: "flat PDF",
  pdf_scanned: "scanned PDF",
  xlsx: "XLSX",
  docx: "DOCX",
  html: "HTML",
  other: "other",
  unknown: "unknown format",
};

const TIER_LABEL: Record<ExtractionActivityItem["extraction_tier"], string> = {
  tier1: "Tier 1",
  tier2: "Tier 2",
  tier3: "Tier 3",
  tier4: "Tier 4",
  tier4_ocr: "Tier 4 + OCR",
  tier4_fallback: "Tier 4 fallback",
  tier6: "Tier 6",
  reconciliation: "Reconcile",
  unsupported: "Unsupported",
  unknown: "Unknown tier",
};

const OUTCOME_LABEL: Record<ExtractionActivityItem["outcome"], string> = {
  extracted: "First extraction",
  re_extracted: "Re-extraction",
  already_current: "Already current",
  reconciled: "Reconciled",
  failed: "Failed",
};

export default async function PipelineObservationPage() {
  const snapshot = await fetchPipelineObservation();

  return (
    <div className="po-page mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <div className="meta">§ Pipeline observation</div>
      <div
        className={`po-strip po-strip--${snapshot.strip.lamp}`}
        role="status"
        aria-live="polite"
      >
        {snapshot.strip.text}
      </div>
      <header style={{ paddingTop: 16, paddingBottom: 8 }}>
        <h1
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: "clamp(40px, 6vw, 64px)",
            lineHeight: 1.05,
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          The clocks, <em>and the locked doors.</em>
        </h1>
        <p
          style={{
            marginTop: 18,
            fontSize: 16,
            lineHeight: 1.55,
            color: "var(--ink-2)",
            maxWidth: 720,
          }}
        >
          Every dispatch station on collegedata.fyi, when it last ran on
          schedule, and what it found. If a step goes quiet, the lamp turns
          red — including the monthly search that sat idle from April to
          August 2026. Locked doors (Tableau, SharePoint IRM, SSO) ship in
          the next slice; this page is the clocks.
        </p>
      </header>

      <section>
        <h2
          className="serif"
          style={{ fontSize: 22, lineHeight: 1.2, margin: "48px 0 16px" }}
        >
          Dispatch board
        </h2>
        <div className="po-board">
          {snapshot.stations.map((station) => (
            <article
              key={station.station_id}
              className={`po-tile po-tile--${station.lamp}`}
              tabIndex={0}
              aria-label={`${station.display_name}: ${LAMP_WORD[station.lamp]}, ${station.ago_label}`}
              aria-describedby={`po-tip-${station.station_id}`}
            >
              <div>
                <div className="po-tile-id">{station.cadence_label}</div>
                <h3>{station.display_name}</h3>
                <div className="po-tile-lamp">{LAMP_WORD[station.lamp]}</div>
                <div className="po-tile-ago">{station.ago_label}</div>
                <div className="po-tile-result">{station.result_line}</div>
              </div>
              <p
                id={`po-tip-${station.station_id}`}
                className="po-tile-tip"
                role="tooltip"
              >
                <span className="po-tile-tip-kicker">What this does</span>
                {station.help}
              </p>
            </article>
          ))}
        </div>
        <p className="po-manual">
          Manual sources (not on the strip):{" "}
          {snapshot.manual_sources
            .map((source) => `${source.display_name} — ${source.ago_label}`)
            .join(" · ")}
        </p>
      </section>

      <section className="po-activity">
        <div className="meta">§ Last 14 days · 50 files max</div>
        <h2 className="serif">Recent extraction activity</h2>
        {snapshot.extraction_activity.length ? (
          <div className="po-ledger" role="list">
            {snapshot.extraction_activity.map((item, index) => (
              <article
                className="po-ledger-row"
                key={`${item.activity_at}-${item.school_id}-${index}`}
                role="listitem"
              >
                <time dateTime={item.activity_at} className="po-ledger-time">
                  {item.ago_label} ago
                </time>
                <div className="po-ledger-school">
                  <Link href={`/schools/${item.school_id}`}>
                    {item.school_name}
                  </Link>
                  <span>{item.canonical_year}</span>
                </div>
                <div className="po-ledger-method">
                  {FORMAT_LABEL[item.source_format]} ·{" "}
                  {TIER_LABEL[item.extraction_tier]}
                </div>
                <div className={`po-ledger-outcome po-ledger-outcome--${item.outcome}`}>
                  <strong>{OUTCOME_LABEL[item.outcome]}</strong>
                  {item.field_count !== null ? (
                    <span>{item.field_count} fields</span>
                  ) : null}
                </div>
                <div className="po-ledger-run">
                  <span>{item.trigger_label}</span>
                  {item.run_url ? (
                    <a
                      href={item.run_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Run ↗
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p
            className={`po-ledger-empty${
              snapshot.activity_load_error ? " po-ledger-empty--error" : ""
            }`}
          >
            {snapshot.activity_load_error
              ? "Recent extraction activity could not be loaded. Refresh this page or check the latest extraction run."
              : "No extraction finishes recorded in the last 14 days."}
          </p>
        )}
      </section>

      <section style={{ marginTop: 64 }}>
        <h2
          id="methodology"
          className="serif"
          style={{ fontSize: 22, lineHeight: 1.2, margin: "0 0 16px" }}
        >
          Methodology
        </h2>
        <div className="po-method">
          <p style={{ margin: 0 }}>
            Each station writes a public heartbeat when it starts and when it
            finishes. Lamps are computed at read time from the{" "}
            <strong>scheduled</strong> clock. A manual GitHub run cannot green
            a missing cron. If the scheduled heartbeat is older than the SLA,
            the lamp is red — including when a dispatch succeeded yesterday.
            Missing data is red, not gray.
          </p>
          <p style={{ margin: 0 }}>
            This page is not coverage. Coverage asks whether we have a CDS.
            This board asks whether the machine is running. JSON snapshot:{" "}
            <a href="/pipeline-observation.json">/pipeline-observation.json</a>.
          </p>
        </div>
      </section>
    </div>
  );
}
