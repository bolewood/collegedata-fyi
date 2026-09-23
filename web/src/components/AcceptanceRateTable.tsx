import Link from "next/link";
import type { AcceptanceHistory, AcceptanceYear } from "@/lib/acceptance-history";
import type { ManifestRow } from "@/lib/types";
import { fallLabel, gapLabel, pct, reportLabel } from "@/lib/acceptance-rate-copy";
import { storageUrl } from "@/lib/format";

export type AcceptanceTableRow =
  | { kind: "year"; row: AcceptanceYear }
  | { kind: "gap"; year: string; yearStart: number; hasReport: boolean };

/** Usable years plus named gaps, newest first. A gap notes whether a report is on file. */
export function acceptanceTableRows(
  history: AcceptanceHistory,
  documents: Pick<ManifestRow, "canonical_year" | "sub_institutional">[],
): AcceptanceTableRow[] {
  const onFile = new Set(
    documents.filter((doc) => doc.sub_institutional == null).map((doc) => doc.canonical_year),
  );
  const rows: AcceptanceTableRow[] = [
    ...history.years.map((row) => ({ kind: "year" as const, row })),
    ...history.gaps.map((year) => ({
      kind: "gap" as const,
      year,
      yearStart: Number(year.slice(0, 4)),
      hasReport: onFile.has(year),
    })),
  ];
  const start = (item: AcceptanceTableRow) => (item.kind === "year" ? item.row.yearStart : item.yearStart);
  return rows.sort((a, b) => start(b) - start(a));
}

function count(n: number | null): string {
  return n == null ? "—" : n.toLocaleString("en-US");
}

function fileLabel(row: AcceptanceYear): string {
  const ext = row.sourceStoragePath?.split(".").pop()?.toLowerCase();
  if (ext === "xlsx" || ext === "xls") return "XLSX";
  if (ext === "docx" || ext === "doc") return "DOCX";
  if (ext === "html" || ext === "htm") return "HTML";
  return "PDF";
}

export function AcceptanceRateTable({
  schoolId,
  schoolName,
  rows,
}: {
  schoolId: string;
  schoolName: string;
  rows: AcceptanceTableRow[];
}) {
  return (
    <>
      <p className="acc-table-hint" aria-hidden="true">
        Scroll for enrolled, yield, and source →
      </p>
      <div className="acc-table-frame">
      <div
        className="acc-table-scroll"
        role="region"
        aria-label={`${schoolName} acceptance rate table, scrolls sideways`}
        tabIndex={0}
      >
        <table className="acc-table">
          <caption className="sr-only">
            {schoolName} first-year acceptance rate, applicants, admits, enrolled, and yield by
            entering class, newest first.
          </caption>
          <colgroup>
            <col className="acc-col acc-col--year" />
            <col className="acc-col acc-col--rate" />
            <col className="acc-col acc-col--applied" />
            <col className="acc-col acc-col--admitted" />
            <col className="acc-col acc-col--enrolled" />
            <col className="acc-col acc-col--yield" />
            <col className="acc-col acc-col--source" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Year</th>
              <th scope="col" className="acc-num">
                <span className="acc-th-long">Acceptance rate</span>
                <span className="acc-th-short" aria-hidden="true">Rate</span>
              </th>
              <th scope="col" className="acc-num">Applied</th>
              <th scope="col" className="acc-num">Admitted</th>
              <th scope="col" className="acc-num">Enrolled</th>
              <th scope="col" className="acc-num">Yield</th>
              <th scope="col" className="acc-table__file">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => {
              if (item.kind === "gap") {
                return (
                  <tr key={item.year} className="acc-table__gap">
                    <th scope="row">
                      <span className="acc-table__fall">Fall {item.yearStart}</span>
                      {item.hasReport ? (
                        <Link href={`/schools/${schoolId}/${item.year}`} className="acc-table__report">
                          {reportLabel(item.year)}
                        </Link>
                      ) : null}
                      <span className="acc-table__gap-note" aria-hidden="true">
                        {gapLabel(item.hasReport)}
                      </span>
                    </th>
                    <td className="acc-num acc-table__merged">—</td>
                    <td colSpan={5} className="acc-table__gap-label">
                      {gapLabel(item.hasReport)}
                    </td>
                  </tr>
                );
              }
              const { row } = item;
              const href = storageUrl(row.sourceStoragePath);
              const label = fileLabel(row);
              return (
                <tr key={row.year}>
                  <th scope="row">
                    <span className="acc-table__fall">{fallLabel(row)}</span>
                    <Link href={`/schools/${schoolId}/${row.year}`} className="acc-table__report">
                      {reportLabel(row.year)}
                    </Link>
                  </th>
                  <td className="acc-num acc-table__rate">{pct(row.rate)}</td>
                  <td className="acc-num">{count(row.applied)}</td>
                  <td className="acc-num">{count(row.admitted)}</td>
                  <td className="acc-num">{count(row.enrolled)}</td>
                  <td className="acc-num">{row.yieldRate == null ? "—" : pct(row.yieldRate)}</td>
                  <td className="acc-table__file">
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`${schoolName} ${reportLabel(row.year)}, original ${label} file`}
                      >
                        {label}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      </div>
    </>
  );
}
