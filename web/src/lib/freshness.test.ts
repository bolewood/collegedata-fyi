import { describe, expect, it } from "vitest";
import {
  freshnessSentence,
  latestDocumentFreshness,
  pickFreshnessSignal,
} from "./freshness";
import { buildSchoolRss } from "./school-rss";

describe("pickFreshnessSignal", () => {
  it("prefers embedded modification, then creation, then HTTP Last-Modified, then discovery", () => {
    expect(
      pickFreshnessSignal({
        source_modification_date: "2026-07-01T00:00:00Z",
        source_creation_date: "2026-06-01T00:00:00Z",
        source_http_last_modified: "2026-08-01T00:00:00Z",
        discovered_at: "2026-08-10T00:00:00Z",
      })?.kind,
    ).toBe("embedded_modification");
    expect(
      pickFreshnessSignal({
        source_creation_date: "2026-06-01T00:00:00Z",
        source_http_last_modified: "2026-08-01T00:00:00Z",
        discovered_at: "2026-08-10T00:00:00Z",
      })?.kind,
    ).toBe("embedded_creation");
    expect(
      pickFreshnessSignal({
        source_http_last_modified: "2026-08-01T00:00:00Z",
        discovered_at: "2026-08-10T00:00:00Z",
      })?.kind,
    ).toBe("http_last_modified");
    expect(pickFreshnessSignal({ discovered_at: "2026-08-10T00:00:00Z" })?.kind).toBe(
      "discovered_at",
    );
  });

  it("states when the shown date is only this archive's discovery", () => {
    const sentence = freshnessSentence(
      pickFreshnessSignal({ discovered_at: "2026-08-10T00:00:00Z" }),
    );
    expect(sentence).toContain("discovered the file");
    expect(sentence).toContain("did not send Last-Modified");
  });

  it("uses the latest year document on a school hub", () => {
    const signal = latestDocumentFreshness([
      { canonical_year: "2024-25", discovered_at: "2025-01-01T00:00:00Z" },
      {
        canonical_year: "2025-26",
        source_http_last_modified: "2026-08-01T00:00:00Z",
      },
    ]);
    expect(signal?.kind).toBe("http_last_modified");
  });
});

describe("buildSchoolRss", () => {
  it("emits one item per event and keeps refresh distinct from insert", () => {
    const xml = buildSchoolRss({
      schoolId: "virginia-tech",
      schoolName: "Virginia Tech",
      events: [
        {
          id: 2,
          school_id: "virginia-tech",
          school_name: "Virginia Tech",
          cds_year: "2025-26",
          event_type: "refreshed",
          occurred_at: "2026-08-18T12:00:00Z",
        },
        {
          id: 1,
          school_id: "virginia-tech",
          school_name: "Virginia Tech",
          cds_year: "2025-26",
          event_type: "inserted",
          occurred_at: "2026-08-01T12:00:00Z",
        },
      ],
    });
    expect(xml).toContain("<rss version=\"2.0\">");
    expect(xml).toContain("cds-publish-event-2");
    expect(xml).toContain("cds-publish-event-1");
    expect(xml).toContain("replaced");
    expect(xml).toContain("published");
    expect(xml).toContain("/schools/virginia-tech/2025-26");
    expect(xml).toContain("third-party mirrors");
    expect(xml).not.toContain("mirror_college_transitions");
  });

  it("escapes school names in XML", () => {
    const xml = buildSchoolRss({
      schoolId: "ampersand-u",
      schoolName: "Ampersand & U",
      events: [],
    });
    expect(xml).toContain("Ampersand &amp; U");
  });
});
