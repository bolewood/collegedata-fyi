import { buildCdsWorkbook, spreadsheetFilename } from "@/lib/spreadsheet";
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

  const workbook = buildCdsWorkbook(input);
  return new Response(new Uint8Array(workbook), {
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${spreadsheetFilename(school_id, year, "xlsx")}"`,
      "Cache-Control": SPREADSHEET_CACHE_CONTROL,
    },
  });
}
