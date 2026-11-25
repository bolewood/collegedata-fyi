import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import { isDataQualityLaunched, snapshotDay } from "@/lib/data-quality";
import { loadLatestSnapshot, loadReportsFor } from "@/lib/data-quality-snapshots";

// The reports behind each count, as a static file the page fetches on the first click (never in the page's own bundle).
// Built from the committed file and checked against the snapshot at build; gated like the page and the CSVs.
export const dynamic = "force-static";
export const dynamicParams = false;

function latestDay(): string | null {
  if (!isDataQualityLaunched()) return null;
  const snapshot = loadLatestSnapshot();
  return loadReportsFor(snapshot) ? snapshotDay(snapshot) : null;
}

export function generateStaticParams() {
  const day = latestDay();
  return day ? [{ date: day }] : [];
}

export async function GET(_request: Request, { params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const snapshot = isDataQualityLaunched() ? loadLatestSnapshot() : null;
  const reports = snapshot ? loadReportsFor(snapshot) : null;
  if (!snapshot || !reports || snapshotDay(snapshot) !== date) {
    return new Response("Not found", { status: 404 });
  }
  return new Response(JSON.stringify(reports), {
    headers: { "Content-Type": "application/json; charset=utf-8", Link: DATA_LICENSE_LINK_HEADER },
  });
}
