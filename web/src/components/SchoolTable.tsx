"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { SchoolSummary } from "@/lib/types";
import { Badge } from "./Badge";
import { SchoolGlyph } from "./SchoolGlyph";
import { formatBadgeLabel, formatColor } from "@/lib/format";

type SortKey = "name" | "docs" | "year";
type SortDir = "asc" | "desc";

export function SchoolTable({ schools }: { schools: SchoolSummary[] }) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    let list = q
      ? schools.filter((s) => s.school_name.toLowerCase().includes(q))
      : schools;

    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "name") cmp = a.school_name.localeCompare(b.school_name);
      else if (sortKey === "docs") cmp = a.doc_count - b.doc_count;
      else if (sortKey === "year")
        cmp = (a.latest_year ?? "").localeCompare(b.latest_year ?? "");
      return sortDir === "asc" ? cmp : -cmp;
    });

    return list;
  }, [schools, search, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : "desc");
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <span style={{ marginLeft: 6, color: "var(--ink-4)" }}>↕</span>;
    return <span style={{ marginLeft: 6 }}>{sortDir === "asc" ? "↑" : "↓"}</span>;
  }

  return (
    <div>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by name"
        aria-label="Search schools by name"
        style={{
          marginBottom: 16,
          width: "100%",
          maxWidth: 420,
          height: 36,
          padding: "0 12px",
          border: "1px solid var(--rule)",
          background: "#faf6ec",
          color: "var(--ink)",
          fontFamily: "var(--sans)",
          fontSize: 14,
          borderRadius: 2,
          outline: "none",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "var(--forest)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "var(--rule)";
        }}
      />
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", minWidth: 640, borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr className="meta" style={{ textAlign: "left", borderBottom: "1px solid var(--rule-strong)" }}>
              <th
                style={{ padding: "9px 16px 9px 0", cursor: "pointer", userSelect: "none" }}
                onClick={() => toggleSort("name")}
              >
                School <SortIcon col="name" />
              </th>
              <th
                style={{ padding: "9px 16px", cursor: "pointer", userSelect: "none", textAlign: "right" }}
                onClick={() => toggleSort("docs")}
              >
                Reports <SortIcon col="docs" />
              </th>
              <th
                style={{ padding: "9px 16px", cursor: "pointer", userSelect: "none" }}
                onClick={() => toggleSort("year")}
              >
                Latest year <SortIcon col="year" />
              </th>
              <th style={{ padding: "9px 0" }}>Formats</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((school) => (
              <tr key={school.school_id} className="rule">
                <td style={{ padding: "12px 16px 12px 0" }}>
                  <Link
                    href={`/schools/${school.school_id}`}
                    className="school-name-with-glyph"
                    style={{ fontFamily: "var(--serif)", fontSize: 18 }}
                  >
                    <SchoolGlyph size="sm" brandColors={school.brand_colors} />
                    {school.school_name}
                  </Link>
                </td>
                <td className="nums" style={{ padding: "12px 16px", textAlign: "right" }}>
                  {school.doc_count}
                </td>
                <td className="nums" style={{ padding: "12px 16px" }}>
                  {school.latest_year ?? "—"}
                </td>
                <td style={{ padding: "12px 0" }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {school.formats.map((f) => (
                      <Badge
                        key={f}
                        label={formatBadgeLabel(f)}
                        className={formatColor()}
                      />
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && (
        <p style={{ marginTop: 28, maxWidth: 520, color: "var(--ink-2)", lineHeight: 1.55 }}>
          No reports on file match &ldquo;{search}.&rdquo; Try the site search —
          schools without a report still have a page with the federal numbers.
        </p>
      )}
    </div>
  );
}
