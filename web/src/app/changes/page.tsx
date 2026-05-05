import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchOperatorChangeDigest } from "@/lib/change-intelligence-admin";
import type { ChangeEventRow } from "@/lib/types";

export const metadata: Metadata = {
  title: "Change Intelligence",
  description: "Operator digest for Common Data Set year-over-year change events.",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

function valuePair(event: ChangeEventRow): string {
  if (event.fromValue && event.toValue) return `${event.fromValue} to ${event.toValue}`;
  if (event.fromValue) return `${event.fromValue} to not reported`;
  if (event.toValue) return `not reported to ${event.toValue}`;
  return "n/a";
}

function eventRows(events: ChangeEventRow[]) {
  if (events.length === 0) {
    return (
      <p className="change-digest-empty">
        No matching events in the latest projection.
      </p>
    );
  }
  return (
    <div className="change-digest-table-wrap">
      <table className="change-digest-table">
        <thead>
          <tr>
            <th>School</th>
            <th>Field</th>
            <th>Type</th>
            <th>Severity</th>
            <th>Value</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>
                <Link href={`/schools/${event.schoolId}`}>{event.schoolName}</Link>
                <span>{event.fromYear} to {event.toYear}</span>
              </td>
              <td>{event.fieldLabel}</td>
              <td>{event.eventType.replaceAll("_", " ")}</td>
              <td>{event.severity}</td>
              <td>{valuePair(event)}</td>
              <td>{event.verificationStatus.replaceAll("_", " ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function section(title: string, events: ChangeEventRow[]) {
  return (
    <section className="change-digest-section rule-2">
      <div className="meta">§ {title}</div>
      {eventRows(events)}
    </section>
  );
}

export default async function ChangesPage() {
  if (process.env.CHANGE_INTELLIGENCE_DIGEST_ENABLED !== "true") {
    notFound();
  }

  const { events, summary } = await fetchOperatorChangeDigest();
  const admissions = events.filter((event) => event.fieldFamily === "admissions_pressure");
  const international = events.filter((event) => event.fieldFamily === "international_students");
  const aid = events.filter((event) => event.fieldFamily === "aid_affordability");
  const silences = events.filter((event) => event.eventType === "newly_missing");
  const blockers = events.filter((event) =>
    ["quality_regression", "producer_changed", "format_changed"].includes(event.eventType),
  );

  return (
    <div className="change-digest mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="meta">§ Operator digest</div>
      <h1 className="serif change-digest-title">Change intelligence.</h1>
      <p className="change-digest-lede">
        Internal view of generated Common Data Set change events. Public school
        pages only show events marked public after review.
      </p>

      <div className="change-digest-summary">
        <div>
          <span>Total events</span>
          <strong className="serif stat-num">{summary.total}</strong>
        </div>
        <div>
          <span>Major</span>
          <strong className="serif stat-num">{summary.major}</strong>
        </div>
        <div>
          <span>Review queue</span>
          <strong className="serif stat-num">{summary.candidates}</strong>
        </div>
        <div>
          <span>Public</span>
          <strong className="serif stat-num">{summary.publicVisible}</strong>
        </div>
      </div>

      {summary.latestYear ? (
        <p className="change-digest-note mono">
          Latest comparison year in this digest: {summary.latestYear}.
        </p>
      ) : (
        <p className="change-digest-note mono">
          No events found. Confirm `SUPABASE_SERVICE_ROLE_KEY` is configured for this operator route.
        </p>
      )}

      {section("Biggest admissions changes", admissions)}
      {section("International-student signals", international)}
      {section("Aid and affordability shifts", aid)}
      {section("Reporting gaps and silences", silences)}
      {section("Extraction-quality blockers", blockers)}
    </div>
  );
}
