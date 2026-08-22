import { NextResponse } from "next/server";
import { fetchPipelineObservation, toPublicJson } from "@/lib/pipeline-observation";

export const revalidate = 60;

export async function GET() {
  const snapshot = await fetchPipelineObservation();
  return NextResponse.json(toPublicJson(snapshot), {
    headers: {
      "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300",
    },
  });
}
