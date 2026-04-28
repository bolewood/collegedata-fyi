import Link from "next/link";
import {
  formatBadgeLabel,
  formatExtractionStatus,
  storageUrl,
  dataQualityLabel,
} from "@/lib/format";
import type { ManifestRow } from "@/lib/types";

// Map an extraction status to a chip variant. Only the success state gets
// the forest pill; failures use brick (the alarm color in tokens.css);
// pending/discovered stay neutral so they read as in-flight, not done.
function statusChipClass(status: string): string {
  switch (status) {
    case "extracted":
      return "cd-chip cd-chip--forest";
    case "failed":
      return "cd-chip cd-chip--brick";
    case "extraction_pending":
      return "cd-chip cd-chip--ochre";
    default:
      return "cd-chip";
  }
}

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
  const sourceUrl = doc.source_url;
  const status = doc.extraction_status ?? "discovered";
  const isExtracted = status === "extracted";
  const canLink =
    isExtracted && doc.canonical_year && doc.canonical_year !== "unknown";
  const dqLabel = dataQualityLabel(doc.data_quality_flag ?? null);
  const statusLabel = formatExtractionStatus(status);
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
        <span className={statusChipClass(status)}>{statusLabel}</span>
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
        {pdfUrl ? (
          <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
            Download PDF
          </a>
        ) : sourceUrl ? (
          <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
            View source →
          </a>
        ) : null}
      </div>
    </div>
  );
}
