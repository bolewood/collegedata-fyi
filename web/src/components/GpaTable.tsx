import Link from "next/link";
import type { GpaHistory, GpaYear } from "@/lib/c11-gpa";
import type { ManifestRow } from "@/lib/types";
import { bandShare, gpa } from "@/lib/gpa-copy";
import { fallLabel, gapLabel, reportLabel } from "@/lib/acceptance-rate-copy";
import { storageUrl } from "@/lib/format";

export type GpaTableRow =
  | { kind: "year"; row: GpaYear }
  | { kind: "gap"; year: string; yearStart: number; hasReport: boolean };

export function gpaTableRows(
  history: GpaHistory,
  documents: Pick<ManifestRow, "canonical_year" | "sub_institutional">[],
): GpaTableRow[] {
  const onFile = new Set(
    documents.filter((doc) => doc.sub_institutional == null).map((doc) => doc.canonical_year),
  );
  const rows: GpaTableRow[] = [
    ...history.years.map((row) => ({ kind: "year" as const, row })),
    ...history.gaps.map((year) => ({
      kind: "gap" as const,
      year,
      yearStart: Number(year.slice(0, 4)),
      hasReport: onFile.has(year),
    })),
  ];
  const start = (item: GpaTableRow) => (item.kind === "year" ? item.row.yearStart : item.yearStart);
  return rows.sort((a, b) => start(b) - start(a));
}

function fileLabel(row: GpaYear): string {
  const ext = row.sourceStoragePath?.split(".").pop()?.toLowerCase();
  if (ext === "xlsx" || ext === "xls") return "XLSX";
  if (ext === "docx" || ext === "doc") return "DOCX";
  if (ext === "html" || ext === "htm") return "HTML";
  return "PDF";
}

function submitted(n: number | null): string {
  return n == null ? "—" : bandShare(n);
}

export function GpaTable({
  schoolId,
  schoolName,
  rows,
}: {
  schoolId: string;
  schoolName: string;
  rows: GpaTableRow[];
}) {
  return (
    <>
      <p className="acc-table-hint" aria-hidden="true">
        More columns: 3.50–3.74, reported, source →
      </p>
      <div className="acc-table-frame">
        <div
          className="acc-table-scroll"
          role="region"
          aria-label={`${schoolName} enrolled first-year GPA table, scrolls sideways`}
          tabIndex={0}
        >
          <table className="acc-table acc-table--ed">
            <caption className="sr-only">
              {schoolName} enrolled first-year GPA average and bands by entering class, newest first.
            </caption>
            <colgroup>
              <col className="acc-col acc-col--year" />
              <col className="acc-col acc-col--rate" />
              <col className="acc-col acc-col--applied" />
              <col className="acc-col acc-col--admitted" />
              <col className="acc-col acc-col--applied" />
              <col className="acc-col acc-col--applied" />
              <col className="acc-col acc-col--source" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Year</th>
                <th scope="col" className="acc-num">
                  Average
                </th>
                <th scope="col" className="acc-num">
                  4.0
                </th>
                <th scope="col" className="acc-num">
                  3.75–3.99
                </th>
                <th scope="col" className="acc-num">
                  3.50–3.74
                </th>
                <th scope="col" className="acc-num">
                  Reported
                </th>
                <th scope="col" className="acc-table__file">
                  Source
                </th>
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
                    <td className="acc-num acc-table__rate">{row.average != null ? gpa(row.average) : "—"}</td>
                    <td className="acc-num">{bandShare(row.bands.percents.gpa4)}</td>
                    <td className="acc-num">{bandShare(row.bands.percents.gpa375)}</td>
                    <td className="acc-num">{bandShare(row.bands.percents.gpa350)}</td>
                    <td className="acc-num">{submitted(row.submittedPct)}</td>
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
