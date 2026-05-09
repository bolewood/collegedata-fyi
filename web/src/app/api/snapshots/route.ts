import { NextResponse } from "next/server";

export const revalidate = 3600;

const SNAPSHOT_DATE = "2026-05-09";

export async function GET() {
  const base = `https://www.collegedata.fyi/snapshots/v1/${SNAPSHOT_DATE}`;
  return NextResponse.json(
    {
      generated_at: new Date().toISOString(),
      schema_version: "v1",
      current: `${base}/manifest.json`,
      latest: "https://www.collegedata.fyi/snapshots/latest/manifest.json",
      files: [
        `${base}/schools.jsonl`,
        `${base}/school_facts.jsonl`,
        `${base}/sources.jsonl`,
        `${base}/field_dictionary.json`,
        `${base}/collegedata.duckdb`,
      ],
    },
    {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    },
  );
}

