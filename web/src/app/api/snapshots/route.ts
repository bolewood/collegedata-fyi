import { NextResponse } from "next/server";
import { dataLicenseFields } from "@/lib/data-license";
import { SNAPSHOT_NOTE, snapshotBase, snapshotDate } from "@/lib/snapshot-data";
import { SITE_ORIGIN } from "@/lib/site";

export const revalidate = 3600;

export async function GET() {
  const date = snapshotDate();
  const base = snapshotBase(date);
  return NextResponse.json(
    {
      generated_at: new Date().toISOString(),
      schema_version: "v1",
      snapshot_date: date,
      note: SNAPSHOT_NOTE,
      ...dataLicenseFields(),
      current: `${base}/manifest.json`,
      latest: `${SITE_ORIGIN}/snapshots/latest/manifest.json`,
      files: [
        `${base}/schools.jsonl`,
        `${base}/school_facts.jsonl`,
        `${base}/sources.jsonl`,
        `${base}/field_dictionary.json`,
      ],
    },
    {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    },
  );
}
