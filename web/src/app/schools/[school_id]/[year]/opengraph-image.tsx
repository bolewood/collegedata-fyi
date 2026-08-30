import { ImageResponse } from "next/og";
import {
  fetchCanonicalSchoolId,
  fetchDocumentsBySchoolAndYear,
  fetchExtract,
} from "@/lib/queries";
import { c1HeadlineTotals, fieldNumber } from "@/lib/c1-headline-totals";
import type { FieldValue } from "@/lib/types";
import { cachedSchoolInks, schoolOgColors } from "@/lib/school-inks";

export const alt = "Common Data Set year detail";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 3600;

type Params = { school_id: string; year: string };

function getNum(
  values: Record<string, FieldValue>,
  id: string
): number | null {
  return fieldNumber(values, id);
}

export default async function Image({
  params,
}: {
  params: Promise<Params>;
}) {
  const { school_id, year } = await params;
  const resolvedSchoolId = (await fetchCanonicalSchoolId(school_id)) ?? school_id;
  const docs = await fetchDocumentsBySchoolAndYear(resolvedSchoolId, year);
  const og = schoolOgColors(await cachedSchoolInks(resolvedSchoolId));

  if (docs.length === 0) {
    return new ImageResponse(
      (
        <div
          style={{
            background: og.ground,
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: og.type,
            fontSize: 48,
          }}
        >
          collegedata.fyi
        </div>
      ),
      { ...size }
    );
  }

  const schoolName = docs[0].school_name ?? resolvedSchoolId;

  // Load extracted data for key stats
  const stats: { label: string; value: string }[] = [];

  const doc = docs[0];
  if (doc.extraction_status === "extracted" && doc.document_id) {
    const { mergedValues: values } = await fetchExtract(doc.document_id);
    const schemaVersion = doc.canonical_year ?? doc.cds_year;
    const { applied: totalApplied, admitted: totalAdmitted } = c1HeadlineTotals(
      values,
      schemaVersion,
    );

    if (totalApplied && totalAdmitted && totalApplied > 0) {
      stats.push({
        label: "Acceptance Rate",
        value: ((totalAdmitted / totalApplied) * 100).toFixed(1) + "%",
      });
    }

    if (totalApplied) {
      stats.push({
        label: "Applications",
        value: totalApplied.toLocaleString(),
      });
    }

    const sat25 = getNum(values, "C.905");
    const sat75 = getNum(values, "C.907");
    if (sat25 && sat75) {
      stats.push({ label: "SAT Composite", value: `${sat25}-${sat75}` });
    }

    const act25 = getNum(values, "C.914");
    const act75 = getNum(values, "C.916");
    if (act25 && act75) {
      stats.push({ label: "ACT Composite", value: `${act25}-${act75}` });
    }
  }

  return new ImageResponse(
    (
      <div
        style={{
          background: og.ground,
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "60px 80px",
        }}
      >
        {/* Site badge */}
        <div
          style={{
            display: "flex",
            fontSize: 20,
            color: og.accent,
            marginBottom: 16,
            letterSpacing: 1,
          }}
        >
          collegedata.fyi
        </div>

        {/* School name */}
        <div
          style={{
            display: "flex",
            fontSize: schoolName.length > 40 ? 40 : 52,
            fontWeight: 700,
            color: og.type,
            lineHeight: 1.2,
          }}
        >
          {schoolName}
        </div>

        {/* Year */}
        <div
          style={{
            display: "flex",
            fontSize: 28,
            color: og.type,
            marginTop: 8,
            marginBottom: 32,
          }}
        >
          {`Common Data Set ${year}`}
        </div>

        {/* Stats row */}
        {stats.length > 0 ? (
          <div style={{ display: "flex", gap: 32 }}>
            {stats.slice(0, 4).map((s) => (
              <StatPill key={s.label} label={s.label} value={s.value} type={og.type} />
            ))}
          </div>
        ) : null}
      </div>
    ),
    { ...size }
  );
}

function StatPill({
  label,
  value,
  type,
}: {
  label: string;
  value: string;
  type: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        background: "rgba(241,236,225,0.12)",
        borderRadius: 2,
        padding: "16px 32px",
      }}
    >
      <div style={{ fontSize: 32, fontWeight: 700, color: type }}>
        {value}
      </div>
      <div style={{ fontSize: 14, color: type, opacity: 0.72, marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
