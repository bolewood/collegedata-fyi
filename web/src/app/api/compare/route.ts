import { NextResponse } from "next/server";
import { compareSchools } from "@/lib/public-data";
import { parseCompareFactCategories } from "@/lib/public-fact-category";

export const revalidate = 3600;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const schools =
    url.searchParams
      .get("schools")
      ?.split(",")
      .map((school) => school.trim())
      .filter(Boolean) ?? [];
  const rawCategories = url.searchParams.get("categories");
  const { categories, unsupported } = parseCompareFactCategories(rawCategories);
  const fields =
    url.searchParams
      .get("fields")
      ?.split(",")
      .map((field) => field.trim())
      .filter(Boolean) ?? undefined;

  if (schools.length === 0) {
    return NextResponse.json(
      { error: "missing_schools", message: "Pass one or more canonical school IDs with ?schools=." },
      { status: 400 },
    );
  }

  if (rawCategories !== null && categories?.length === 0) {
    return NextResponse.json(
      {
        error: "invalid_categories",
        message: "Pass at least one recognized public fact category.",
      },
      { status: 400 },
    );
  }

  if (unsupported.length > 0) {
    return NextResponse.json(
      {
        error: "unsupported_categories",
        categories: unsupported,
        message: "Finance facts are available from the per-school facts endpoint, not the fixed-schema compare endpoint.",
      },
      { status: 400 },
    );
  }

  const payload = await compareSchools(schools, { categories, fields });
  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
