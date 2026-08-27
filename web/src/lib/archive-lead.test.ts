import { describe, expect, it } from "vitest";
import {
  archiveLead,
  directoryOnlyLead,
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
      `"Virginia Tech Common Data Set The Virginia Tech Common Data Set is the yearly report the college publishes about itself. 3 reports on file, 2011–2025; the latest is 2025-26. Downloads include PDF, XLSX, and CSV. The school's own page currently asks you to request the file. The original is here. What is a Common Data Set? Subscribe to new reports via RSS."`,
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
      `"Harvey Mudd College Common Data Set The Harvey Mudd College Common Data Set is the yearly report the college publishes about itself. 16 reports on file, 2010–2025; the latest is 2025-26. Downloads include PDF, XLSX, and CSV. The school's own page is the publisher. This page is the public copy, with the numbers next to the file. What is a Common Data Set? Subscribe to new reports via RSS."`,
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
      `"Thin College Common Data Set The Thin College Common Data Set is the yearly report the college publishes about itself. 1 report on file, 2023-24; the latest is 2023-24. Downloads include PDF, XLSX, and CSV. What is a Common Data Set? Subscribe to new reports via RSS."`,
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

  it("tells the truth on directory-only pages with and without federal numbers", () => {
    expect(directoryOnlyLead(true)).toBe(
      "We haven’t found a Common Data Set from this school. The federal numbers are below.",
    );
    expect(directoryOnlyLead(false)).toBe(
      "We haven’t found a Common Data Set from this school, and we don’t have federal numbers for it either.",
    );
  });

  it("year-page lead names the school, year, and original file", () => {
    const lead = yearArchiveLead({
      schoolId: "virginia-tech",
      schoolName: "Virginia Tech",
      year: "2025-26",
      ipedsId: "233921",
      hasExtract: true,
      sourceDownloadHref: "https://example.invalid/vt.xlsx",
    });
    expect(lead.heading).toBe("Virginia Tech Common Data Set 2025-26");
    const text = leadPlainText(lead);
    expect(text).toContain("The 2025-26 Common Data Set for Virginia Tech");
    expect(text).toContain("as the school published them");
    expect(text).toContain("Download the original file");
    expect(text).toContain("school's page for these reports");
    expect(text).toContain("RSS");
    expect(text).not.toMatch(/extracted/i);
    expect(leadContainsBannedCopy(text)).toBe(false);
  });

  it("omits the download link when there is no stored file", () => {
    const lead = yearArchiveLead({
      schoolId: "thin-college",
      schoolName: "Thin College",
      year: "2023-24",
    });
    expect(leadPlainText(lead)).not.toContain("Download the original file");
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
    expect(text).toContain("the latest is 2025-26");
    expect(text).not.toContain("unknown");
    expect(text).not.toMatch(/extracted/i);
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
