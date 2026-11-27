import { describe, expect, it } from "vitest";
import { APEX_TO_WWW_REDIRECTS, CANONICAL_ORIGIN } from "./apex-redirect";
import { MCP_SERVER_NAME as MCP_NAME_FROM_TOOLS } from "./mcp/tools";
import { SITE_URL } from "./sitemap-static";
import {
  API_HOST,
  API_ORIGIN,
  PROJECT_ORIGIN,
  APEX_HOST,
  MCP_SERVER_NAME,
  SITE_HOST,
  SITE_NAME,
  FORMER_NAME,
  SITE_ORIGIN,
} from "./site";

// These pin the rename values and that apex-redirect,
// sitemap-static and mcp/tools read them from site.ts. Other call sites are
// covered by the route comparison in the PR, not by this test.
describe("site constants", () => {
  it("pins the post-rename values", () => {
    expect(SITE_NAME).toBe("Quadfile");
    expect(FORMER_NAME).toBe("collegedata.fyi");
    expect(SITE_ORIGIN).toBe("https://www.quadfile.org");
    expect(SITE_HOST).toBe("www.quadfile.org");
    expect(APEX_HOST).toBe("quadfile.org");
    expect(API_ORIGIN).toBe("https://api.quadfile.org");
    expect(API_HOST).toBe("api.quadfile.org");
    expect(PROJECT_ORIGIN).toBe("https://isduwmygvmdozhpvzaix.supabase.co");
    expect(MCP_SERVER_NAME).toBe("quadfile");
  });

  it("derives hosts from origins", () => {
    expect(new URL(SITE_ORIGIN).host).toBe(SITE_HOST);
    expect(new URL(API_ORIGIN).host).toBe(API_HOST);
    expect(SITE_HOST).toBe(`www.${APEX_HOST}`);
  });

  it("is what the apex redirect, sitemap and MCP server read", () => {
    expect(CANONICAL_ORIGIN).toBe(SITE_ORIGIN);
    expect(SITE_URL).toBe(SITE_ORIGIN);
    expect(MCP_NAME_FROM_TOOLS).toBe(MCP_SERVER_NAME);
    for (const redirect of APEX_TO_WWW_REDIRECTS) {
      expect(redirect.has[0].value).toBe(APEX_HOST);
      expect(redirect.destination.startsWith(SITE_ORIGIN)).toBe(true);
    }
  });
});
