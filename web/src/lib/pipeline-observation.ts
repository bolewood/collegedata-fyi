import { cache } from "react";
import {
  BOARD_STATION_IDS,
  LAMP_HEX,
  MANUAL_STATION_IDS,
  stationLamp,
  stripLamp,
  type HeartbeatStatus,
  type Lamp,
  type StationClass,
  type StripLamp,
} from "./pipeline-lamps";

export type PipelineFactRow = {
  station_id: string;
  display_name: string;
  cadence_label: string;
  class: StationClass;
  on_board: boolean;
  sort_order: number;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_status: HeartbeatStatus | null;
  last_trigger: string | null;
  last_summary: Record<string, unknown> | null;
  last_scheduled_finished_at: string | null;
  last_scheduled_status: HeartbeatStatus | null;
  last_scheduled_summary: Record<string, unknown> | null;
  last_scheduled_error_code: string | null;
  last_error_code: string | null;
  source_url: string | null;
  queue_unfinished: number | null;
  extraction_pending: number | null;
};

export type PipelineStationView = {
  station_id: string;
  display_name: string;
  cadence_label: string;
  class: StationClass;
  on_board: boolean;
  lamp: Lamp;
  last_scheduled_finished_at: string | null;
  last_scheduled_status: HeartbeatStatus | null;
  last_finished_at: string | null;
  last_started_at: string | null;
  last_trigger: string | null;
  last_status: HeartbeatStatus | null;
  summary: Record<string, unknown>;
  error_code: string;
  source_url: string | null;
  result_line: string;
  ago_label: string;
  help: string;
  queue_unfinished: number | null;
  extraction_pending: number | null;
};

export type PipelineSnapshot = {
  as_of: string;
  load_error: boolean;
  strip: { lamp: StripLamp; text: string };
  stations: PipelineStationView[];
  locked_doors: [];
  manual_sources: Array<{
    station_id: string;
    display_name: string;
    last_finished_at: string | null;
    ago_label: string;
  }>;
  methodology_url: string;
};

