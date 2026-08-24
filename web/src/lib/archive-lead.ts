import { isCanonicalCdsYear, yearRange } from "./format";
import {
  getOfficialCdsPage,
  type OfficialCdsPage,
} from "./official-cds-page";
import { freshnessSentence, latestDocumentFreshness, pickFreshnessSignal } from "./freshness";
import { schoolFeedPath } from "./school-rss";

export type ArchiveDocumentFacts = {
  canonical_year: string | null;
  source_format: string | null;
  extraction_status: string | null;
  source_modification_date?: string | null;
  source_creation_date?: string | null;
  source_http_last_modified?: string | null;
  discovered_at?: string | null;
};

export type ArchiveLeadFacts = {
  schoolId: string;
  schoolName: string;
  ipedsId?: string | null;
  documents: ArchiveDocumentFacts[];
  directoryOnly?: boolean;
};

export type YearArchiveLeadFacts = {
  schoolId: string;
  schoolName: string;
  year: string;
  ipedsId?: string | null;
  hasExtract?: boolean;
  sourceDownloadHref?: string | null;
  source_modification_date?: string | null;
  source_creation_date?: string | null;
  source_http_last_modified?: string | null;
  discovered_at?: string | null;
};

export type LeadPart =
  | { type: "text"; text: string }
  | { type: "link"; href: string; text: string; external?: boolean };

export type ArchiveLead = {
  heading: string;
  paragraphs: LeadPart[][];
};

const FORMAT_LABELS: Record<string, string> = {
  pdf: "PDF",
  pdf_fillable: "PDF",
  pdf_flat: "PDF",
  pdf_scanned: "PDF",
  xlsx: "XLSX",
  xls: "XLSX",
  docx: "DOCX",
  doc: "DOCX",
  html: "HTML",
  htm: "HTML",
  csv: "CSV",
};

const BANNED_LEAD_WORDS = [
  "prestigious",
  "elite",
  "top stem",
  "chance me",
  "how to get in",
];

export function officialPageLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return `${host} CDS page`;
  } catch {
    return "school CDS page";
  }
}

function uniqueYears(documents: ArchiveDocumentFacts[]): string[] {
  return Array.from(
    new Set(
      documents
        .map((doc) => doc.canonical_year)
        .filter(isCanonicalCdsYear),
    ),
  ).sort();
}

function extractedYears(documents: ArchiveDocumentFacts[]): string[] {
  return uniqueYears(
    documents.filter((doc) => doc.extraction_status === "extracted"),
  );
}

function formatLabels(documents: ArchiveDocumentFacts[]): string[] {
  const labels = new Set<string>();
  for (const doc of documents) {
    const format = doc.source_format?.toLowerCase() ?? "";
    const label = FORMAT_LABELS[format];
    if (label) labels.add(label);
  }
  if (documents.some((doc) => doc.extraction_status === "extracted")) {
    labels.add("XLSX");
    labels.add("CSV");
  }
  const order = ["PDF", "XLSX", "CSV", "DOCX", "HTML"];
  return order.filter((label) => labels.has(label));
}

