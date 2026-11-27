/**
 * GET /api/facts/{school_id}
 *
 * Flat-JSON facts endpoint for LLM tool-use / quick citation.
 *
 * DEPRECATED: use /api/schools/{school_id}/facts. Returns admissions counts for
 * the school's most recent extracted year, read from the year-aware
 * school_browser_rows projection. Shape is flat and stable.
 *
 * Use cases:
 *   - ChatGPT / Claude tool-call: "curl https://www.collegedata.fyi/api/facts/mit"
 *     and summarize it
 *   - Copy-paste into a notebook without parsing nested Dataset metadata
 *   - Server-side rendering where the full 1,105-field extract is overkill
 *
 * Per ADR 0008, this endpoint honors the participation_status filter — a
 * school that has been withdrawn from the public catalog returns 404 here.
 */

import { dataLicenseFields } from "@/lib/data-license";
import { REPO_URL } from "@/lib/repo";
import { NextResponse } from "next/server";
import {
  fetchCanonicalSchoolId,
  fetchSchoolDocuments,
  fetchExtract,
  fetchSchoolYearFacts,
} from "@/lib/queries";
import { legacyAdmissions, legacyRaw, legacyRawNote } from "@/lib/legacy-facts";
import { schoolRedirectUrl } from "@/lib/school-alias";
import { SITE_ORIGIN } from "@/lib/site";

export const revalidate = 3600; // hourly — matches the rest of the app

type FieldValue = { value: string } | Record<string, unknown>;

function readValue(
  values: Record<string, FieldValue>,
  questionNumber: string,
): string | null {
  const v = values[questionNumber];
  if (!v || typeof v !== "object") return null;
  const raw = (v as { value?: unknown }).value;
  return typeof raw === "string" ? raw : null;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ school_id: string }> },
) {
  const { school_id } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    return NextResponse.redirect(
      schoolRedirectUrl(request.url, `/api/facts/${canonicalSchoolId}`),
      308,
    );
  }
  const docs = await fetchSchoolDocuments(school_id);
  // The list sorts canonical_year as text, so an "unknown"-year document comes
  // first, and wrong_file documents are not filtered out. Neither has a
  // projection row. Prefer the newest dated whole-institution filing; fall back
  // to the first extracted document only when none qualifies.
  const candidates = docs.filter((d) => d.extraction_status === "extracted" && d.document_id);
  const extracted =
    candidates.find(
      (d) =>
        /^\d{4}-\d{2}$/.test(d.canonical_year ?? "") &&
        d.data_quality_flag !== "wrong_file" &&
        d.sub_institutional == null,
    ) ?? candidates[0];

  if (!extracted || !extracted.document_id) {
    return NextResponse.json(
      {
        error: "school_not_found_or_not_extracted",
        school_id,
        message:
          "No extracted Common Data Set document available for this school. Find a canonical school_id with /api/schools/search?q=, or use /api/schools/{school_id}/facts.",
      },
      { status: 404 },
    );
  }

  const [{ canonical, mergedValues }, yearFacts] = await Promise.all([
    fetchExtract(extracted.document_id, school_id),
    fetchSchoolYearFacts(school_id),
  ]);

  // Counts come from the year-aware school_browser_rows projection for this
  // same document, never from hardcoded question numbers (issue #267).
  const admissions = legacyAdmissions(yearFacts, extracted.document_id);
  const templateYear =
    (canonical?.notes as { schema_version?: string } | null)?.schema_version ??
    extracted.canonical_year;

  const body = {
    school_id,
    school_name: extracted.school_name,
    cds_year: extracted.canonical_year,
    source_format: extracted.source_format,
    applied: admissions.applied,
    admitted: admissions.admitted,
    enrolled: admissions.enrolled,
    acceptance_rate_pct: admissions.acceptance_rate_pct,
    yield_rate_pct: admissions.yield_rate_pct,
    source_url: extracted.source_url,
    archive_url: `${SITE_ORIGIN}/schools/${school_id}/${extracted.canonical_year}`,
    raw: legacyRaw(templateYear, (q) => readValue(mergedValues, q)),
    raw_note: legacyRawNote(school_id),
    deprecated: true,
    replacement: `/api/schools/${school_id}/facts`,
    ...dataLicenseFields(),
    note:
      `Values extracted from the school's own Common Data Set document. Pipeline source: ${REPO_URL}. For the full extract, query /rest/v1/cds_artifacts directly using the public anon-key instructions at /api.`,
  };

  return NextResponse.json(body, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
