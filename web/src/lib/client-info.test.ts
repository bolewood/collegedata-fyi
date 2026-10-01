import { describe, expect, it } from "vitest";
import {
  clientInfoHeaders,
  externalLinkRel,
  FRIENDLY_API_CLIENT_INFO,
  isArchiveFileUrl,
  SITE_CLIENT_INFO,
} from "./client-info";

describe("clientInfoHeaders", () => {
  it("uses supabase-js's exact header casing so the default is replaced, not merged", () => {
    expect(Object.keys(clientInfoHeaders())).toEqual(["X-Client-Info"]);
    expect(clientInfoHeaders()["X-Client-Info"]).toBe(SITE_CLIENT_INFO);
  });

  it("tags site and friendly-API traffic with distinct tokens", () => {
    expect(SITE_CLIENT_INFO.startsWith("collegedata-web/")).toBe(true);
    expect(FRIENDLY_API_CLIENT_INFO.startsWith("collegedata-friendly-api/")).toBe(true);
    expect(clientInfoHeaders(FRIENDLY_API_CLIENT_INFO)["X-Client-Info"]).toBe(FRIENDLY_API_CLIENT_INFO);
  });
});

describe("isArchiveFileUrl", () => {
  it("matches archived files on the custom domain and the raw Supabase host", () => {
    expect(
      isArchiveFileUrl("https://api.collegedata.fyi/storage/v1/object/public/sources/yale/2024-25/cds.pdf"),
    ).toBe(true);
    expect(
      isArchiveFileUrl(
        "https://isduwmygvmdozhpvzaix.supabase.co/storage/v1/object/public/sources/yale/2024-25/cds.pdf",
      ),
    ).toBe(true);
  });

  it("rejects other hosts, other paths, and junk", () => {
    expect(isArchiveFileUrl("https://oir.yale.edu/cds.pdf")).toBe(false);
    expect(isArchiveFileUrl("https://api.collegedata.fyi/rest/v1/cds_manifest")).toBe(false);
    expect(isArchiveFileUrl("https://evil.example/storage/v1/object/public/sources/x.pdf")).toBe(false);
    expect(isArchiveFileUrl("/schools/yale")).toBe(false);
    expect(isArchiveFileUrl(null)).toBe(false);
    expect(isArchiveFileUrl("")).toBe(false);
  });
});

describe("externalLinkRel", () => {
  it("keeps the Referer only for archived files", () => {
    expect(
      externalLinkRel("https://api.collegedata.fyi/storage/v1/object/public/sources/yale/2024-25/cds.pdf"),
    ).toBe("noopener");
    expect(externalLinkRel("https://oir.yale.edu/cds.pdf")).toBe("noopener noreferrer");
    expect(externalLinkRel(undefined)).toBe("noopener noreferrer");
  });
});
