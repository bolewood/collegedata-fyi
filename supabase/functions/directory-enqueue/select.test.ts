// Tests for directory-enqueue selection logic. Pure functions; no DB
// or network. Covers PRD 015 M2's filter chain and operator behaviors.

import { assertEquals } from "jsr:@std/assert";
import {
  DirectoryRow,
  LatestTerminal,
  normalizeSeedUrl,
  selectCandidates,
  SelectionInputs,
  SkipReason,
} from "./select.ts";

// Reference clock for cooldown math. All test rows are dated relative
// to this so we can reason about "X days ago" without fighting actual
// wall-clock drift in CI.
const NOW = new Date("2026-04-29T12:00:00Z");

function row(overrides: Partial<DirectoryRow> = {}): DirectoryRow {
  return {
    ipeds_id: "100654",
    school_id: "alabama-am",
    school_name: "Alabama A&M",
    state: "AL",
    website_url: "www.aamu.edu",
    undergraduate_enrollment: 5000,
    ...overrides,
  };
}

function inputs(overrides: Partial<SelectionInputs> = {}): SelectionInputs {
  return {
    rows: [],
    schoolsYamlIpeds: new Set(),
    schoolsWithCds: new Set(),
    inFlightSchools: new Set(),
    latestTerminals: new Map(),
    minEnrollment: 0,
    state: null,
    forceRecheck: false,
    uniformCooldownDays: null,
    limit: 100,
    now: NOW,
    ...overrides,
  };
}

function skip(map: Map<SkipReason, number>, reason: SkipReason): number {
  return map.get(reason) ?? 0;
}

// ─── Basic selection ────────────────────────────────────────────────

Deno.test("selectCandidates: in-scope row with website passes through", () => {
  const result = selectCandidates(inputs({
    rows: [row()],
  }));
  assertEquals(result.selected.length, 1);
  assertEquals(result.selected[0].school_id, "alabama-am");
  assertEquals(result.skipped.size, 0);
});

Deno.test("selectCandidates: empty website_url is skipped", () => {
  const result = selectCandidates(inputs({
    rows: [row({ website_url: null }), row({ school_id: "ok", website_url: "  " })],
  }));
  assertEquals(result.selected.length, 0);
  assertEquals(skip(result.skipped, "no_website_url"), 2);
});

// ─── Operator filters ───────────────────────────────────────────────

Deno.test("selectCandidates: min_enrollment filter applied", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "small", undergraduate_enrollment: 500 }),
      row({ school_id: "large", undergraduate_enrollment: 20000 }),
      row({ school_id: "null-enroll", undergraduate_enrollment: null }),
    ],
    minEnrollment: 1000,
  }));
  assertEquals(result.selected.map((r) => r.school_id), ["large"]);
  assertEquals(skip(result.skipped, "below_min_enrollment"), 2);
});

Deno.test("selectCandidates: state filter applied", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "tx-school", state: "TX" }),
      row({ school_id: "ca-school", state: "CA" }),
      row({ school_id: "no-state", state: null }),
    ],
    state: "TX",
  }));
  assertEquals(result.selected.map((r) => r.school_id), ["tx-school"]);
  assertEquals(skip(result.skipped, "state_mismatch"), 2);
});

// ─── Universe exclusions ────────────────────────────────────────────

Deno.test("selectCandidates: schools.yaml-covered IPEDS excluded", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ ipeds_id: "111111", school_id: "in-yaml" }),
      row({ ipeds_id: "222222", school_id: "scorecard-only" }),
    ],
    schoolsYamlIpeds: new Set(["111111"]),
  }));
  assertEquals(result.selected.map((r) => r.school_id), ["scorecard-only"]);
  assertEquals(skip(result.skipped, "schools_yaml_covered"), 1);
});

Deno.test("selectCandidates: schools with cds_documents row excluded", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "has-cds" }),
      row({ ipeds_id: "222222", school_id: "no-cds" }),
    ],
    schoolsWithCds: new Set(["has-cds"]),
  }));
  assertEquals(result.selected.map((r) => r.school_id), ["no-cds"]);
  assertEquals(skip(result.skipped, "already_has_cds"), 1);
});

Deno.test("selectCandidates: in-flight queue rows excluded", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "in-flight" }),
      row({ ipeds_id: "222222", school_id: "ready-to-go" }),
    ],
    inFlightSchools: new Set(["in-flight"]),
  }));
  assertEquals(result.selected.map((r) => r.school_id), ["ready-to-go"]);
  assertEquals(skip(result.skipped, "in_flight"), 1);
});

// ─── Cooldown ───────────────────────────────────────────────────────

function terminal(
  schoolId: string,
  daysAgo: number,
  outcome: LatestTerminal["last_outcome"],
): [string, LatestTerminal] {
  const processed = new Date(NOW.getTime() - daysAgo * 24 * 60 * 60 * 1000);
  return [schoolId, {
    school_id: schoolId,
    processed_at: processed.toISOString(),
    last_outcome: outcome,
  }];
}

Deno.test("selectCandidates: school in unchanged_verified cooldown skipped", () => {
  // 30-day cooldown for unchanged_verified; 10 days elapsed = still in cooldown.
  const result = selectCandidates(inputs({
    rows: [row({ school_id: "in-cooldown" })],
    latestTerminals: new Map([terminal("in-cooldown", 10, "unchanged_verified")]),
  }));
  assertEquals(result.selected.length, 0);
  assertEquals(skip(result.skipped, "cooldown"), 1);
});

Deno.test("selectCandidates: school past cooldown window enqueued", () => {
  // 30-day cooldown for unchanged_verified; 35 days elapsed = past cooldown.
  const result = selectCandidates(inputs({
    rows: [row({ school_id: "out-of-cooldown" })],
    latestTerminals: new Map([terminal("out-of-cooldown", 35, "unchanged_verified")]),
  }));
  assertEquals(result.selected.length, 1);
});

