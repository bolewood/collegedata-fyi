// PRD 040: one vocabulary for source formats. /data-quality, /coverage and
// /pipeline-observation all read labels from this map, so the site never says
// "XLSX" in one place and "spreadsheet" in another.

const FORMAT_LABELS: Record<string, string> = {
  pdf_flat: "standard PDF",
  pdf_fillable: "fillable PDF",
  pdf_scanned: "scanned PDF",
  xlsx: "spreadsheet",
  html: "web page",
  docx: "Word",
};

export const OTHER_FORMAT_LABEL = "other or unknown format";

/** Public label for a `source_format` value. `other`, `unknown`, null and anything new share one label. */
export function formatLabel(format: string | null | undefined): string {
  if (format && Object.prototype.hasOwnProperty.call(FORMAT_LABELS, format)) {
    return FORMAT_LABELS[format];
  }
  return OTHER_FORMAT_LABEL;
}
