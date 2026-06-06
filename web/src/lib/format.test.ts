import { describe, expect, it } from "vitest";
import { sourceDownloadLabel } from "./format";

describe("sourceDownloadLabel", () => {
  it("uses the storage extension when the stored source format is stale", () => {
    expect(
      sourceDownloadLabel(
        "pdf_flat",
        "mississippi-state-university/2022-23/hash.html",
      ),
    ).toBe("Download HTML");
  });

  it("labels PDF source variants as PDFs", () => {
    expect(sourceDownloadLabel("pdf_scanned", "school/2025-26/hash.pdf")).toBe(
      "Download PDF",
    );
  });
});
