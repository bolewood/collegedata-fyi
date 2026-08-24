import { describe, expect, it } from "vitest";
import {
  archiveLead,
  leadContainsBannedCopy,
  leadPlainText,
  yearArchiveLead,
} from "./archive-lead";

const vtDocs = [
  { canonical_year: "2011-12", source_format: "pdf_flat", extraction_status: "extracted" },
  { canonical_year: "2024-25", source_format: "xlsx", extraction_status: "extracted" },
  { canonical_year: "2025-26", source_format: "xlsx", extraction_status: "extracted" },
];

const hmcDocs = Array.from({ length: 16 }, (_, i) => {
  const start = 2010 + i;
  return {
    canonical_year: `${start}-${String((start + 1) % 100).padStart(2, "0")}`,
    source_format: i === 15 ? "pdf_fillable" : "pdf_flat",
    extraction_status: "extracted",
  };
});

describe("archiveLead", () => {
  it("snapshots Virginia Tech gated-official copy", () => {
    const lead = archiveLead({
      schoolId: "virginia-tech",
      schoolName: "Virginia Tech",
      ipedsId: "233921",
      documents: vtDocs,
    });
    expect(leadPlainText(lead)).toMatchInlineSnapshot(
      `"Virginia Tech Common Data Set archive, 2011–2025 (3 documents). This page archives 3 documents from 2011–2025. Latest extracted year is 2025-26. Downloads include PDF, XLSX, and CSV. The school's own CDS page currently asks the public to request the file. This page is the archived source plus extract. What is a Common Data Set? Subscribe to school-published files via RSS."`,
    );
    expect(leadContainsBannedCopy(leadPlainText(lead))).toBe(false);
  });

  it("snapshots Harvey Mudd excellent-official copy", () => {
    const lead = archiveLead({
      schoolId: "harvey-mudd",
      schoolName: "Harvey Mudd College",
      ipedsId: "115409",
      documents: hmcDocs,
    });
    expect(leadPlainText(lead)).toMatchInlineSnapshot(
      `"Harvey Mudd College Common Data Set archive, 2010–2025 (16 documents). This page archives 16 documents from 2010–2025. Latest extracted year is 2025-26. Downloads include PDF, XLSX, and CSV. The school's own CDS page is the publisher; this page is the archive and extract. What is a Common Data Set? Subscribe to school-published files via RSS."`,
    );
    expect(leadContainsBannedCopy(leadPlainText(lead))).toBe(false);
  });

  it("snapshots a thin school without an official landing page", () => {
    const lead = archiveLead({
      schoolId: "thin-college",
      schoolName: "Thin College",
      documents: [
        {
          canonical_year: "2023-24",
          source_format: "pdf_scanned",
          extraction_status: "extracted",
        },
      ],
    });
    expect(leadPlainText(lead)).toMatchInlineSnapshot(
      `"Thin College Common Data Set archive, 2023-24 (1 document). This page archives 1 document from 2023-24. Latest extracted year is 2023-24. Downloads include PDF, XLSX, and CSV. What is a Common Data Set? Subscribe to school-published files via RSS."`,
    );
  });

  it("does not claim an archive for directory-only schools", () => {
    expect(
      archiveLead({
        schoolId: "directory-only",
        schoolName: "Directory College",
        directoryOnly: true,
        documents: [],
      }),
    ).toBeNull();
  });

  it("year-page lead names the school, year, and source file", () => {
    const lead = yearArchiveLead({
      schoolId: "virginia-tech",
      schoolName: "Virginia Tech",
      year: "2025-26",
      ipedsId: "233921",
      hasExtract: true,
      sourceDownloadHref: "https://example.invalid/vt.xlsx",
    });
    expect(lead.heading).toBe("Virginia Tech Common Data Set 2025-26");
    expect(leadPlainText(lead)).toContain("archived source file");
    expect(leadPlainText(lead)).toContain("extracted field tables");
    expect(leadPlainText(lead)).toContain("school's own CDS page");
    expect(leadPlainText(lead)).toContain("RSS");
    expect(leadContainsBannedCopy(leadPlainText(lead))).toBe(false);
  });

  it("ignores sentinel CDS years when naming the archive range", () => {
    const lead = archiveLead({
      schoolId: "umich",
      schoolName: "University of Michigan",
      documents: [
        {
          canonical_year: "unknown",
          source_format: "pdf_flat",
          extraction_status: "extracted",
        },
        {
          canonical_year: "2025-26",
          source_format: "xlsx",
          extraction_status: "extracted",
        },
        {
          canonical_year: "2000-01",
          source_format: "pdf_flat",
          extraction_status: "extracted",
        },
      ],
    });
    const text = leadPlainText(lead);
    expect(text).toContain("2000–2025");
    expect(text).toContain("Latest extracted year is 2025-26");
    expect(text).not.toContain("unknown");
  });

  it("states when a year-page date is only this archive's discovery", () => {
    const lead = yearArchiveLead({
      schoolId: "thin-college",
      schoolName: "Thin College",
      year: "2023-24",
      discovered_at: "2026-08-10T00:00:00Z",
    });
    expect(leadPlainText(lead)).toContain("discovered the file");
    expect(leadPlainText(lead)).toContain("did not send Last-Modified");
  });
});
