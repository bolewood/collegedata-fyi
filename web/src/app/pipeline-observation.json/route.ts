import { NextResponse } from "next/server";
import { fetchPipelineObservation, toPublicJson } from "@/lib/pipeline-observation";

// Same contract as /pipeline-observation: never serve a stale ISR copy.
export const dynamic = "force-dynamic";

export async function GET() {
  const snapshot = await fetchPipelineObservation();
  return NextResponse.json(toPublicJson(snapshot), {
    headers: {
      "Cache-Control": "private, no-store, no-cache, max-age=0, must-revalidate",
    },
  });
}