Deno.test("selectCandidates: auth_walled_microsoft uses 90-day cooldown", () => {
  // 89 days elapsed = still in 90-day auth-wall cooldown.
  const result = selectCandidates(inputs({
    rows: [row({ school_id: "walled" })],
    latestTerminals: new Map([terminal("walled", 89, "auth_walled_microsoft")]),
  }));
  assertEquals(result.selected.length, 0);
  assertEquals(skip(result.skipped, "cooldown"), 1);
});

Deno.test("selectCandidates: transient outcome has zero cooldown", () => {
  // transient = retry next run, no cooldown even at 0 days.
  const result = selectCandidates(inputs({
    rows: [row({ school_id: "transient-school" })],
    latestTerminals: new Map([terminal("transient-school", 0, "transient")]),
  }));
  assertEquals(result.selected.length, 1);
});

Deno.test("selectCandidates: force_recheck bypasses cooldown", () => {
  const result = selectCandidates(inputs({
    rows: [row({ school_id: "would-be-cooled" })],
    latestTerminals: new Map([terminal("would-be-cooled", 1, "auth_walled_microsoft")]),
    forceRecheck: true,
  }));
  assertEquals(result.selected.length, 1);
});

Deno.test("selectCandidates: uniform cooldown_days override applies to all outcomes", () => {
  // transient has DEFAULT_COOLDOWN_DAYS=0; with uniform override of 7 days,
  // a 5-day-old transient row is now in cooldown.
  const result = selectCandidates(inputs({
    rows: [row({ school_id: "transient-cooled" })],
    latestTerminals: new Map([terminal("transient-cooled", 5, "transient")]),
    uniformCooldownDays: 7,
  }));
  assertEquals(result.selected.length, 0);
  assertEquals(skip(result.skipped, "cooldown"), 1);
});

// ─── Ordering and limit ─────────────────────────────────────────────

Deno.test("selectCandidates: limit caps the selected count", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "a", undergraduate_enrollment: 1000 }),
      row({ school_id: "b", undergraduate_enrollment: 2000 }),
      row({ school_id: "c", undergraduate_enrollment: 3000 }),
    ],
    limit: 2,
  }));
  assertEquals(result.selected.length, 2);
});

Deno.test("selectCandidates: orders by enrollment DESC NULLS LAST", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "small", undergraduate_enrollment: 500 }),
      row({ school_id: "null", undergraduate_enrollment: null }),
      row({ school_id: "huge", undergraduate_enrollment: 30000 }),
      row({ school_id: "mid", undergraduate_enrollment: 10000 }),
    ],
    limit: 4,
  }));
  assertEquals(
    result.selected.map((r) => r.school_id),
    ["huge", "mid", "small", "null"],
  );
});

Deno.test("selectCandidates: equal enrollments tie-break by school_name", () => {
  const result = selectCandidates(inputs({
    rows: [
      row({ school_id: "z", school_name: "Zeta", undergraduate_enrollment: 5000 }),
      row({ school_id: "a", school_name: "Alpha", undergraduate_enrollment: 5000 }),
    ],
    limit: 2,
  }));
  assertEquals(result.selected.map((r) => r.school_id), ["a", "z"]);
});

Deno.test("selectCandidates: limit=0 is a no-op", () => {
  const result = selectCandidates(inputs({
    rows: [row()],
    limit: 0,
  }));
  assertEquals(result.selected.length, 0);
  // Nothing was filtered — limit is reached on iteration entry.
  assertEquals(result.skipped.size, 0);
});

Deno.test("selectCandidates: filter order — earlier reasons win bucket", () => {
  // A row with both no-website AND below min-enrollment should be
  // bucketed under no_website_url (the earlier filter).
  const result = selectCandidates(inputs({
    rows: [row({ website_url: "", undergraduate_enrollment: 100 })],
    minEnrollment: 1000,
  }));
  assertEquals(skip(result.skipped, "no_website_url"), 1);
  assertEquals(skip(result.skipped, "below_min_enrollment"), 0);
});

// ─── normalizeSeedUrl ───────────────────────────────────────────────

Deno.test("normalizeSeedUrl: existing https URL passes through", () => {
  assertEquals(
    normalizeSeedUrl("https://www.harvard.edu"),
    "https://www.harvard.edu",
  );
});

Deno.test("normalizeSeedUrl: existing http URL passes through", () => {
  assertEquals(
    normalizeSeedUrl("http://example.edu"),
    "http://example.edu",
  );
});

Deno.test("normalizeSeedUrl: bare hostname becomes https", () => {
  assertEquals(
    normalizeSeedUrl("www.aamu.edu"),
    "https://www.aamu.edu",
  );
});

Deno.test("normalizeSeedUrl: hostname with path becomes https", () => {
  assertEquals(
    normalizeSeedUrl("aamu.edu/admissions"),
    "https://aamu.edu/admissions",
  );
});

Deno.test("normalizeSeedUrl: leading slash stripped", () => {
  assertEquals(
    normalizeSeedUrl("///example.edu"),
    "https://example.edu",
  );
});

Deno.test("normalizeSeedUrl: empty / null / whitespace returns null", () => {
  assertEquals(normalizeSeedUrl(null), null);
  assertEquals(normalizeSeedUrl(undefined), null);
  assertEquals(normalizeSeedUrl(""), null);
  assertEquals(normalizeSeedUrl("   "), null);
});

Deno.test("normalizeSeedUrl: invalid https URL returns null", () => {
  // Existing https-prefixed input that does not parse as a URL is
  // rejected rather than silently passed through.
  assertEquals(normalizeSeedUrl("https://"), null);
});