const SEED_META: Array<{
  station_id: (typeof BOARD_STATION_IDS)[number] | (typeof MANUAL_STATION_IDS)[number];
  display_name: string;
  cadence_label: string;
  class: StationClass;
  on_board: boolean;
  help: string;
}> = [
  {
    station_id: "finder_brave",
    display_name: "Finder",
    cadence_label: "monthly · scheduled SLA 40d",
    class: "monthly_sla",
    on_board: true,
    help: "Once a month we ask Brave Search to find Common Data Set pages for schools that still have no listing. If this goes quiet, we stop discovering new files.",
  },
  {
    station_id: "finder_stuck_pdf",
    display_name: "Stuck PDFs",
    cadence_label: "monthly · scheduled SLA 40d",
    class: "monthly_sla",
    on_board: true,
    help: "Many seeds point at a single old PDF. This step re-checks those schools so we can find the office's actual CDS listing instead of one frozen year.",
  },
  {
    station_id: "finder_landing_hints",
    display_name: "Landing hints",
    cadence_label: "monthly · scheduled SLA 40d",
    class: "monthly_sla",
    on_board: true,
    help: "When a PDF seed is really a landing page — the office's CDS index — we rewrite it so weekly archive can collect every year they publish.",
  },
  {
    station_id: "archive_enqueue",
    display_name: "Enqueue",
    cadence_label: "daily · SLA 36h",
    class: "daily_sla",
    on_board: true,
    help: "Every night we decide which schools are due for a fresh look and put them on the archive queue. Schools we already checked recently are skipped.",
  },
  {
    station_id: "archive_process",
    display_name: "Process",
    cadence_label: "every 30s",
    class: "continuous_sla",
    on_board: true,
    help: "About every 30 seconds we take one school off the queue, download what we can, and archive it. This is the machine's pulse.",
  },
  {
    station_id: "extraction_worker",
    display_name: "Extract",
    cadence_label: "daily · pending drain",
    class: "daily_sla",
    on_board: true,
    help: "After a file is archived, we pull the numbers out of it. The daily job only drains a handful, so a backlog here is late — not necessarily a crash.",
  },
  {
    station_id: "coverage_refresh",
    display_name: "Coverage",
    cadence_label: "hourly · SLA 3h",
    class: "hourly_sla",
    on_board: true,
    help: "Hourly we rebuild the public coverage ledger: which schools have a current CDS, an older one, or none we could find.",
  },
  {
    station_id: "serving_cache_refresh",
    display_name: "Serving caches",
    cadence_label: "hourly · SLA 3h",
    class: "hourly_sla",
    on_board: true,
    help: "Hourly we refresh the homepage and API caches so the public site is not reading live tables on every visit.",
  },
  {
    station_id: "ipeds_release_probe",
    display_name: "IPEDS probe",
    cadence_label: "monthly · scheduled SLA 40d",
    class: "monthly_sla",
    on_board: true,
    help: "Once a month we check whether NCES has posted a new IPEDS Access database. A quiet \"no new release\" is still a healthy tick.",
  },
  {
    station_id: "schema_build",
    display_name: "Schema",
    cadence_label: "yearly · slate until a heartbeat",
    class: "yearly",
    on_board: true,
    help: "Once a year an operator loads the new CDS year schema. Gray until that happens; red only if it has been more than 18 months.",
  },
  {
    station_id: "scorecard_load",
    display_name: "Scorecard",
    cadence_label: "yearly · slate until a heartbeat",
    class: "yearly",
    on_board: true,
    help: "Once a year an operator loads College Scorecard. Gray until that load is recorded; red if it is more than 18 months old.",
  },
  {
    station_id: "directory_enqueue",
    display_name: "Directory enqueue",
    cadence_label: "manual",
    class: "adhoc",
    on_board: false,
    help: "Operator-only: seed the archive queue from the IPEDS directory. Not on the status strip.",
  },
  {
    station_id: "mirror_ingest",
    display_name: "Mirror ingest",
    cadence_label: "manual",
    class: "adhoc",
    on_board: false,
    help: "Operator-only: ingest a secondary-source mirror. Not on the status strip.",
  },
];

const ERROR_COPY: Record<string, string> = {
  search_provider_rejected: "Search provider rejected the request.",
  missing_required_secret: "A required secret is missing.",
  heartbeat_summary_malformed: "Heartbeat summary was missing required keys.",
  worker_timeout: "Worker hit its deadline without a clean finish.",
  job_failed: "The job finished in error.",
  none: "",
};

type UntypedRpc = {
  rpc: (
    fn: string,
  ) => Promise<{ data: PipelineFactRow[] | null; error: { message: string } | null }>;
};

