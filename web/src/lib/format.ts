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
    case "html":
      return "HTML";
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

export function formatCurrency(
  n: number | null | undefined,
): string {
  if (n == null) return "";
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

export function formatCount(n: number | null | undefined): string {
  return n == null ? "—" : n.toLocaleString("en-US");
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Scorecard stores rates as 0-1 decimals (numeric(5,4) columns). Multiply by
// 100 for display. Caller controls decimals — headline cards typically want
// 0, context stats want 1 to avoid hiding interesting signal (e.g. 4.7% vs 5%).
export function formatPercent(
  n: number | null | undefined,
  decimals = 0,
): string {
  if (n == null) return "";
  return `${(n * 100).toFixed(decimals)}%`;
}

export function yearRange(
  earliest: string | null,
  latest: string | null
): string {
  if (!earliest && !latest) return "N/A";
  if (earliest === latest) return earliest!;
  const startYear = (s: string | null) => (s ? s.split("-")[0] : "");
  return `${startYear(earliest)}\u2013${startYear(latest)}`;
}

export function sectionLetter(questionNumber: string): string {
  return questionNumber.split(".")[0];
}

export function dataQualityLabel(flag: string | null): string | null {
  switch (flag) {
    case "blank_template":
      return "Blank template";
    case "wrong_file":
      return "Wrong file archived";
    case "low_coverage":
      return "Low field coverage";
    default:
      return null;
  }
}

export function dataQualityColor(): string {
  return "bg-amber-100 text-amber-800";
}
