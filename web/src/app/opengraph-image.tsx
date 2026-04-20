import { ImageResponse } from "next/og";
import { fetchManifest, computeStats } from "@/lib/queries";

export const alt = "collegedata.fyi - Open-source Common Data Set archive";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 3600;

export default async function Image() {
  const manifest = await fetchManifest();
  const stats = computeStats(manifest);

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
          alignItems: "center",
          padding: "60px",
        }}
      >
        {/* Site name */}
        <div
          style={{
            display: "flex",
            fontSize: 64,
            fontWeight: 700,
            color: "#ffffff",
            marginBottom: 12,
          }}
        >
          collegedata.fyi
        </div>

        {/* Tagline */}
        <div
          style={{
            display: "flex",
            fontSize: 28,
            color: "#94a3b8",
            marginBottom: 48,
          }}
        >
          College data, straight from the source.
        </div>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: 60,
          }}
        >
          <StatPill label="Schools" value={stats.total_schools.toLocaleString()} />
          <StatPill label="Documents" value={stats.total_documents.toLocaleString()} />
          <StatPill label="Extracted" value={`${stats.extraction_pct}%`} />
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
        padding: "20px 40px",
      }}
    >
      <div style={{ fontSize: 40, fontWeight: 700, color: "#ffffff" }}>
        {value}
      </div>
      <div style={{ fontSize: 18, color: "#94a3b8", marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
