import { ImageResponse } from "next/og";
import { fetchSchoolDocuments } from "@/lib/queries";
import { yearRange } from "@/lib/format";

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
  const docs = await fetchSchoolDocuments(school_id);

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

  const name = docs[0].school_name ?? school_id;
  const years = docs
    .map((d) => d.canonical_year)
    .filter((y): y is string => y != null)
    .sort();

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
            fontSize: name.length > 40 ? 44 : 56,
            fontWeight: 700,
            color: "#ffffff",
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
          />
          {years.length > 0 ? (
            <StatPill
              label="Years"
              value={yearRange(years[0], years[years.length - 1])}
            />
          ) : null}
          <StatPill
            label="Extracted"
            value={docs.filter((d) => d.extraction_status === "extracted").length.toString()}
          />
        </div>
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
        padding: "20px 36px",
      }}
    >
      <div style={{ fontSize: 36, fontWeight: 700, color: "#ffffff" }}>
        {value}
      </div>
      <div style={{ fontSize: 16, color: "#94a3b8", marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
