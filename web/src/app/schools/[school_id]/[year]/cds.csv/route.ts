import { buildCdsCsv, spreadsheetFilename } from "@/lib/spreadsheet";
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
        `/schools/${canonicalSchoolId}/${year}/cds.csv`,
      ),
      308,
    );
  }
  const input = await fetchSpreadsheetInput(school_id, year);
  if (!input) {
    return notFoundResponse(school_id, year);
  }

  return new Response(buildCdsCsv(input), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${spreadsheetFilename(school_id, year, "csv")}"`,
      "Cache-Control": SPREADSHEET_CACHE_CONTROL,
    },
  });
}
