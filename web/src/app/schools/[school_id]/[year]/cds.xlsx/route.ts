import { buildCdsWorkbook, spreadsheetFilename } from "@/lib/spreadsheet";
import {
  fetchSpreadsheetInput,
  notFoundResponse,
  SPREADSHEET_CACHE_CONTROL,
} from "@/lib/spreadsheet-source";
import { fetchCanonicalSchoolId } from "@/lib/queries";
import { schoolRedirectUrl } from "@/lib/school-alias";

export const revalidate = 3600;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ school_id: string; year: string }> },
) {
  const { school_id, year } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    return Response.redirect(
      schoolRedirectUrl(
        request.url,
        `/schools/${canonicalSchoolId}/${year}/cds.xlsx`,
      ),
      308,
    );
  }
  const input = await fetchSpreadsheetInput(school_id, year);
  if (!input) {
    return notFoundResponse(school_id, year);
  }

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
