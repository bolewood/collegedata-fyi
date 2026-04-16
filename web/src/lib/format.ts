import { STORAGE_BASE_URL } from "./supabase";

export function formatBadgeLabel(format: string | null): string {
  switch (format) {
    case "pdf_fillable":
      return "Fillable PDF";
    case "pdf_flat":
      return "Flat PDF";
    case "pdf_scanned":
      return "Scanned PDF";
    case "xlsx":
      return "Excel";
    case "docx":
      return "Word";
    default:
      return format ?? "Unknown";
  }
}

export function formatExtractionStatus(status: string): string {
  switch (status) {
    case "extracted":
      return "Extracted";
    case "extraction_pending":
      return "Pending";
    case "failed":
      return "Failed";
    case "discovered":
      return "Discovered";
    default:
      return status;
  }
}

export function statusColor(status: string): string {
  switch (status) {
    case "extracted":
      return "bg-green-100 text-green-800";
    case "extraction_pending":
      return "bg-yellow-100 text-yellow-800";
    case "failed":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-700";
  }
}

export function formatColor(): string {
  return "bg-gray-100 text-gray-700";
}

export function storageUrl(path: string | null): string | null {
  if (!path) return null;
  return `${STORAGE_BASE_URL}/${path}`;
}

export function yearRange(
  earliest: string | null,
  latest: string | null
): string {
  if (!earliest && !latest) return "N/A";
  if (earliest === latest) return earliest!;
  return `${earliest} to ${latest}`;
}

export function sectionLetter(questionNumber: string): string {
  return questionNumber.split(".")[0];
}
