// directory-enqueue selection logic — pure functions, no I/O.
//
// PRD 015 M2. Picks the next batch of in-scope directory institutions
// that should be probed by the resolver. The four exclusion sets and
// the cooldown set are loaded by the edge function via PostgREST and
// passed in here so this module stays testable without a DB.

import {
  DEFAULT_COOLDOWN_DAYS,
  ProbeOutcome,
} from "../_shared/probe_outcome.ts";

// Subset of institution_directory columns we read at enqueue time.
// Mirrors the SELECT in index.ts so refactors of one update the other.
export interface DirectoryRow {
  ipeds_id: string;
  school_id: string;
  school_name: string;
  state: string | null;
  website_url: string | null;
  undergraduate_enrollment: number | null;
}

// Most-recent terminal archive_queue row per school. Drives cooldown.
export interface LatestTerminal {
  school_id: string;
  processed_at: string; // ISO 8601
  last_outcome: ProbeOutcome;
}

export interface SelectionInputs {
  rows: DirectoryRow[];
  // IPEDS UNITIDs already covered by the schools.yaml universe.
  // Loaded from institution_slug_crosswalk WHERE source = 'schools_yaml'.
  // archive-enqueue is the canonical writer for these — directory-enqueue
  // must skip them so the same school doesn't end up enqueued twice on
  // overlapping cron + manual runs.
  schoolsYamlIpeds: Set<string>;
  // school_ids that already have any cds_documents row. Per PRD: "Enqueue
  // in-scope institutions that have no cds_documents row and no recent
  // archive attempt." A row with participation_status='not_yet_found'
  // counts as "we have already attempted this school" — directory-enqueue
  // should not redundantly seed it.
  schoolsWithCds: Set<string>;
  // school_ids with an in-flight archive_queue row (status='ready' or
  // 'processing'). Without this guard, a re-run before any rows are
  // processed would pile duplicate ready rows under different run_ids.
  inFlightSchools: Set<string>;
  // Most-recent terminal row per school within the cooldown lookback
  // window. The edge function loads only rows newer than 95 days
  // (longest cooldown is 90d) since older rows can never be in cooldown.
  latestTerminals: Map<string, LatestTerminal>;
  // Operator filters.
  minEnrollment: number;
  state: string | null;
  forceRecheck: boolean;
  uniformCooldownDays: number | null;
  limit: number;
  now: Date;
}

export type SkipReason =
  | "no_website_url"
  | "below_min_enrollment"
  | "state_mismatch"
  | "schools_yaml_covered"
  | "already_has_cds"
  | "in_flight"
  | "cooldown";

export interface SelectionResult {
  selected: DirectoryRow[];
  skipped: Map<SkipReason, number>;
  // Number of in-scope rows considered before any filter applied.
  // Same as inputs.rows.length but echoed for the caller's summary.
  considered: number;
}

// Apply filters in a fixed order so skip-reason counts are unambiguous.
// A row is bucketed under the FIRST reason that excludes it. Order
// matches the spirit of "cheapest, most-explicit filter first": URL
// shape, then operator filters, then exclusion sets, then cooldown.
export function selectCandidates(inputs: SelectionInputs): SelectionResult {
  const skipped = new Map<SkipReason, number>();
  const bumpSkip = (reason: SkipReason) => {
    skipped.set(reason, (skipped.get(reason) ?? 0) + 1);
  };

  // Sort by enrollment DESC NULLS LAST, then school_name ASC for
  // deterministic tie-break. Operator runs target the highest-interest
  // schools first; rows without enrollment data sort last so they don't
  // crowd out larger known schools when limit is small.
  const sorted = [...inputs.rows].sort((a, b) => {
    const ae = a.undergraduate_enrollment;
    const be = b.undergraduate_enrollment;
    if (ae == null && be == null) return a.school_name.localeCompare(b.school_name);
    if (ae == null) return 1;
    if (be == null) return -1;
    if (ae !== be) return be - ae;
    return a.school_name.localeCompare(b.school_name);
  });

  const selected: DirectoryRow[] = [];
  const nowMs = inputs.now.getTime();

  for (const row of sorted) {
    if (selected.length >= inputs.limit) break;

    const url = (row.website_url ?? "").trim();
    if (!url) {
      bumpSkip("no_website_url");
      continue;
    }
    if (
      inputs.minEnrollment > 0 &&
      (row.undergraduate_enrollment ?? 0) < inputs.minEnrollment
    ) {
      bumpSkip("below_min_enrollment");
      continue;
    }
    if (inputs.state && row.state !== inputs.state) {
      bumpSkip("state_mismatch");
      continue;
    }
    if (inputs.schoolsYamlIpeds.has(row.ipeds_id)) {
      bumpSkip("schools_yaml_covered");
      continue;
    }
    if (inputs.schoolsWithCds.has(row.school_id)) {
      bumpSkip("already_has_cds");
      continue;
    }
    if (inputs.inFlightSchools.has(row.school_id)) {
      bumpSkip("in_flight");
      continue;
    }

    if (!inputs.forceRecheck) {
      const latest = inputs.latestTerminals.get(row.school_id);
      if (latest) {
        const cooldownDays = inputs.uniformCooldownDays ??
          DEFAULT_COOLDOWN_DAYS[latest.last_outcome] ?? 0;
        if (cooldownDays > 0) {
          const elapsedMs = nowMs - new Date(latest.processed_at).getTime();
          if (elapsedMs < cooldownDays * 24 * 60 * 60 * 1000) {
            bumpSkip("cooldown");
            continue;
          }
        }
      }
    }

    selected.push(row);
  }

  return {
    selected,
    skipped,
    considered: inputs.rows.length,
  };
}

// Normalize a Scorecard INSTURL to a fetchable URL. Scorecard rows
// frequently carry bare hostnames (`www.harvard.edu`) or schemeless
// values (`harvard.edu/admissions`). The resolver expects a real URL;
// fix the common cases here so callers don't have to. Returns null
// for empty or obviously malformed inputs (the caller already filtered
// nulls upstream, so this is defense-in-depth).
export function normalizeSeedUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  // Already has a scheme — accept as-is if it parses.
  if (/^https?:\/\//i.test(trimmed)) {
    try {
      new URL(trimmed);
      return trimmed;
    } catch {
      return null;
    }
  }
  // Bare hostname or path — assume https.
  const candidate = `https://${trimmed.replace(/^\/+/, "")}`;
  try {
    new URL(candidate);
    return candidate;
  } catch {
    return null;
  }
}
