import { NextResponse } from "next/server";
import {
  fetchCanonicalSchoolId,
  fetchInstitutionCoverage,
  fetchSchoolDirectPublishEvents,
  fetchSchoolDocuments,
} from "@/lib/queries";
import { buildSchoolRss, schoolFeedPath } from "@/lib/school-rss";

export const revalidate = 3600;

type Params = { school_id: string };

export async function GET(
  _request: Request,
  context: { params: Promise<Params> },
) {
  const { school_id } = await context.params;
  const canonicalSchoolId = (await fetchCanonicalSchoolId(school_id)) ?? school_id;
  if (canonicalSchoolId !== school_id) {
    return NextResponse.redirect(
      new URL(schoolFeedPath(canonicalSchoolId), "https://www.collegedata.fyi"),
      301,
    );
  }

  const docs = await fetchSchoolDocuments(canonicalSchoolId);
  const coverage =
    docs.length === 0
      ? await fetchInstitutionCoverage(canonicalSchoolId)
      : null;
  if (docs.length === 0 && !coverage) {
    return new NextResponse("Not Found", { status: 404 });
  }

  const schoolName =
    docs[0]?.school_name ?? coverage?.school_name ?? canonicalSchoolId;
  const events = await fetchSchoolDirectPublishEvents(canonicalSchoolId);
  const xml = buildSchoolRss({
    schoolId: canonicalSchoolId,
    schoolName,
    events: events.map((event) => ({ ...event, school_name: schoolName })),
  });

  return new NextResponse(xml, {
    status: 200,
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
