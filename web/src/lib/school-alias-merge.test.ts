import { describe, expect, it } from "vitest";
import {
  canonicalizeSchoolRows,
  liveAliasSlugsFor,
  mergeAliasDocuments,
} from "./school-alias";

const VT = "virginia-polytechnic-institute-and-state-university";

function doc(
  school_id: string,
  canonical_year: string,
  ipeds_id: string | null = null,
  sub_institutional: string | null = null,
) {
  return { school_id, canonical_year, ipeds_id, sub_institutional };
}

describe("liveAliasSlugsFor", () => {
  it("returns live crosswalk aliases that resolve to the canonical slug", () => {
    const rows = [
      { school_id: VT, alias: VT, is_primary: true },
      { school_id: VT, alias: "virginia-tech", is_primary: false },
    ];
    expect(liveAliasSlugsFor(VT, rows)).toEqual(["virginia-tech"]);
  });

  it("never merges retired aliases or aliases owned by another primary", () => {
    const rows = [
      { school_id: "tufts", alias: "tufts-university", is_primary: false },
      { school_id: "alpha", alias: "shared", is_primary: false },
      { school_id: "beta", alias: "shared", is_primary: true },
    ];
    expect(
      liveAliasSlugsFor("tufts", rows, [{ alias: "tufts-university", school_id: "tufts" }]),
    ).toEqual([]);
    expect(liveAliasSlugsFor("alpha", rows)).toEqual([]);
  });
});

describe("mergeAliasDocuments", () => {
  it("fills only years the canonical slug lacks, newest first", () => {
    const merged = mergeAliasDocuments(VT, [
      doc(VT, "2024-25", "233921"),
      doc(VT, "2023-24", "233921"),
      doc("virginia-tech", "2025-26"),
      doc("virginia-tech", "2024-25"),
      doc("virginia-tech", "2012-13"),
    ]);
    expect(merged.map((row) => `${row.school_id}:${row.canonical_year}`)).toEqual([
      "virginia-tech:2025-26",
      `${VT}:2024-25`,
      `${VT}:2023-24`,
      "virginia-tech:2012-13",
    ]);
  });

  it("skips alias rows stamped with a different IPEDS id", () => {
    const merged = mergeAliasDocuments("rutgers", [
      doc("rutgers", "2023-24", "186380"),
      doc("rutgers-camden", "2019-20", "186399"),
    ]);
    expect(merged).toHaveLength(1);
  });

  it("keeps sub-institutional variants as separate slots", () => {
    const merged = mergeAliasDocuments("a", [
      doc("a", "2024-25", null, null),
      doc("b", "2024-25", null, "Law School"),
    ]);
    expect(merged.map((row) => row.sub_institutional)).toEqual([null, "Law School"]);
  });
});

describe("canonicalizeSchoolRows", () => {
  it("re-keys alias rows, dedupes shared years, and drops retired slugs", () => {
    const resolve = (id: string) =>
      id === "tufts-university" ? null : id === "virginia-tech" ? VT : id;
    const rows = canonicalizeSchoolRows(
      [
        doc(VT, "2024-25", "233921"),
        doc("virginia-tech", "2024-25"),
        doc("virginia-tech", "2025-26"),
        doc("tufts-university", "2019-20"),
      ],
      resolve,
    );
    expect(rows.map((row) => `${row.school_id}:${row.canonical_year}`)).toEqual([
      `${VT}:2025-26`,
      `${VT}:2024-25`,
    ]);
  });
});
