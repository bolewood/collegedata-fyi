import Link from "next/link";
import type { AcceptanceHistory, AcceptanceYear } from "@/lib/acceptance-history";
import type { ManifestRow } from "@/lib/types";
import { entryTerm } from "@/lib/acceptance-rate-copy";
import { share } from "@/lib/school-summary";
import { storageUrl } from "@/lib/format";

export type AcceptanceTableRow =
  | { kind: "year"; row: AcceptanceYear }
  | { kind: "gap"; year: string; hasReport: boolean };

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
    ...history.gaps.map((year) => ({ kind: "gap" as const, year, hasReport: onFile.has(year) })),
  ];
  const key = (item: AcceptanceTableRow) => (item.kind === "year" ? item.row.year : item.year);
  return rows.sort((a, b) => key(b).localeCompare(key(a)));
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
    <p className="acc-table-hint" aria-hidden="true">Table scrolls sideways →</p>
    <div
      className="acc-table-scroll"
      role="region"
      aria-label={`${schoolName} acceptance rate table, scrolls sideways`}
      tabIndex={0}
    >
      <table className="acc-table">
        <caption className="sr-only">
          {schoolName} first-year applicants, admits, acceptance rate, enrolled, and yield by
          report year, newest first.
        </caption>
        <thead>
          <tr>
            <th scope="col">Report year</th>
            <th scope="col" className="acc-num">Applied</th>
            <th scope="col" className="acc-num">Admitted</th>
            <th scope="col" className="acc-num">Acceptance rate</th>
            <th scope="col" className="acc-num">Enrolled</th>
            <th scope="col" className="acc-num">Yield</th>
            <th scope="col">Original file</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => {
            if (item.kind === "gap") {
              return (
                <tr key={item.year} className="acc-table__gap">
                  <th scope="row">
                    <span className="acc-table__year">{item.year}</span>
                  </th>
                  <td className="acc-num">—</td>
                  <td className="acc-num">—</td>
                  <td className="acc-num">—</td>
                  <td className="acc-num">—</td>
                  <td className="acc-num">—</td>
                  <td className="acc-table__file">
                    {item.hasReport ? (
                      <Link href={`/schools/${schoolId}/${item.year}`}>Report on file</Link>
                    ) : (
                      "No report on file"
                    )}
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
                  <Link href={`/schools/${schoolId}/${row.year}`} className="acc-table__year">
                    {row.year}
                  </Link>
                  <span className="acc-table__term">{entryTerm(row)}</span>
                </th>
                <td className="acc-num">{count(row.applied)}</td>
                <td className="acc-num">{count(row.admitted)}</td>
                <td className="acc-num acc-table__rate">{share(row.rate)}</td>
                <td className="acc-num">{count(row.enrolled)}</td>
                <td className="acc-num">{row.yieldRate == null ? "—" : share(row.yieldRate)}</td>
                <td className="acc-table__file">
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`${schoolName} ${row.year} Common Data Set, original ${label} file`}
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
    </>
  );
}
