import type { InstitutionCoverage } from "@/lib/types";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "@/lib/data-license";
import {
  COVERAGE_CSV_DEFINITION_NOTE,
  COVERAGE_CSV_FEDERAL_NOTE,
  buildCoverageCsv,
  coverageCsvFilename,
} from "@/lib/coverage-model";
import { CSV_BOM } from "@/lib/data-quality";

/** Saves rows as a CSV file from the browser. Nothing is fetched: the file is the rows on screen. */
export function downloadCoverageCsv(rows: InstitutionCoverage[], scope: "view" | "all") {
  const day = new Date().toISOString().slice(0, 10);
  const blob = new Blob([CSV_BOM + buildCoverageCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = coverageCsvFilename(scope, day);
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * The two CSV buttons and what the file's columns are. `viewRows` is what the
 * table shows, in its order; `allRows` is every tracked college.
 */
export function CoverageDownloads({ viewRows, allRows }: { viewRows: InstitutionCoverage[]; allRows: InstitutionCoverage[] }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="cd-chip"
          style={{ cursor: "pointer", background: "transparent" }}
          onClick={() => downloadCoverageCsv(viewRows, "view")}
        >
          Download this view (CSV)
        </button>
        <button
          type="button"
          className="cd-chip"
          style={{ cursor: "pointer", background: "transparent" }}
          onClick={() => downloadCoverageCsv(allRows, "all")}
        >
          Download all colleges (CSV)
        </button>
      </div>
      <p className="meta" style={{ marginTop: 8, marginBottom: 0, maxWidth: 720 }}>
        {COVERAGE_CSV_FEDERAL_NOTE} The school ID, status, year and last-checked columns are licensed{" "}
        <a href={DATA_LICENSE_URL} style={{ textDecoration: "underline" }}>
          {DATA_LICENSE_NAME}
        </a>
        . {COVERAGE_CSV_DEFINITION_NOTE}
      </p>
    </div>
  );
}