function joinList(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function officialSource(
  schoolId: string,
  ipedsId?: string | null,
): OfficialCdsPage | null {
  return getOfficialCdsPage(schoolId, ipedsId);
}

export function archiveLead(facts: ArchiveLeadFacts): ArchiveLead | null {
  if (facts.directoryOnly) return null;
  if (facts.documents.length === 0) return null;

  const years = uniqueYears(facts.documents);
  const extracted = extractedYears(facts.documents);
  const range = years.length > 0 ? yearRange(years[0], years[years.length - 1]) : null;
  const count = facts.documents.length;
  const countLabel = `${count} document${count === 1 ? "" : "s"}`;
  const heading = range
    ? `${facts.schoolName} Common Data Set archive, ${range} (${countLabel}).`
    : `${facts.schoolName} Common Data Set archive (${countLabel}).`;

  const paragraphs: LeadPart[][] = [];

  const first: LeadPart[] = [
    {
      type: "text",
      text: range
        ? `This page archives ${countLabel} from ${range}.`
        : `This page archives ${countLabel}.`,
    },
  ];
  if (extracted.length > 0) {
    first.push({
      type: "text",
      text: ` Latest extracted year is ${extracted[extracted.length - 1]}.`,
    });
  }
  const formats = formatLabels(facts.documents);
  if (formats.length > 0) {
    first.push({
      type: "text",
      text: ` Downloads include ${joinList(formats)}.`,
    });
  }
  paragraphs.push(first);

  const official = officialSource(facts.schoolId, facts.ipedsId);
  if (official) {
    const sourceLink: LeadPart = {
      type: "link",
      href: official.url,
      text: "school's own CDS page",
      external: true,
    };
    if (official.access === "request") {
      paragraphs.push([
        { type: "text", text: "The " },
        sourceLink,
        {
          type: "text",
          text: " currently asks the public to request the file. This page is the archived source plus extract.",
        },
      ]);
    } else {
      paragraphs.push([
        { type: "text", text: "The " },
        sourceLink,
        { type: "text", text: " is the publisher; this page is the archive and extract." },
      ]);
    }
  }

  paragraphs.push([
    { type: "text", text: "What is a " },
    {
      type: "link",
      href: "/about/common-data-set",
      text: "Common Data Set",
    },
    { type: "text", text: "?" },
  ]);

  const freshness = freshnessSentence(latestDocumentFreshness(facts.documents));
  if (freshness) {
    paragraphs.push([{ type: "text", text: freshness }]);
  }
  paragraphs.push([
    { type: "text", text: "Subscribe to school-published files via " },
    {
      type: "link",
      href: schoolFeedPath(facts.schoolId),
      text: "RSS",
    },
    { type: "text", text: "." },
  ]);

  return { heading, paragraphs };
}

export function yearArchiveLead(facts: YearArchiveLeadFacts): ArchiveLead {
  const official = officialSource(facts.schoolId, facts.ipedsId);
  const parts: LeadPart[] = [
    {
      type: "text",
      text: `This is the archived source file for ${facts.schoolName} Common Data Set ${facts.year}`,
    },
  ];
  if (facts.hasExtract) {
    parts.push({ type: "text", text: " plus the extracted field tables" });
  }
  parts.push({ type: "text", text: "." });

  if (facts.sourceDownloadHref) {
    parts.push({ type: "text", text: " " });
    parts.push({
      type: "link",
      href: facts.sourceDownloadHref,
      text: "Download the source",
      external: true,
    });
    parts.push({ type: "text", text: "." });
  }

  if (official) {
    parts.push({ type: "text", text: " See the " });
    parts.push({
      type: "link",
      href: official.url,
      text: "school's own CDS page",
      external: true,
    });
    parts.push({ type: "text", text: "." });
  }

  const freshness = freshnessSentence(pickFreshnessSignal(facts));
  if (freshness) {
    parts.push({ type: "text", text: " " });
    parts.push({ type: "text", text: freshness });
  }

  parts.push({ type: "text", text: " Subscribe via " });
  parts.push({
    type: "link",
    href: schoolFeedPath(facts.schoolId),
    text: "RSS",
  });
  parts.push({ type: "text", text: "." });

  return {
    heading: `${facts.schoolName} Common Data Set ${facts.year}`,
    paragraphs: [parts],
  };
}

export function leadPlainText(lead: ArchiveLead | null): string {
  if (!lead) return "";
  const paragraphs = lead.paragraphs
    .map((parts) => parts.map((part) => part.text).join(""))
    .join(" ");
  return `${lead.heading} ${paragraphs}`.replace(/\s+/g, " ").trim();
}

export function leadContainsBannedCopy(text: string): boolean {
  const lower = text.toLowerCase();
  return BANNED_LEAD_WORDS.some((word) => lower.includes(word));
}
