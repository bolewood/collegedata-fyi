"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  WAITLIST_CASES,
  type WaitlistBucketSummary,
  type WaitlistRecipeRow,
} from "@/lib/waitlist-recipe-data";
import {
  WAITLIST_ANALYSIS_ROWS,
  WAITLIST_ANALYSIS_SUMMARY,
  WAITLIST_REPORTED_ANOMALY_ROWS,
  type WaitlistBucketKey,
  summarizeWaitlistBuckets,
} from "@/lib/waitlist-recipe-analysis";

const BUCKET_LABELS: Record<WaitlistBucketKey, string> = {
  selectivity: "Admit-rate band",
  control: "Control",
  size: "Undergrad size",
  carnegie: "Carnegie class",
};

const W = 980;
const H = 540;
const M = { l: 210, r: 36, t: 34, b: 58 };
const IW = W - M.l - M.r;

function formatPct(value: number | null, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatNumber(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return value.toLocaleString("en-US");
}

function formatSuccessPct(value: number | null): string {
  if (value == null) return "n/a";
  return formatPct(value, value > 0 && value < 0.01 ? 2 : 1);
}

function compactNumber(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  return String(value);
}

function hash01(input: string): number {
  let h = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 10000) / 10000;
}

function xScale(rate: number | null): number {
  const clamped = Math.max(0, Math.min(1, rate ?? 0));
  return M.l + Math.sqrt(clamped) * IW;
}

function radius(accepted: number | null): number {
  if (!accepted || accepted <= 0) return 3.5;
  return 3.5 + Math.sqrt(Math.min(accepted, 20000) / 20000) * 9;
}

function rowMedian(summary: WaitlistBucketSummary): number {
  return summary.medianSuccessRate ?? 0;
}

