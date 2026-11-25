import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import {
  CSV_BOM,
  TABLE_TITLES,
  buildQualityCsv,
  hasFederalChecks,
  hasSections,
  isDataQualityLaunched,
  qualityCsvFilename,
  type QualityTableId,
  type QualityYear,
} from "@/lib/data-quality";
import { loadLatestSnapshot } from "@/lib/data-quality-snapshots";

// Built from the committed snapshot at build, like the page. A new snapshot
// reaches the site with the next deploy.
export const dynamic = "force-static";
export const dynamicParams = false;

/** A table that a snapshot written before it existed doesn't have is a 404, not an empty file. */
function tableServed(table: QualityTableId, year: QualityYear): boolean {
  if (table === "sections") return hasSections(year);
  if (table === "enrollment" || table === "tuition") return hasFederalChecks(year);
  return true;
}

export function generateStaticParams() {
  const snapshot = isDataQualityLaunched() ? loadLatestSnapshot() : null;
  if (!snapshot) return [];
  return (Object.keys(TABLE_TITLES) as QualityTableId[]).flatMap((table) =>
    snapshot.years.filter((y) => tableServed(table, y)).map((y) => ({ table, year: y.cds_year })),
  );
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ table: string; year: string }> },
) {
  const { table, year } = await params;
  const snapshot = isDataQualityLaunched() ? loadLatestSnapshot() : null;
  const found = snapshot?.years.find((y) => y.cds_year === year);
  if (!snapshot || !found || !Object.hasOwn(TABLE_TITLES, table) || !tableServed(table as QualityTableId, found)) {
    return new Response("Not found", { status: 404 });
  }
  return new Response(CSV_BOM + buildQualityCsv(table as QualityTableId, found), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${qualityCsvFilename(table as QualityTableId, year, snapshot.snapshot_of)}"`,
      Link: DATA_LICENSE_LINK_HEADER,
    },
  });
}
