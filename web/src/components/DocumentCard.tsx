import Link from "next/link";
import {
  formatBadgeLabel,
  formatExtractionStatus,
  storageUrl,
  dataQualityLabel,
} from "@/lib/format";
import type { ManifestRow } from "@/lib/types";

// One row of the documents ledger. Year sits in display serif; the format
// and status are mono chips; download/view actions are right-aligned. Last
// row drops the dashed separator so the ledger ends on a hairline rule.
export function DocumentCard({
  doc,
  isLast = false,
}: {
  doc: ManifestRow;
  isLast?: boolean;
}) {
  const pdfUrl = storageUrl(doc.source_storage_path);
  const isExtracted = doc.extraction_status === "extracted";
  const canLink =
    isExtracted && doc.canonical_year && doc.canonical_year !== "unknown";
  const dqLabel = dataQualityLabel(doc.data_quality_flag ?? null);
  const statusLabel = formatExtractionStatus(
    doc.extraction_status ?? "discovered",
  );
  const formatLabel = doc.source_format
    ? formatBadgeLabel(doc.source_format)
    : null;

  const rowStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "96px 1fr auto",
    gap: 20,
    alignItems: "center",
    padding: "16px 0",
    borderBottom: isLast
      ? "1px solid var(--rule)"
      : "1px dashed var(--rule)",
  };

  return (
    <div style={rowStyle}>
      <span
        className="serif nums"
        style={{ fontSize: 24, letterSpacing: "-0.01em" }}
      >
        {doc.canonical_year ?? doc.cds_year}
      </span>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        {formatLabel && <span className="cd-chip">{formatLabel}</span>}
        <span
          className={
            isExtracted ? "cd-chip cd-chip--forest" : "cd-chip"
          }
        >
          {statusLabel}
        </span>
        {dqLabel && (
          <span
            className="cd-chip"
            style={{ borderColor: "var(--ochre)", color: "var(--ochre)" }}
          >
            {dqLabel}
          </span>
        )}
        {doc.sub_institutional && (
          <span
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.05em",
            }}
          >
            {doc.sub_institutional}
          </span>
        )}
      </div>

      <div
        style={{
          display: "flex",
          gap: 18,
          alignItems: "center",
          fontSize: 13,
        }}
      >
        {canLink && (
          <Link href={`/schools/${doc.school_id}/${doc.canonical_year}`}>
            View fields →
          </Link>
        )}
        {pdfUrl && (
          <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
            Download PDF
          </a>
        )}
      </div>
    </div>
  );
}
