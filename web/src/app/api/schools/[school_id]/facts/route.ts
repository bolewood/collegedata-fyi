import { NextResponse } from "next/server";
import {
  getSchoolFacts,
} from "@/lib/public-data";
import { parsePublicFactCategories } from "@/lib/public-fact-category";
import { fetchCanonicalSchoolId } from "@/lib/queries";
import { schoolRedirectUrl } from "@/lib/school-alias";

export const revalidate = 3600;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ school_id: string }> },
) {
  const { school_id } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    return NextResponse.redirect(
      schoolRedirectUrl(request.url, `/api/schools/${canonicalSchoolId}/facts`),
      308,
    );
  }
  const url = new URL(request.url);
  const rawCategories = url.searchParams.get("categories");
  const categories = parsePublicFactCategories(rawCategories);
  if (rawCategories !== null && categories?.length === 0) {
    return NextResponse.json(
      {
        error: "invalid_categories",
        message: "Pass at least one recognized public fact category.",
      },
      { status: 400 },
    );
  }
  const fields =
    url.searchParams
      .get("fields")
      ?.split(",")
      .map((field) => field.trim())
      .filter(Boolean) ?? undefined;

  const payload = await getSchoolFacts(school_id, { categories, fields });
  if (!payload) {
    return NextResponse.json(
      {
        error: "school_not_found",
        school_id,
        message: "No public CollegeData.FYI school, CDS, or federal baseline row was found for this school_id.",
      },
      { status: 404 },
    );
  }

  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
