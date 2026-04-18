import Link from "next/link";
import { Badge } from "./Badge";
import {
  formatBadgeLabel,
  formatExtractionStatus,
  statusColor,
  formatColor,
  storageUrl,
} from "@/lib/format";
import type { ManifestRow } from "@/lib/types";

export function DocumentCard({ doc }: { doc: ManifestRow }) {
  const pdfUrl = storageUrl(doc.source_storage_path);
  const isExtracted = doc.extraction_status === "extracted";
  const canLink = isExtracted && doc.canonical_year && doc.canonical_year !== "unknown";

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50">
      <div className="flex items-center gap-3 flex-wrap">
        {canLink ? (
          <Link
            href={`/schools/${doc.school_id}/${doc.canonical_year}`}
            className="text-blue-600 hover:text-blue-800 font-medium"
          >
            {doc.canonical_year}
          </Link>
        ) : (
          <span className="font-medium text-gray-700">
            {doc.canonical_year ?? doc.cds_year}
          </span>
        )}

        {doc.sub_institutional && (
          <span className="text-xs text-gray-500">
            {doc.sub_institutional}
          </span>
        )}

        {doc.source_format && (
          <Badge
            label={formatBadgeLabel(doc.source_format)}
            className={formatColor()}
          />
        )}

        <Badge
          label={formatExtractionStatus(doc.extraction_status ?? "discovered")}
          className={statusColor(doc.extraction_status ?? "discovered")}
        />
      </div>

      {pdfUrl && (
        <a
          href={pdfUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 ml-4 text-sm text-blue-600 hover:text-blue-800"
        >
          Download PDF
        </a>
      )}
    </div>
  );
}
