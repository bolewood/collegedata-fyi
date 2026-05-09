import { snapshotFile } from "@/lib/snapshot-data";

export const revalidate = 3600;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ snapshot_date: string; file: string }> },
) {
  const { file } = await params;
  const payload = await snapshotFile(file);
  return new Response(payload.body, {
    status: payload.status ?? 200,
    headers: {
      "Content-Type": payload.contentType,
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}

