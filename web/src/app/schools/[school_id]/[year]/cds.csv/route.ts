import { buildCdsCsv, spreadsheetFilename } from "@/lib/spreadsheet";
import {
  fetchSpreadsheetInput,
  notFoundResponse,
  SPREADSHEET_CACHE_CONTROL,
} from "@/lib/spreadsheet-source";

export const revalidate = 3600;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ school_id: string; year: string }> },
) {
  const { school_id, year } = await params;
  const input = await fetchSpreadsheetInput(school_id, year);
  if (!input) return notFoundResponse(school_id, year);

  return new Response(buildCdsCsv(input), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${spreadsheetFilename(school_id, year, "csv")}"`,
      "Cache-Control": SPREADSHEET_CACHE_CONTROL,
    },
  });
}
