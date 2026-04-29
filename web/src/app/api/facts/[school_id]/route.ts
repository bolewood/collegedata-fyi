/**
 * GET /api/facts/{school_id}
 *
 * Flat-JSON facts endpoint for LLM tool-use / quick citation.
 *
 * Returns the most-queried CDS fields for the school's most recent extracted
 * year. Shape is deliberately denormalized and stable: no nesting, no schema
 * wrapper, keys match the canonical CDS question numbers that produced them.
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

import { NextResponse } from "next/server";
import {
  fetchSchoolDocuments,
  fetchExtract,
} from "@/lib/queries";

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

function asInt(s: string | null): number | null {
  if (s === null) return null;
  const cleaned = s.replace(/[, ]/g, "");
  const n = parseInt(cleaned, 10);
  return Number.isFinite(n) ? n : null;
}

function asPct(a: number | null, b: number | null): number | null {
  if (a === null || b === null || b === 0) return null;
  return Math.round((a / b) * 1000) / 10; // one decimal place
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ school_id: string }> },
) {
  const { school_id } = await params;
  const docs = await fetchSchoolDocuments(school_id);
  const extracted = docs.find((d) => d.extraction_status === "extracted" && d.document_id);

  if (!extracted || !extracted.document_id) {
    return NextResponse.json(
      {
        error: "school_not_found_or_not_extracted",
        school_id,
        message:
          "No extracted Common Data Set document available for this school. Try /api/facts/{school_id} with a canonical school_id from /rest/v1/cds_manifest?select=school_id.",
      },
      { status: 404 },
    );
  }

  const { mergedValues } = await fetchExtract(extracted.document_id);

  // CDS canonical question numbers for the "most-queried" fields.
  //   C.116 = total first-time, first-year applicants
  //   C.117 = total admitted
  //   C.120 = total enrolled
  //   B.101 = total full-time men enrolled
  //   B.126 = total full-time women enrolled
  //   B.201-B.220 = retention/persistence (subset per year)
  //   A.101 = name of institution
  // Values are strings in the source; we coerce to int / pct where sensible
  // but always include the raw string alongside for fidelity.
  const applied = asInt(readValue(mergedValues, "C.116"));
  const admitted = asInt(readValue(mergedValues, "C.117"));
  const enrolled = asInt(readValue(mergedValues, "C.120"));

  const body = {
    school_id,
    school_name: extracted.school_name,
    cds_year: extracted.canonical_year,
    source_format: extracted.source_format,
    applied,
    admitted,
    enrolled,
    acceptance_rate_pct: asPct(admitted, applied),
    yield_rate_pct: asPct(enrolled, admitted),
    source_url: extracted.source_url,
    archive_url: `https://www.collegedata.fyi/schools/${school_id}/${extracted.canonical_year}`,
    raw: {
      // Include the full canonical field dict so LLMs can cite any other
      // question by question_number. Keys are stable across years.
      C_116_applied_total: readValue(mergedValues, "C.116"),
      C_117_admitted_total: readValue(mergedValues, "C.117"),
      C_120_enrolled_total: readValue(mergedValues, "C.120"),
      B_101_ft_men_enrolled: readValue(mergedValues, "B.101"),
      B_126_ft_women_enrolled: readValue(mergedValues, "B.126"),
    },
    note:
      "Values extracted from the school's own Common Data Set document. Pipeline source: https://github.com/bolewood/collegedata-fyi. For the full extract, query /rest/v1/cds_artifacts directly using the public anon-key instructions at /api.",
  };

  return NextResponse.json(body, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
