import { NextResponse } from "next/server";
import {
  publicFieldDefinitions,
  type PublicFactCategory,
} from "@/lib/public-data";

export const revalidate = 3600;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const category = url.searchParams.get("category") as PublicFactCategory | null;
  const fields = publicFieldDefinitions().filter((field) =>
    category ? field.category === category : true,
  );
  return NextResponse.json(
    {
      generated_at: new Date().toISOString(),
      fields,
    },
    {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    },
  );
}

