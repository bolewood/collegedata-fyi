import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import {
  buildCoverageCsv,
  coverageCsvFilename,
  filterCoverageRows,
  parseCoverageSort,
  parseCoverageView,
  sortCoverageRows,
} from "@/lib/coverage-model";
import { CSV_BOM, isDataQualityLaunched } from "@/lib/data-quality";
import { fetchCoverageRows } from "@/lib/queries";

/**
 * The /coverage table as a file. It takes the page's own query string
 * (status, all, state, size, checked, q) plus `sort` and `dir`, so the file
 * has the rows and the order the reader sees. `all=1` alone is every college.
 */
export async function GET(request: Request) {
  if (!isDataQualityLaunched()) return new Response("Not found", { status: 404 });
  const params = new URL(request.url).searchParams;
  const view = parseCoverageView(params);
  const { key, dir } = parseCoverageSort(params);
  const rows = sortCoverageRows(filterCoverageRows(await fetchCoverageRows(), view), key, dir);
  const everyCollege = view.all && !view.state && view.size === "any" && view.checked === "any" && !view.q;
  const day = new Date().toISOString().slice(0, 10);
  return new Response(CSV_BOM + buildCoverageCsv(rows), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${coverageCsvFilename(everyCollege ? "all" : "view", day)}"`,
      "Cache-Control": "public, s-maxage=900, stale-while-revalidate=3600",
      Link: DATA_LICENSE_LINK_HEADER,
    },
  });
}
