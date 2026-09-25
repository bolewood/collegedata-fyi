import Link from "next/link";
import type { AcceptanceYear } from "@/lib/acceptance-history";
import { fallLabel, gapLabel, pct, reportLabel } from "@/lib/acceptance-rate-copy";
import { storageUrl } from "@/lib/format";
import { type AcceptanceTableRow } from "./AcceptanceRateTable";

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

export function EarlyDecisionTable({
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
        More columns: admitted, source →
      </p>
      <div className="acc-table-frame">
        <div
          className="acc-table-scroll"
          role="region"
          aria-label={`${schoolName} early decision table, scrolls sideways`}
          tabIndex={0}
        >
          <table className="acc-table acc-table--ed">
            <caption className="sr-only">
              {schoolName} early decision acceptance rate, applicants, and admits by entering class,
              newest first.
            </caption>
            <colgroup>
              <col className="acc-col acc-col--year" />
              <col className="acc-col acc-col--rate" />
              <col className="acc-col acc-col--applied" />
              <col className="acc-col acc-col--admitted" />
              <col className="acc-col acc-col--source" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Year</th>
                <th scope="col" className="acc-num">
                  <span className="acc-th-long">Acceptance rate</span>
                  <span className="acc-th-short" aria-hidden="true">
                    Rate
                  </span>
                </th>
                <th scope="col" className="acc-num">
                  Applied
                </th>
                <th scope="col" className="acc-num">
                  Admitted
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
                      <td colSpan={3} className="acc-table__gap-label">
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
