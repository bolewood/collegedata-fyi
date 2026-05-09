import { NextResponse } from "next/server";
import {
  compareSchools,
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

export async function GET(request: Request) {
  const url = new URL(request.url);
  const schools =
    url.searchParams
      .get("schools")
      ?.split(",")
      .map((school) => school.trim())
      .filter(Boolean) ?? [];
  const categories = parseCategories(url.searchParams.get("categories"));
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

  const payload = await compareSchools(schools, { categories, fields });
  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}

