import { describe, expect, it } from "vitest";
import { formatRecipeShare, sourceDownloadLabel } from "./format";

describe("formatRecipeShare", () => {
  it("uses whole percents at 10% and above", () => {
    expect(formatRecipeShare(0.762)).toBe("76%");
    expect(formatRecipeShare(0.836)).toBe("84%");
    expect(formatRecipeShare(0.1)).toBe("10%");
  });

  it("keeps one tenth below 10%", () => {
    expect(formatRecipeShare(0.0365)).toBe("3.6%");
    expect(formatRecipeShare(0.054)).toBe("5.4%");
    expect(formatRecipeShare(0.004)).toBe("0.4%");
  });

  it("lets draw-rate figures keep a tenth even above 10%", () => {
    expect(formatRecipeShare(0.048, 1)).toBe("4.8%");
    expect(formatRecipeShare(0.151, 1)).toBe("15.1%");
  });
});

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
