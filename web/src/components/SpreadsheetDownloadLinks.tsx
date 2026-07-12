"use client";

import { trackEvent } from "@/lib/analytics";

// Download links for the per-school CDS spreadsheet routes (PRD 025).
// Rendered next to the source-document link on the school-year page when
// structured field values exist. Plain anchors on purpose: the global
// `.cd-theme a` rule supplies the canonical link treatment (ink text,
// rule-strong underline, forest-ink hover).
export function SpreadsheetDownloadLinks({
  schoolId,
  year,
}: {
  schoolId: string;
  year: string;
}) {
  const base = `/schools/${schoolId}/${year}`;

  function track(fileType: "xlsx" | "csv") {
    trackEvent("spreadsheet_downloaded", {
      school_id: schoolId,
      cds_year: year,
      file_type: fileType,
    });
  }

  return (
    <span className="inline-flex items-baseline gap-3 text-sm">
      <a href={`${base}/cds.xlsx`} onClick={() => track("xlsx")}>
        Download spreadsheet
      </a>
      <a href={`${base}/cds.csv`} onClick={() => track("csv")}>
        CSV
      </a>
    </span>
  );
}