function Chart({
  bucketKey,
  rows,
  summaries,
}: {
  bucketKey: WaitlistBucketKey;
  rows: readonly WaitlistRecipeRow[];
  summaries: readonly WaitlistBucketSummary[];
}) {
  const [hover, setHover] = useState<WaitlistRecipeRow | null>(null);
  const bucketIndex = new Map<string, number>(summaries.map((bucket, index) => [bucket.label, index]));
  const rowH = (H - M.t - M.b) / summaries.length;
  const yCenter = (index: number) => M.t + rowH * index + rowH / 2;
  const xTicks = [0, 0.02, 0.1, 0.25, 0.5, 1];

  return (
    <div className="cd-card" style={{ padding: 24, position: "relative" }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 12,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div className="meta">Fig. 1 · Wait-list success by {BUCKET_LABELS[bucketKey].toLowerCase()}</div>
        <div className="mono" style={{ color: "var(--ink-3)", fontSize: 11 }}>
          DOT SIZE = ACCEPTED WAIT-LIST SPOTS · X-AXIS USES SQRT SCALE
        </div>
      </div>

      <div style={{ overflowX: "auto" }}>
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          style={{ display: "block", height: "auto", maxWidth: "100%", minWidth: 720 }}
          role="img"
          aria-label="Dot plot of wait-list success rates grouped by school type"
        >
        <rect
          x={xScale(0)}
          y={M.t}
          width={xScale(0.02) - xScale(0)}
          height={H - M.t - M.b}
          fill="var(--brick)"
          opacity="0.07"
        />
        <rect
          x={xScale(0.02)}
          y={M.t}
          width={xScale(0.1) - xScale(0.02)}
          height={H - M.t - M.b}
          fill="var(--ochre)"
          opacity="0.06"
        />
        <rect
          x={xScale(0.1)}
          y={M.t}
          width={xScale(1) - xScale(0.1)}
          height={H - M.t - M.b}
          fill="var(--forest)"
          opacity="0.05"
        />

        {xTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={xScale(tick)}
              x2={xScale(tick)}
              y1={M.t}
              y2={H - M.b}
              stroke="var(--chart-grid)"
            />
            <text
              x={xScale(tick)}
              y={H - M.b + 22}
              textAnchor="middle"
              fontFamily="var(--mono)"
              fontSize="11"
              fill="var(--chart-axis)"
            >
              {tick === 0 ? "0" : formatPct(tick, tick < 0.1 ? 0 : 0)}
            </text>
          </g>
        ))}

        {summaries.map((summary, index) => {
          const y = yCenter(index);
          return (
            <g key={summary.label}>
              <line x1={M.l} x2={W - M.r} y1={y} y2={y} stroke="var(--rule)" />
              <text
                x={M.l - 14}
                y={y - 5}
                textAnchor="end"
                fontFamily="var(--sans)"
                fontSize="13"
                fill="var(--ink)"
              >
                {summary.label}
              </text>
              <text
                x={M.l - 14}
                y={y + 12}
                textAnchor="end"
                fontFamily="var(--mono)"
                fontSize="10"
                fill="var(--ink-3)"
              >
                {summary.schools} schools · median {formatPct(summary.medianSuccessRate)}
              </text>
              <line
                x1={xScale(rowMedian(summary))}
                x2={xScale(rowMedian(summary))}
                y1={y - rowH * 0.34}
                y2={y + rowH * 0.34}
                stroke="var(--forest)"
                strokeWidth="2"
              />
            </g>
          );
        })}

        {rows.map((row) => {
          const index = bucketIndex.get(row[bucketKey]);
          if (index == null || row.waitListSuccessRate == null) return null;
          const jitter = (hash01(row.documentId) - 0.5) * rowH * 0.56;
          const y = yCenter(index) + jitter;
          const highlighted =
            row.schoolId === "uc-berkeley" ||
            row.schoolId === "uva" ||
            row.schoolId === "baylor-university";
          return (
            <circle
              key={row.documentId}
              cx={xScale(row.waitListSuccessRate)}
              cy={y}
              r={radius(row.waitListAccepted)}
              fill={highlighted ? "var(--forest)" : "var(--ink)"}
              opacity={highlighted ? 0.9 : 0.64}
              stroke="var(--paper)"
              strokeWidth="1.2"
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHover(row)}
              onMouseLeave={() => setHover(null)}
            />
          );
        })}

        <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--ink)" />
          <text
            x={M.l + IW / 2}
            y={H - 12}
            textAnchor="middle"
            fontFamily="var(--sans)"
            fontSize="12"
            fill="var(--ink)"
          >
            Chance of admission after accepting a wait-list spot →
          </text>
        </svg>
      </div>

      <div
        className="mono"
        style={{
          display: "flex",
          gap: 16,
          alignItems: "center",
          borderTop: "1px solid var(--rule)",
          color: "var(--ink-3)",
          flexWrap: "wrap",
          fontSize: 11,
          marginTop: 12,
          paddingTop: 12,
        }}
      >
        <span><span style={{ color: "var(--brick)" }}>■</span> under 2%</span>
        <span><span style={{ color: "var(--ochre)" }}>■</span> 2-10%</span>
        <span><span style={{ color: "var(--forest)" }}>■</span> 10%+</span>
        <span style={{ marginLeft: "auto" }}>
          Vertical forest ticks mark each bucket median; reported anomalous rows are excluded.
        </span>
      </div>

      {hover && (
        <div
          role="status"
          className="mono"
          style={{
            position: "absolute",
            left: 24,
            bottom: 70,
            background: "var(--ink)",
            color: "var(--paper)",
            padding: "10px 14px",
            borderRadius: 2,
            fontSize: 12,
            lineHeight: 1.5,
            maxWidth: 360,
            pointerEvents: "none",
            zIndex: 3,
          }}
        >
          <div className="serif" style={{ color: "var(--paper)", fontSize: 15 }}>
            {hover.schoolName}
          </div>
          <div style={{ color: "var(--ink-4)" }}>CDS {hover.year} · {hover.selectivity}</div>
          <div style={{ marginTop: 6 }}>
            {formatNumber(hover.waitListAdmitted)} admitted from{" "}
            {formatNumber(hover.waitListAccepted)} accepted spots
          </div>
          <div>Wait-list success: {formatPct(hover.waitListSuccessRate)}</div>
          <div style={{ color: "var(--ink-4)", marginTop: 6 }}>
            Offered {formatNumber(hover.waitListOffered)} · Admit rate{" "}
            {formatPct(hover.acceptanceRate)}
          </div>
        </div>
      )}
    </div>
  );
}

