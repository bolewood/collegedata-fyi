"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { SchoolSummary } from "@/lib/types";

export function SchoolSearch({ schools }: { schools: SchoolSummary[] }) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const filtered = query.length > 0
    ? schools.filter((s) =>
        s.school_name.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 10)
    : [];

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  function handleSelect(schoolId: string) {
    setIsOpen(false);
    setQuery("");
    router.push(`/schools/${schoolId}`);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || filtered.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelect(filtered[selectedIndex].school_id);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  }

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
        placeholder={`Search ${schools.length} schools...`}
        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-lg shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
      />
      {isOpen && filtered.length > 0 && (
        <ul
          ref={listRef}
          className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-80 overflow-auto"
        >
          {filtered.map((school, i) => (
            <li
              key={school.school_id}
              onMouseDown={() => handleSelect(school.school_id)}
              className={`px-4 py-2.5 cursor-pointer text-sm ${
                i === selectedIndex
                  ? "bg-blue-50 text-blue-900"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <span className="font-medium">{school.school_name}</span>
              <span className="ml-2 text-gray-400">
                {school.doc_count} doc{school.doc_count !== 1 ? "s" : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
