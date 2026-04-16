"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { SchoolSummary } from "@/lib/types";
import { Badge } from "./Badge";
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
    if (sortKey !== col) return <span className="text-gray-300 ml-1">&#x2195;</span>;
    return <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>;
  }

  return (
    <div>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Filter schools..."
        className="mb-4 w-full max-w-md rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
      />
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th
                className="py-2 pr-4 cursor-pointer select-none"
                onClick={() => toggleSort("name")}
              >
                School <SortIcon col="name" />
              </th>
              <th
                className="py-2 pr-4 cursor-pointer select-none text-right"
                onClick={() => toggleSort("docs")}
              >
                Documents <SortIcon col="docs" />
              </th>
              <th
                className="py-2 pr-4 cursor-pointer select-none"
                onClick={() => toggleSort("year")}
              >
                Latest Year <SortIcon col="year" />
              </th>
              <th className="py-2">Formats</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((school) => (
              <tr
                key={school.school_id}
                className="border-b border-gray-100 hover:bg-gray-50"
              >
                <td className="py-2.5 pr-4">
                  <Link
                    href={`/schools/${school.school_id}`}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {school.school_name}
                  </Link>
                </td>
                <td className="py-2.5 pr-4 text-right text-gray-600">
                  {school.doc_count}
                </td>
                <td className="py-2.5 pr-4 text-gray-600">
                  {school.latest_year ?? "—"}
                </td>
                <td className="py-2.5">
                  <div className="flex gap-1 flex-wrap">
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
        <p className="mt-8 text-center text-gray-500">
          No schools found matching &ldquo;{search}&rdquo;
        </p>
      )}
      <p className="mt-4 text-xs text-gray-400">
        {filtered.length} of {schools.length} schools
      </p>
    </div>
  );
}
