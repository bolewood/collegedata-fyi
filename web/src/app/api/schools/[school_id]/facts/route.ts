import { NextResponse } from "next/server";
import {
  getSchoolFacts,
  type PublicFactCategory,
} from "@/lib/public-data";

export const revalidate = 3600;

const CATEGORIES = new Set<PublicFactCategory>([
  "identity",
  "admissions",
  "enrollment",
  "cost",
  "aid",
  "outcomes",
  "sources",
]);

function parseCategories(value: string | null): PublicFactCategory[] | undefined {
  if (!value) return undefined;
  return value
    .split(",")
    .map((part) => part.trim())
    .filter((part): part is PublicFactCategory => CATEGORIES.has(part as PublicFactCategory));
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ school_id: string }> },
) {
  const { school_id } = await params;
  const url = new URL(request.url);
  const categories = parseCategories(url.searchParams.get("categories"));
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

