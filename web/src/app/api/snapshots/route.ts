import { NextResponse } from "next/server";
import { SNAPSHOT_NOTE, snapshotBase, snapshotDate } from "@/lib/snapshot-data";

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
      current: `${base}/manifest.json`,
      latest: "https://www.collegedata.fyi/snapshots/latest/manifest.json",
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
