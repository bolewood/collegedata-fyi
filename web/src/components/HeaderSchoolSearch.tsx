"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import type { InstitutionSearchResult } from "@/lib/types";
import { CoverageBadge } from "./CoverageBadge";

const DEBOUNCE_MS = 180;

export function HeaderSchoolSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstitutionSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();
  const genRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      genRef.current += 1;
      setResults([]);
      setIsLoading(false);
      return;
    }

    const gen = ++genRef.current;
    setIsLoading(true);
    const timer = setTimeout(async () => {
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
        p_limit: 7,
      });
      if (gen !== genRef.current) return;
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

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
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
    <div className="cd-header-search">
      <label className="sr-only" htmlFor="header-school-search">
        Search for a school
      </label>
      <input
        id="header-school-search"
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 160)}
        onKeyDown={handleKeyDown}
        placeholder="Jump to a school"
        autoComplete="off"
      />
      {showDropdown && (
        <ul className="cd-header-search__results">
          {results.length === 0 && isLoading && (
            <li className="cd-header-search__empty">Searching...</li>
          )}
          {results.map((result, index) => (
            <li
              key={result.school_id}
              className="cd-header-search__result"
              data-active={index === selectedIndex ? "true" : "false"}
              onMouseDown={() => handleSelect(result.school_id)}
            >
              <span className="cd-header-search__school">
                <span className="cd-header-search__name">{result.school_name}</span>
                <span className="cd-header-search__meta">
                  {[result.city, result.state].filter(Boolean).join(", ") || "Institution profile"}
                  {result.latest_available_cds_year ? ` - CDS ${result.latest_available_cds_year}` : ""}
                </span>
              </span>
              <CoverageBadge
                status={result.coverage_status}
                label={result.coverage_label}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
