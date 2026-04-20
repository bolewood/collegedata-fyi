import { ImageResponse } from "next/og";
import {
  fetchDocumentsBySchoolAndYear,
  fetchExtract,
} from "@/lib/queries";
import type { FieldValue } from "@/lib/types";

export const alt = "Common Data Set year detail";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 3600;

type Params = { school_id: string; year: string };

function getNum(
  values: Record<string, FieldValue>,
  id: string
): number | null {
  const field = values[id];
  if (!field) return null;
  const v = field.value_decoded ?? field.value;
  const n = parseFloat(v.replace(/,/g, ""));
  return isNaN(n) ? null : n;
}

function sumFields(
  values: Record<string, FieldValue>,
  ...ids: string[]
): number | null {
  let total = 0;
  let found = false;
  for (const id of ids) {
    const n = getNum(values, id);
    if (n != null) {
      total += n;
      found = true;
    }
  }
  return found ? total : null;
}

export default async function Image({
  params,
}: {
  params: Promise<Params>;
}) {
  const { school_id, year } = await params;
  const docs = await fetchDocumentsBySchoolAndYear(school_id, year);

  if (docs.length === 0) {
    return new ImageResponse(
      (
        <div
          style={{
            background: "#1e3a5f",
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            fontSize: 48,
          }}
        >
          collegedata.fyi
        </div>
      ),
      { ...size }
    );
  }

  const schoolName = docs[0].school_name ?? school_id;

  // Load extracted data for key stats
  const stats: { label: string; value: string }[] = [];

  const doc = docs[0];
  if (doc.extraction_status === "extracted" && doc.document_id) {
    const { mergedValues: values } = await fetchExtract(doc.document_id);

    const totalApplied = sumFields(values, "C.101", "C.102", "C.103");
    const totalAdmitted = sumFields(values, "C.104", "C.105", "C.106");

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

    const act25 = getNum(values, "C.921");
    const act75 = getNum(values, "C.923");
    if (act25 && act75) {
      stats.push({ label: "ACT Composite", value: `${act25}-${act75}` });
    }
  }

  return new ImageResponse(
    (
      <div
        style={{
          background: "linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%)",
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
            color: "#60a5fa",
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
            color: "#ffffff",
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
            color: "#94a3b8",
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
              <StatPill key={s.label} label={s.label} value={s.value} />
            ))}
          </div>
        ) : null}
      </div>
    ),
    { ...size }
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        background: "rgba(255,255,255,0.1)",
        borderRadius: 16,
        padding: "16px 32px",
      }}
    >
      <div style={{ fontSize: 32, fontWeight: 700, color: "#ffffff" }}>
        {value}
      </div>
      <div style={{ fontSize: 14, color: "#94a3b8", marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
