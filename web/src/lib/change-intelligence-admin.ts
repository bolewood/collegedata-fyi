import "server-only";

import { cache } from "react";
import { createClient } from "@supabase/supabase-js";
import type {
  ChangeEventRow,
  ChangeEventSeverity,
  ChangeEventType,
  ChangeEventVerificationStatus,
} from "./types";

type UntypedSupabase = {
  from: (table: string) => any;
};

export type ChangeDigestSummary = {
  total: number;
  major: number;
  notable: number;
  watch: number;
  candidates: number;
  confirmed: number;
  publicVisible: number;
  latestYear: string | null;
};

function numberOrNull(value: unknown): number | null {
  if (value == null || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function operatorClient(): UntypedSupabase | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceKey) return null;
  return createClient(url, serviceKey) as unknown as UntypedSupabase;
}

function mapChangeEvent(row: any): ChangeEventRow {
  return {
    id: String(row.id),
    schoolId: String(row.school_id),
    schoolName: String(row.school_name ?? row.school_id),
    fieldKey: String(row.field_key),
    fieldLabel: String(row.field_label ?? row.field_key),
    fieldFamily: String(row.field_family ?? "other"),
    fromYear: String(row.from_year),
    toYear: String(row.to_year),
    toYearStart: numberOrNull(row.to_year_start),
    eventType: row.event_type as ChangeEventType,
    severity: row.severity as ChangeEventSeverity,
    fromValue: row.from_value == null ? null : String(row.from_value),
    toValue: row.to_value == null ? null : String(row.to_value),
    absoluteDelta: numberOrNull(row.absolute_delta),
    relativeDelta: numberOrNull(row.relative_delta),
    summary: String(row.summary ?? ""),
    fromArchiveUrl: row.from_archive_url ?? null,
    toArchiveUrl: row.to_archive_url ?? null,
    verificationStatus: row.verification_status as ChangeEventVerificationStatus,
  };
}

export const fetchOperatorChangeDigest = cache(
  async function fetchOperatorChangeDigest(): Promise<{
    events: ChangeEventRow[];
    summary: ChangeDigestSummary;
  }> {
    const client = operatorClient();
    if (!client) {
      return {
        events: [],
        summary: {
          total: 0,
          major: 0,
          notable: 0,
          watch: 0,
          candidates: 0,
          confirmed: 0,
          publicVisible: 0,
          latestYear: null,
        },
      };
    }

    const { data, error } = await client
      .from("cds_field_change_events")
      .select(
        "id, school_id, school_name, field_key, field_label, field_family, from_year, to_year, to_year_start, event_type, severity, from_value, to_value, absolute_delta, relative_delta, summary, from_archive_url, to_archive_url, verification_status, public_visible",
      )
      .order("to_year_start", { ascending: false })
      .order("severity", { ascending: true })
      .limit(300);

    if (error) {
      throw new Error(`Failed to fetch change digest: ${error.message}`);
    }

    const rows = data ?? [];
    const events = rows.map(mapChangeEvent);
    return {
      events,
      summary: {
        total: rows.length,
        major: rows.filter((row: any) => row.severity === "major").length,
        notable: rows.filter((row: any) => row.severity === "notable").length,
        watch: rows.filter((row: any) => row.severity === "watch").length,
        candidates: rows.filter((row: any) => row.verification_status === "candidate").length,
        confirmed: rows.filter((row: any) => row.verification_status === "confirmed").length,
        publicVisible: rows.filter((row: any) => row.public_visible === true).length,
        latestYear: events[0]?.toYear ?? null,
      },
    };
  },
);
