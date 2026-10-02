import { describe, expect, it } from "vitest";
import {
  buildApiUsageEvent,
  clientFamily,
  routeKindFromPath,
  userAgentFamily,
} from "./api-usage";

describe("api usage attribution", () => {
  it("classifies first-party MCP calls from headers and query markers", () => {
    const request = new Request(
      "https://www.collegedata.fyi/api/schools/mit/facts?cd_client=mcp&cd_tool=get_school_facts&cd_client_version=0.1.0",
      {
        headers: {
          "user-agent": "node",
          "x-vercel-ip-country": "US",
        },
      },
    );

    expect(buildApiUsageEvent(request)).toMatchObject({
      route_kind: "school_facts",
      client_family: "mcp",
      client_name: "mcp",
      client_tool: "get_school_facts",
      client_version: "0.1.0",
      user_agent_family: "node_fetch",
      country: "US",
      school_id: "mit",
    });
  });

  it("keeps search queries out of logged events", () => {
    const request = new Request("https://www.collegedata.fyi/api/schools/search?q=stanford");
    expect(buildApiUsageEvent(request)).toMatchObject({
      route_path: "/api/schools/search",
      route_kind: "schools_search",
      school_id: null,
    });
    expect(JSON.stringify(buildApiUsageEvent(request))).not.toContain("stanford");
  });

  it("records compare school counts without storing the full query string", () => {
    const request = new Request("https://www.collegedata.fyi/api/compare?schools=mit,yale,stanford");
    expect(buildApiUsageEvent(request)).toMatchObject({
      route_kind: "compare",
      school_count: 3,
      school_id: null,
    });
  });

  it("classifies common clients conservatively", () => {
    expect(clientFamily("my-app", "node")).toBe("integration");
    expect(clientFamily(null, "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15")).toBe("browser");
    expect(clientFamily(null, "Mozilla/5.0")).toBe("script");
    expect(clientFamily(null, "Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/124.0")).toBe("script");
    expect(clientFamily(null, "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")).toBe(
      "declared_bot",
    );
    expect(clientFamily(null, "Mozilla/5.0 (Linux; Android 10) GoogleOther")).toBe("declared_bot");
    expect(clientFamily(null, "curl/8.0")).toBe("script");
    expect(clientFamily(null, "ClaudeBot")).toBe("ai_crawler");
    expect(clientFamily(null, "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)")).toBe("ai_crawler");
    expect(clientFamily(null, "Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot)")).toBe("ai_user");
    expect(clientFamily(null, "Claude-User (claude-code/2.1; +https://support.anthropic.com/)")).toBe("ai_user");
    expect(userAgentFamily("python-requests/2.32")).toBe("python");
  });

  it("normalizes public API route kinds", () => {
    expect(routeKindFromPath("/api/schools/search")).toBe("schools_search");
    expect(routeKindFromPath("/api/mcp")).toBe("mcp");
    expect(routeKindFromPath("/api/schools/mit/sources")).toBe("school_sources");
    expect(routeKindFromPath("/api/facts/mit")).toBe("legacy_school_facts");
  });
});