function BucketTable({
  summaries,
}: {
  summaries: readonly WaitlistBucketSummary[];
}) {
  return (
    <div className="cd-card" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr className="mono" style={{ color: "var(--ink-3)", fontSize: 10.5, letterSpacing: "0.06em" }}>
            <th style={{ textAlign: "left", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>
              Bucket
            </th>
            <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>
              Schools
            </th>
            <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>
              Median success
            </th>
            <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>
              Weighted success
            </th>
            <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>
              Under 2%
            </th>
            <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>
              Median accepted
            </th>
          </tr>
        </thead>
        <tbody>
          {summaries.map((bucket) => (
            <tr key={bucket.label}>
              <td style={{ padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                {bucket.label}
              </td>
              <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                {bucket.schools}
              </td>
              <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                {formatPct(bucket.medianSuccessRate)}
              </td>
              <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                {formatPct(bucket.weightedSuccessRate)}
              </td>
              <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                {formatPct(bucket.zeroishShare, 0)}
              </td>
              <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                {formatNumber(bucket.medianAccepted)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CaseStudy({ row }: { row: WaitlistRecipeRow }) {
  const complete = row.complete && row.waitListSuccessRate != null;
  return (
    <article className="cd-card cd-card--cut" style={{ padding: 18 }}>
      <div className="meta">{row.year} · {row.selectivity}</div>
      <h3 className="serif" style={{ fontSize: 22, margin: "8px 0 0" }}>
        <Link href={row.schoolUrl} style={{ textDecoration: "none" }}>
          {row.schoolName}
        </Link>
      </h3>
      <div
        className="nums"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 10,
          marginTop: 14,
        }}
      >
        <div>
          <div className="meta">Offered</div>
          <strong className="serif" style={{ fontSize: 24 }}>{formatNumber(row.waitListOffered)}</strong>
        </div>
        <div>
          <div className="meta">Accepted</div>
          <strong className="serif" style={{ fontSize: 24 }}>{formatNumber(row.waitListAccepted)}</strong>
        </div>
        <div>
          <div className="meta">Admitted</div>
          <strong className="serif" style={{ fontSize: 24 }}>{formatNumber(row.waitListAdmitted)}</strong>
        </div>
      </div>
      <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, marginTop: 12 }}>
        {complete ? (
          <>
            {formatSuccessPct(row.waitListSuccessRate)} of students who accepted a spot were admitted from
            the wait list. The same CDS row reports a normal admit rate of {formatPct(row.acceptanceRate)}.
          </>
        ) : (
          <>
            The CDS projection has wait-list scale but not enough complete C2 counts to compute a
            success rate, so this row is excluded from bucket medians.
          </>
        )}
      </p>
    </article>
  );
}

export function WaitlistOddsExplorer() {
  const [bucketKey, setBucketKey] = useState<WaitlistBucketKey>("selectivity");
  const [tableMode, setTableMode] = useState<"lowest" | "largest">("lowest");

  const bucketSummaries = useMemo(
    () => summarizeWaitlistBuckets(WAITLIST_ANALYSIS_ROWS, bucketKey),
    [bucketKey],
  );
  const rankedRows = useMemo(() => {
    const rows = [...WAITLIST_ANALYSIS_ROWS];
    if (tableMode === "largest") {
      rows.sort((a, b) => (b.waitListAccepted ?? 0) - (a.waitListAccepted ?? 0));
    } else {
      rows.sort((a, b) => (a.waitListSuccessRate ?? 0) - (b.waitListSuccessRate ?? 0));
    }
    return rows.slice(0, 15);
  }, [tableMode]);

  return (
    <>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 14,
          marginTop: 28,
        }}
        className="waitlist-recipe-stats"
      >
        {[
          ["Analysis rows", WAITLIST_ANALYSIS_SUMMARY.analysisRows.toLocaleString("en-US")],
          ["Median success", formatPct(WAITLIST_ANALYSIS_SUMMARY.medianSuccessRate)],
          ["Weighted success", formatPct(WAITLIST_ANALYSIS_SUMMARY.weightedSuccessRate)],
          ["Flagged rows", WAITLIST_ANALYSIS_SUMMARY.reportedAnomalyRows.toLocaleString("en-US")],
        ].map(([label, value]) => (
          <div key={label} className="cd-card" style={{ padding: 16 }}>
            <div className="meta">{label}</div>
            <div className="serif nums" style={{ fontSize: 32, marginTop: 6, lineHeight: 1 }}>
              {value}
            </div>
          </div>
        ))}
      </section>

      <section style={{ marginTop: 28 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {(Object.keys(BUCKET_LABELS) as WaitlistBucketKey[]).map((key) => (
            <button
              key={key}
              type="button"
              className={`cd-btn ${bucketKey === key ? "" : "cd-btn--ghost"}`}
              style={{ padding: "8px 12px", fontSize: 13 }}
              onClick={() => setBucketKey(key)}
            >
              {BUCKET_LABELS[key]}
            </button>
          ))}
        </div>
        <Chart bucketKey={bucketKey} rows={WAITLIST_ANALYSIS_ROWS} summaries={bucketSummaries} />
      </section>

      <section style={{ marginTop: 24 }}>
        <div className="cd-card" style={{ padding: 18 }}>
          <div className="meta">§ Reported-data caveat</div>
          <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.6, margin: "8px 0 0" }}>
            {WAITLIST_ANALYSIS_SUMMARY.reportedAnomalyRows} high-volume rows report that at least 95%
            of students who accepted a wait-list spot were admitted. Some of those values appear
            verbatim in the source PDFs, and at least one row has a blank accepted-count cell that the
            extractor filled from the admitted-count row. They are preserved below as source-reported
            anomalies, but excluded from medians, bucket summaries, and the main chart.
          </p>
          <div style={{ overflowX: "auto", marginTop: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr className="mono" style={{ color: "var(--ink-3)", fontSize: 10.5, letterSpacing: "0.06em" }}>
                  <th style={{ textAlign: "left", padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>School</th>
                  <th style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>Year</th>
                  <th style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>Accepted</th>
                  <th style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>Admitted</th>
                  <th style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>Reported rate</th>
                </tr>
              </thead>
              <tbody>
                {WAITLIST_REPORTED_ANOMALY_ROWS.map((row) => (
                  <tr key={row.documentId}>
                    <td style={{ padding: "10px 0", borderBottom: "1px dashed var(--rule)" }}>
                      <Link href={row.schoolUrl}>{row.schoolName}</Link>
                    </td>
                    <td className="nums" style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px dashed var(--rule)" }}>
                      {row.year}
                    </td>
                    <td className="nums" style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px dashed var(--rule)" }}>
                      {formatNumber(row.waitListAccepted)}
                    </td>
                    <td className="nums" style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px dashed var(--rule)" }}>
                      {formatNumber(row.waitListAdmitted)}
                    </td>
                    <td className="nums" style={{ textAlign: "right", padding: "10px 0", borderBottom: "1px dashed var(--rule)" }}>
                      {formatPct(row.waitListSuccessRate)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section
        style={{
          marginTop: 44,
          display: "grid",
          gridTemplateColumns: "220px 1fr",
          gap: 36,
        }}
        className="cd-recipe-guide"
      >
        <div>
          <div className="meta">§ The answer</div>
          <div className="serif" style={{ color: "var(--ink-2)", fontSize: 21, fontStyle: "italic", lineHeight: 1.25, marginTop: 8 }}>
            Hope is allowed.
            <br />
            Planning on it is not.
          </div>
        </div>
        <p style={{ color: "var(--ink-2)", fontSize: 16, lineHeight: 1.65, margin: 0 }}>
          Across complete CDS wait-list rows in the current corpus, the median school admits{" "}
          {formatPct(WAITLIST_ANALYSIS_SUMMARY.medianSuccessRate)} of students who accept a spot.
          That sounds meaningful until you split the schools: the most selective buckets cluster
          around low single digits, and {WAITLIST_ANALYSIS_SUMMARY.zeroishRows} complete rows are
          effectively closed doors under 2%. Higher rates exist, but they are concentrated at less
          selective schools and in years where the enrollment model missed badly. Reported near-total
          wait-list admit rows are treated as data-quality caveats rather than odds estimates.
        </p>
      </section>

      <section style={{ marginTop: 44 }}>
        <div className="meta" style={{ marginBottom: 10 }}>§ Bucket table</div>
        <BucketTable summaries={bucketSummaries} />
      </section>

      <section style={{ marginTop: 44 }}>
        <div className="meta" style={{ marginBottom: 12 }}>§ Case studies from the corpus</div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 16,
          }}
          className="waitlist-case-grid"
        >
          {WAITLIST_CASES.map((row) => (
            <CaseStudy key={row.documentId} row={row} />
          ))}
        </div>
      </section>

      <section style={{ marginTop: 44 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div className="meta">§ Extremes</div>
            <h2 className="serif" style={{ fontSize: 26, margin: "6px 0 0" }}>
              The rows that shape expectations.
            </h2>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className={`cd-btn ${tableMode === "lowest" ? "" : "cd-btn--ghost"}`}
              style={{ padding: "8px 12px", fontSize: 13 }}
              onClick={() => setTableMode("lowest")}
            >
              Lowest odds
            </button>
            <button
              type="button"
              className={`cd-btn ${tableMode === "largest" ? "" : "cd-btn--ghost"}`}
              style={{ padding: "8px 12px", fontSize: 13 }}
              onClick={() => setTableMode("largest")}
            >
              Largest lists
            </button>
          </div>
        </div>
        <div className="cd-card" style={{ marginTop: 14, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr className="mono" style={{ color: "var(--ink-3)", fontSize: 10.5, letterSpacing: "0.06em" }}>
                <th style={{ textAlign: "left", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>School</th>
                <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>Year</th>
                <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>Accepted</th>
                <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>Admitted</th>
                <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>WL success</th>
                <th style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px solid var(--rule)" }}>Admit rate</th>
              </tr>
            </thead>
            <tbody>
              {rankedRows.map((row) => (
                <tr key={row.documentId}>
                  <td style={{ padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                    <Link href={row.schoolUrl}>{row.schoolName}</Link>
                    <div className="mono" style={{ color: "var(--ink-3)", fontSize: 10.5, marginTop: 2 }}>
                      {row.selectivity}
                    </div>
                  </td>
                  <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                    {row.year}
                  </td>
                  <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                    {compactNumber(row.waitListAccepted)}
                  </td>
                  <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                    {compactNumber(row.waitListAdmitted)}
                  </td>
                  <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                    {formatPct(row.waitListSuccessRate, row.waitListSuccessRate && row.waitListSuccessRate < 0.01 ? 2 : 1)}
                  </td>
                  <td className="nums" style={{ textAlign: "right", padding: "12px 14px", borderBottom: "1px dashed var(--rule)" }}>
                    {formatPct(row.acceptanceRate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
