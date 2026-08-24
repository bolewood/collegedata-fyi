import { ImageResponse } from "next/og";
import { fetchCanonicalSchoolId, fetchSchoolDocuments } from "@/lib/queries";
import { isCanonicalCdsYear, yearRange } from "@/lib/format";
import { cachedSchoolInks, schoolOgColors } from "@/lib/school-inks";

export const alt = "School Common Data Set archive";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 3600;

export default async function Image({
  params,
}: {
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  const resolvedSchoolId = (await fetchCanonicalSchoolId(school_id)) ?? school_id;
  const docs = await fetchSchoolDocuments(resolvedSchoolId);
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

  const name = docs[0].school_name ?? resolvedSchoolId;
  const years = docs
    .map((d) => d.canonical_year)
    .filter(isCanonicalCdsYear)
    .sort();

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
            fontSize: name.length > 40 ? 44 : 56,
            fontWeight: 700,
            color: og.type,
            lineHeight: 1.2,
            marginBottom: 24,
          }}
        >
          {name}
        </div>

        {/* Info row */}
        <div style={{ display: "flex", gap: 40, marginTop: 16 }}>
          <StatPill
            label="Documents"
            value={docs.length.toString()}
            type={og.type}
          />
          {years.length > 0 ? (
            <StatPill
              label="Years"
              value={yearRange(years[0], years[years.length - 1])}
              type={og.type}
            />
          ) : null}
          <StatPill
            label="Extracted"
            value={docs.filter((d) => d.extraction_status === "extracted").length.toString()}
            type={og.type}
          />
        </div>
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
        padding: "20px 36px",
      }}
    >
      <div style={{ fontSize: 36, fontWeight: 700, color: type }}>
        {value}
      </div>
      <div style={{ fontSize: 16, color: type, opacity: 0.72, marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
