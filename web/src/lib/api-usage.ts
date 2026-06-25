export type ApiUsageEvent = {
  request_source: "friendly_api";
  route_path: string;
  route_kind: string;
  http_method: string;
  client_family: string;
  client_name: string | null;
  client_version: string | null;
  client_tool: string | null;
  user_agent_family: string;
  referer_host: string | null;
  country: string | null;
  school_id: string | null;
  school_count: number | null;
};

const MAX_TOKEN_LENGTH = 80;

function firstValue(headers: Headers, name: string): string | null {
  const value = headers.get(name);
  return value && value.trim() ? value.trim() : null;
}

function cleanToken(value: string | null, maxLength = MAX_TOKEN_LENGTH): string | null {
  if (!value) return null;
  const cleaned = value
    .trim()
    .slice(0, maxLength)
    .replace(/[^a-zA-Z0-9._:/@+-]/g, "-")
    .replace(/-+/g, "-");
  return cleaned || null;
}

function refererHost(value: string | null): string | null {
  if (!value) return null;
  try {
    return cleanToken(new URL(value).hostname.toLowerCase(), 160);
  } catch {
    return null;
  }
}

export function userAgentFamily(userAgent: string | null): string {
  const ua = userAgent?.toLowerCase() ?? "";
  if (!ua) return "unknown";
  if (ua.includes("claude") || ua.includes("anthropic")) return "ai_agent";
  if (ua.includes("chatgpt") || ua.includes("openai")) return "ai_agent";
  if (ua.includes("perplexity") || ua.includes("copilot")) return "ai_agent";
  if (ua.includes("curl/")) return "curl";
  if (ua.includes("python-requests") || ua.includes("aiohttp")) return "python";
  if (ua === "node" || ua.includes("node-fetch") || ua.includes("undici")) return "node_fetch";
  if (ua.includes("mozilla/")) return "browser";
  return "script";
}

export function clientFamily(clientName: string | null, userAgent: string | null): string {
  const marker = clientName?.toLowerCase() ?? "";
  if (marker.includes("mcp")) return "mcp";
  if (marker.includes("cli")) return "cli";
  if (marker) return "integration";

  const uaFamily = userAgentFamily(userAgent);
  if (uaFamily === "browser") return "browser";
  if (uaFamily === "ai_agent") return "ai_agent";
  if (["curl", "python", "node_fetch", "script"].includes(uaFamily)) return "script";
  return "unknown";
}

function schoolIdFromPath(parts: string[]): string | null {
  if (parts[0] === "api" && parts[1] === "schools" && parts[2] && parts[2] !== "search") {
    return cleanToken(decodeURIComponent(parts[2]), 160);
  }
  if (parts[0] === "api" && parts[1] === "facts" && parts[2]) {
    return cleanToken(decodeURIComponent(parts[2]), 160);
  }
  return null;
}

function schoolCount(url: URL, routeKind: string): number | null {
  if (routeKind !== "compare") return null;
  return (
    url.searchParams
      .get("schools")
      ?.split(",")
      .map((school) => school.trim())
      .filter(Boolean).length ?? 0
  );
}

export function routeKindFromPath(pathname: string): string {
  const parts = pathname.split("/").filter(Boolean);
  if (pathname === "/api/schools/search") return "schools_search";
  if (parts[0] === "api" && parts[1] === "schools" && parts[3] === "facts") return "school_facts";
  if (parts[0] === "api" && parts[1] === "schools" && parts[3] === "sources") return "school_sources";
  if (parts[0] === "api" && parts[1] === "facts" && parts[2]) return "legacy_school_facts";
  if (pathname === "/api/compare") return "compare";
  if (pathname === "/api/fields") return "fields";
  if (pathname === "/api/snapshots") return "snapshots";
  return "other_api";
}

export function buildApiUsageEvent(request: Request): ApiUsageEvent {
  const url = new URL(request.url);
  const routeKind = routeKindFromPath(url.pathname);
  const clientName = cleanToken(
    firstValue(request.headers, "x-collegedata-client") ?? url.searchParams.get("cd_client"),
  );
  const userAgent = firstValue(request.headers, "user-agent");
  const parts = url.pathname.split("/").filter(Boolean);

  return {
    request_source: "friendly_api",
    route_path: url.pathname,
    route_kind: routeKind,
    http_method: request.method.toUpperCase(),
    client_family: clientFamily(clientName, userAgent),
    client_name: clientName,
    client_version: cleanToken(
      firstValue(request.headers, "x-collegedata-client-version") ?? url.searchParams.get("cd_client_version"),
    ),
    client_tool: cleanToken(
      firstValue(request.headers, "x-collegedata-mcp-tool") ??
        firstValue(request.headers, "x-collegedata-cli-command") ??
        url.searchParams.get("cd_tool") ??
        url.searchParams.get("cd_command"),
    ),
    user_agent_family: userAgentFamily(userAgent),
    referer_host: refererHost(firstValue(request.headers, "referer")),
    country: cleanToken(firstValue(request.headers, "x-vercel-ip-country"), 8),
    school_id: schoolIdFromPath(parts),
    school_count: schoolCount(url, routeKind),
  };
}

export async function recordApiUsageEvent(event: ApiUsageEvent): Promise<void> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceKey) return;

  try {
    await fetch(`${supabaseUrl.replace(/\/$/, "")}/rest/v1/api_usage_events`, {
      method: "POST",
      headers: {
        apikey: serviceKey,
        authorization: `Bearer ${serviceKey}`,
        "content-type": "application/json",
        prefer: "return=minimal",
      },
      body: JSON.stringify(event),
    });
  } catch {
    // Usage telemetry must never affect the public API response path.
  }
}