function isStaticBuild(): boolean {
  return (
    process.env.NEXT_PHASE === "phase-production-build" ||
    process.env.npm_lifecycle_event === "build"
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asStatus(value: unknown): HeartbeatStatus | null {
  if (value === "never" || value === "running" || value === "ok" || value === "error") {
    return value;
  }
  return null;
}

export function formatAgo(iso: string | null | undefined, now: Date): string {
  if (!iso) return "no heartbeat";
  const ms = now.getTime() - new Date(iso).getTime();
  if (!Number.isFinite(ms)) return "no heartbeat";
  const sec = Math.max(0, Math.round(ms / 1000));
  if (sec < 60) return `${sec} sec`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min`;
  const hours = Math.round(min / 60);
  if (hours < 48) return hours === 1 ? "1 hour" : `${hours} hours`;
  const days = Math.round(hours / 24);
  return days === 1 ? "1 day" : `${days} days`;
}

function resultLine(row: PipelineFactRow, lamp: Lamp): string {
  const summary = asRecord(row.last_scheduled_summary);
  const errorCode = row.last_scheduled_error_code ?? row.last_error_code ?? "none";
  const errorCopy = ERROR_COPY[errorCode] ?? "";
  if (lamp === "down" && errorCopy) return errorCopy;
  switch (row.station_id) {
    case "finder_brave":
      return `${num(summary.probed)} probed · ${num(summary.found)} found · ${num(summary.budget_remaining)} budget left`;
    case "finder_stuck_pdf":
      return `${num(summary.stuck)} stuck · ${num(summary.reprobed)} reprobed · ${num(summary.still_stuck)} still stuck`;
    case "finder_landing_hints":
      return `${num(summary.proposals)} proposals · ${num(summary.promoted)} promoted`;
    case "archive_enqueue":
      return `${num(summary.queued)} queued · ${num(summary.skipped)} skipped`;
    case "archive_process":
      return `queue ${num(row.queue_unfinished ?? summary.queue_depth)} · ${num(summary.inserted)} inserted · ${num(summary.events_written)} events`;
    case "extraction_worker":
      return `${num(row.extraction_pending ?? summary.pending_remaining)} pending · ${String(summary.stopped_reason ?? "—")}`;
    case "coverage_refresh":
      return `${num(summary.current)} current · ${num(summary.stale)} stale`;
    case "serving_cache_refresh":
      return summary.ok === false ? "refresh failed" : "refresh_public_serving_caches";
    case "ipeds_release_probe":
      return summary.new_release === true ? "new release listed" : "no new release";
    case "schema_build":
      return Array.isArray(summary.years) ? `years ${summary.years.join(", ")}` : "Do not infer vintage from git.";
    case "scorecard_load":
      return summary.vintage ? `vintage ${String(summary.vintage)}` : "Do not infer vintage from git.";
    default:
      return lamp === "down" ? "No scheduled heartbeat." : "";
  }
}

function num(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function seedFacts(): PipelineFactRow[] {
  return SEED_META.map((meta) => ({
    station_id: meta.station_id,
    display_name: meta.display_name,
    cadence_label: meta.cadence_label,
    class: meta.class,
    on_board: meta.on_board,
    sort_order: 0,
    last_started_at: null,
    last_finished_at: null,
    last_status: "never",
    last_trigger: null,
    last_summary: {},
    last_scheduled_finished_at: null,
    last_scheduled_status: "never",
    last_scheduled_summary: {},
    last_scheduled_error_code: "none",
    last_error_code: "none",
    source_url: null,
    queue_unfinished: meta.station_id === "archive_process" ? 0 : null,
    extraction_pending: meta.station_id === "extraction_worker" ? 0 : null,
  }));
}

function stripText(lamp: StripLamp, stations: PipelineStationView[], loadError: boolean): string {
  if (loadError) return "Could not load station clocks.";
  const overdue = stations.filter((station) => station.on_board && station.lamp === "down");
  const late = stations.filter((station) => station.on_board && station.lamp === "late");
  if (lamp === "down") {
    const first = overdue[0];
    const detail = first
      ? `${first.display_name} ${first.ago_label}`
      : "scheduled clock missing";
    return `${overdue.length} station${overdue.length === 1 ? "" : "s"} overdue · ${detail}`;
  }
  if (lamp === "late") {
    const first = late[0];
    return first
      ? `${first.display_name} late · ${first.result_line}`
      : "Extraction is behind.";
  }
  return "Every scheduled station is on the clock.";
}

export function snapshotFromFacts(
  facts: PipelineFactRow[],
  now: Date,
  options: { loadError?: boolean } = {},
): PipelineSnapshot {
  const byId = new Map(facts.map((row) => [row.station_id, row]));
  const merged = SEED_META.map((meta) => byId.get(meta.station_id) ?? seedFacts().find((row) => row.station_id === meta.station_id)!);
  const stations = merged.map((row) => {
    const lamp = stationLamp({
      stationId: row.station_id,
      class: row.class,
      lastStatus: asStatus(row.last_status),
      lastStartedAt: row.last_started_at,
      lastFinishedAt: row.last_finished_at,
      lastScheduledStatus: asStatus(row.last_scheduled_status),
      lastScheduledFinishedAt: row.last_scheduled_finished_at,
      lastScheduledSummary: asRecord(row.last_scheduled_summary),
      queueUnfinished: row.queue_unfinished,
      extractionPending: row.extraction_pending,
      now,
    });
    const clockIso =
      row.class === "yearly" ? row.last_finished_at : row.last_scheduled_finished_at;
    return {
      station_id: row.station_id,
      display_name: row.display_name,
      cadence_label: row.cadence_label,
      class: row.class,
      on_board: row.on_board,
      lamp,
      last_scheduled_finished_at: row.last_scheduled_finished_at,
      last_scheduled_status: asStatus(row.last_scheduled_status),
      last_finished_at: row.last_finished_at,
      last_started_at: row.last_started_at,
      last_trigger: row.last_trigger,
      last_status: asStatus(row.last_status),
      summary: asRecord(row.last_scheduled_summary),
      error_code: row.last_scheduled_error_code ?? "none",
      source_url: row.source_url,
      result_line: resultLine(row, lamp),
      ago_label: formatAgo(clockIso, now),
      help: SEED_META.find((meta) => meta.station_id === row.station_id)?.help ?? "",
      queue_unfinished: row.queue_unfinished,
      extraction_pending: row.extraction_pending,
    };
  });
  const board = stations.filter((station) => station.on_board);
  const lamp = options.loadError ? "down" : stripLamp(board.map((station) => station.lamp));
  return {
    as_of: now.toISOString(),
    load_error: Boolean(options.loadError),
    strip: { lamp, text: stripText(lamp, stations, Boolean(options.loadError)) },
    stations: board,
    locked_doors: [],
    manual_sources: stations
      .filter((station) => !station.on_board)
      .map((station) => ({
        station_id: station.station_id,
        display_name: station.display_name,
        last_finished_at: station.last_finished_at,
        ago_label: formatAgo(station.last_finished_at, now),
      })),
    methodology_url: "https://www.collegedata.fyi/pipeline-observation#methodology",
  };
}

export function seedPipelineSnapshot(
  now = new Date(),
  loadError = false,
): PipelineSnapshot {
  return snapshotFromFacts(seedFacts(), now, { loadError });
}

export function toPublicJson(snapshot: PipelineSnapshot) {
  return {
    as_of: snapshot.as_of,
    strip: snapshot.strip,
    stations: snapshot.stations.map((station) => ({
      station_id: station.station_id,
      lamp: station.lamp,
      label: station.display_name,
      last_scheduled_finished_at: station.last_scheduled_finished_at,
      last_scheduled_status: station.last_scheduled_status,
      last_finished_at: station.last_finished_at,
      last_trigger: station.last_trigger,
      summary: station.summary,
      error_code: station.error_code,
    })),
    locked_doors: snapshot.locked_doors,
    manual_sources: snapshot.manual_sources.map((source) => ({
      station_id: source.station_id,
      last_finished_at: source.last_finished_at,
    })),
    methodology_url: snapshot.methodology_url,
  };
}

export { LAMP_HEX };

export const fetchPipelineObservation = cache(async function fetchPipelineObservation(): Promise<PipelineSnapshot> {
  const now = new Date();
  if (isStaticBuild()) return seedPipelineSnapshot(now, false);
  try {
    const { supabase } = await import("./supabase");
    const { data, error } = await (supabase as unknown as UntypedRpc).rpc(
      "pipeline_station_facts",
    );
    if (error) throw new Error(error.message);
    if (!data?.length) return seedPipelineSnapshot(now, true);
    return snapshotFromFacts(data, now);
  } catch {
    return seedPipelineSnapshot(now, true);
  }
});
