"use client";

import Link from "next/link";
import {
  formatBadgeLabel,
  formatExtractionStatus,
  storageUrl,
  dataQualityLabel,
  sourceDownloadLabel,
} from "@/lib/format";
import { trackSourceOpened, trackEvent } from "@/lib/analytics";
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
  const sourceDownloadUrl = storageUrl(doc.source_storage_path);
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

  return (
    <div
      className="document-card-row"
      style={{
        borderBottom: isLast
          ? "1px solid var(--rule)"
          : "1px dashed var(--rule)",
      }}
    >
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

      <div className="document-card-row__actions">
        {canLink && (
          <Link
            href={`/schools/${doc.school_id}/${doc.canonical_year}`}
            onClick={() =>
              trackEvent("school_document_fields_opened", {
                school_id: doc.school_id,
                cds_year: doc.canonical_year,
                source_format: doc.source_format,
              })
            }
          >
            View fields →
          </Link>
        )}
        {sourceDownloadUrl ? (
          <a
            href={sourceDownloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() =>
              trackSourceOpened({
                surface: "school_documents",
                schoolId: doc.school_id,
                cdsYear: doc.canonical_year ?? doc.cds_year,
                sourceFormat: doc.source_format,
                action: "download",
              })
            }
          >
            {sourceDownloadLabel(doc.source_format, doc.source_storage_path)}
          </a>
        ) : sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() =>
              trackSourceOpened({
                surface: "school_documents",
                schoolId: doc.school_id,
                cdsYear: doc.canonical_year ?? doc.cds_year,
                sourceFormat: doc.source_format,
                action: "view_source",
              })
            }
          >
            View source →
          </a>
        ) : null}
      </div>
    </div>
  );
}
