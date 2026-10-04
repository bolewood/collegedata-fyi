"use client";

import { useEffect, useState } from "react";
import { formatRecipeShare } from "@/lib/format";
import { formatUsd, type AlignmentGapMeritRow } from "@/lib/alignment-gap-recipe-analysis";

export function AlignmentGapExamplesTable({
  title,
  rows,
}: {
  title: string;
  rows: readonly AlignmentGapMeritRow[];
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const handleSelect = (event: Event) => {
      const custom = event as CustomEvent<string | null>;
      setSelectedId(custom.detail ?? null);
    };
    window.addEventListener("collegedata:select-school", handleSelect);
    return () => window.removeEventListener("collegedata:select-school", handleSelect);
  }, []);

  const handleClick = (schoolId: string) => {
    const nextId = selectedId === schoolId ? null : schoolId;
    setSelectedId(nextId);
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("collegedata:select-school", { detail: nextId }),
      );
      // If selecting a school, scroll chart into view gently if off-screen
      if (nextId) {
        const chart = document.querySelector("[data-testid='alignment-gap-merit-chart']");
        if (chart) {
          const rect = chart.getBoundingClientRect();
          if (rect.bottom < 0 || rect.top > window.innerHeight) {
            chart.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        }
      }
    }
  };

  return (
    <section style={{ marginTop: 28, overflowX: "auto" }}>
      <div
        className="meta"
        style={{
          marginBottom: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "none" }}>
          Click a school to highlight on the chart
        </span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr className="meta" style={{ textAlign: "left", color: "var(--ink-3)" }}>
            <th style={{ padding: "8px 12px 8px 0" }}>School</th>
            <th style={{ padding: "8px 12px" }}>Gap/yr</th>
            <th style={{ padding: "8px 12px" }}>Merit spend / first-year</th>
            <th style={{ padding: "8px 12px" }}>Merit share</th>
            <th style={{ padding: "8px 12px" }}>Avg merit grant</th>
            <th style={{ padding: "8px 12px" }}>Net price</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isSelected = selectedId === row.schoolId;
            return (
              <tr
                key={row.schoolId}
                onClick={() => handleClick(row.schoolId)}
                style={{
                  borderTop: "1px solid var(--rule)",
                  cursor: "pointer",
                  background: isSelected ? "var(--paper-2)" : "transparent",
                  transition: "background 0.15s ease",
                }}
              >
                <td style={{ padding: "8px 12px 8px 0", fontWeight: isSelected ? 600 : 400 }}>
                  {row.schoolName.replace("-Main", "")}
                  {isSelected && (
                    <span style={{ marginLeft: 6, fontSize: 11, color: "var(--brick)" }}>
                      ●
                    </span>
                  )}
                </td>
                <td style={{ padding: "8px 12px", fontFamily: "var(--mono)" }}>
                  {formatUsd(row.gap)}
                </td>
                <td
                  style={{
                    padding: "8px 12px",
                    fontWeight: 600,
                    fontFamily: "var(--mono)",
                    color: row.meritPerFirstYear >= row.gap ? "var(--forest)" : "var(--ochre)",
                  }}
                >
                  {formatUsd(row.meritPerFirstYear)}
                </td>
                <td style={{ padding: "8px 12px", fontFamily: "var(--mono)" }}>
                  {formatRecipeShare(row.meritShare, 0)}
                </td>
                <td style={{ padding: "8px 12px", fontFamily: "var(--mono)" }}>
                  {row.avgMeritGrant > 0 ? formatUsd(row.avgMeritGrant) : "$0"}
                </td>
                <td style={{ padding: "8px 12px", fontFamily: "var(--mono)" }}>
                  {formatUsd(row.avgNetPrice)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
