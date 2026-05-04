"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import type { InstitutionSearchResult } from "@/lib/types";
import { CoverageBadge } from "./CoverageBadge";

// PRD 015 M4 — server-backed autocomplete over institution_cds_coverage.
// Calls the search_institutions RPC with a debounced query so missing-
// CDS and not-yet-checked schools surface as first-class results. The
// RPC ranks name-exact > prefix > substring; we just render the order
// it returns.
//
// Replaces the prior in-memory ILIKE that only knew about CDS-backed
// schools (see git blame for the swap).

const DEBOUNCE_MS = 220;

export function SchoolSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstitutionSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  // Generation counter so a slow network response can never overwrite
  // a fresher one. Each new query increments; only the latest gen
  // commits to state.
  const genRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    const gen = ++genRef.current;
    setIsLoading(true);
    const timer = setTimeout(async () => {
      // database.types.ts lags new RPCs until regenerated; cast to a
      // permissive shape so the call typechecks. Same pattern queries.ts
      // uses for tables that aren't in the generated type yet.
      const rpcClient = supabase as unknown as {
        rpc: (
          fn: string,
          args: Record<string, unknown>,
        ) => Promise<{
          data: InstitutionSearchResult[] | null;
          error: { message: string } | null;
        }>;
      };
      const { data, error } = await rpcClient.rpc("search_institutions", {
        p_query: trimmed,
        p_limit: 10,
      });
      if (gen !== genRef.current) return; // a newer query has fired
      setIsLoading(false);
      if (error) {
        setResults([]);
        return;
      }
      setResults(data ?? []);
      setSelectedIndex(0);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  function handleSelect(schoolId: string) {
    setIsOpen(false);
    setQuery("");
    setResults([]);
    router.push(`/schools/${schoolId}`);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelect(results[selectedIndex].school_id);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  }

  const showDropdown = isOpen && (results.length > 0 || (isLoading && query.trim().length > 0));

  return (
    <div className="relative w-full max-w-lg mx-auto">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 200)}
        onKeyDown={handleKeyDown}
        placeholder="Search schools by name, alias, or city..."
        className="w-full px-4 py-3"
        style={{
          border: "1px solid var(--rule-strong)",
          background: "#faf6ec",
          color: "var(--ink)",
          fontFamily: "var(--sans)",
          fontSize: 16,
          borderRadius: 2,
          outline: "none",
        }}
        onFocusCapture={(e) => {
          e.currentTarget.style.borderColor = "var(--forest)";
        }}
        onBlurCapture={(e) => {
          e.currentTarget.style.borderColor = "var(--rule-strong)";
        }}
      />
      {showDropdown && (
        <ul
          ref={listRef}
          className="absolute z-10 mt-1 w-full overflow-auto"
          style={{
            background: "#faf6ec",
            border: "1px solid var(--rule-strong)",
            borderRadius: 2,
            maxHeight: 360,
          }}
        >
          {results.length === 0 && isLoading && (
            <li
              className="px-4 py-3 mono"
              style={{ color: "var(--ink-3)", fontSize: 12 }}
            >
              Searching…
            </li>
          )}
          {results.map((r, i) => (
            <li
              key={r.school_id}
              onMouseDown={() => handleSelect(r.school_id)}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 12,
                alignItems: "baseline",
                padding: "10px 14px",
                cursor: "pointer",
                background: i === selectedIndex ? "var(--paper-2)" : "transparent",
                borderTop: i === 0 ? "none" : "1px solid var(--rule)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontFamily: "var(--serif)",
                    fontSize: 17,
                    color: "var(--ink)",
                    lineHeight: 1.2,
                  }}
                >
                  {r.school_name}
                </div>
                {(r.city || r.state) && (
                  <div
                    className="mono"
                    style={{
                      display: "flex",
                      gap: 8,
                      flexWrap: "wrap",
                      fontSize: 11,
                      color: "var(--ink-3)",
                      marginTop: 2,
                    }}
                  >
                    <span>{[r.city, r.state].filter(Boolean).join(", ")}</span>
                    {r.latest_available_cds_year && (
                      <span>
                        CDS {r.latest_available_cds_year}
                      </span>
                    )}
                  </div>
                )}
              </div>
              <CoverageBadge status={r.coverage_status} label={r.coverage_label} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
