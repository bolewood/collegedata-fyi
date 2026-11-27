import { ImageResponse } from "next/og";
import { fetchManifest, computeStats } from "@/lib/queries";
import { SITE_NAME } from "@/lib/site";

export const alt = `${SITE_NAME} - Open-source college data`;
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
          background: "#f1ece1",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: "60px",
        }}
      >
        {/* Wordmark: four forest squares, QUADFILE in tracked caps */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            marginBottom: 20,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", width: 64, gap: 8, marginRight: 28 }}>
            <div style={{ width: 28, height: 28, background: "#3f5b3a" }} />
            <div style={{ width: 28, height: 28, background: "#3f5b3a" }} />
            <div style={{ width: 28, height: 28, background: "#3f5b3a" }} />
            <div style={{ width: 28, height: 28, background: "#3f5b3a" }} />
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 72,
              letterSpacing: "0.14em",
              color: "#1c1e1b",
            }}
          >
            QUADFILE
          </div>
        </div>

        {/* Tagline */}
        <div
          style={{
            display: "flex",
            fontSize: 28,
            color: "#65645d",
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
        background: "#e9e3d4",
        border: "1px solid rgba(28,30,27,0.28)",
        borderRadius: 2,
        padding: "20px 40px",
      }}
    >
      <div style={{ fontSize: 40, color: "#1c1e1b" }}>
        {value}
      </div>
      <div style={{ fontSize: 18, color: "#65645d", marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
