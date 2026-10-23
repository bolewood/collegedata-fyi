"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import type { InstitutionSearchResult } from "@/lib/types";
import { withGlyph, type GlyphInks } from "@/lib/derive-inks";
import { isCanonicalCdsYear } from "@/lib/format";
import { SchoolGlyph } from "./SchoolGlyph";

import {
  CDS_CATALOG_SECTIONS,
  parseCatalogQuery,
  type CatalogSectionTarget,
  type ParsedCatalogQuery,
} from "@/lib/catalog-query";

export {
  CDS_CATALOG_SECTIONS,
  parseCatalogQuery,
  type CatalogSectionTarget,
  type ParsedCatalogQuery,
};

type CatalogItem = {
  id: string;
  title: string;
  subtitle: string;
  callNumber: string;
  href: string;
  glyph?: GlyphInks;
};

type SearchHit = InstitutionSearchResult & { glyph: GlyphInks };

export function CmdKCatalog() {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const titleId = useId();
  const router = useRouter();
  const pathname = usePathname();

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [schoolHits, setSchoolHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const genRef = useRef(0);

  const currentSchoolContext = useMemo(() => {
    if (!pathname) return null;
    const match = /^\/schools\/([^/]+)(?:\/([^/]+))?/.exec(pathname);
    if (!match) return null;
    return {
      schoolId: match[1],
      year: match[2] && isCanonicalCdsYear(match[2]) ? match[2] : null,
    };
  }, [pathname]);

  const parsed = useMemo(() => parseCatalogQuery(query), [query]);

  function openDialog() {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) {
      dialog.showModal();
    }
    setIsOpen(true);
    setSelectedIndex(0);
    window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 10);
  }

  function closeDialog() {
    const dialog = dialogRef.current;
    if (dialog && dialog.open) {
      dialog.close();
    }
    setIsOpen(false);
  }

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    function handleGlobalKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const dialog = dialogRef.current;
        if (dialog?.open) {
          closeDialog();
        } else {
          openDialog();
        }
      }
    }
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  // Mandatory fallback for browsers without native <dialog closedby="any"> support
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    function handleCloseEvent() {
      setIsOpen(false);
    }
    dialog.addEventListener("close", handleCloseEvent);

    let handleBackdropClick: ((event: MouseEvent) => void) | null = null;
    if (
      typeof HTMLDialogElement !== "undefined" &&
      !("closedBy" in HTMLDialogElement.prototype)
    ) {
      handleBackdropClick = (event: MouseEvent) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const isDialogContent =
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width;
        if (isDialogContent) return;
        dialog.close();
      };
      dialog.addEventListener("click", handleBackdropClick);
    }

    return () => {
      dialog.removeEventListener("close", handleCloseEvent);
      if (handleBackdropClick) {
        dialog.removeEventListener("click", handleBackdropClick);
      }
    };
  }, []);

  // Query Supabase RPC when schoolQuery (or raw query fallback) changes
  useEffect(() => {
    if (!isOpen) return;
    const effectiveSchoolQuery = (parsed.schoolQuery || query).trim();
    if (!effectiveSchoolQuery || effectiveSchoolQuery.startsWith("§")) {
      genRef.current += 1;
      setSchoolHits([]);
      setLoading(false);
      return;
    }

    const gen = ++genRef.current;
    setLoading(true);
    const timer = window.setTimeout(async () => {
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
        p_query: effectiveSchoolQuery,
        p_limit: 6,
      });
      if (gen !== genRef.current) return;
      setLoading(false);
      if (error || !data) {
        setSchoolHits([]);
        return;
      }
      setSchoolHits(data.map(withGlyph));
      setSelectedIndex(0);
    }, 150);

    return () => window.clearTimeout(timer);
  }, [isOpen, parsed.schoolQuery, query]);

  const items = useMemo<CatalogItem[]>(() => {
    const list: CatalogItem[] = [];
    const qLower = query.trim().toLowerCase();

    // 1. If on a school/year page, offer direct in-page / latest-year section & field jumps
    if (currentSchoolContext) {
      const baseYearPath = currentSchoolContext.year
        ? `/schools/${currentSchoolContext.schoolId}/${currentSchoolContext.year}`
        : `/schools/${currentSchoolContext.schoolId}`;

      if (parsed.fieldId) {
        list.push({
          id: `ctx-field-${parsed.fieldId}`,
          title: `Jump to field ${parsed.fieldId}`,
          subtitle: `Scroll to canonical CDS field ${parsed.fieldId} on current school`,
          callNumber: `FIELD ${parsed.fieldId}`,
          href: `${baseYearPath}#${parsed.fieldId}`,
        });
      }

      if (parsed.sectionTarget) {
        list.push({
          id: `ctx-sec-${parsed.sectionTarget.code}`,
          title: `${parsed.sectionTarget.code} · ${parsed.sectionTarget.label}`,
          subtitle: `Jump to section on ${currentSchoolContext.schoolId}`,
          callNumber: parsed.sectionTarget.code,
          href: `${baseYearPath}${parsed.sectionTarget.anchor}`,
        });
      }
    }

    // 2. School search hits (with compound year / section / field jump when specified!)
    for (const hit of schoolHits) {
      const targetYear =
        parsed.year ??
        (isCanonicalCdsYear(hit.latest_available_cds_year)
          ? hit.latest_available_cds_year
          : null);
      const locationStr = [hit.city, hit.state].filter(Boolean).join(", ");

      if ((parsed.sectionTarget || parsed.fieldId || parsed.year) && targetYear) {
        const anchor = parsed.fieldId
          ? `#${parsed.fieldId}`
          : parsed.sectionTarget?.anchor ?? "";
        const callBadge = parsed.fieldId
          ? `${targetYear} · ${parsed.fieldId}`
          : parsed.sectionTarget
            ? `${targetYear} · ${parsed.sectionTarget.code}`
            : `${targetYear} CDS`;
        list.push({
          id: `compound-${hit.school_id}-${callBadge}`,
          title: `${hit.school_name} — ${
            parsed.fieldId
              ? `Field ${parsed.fieldId}`
              : parsed.sectionTarget
                ? `${parsed.sectionTarget.code} ${parsed.sectionTarget.label}`
                : `${targetYear} Common Data Set`
          }`,
          subtitle: `${locationStr || "Institution"} · Direct report jump`,
          callNumber: callBadge,
          href: `/schools/${hit.school_id}/${targetYear}${anchor}`,
          glyph: hit.glyph,
        });
      }

      list.push({
        id: `school-${hit.school_id}`,
        title: hit.school_name,
        subtitle: [
          locationStr || "Institution profile",
          isCanonicalCdsYear(hit.latest_available_cds_year)
            ? `Latest CDS ${hit.latest_available_cds_year}`
            : hit.coverage_label,
        ]
          .filter(Boolean)
          .join(" · "),
        callNumber: isCanonicalCdsYear(hit.latest_available_cds_year)
          ? `CDS ${hit.latest_available_cds_year}`
          : "DIRECTORY",
        href: `/schools/${hit.school_id}`,
        glyph: hit.glyph,
      });
    }

    // 3. Matching CDS sections when browsing on a year page or empty/section query
    if (currentSchoolContext?.year || !qLower || qLower.startsWith("§")) {
      const base = currentSchoolContext?.year
        ? `/schools/${currentSchoolContext.schoolId}/${currentSchoolContext.year}`
        : null;
      if (base) {
        const matchingSections = CDS_CATALOG_SECTIONS.filter(
          (s) =>
            !qLower ||
            s.code.toLowerCase().includes(qLower) ||
            s.label.toLowerCase().includes(qLower) ||
            s.keywords.some((k) => k.includes(qLower.replace(/^§/, ""))),
        ).slice(0, 5);
        for (const sec of matchingSections) {
          if (!list.some((item) => item.id === `ctx-sec-${sec.code}`)) {
            list.push({
              id: `sec-${sec.code}`,
              title: `${sec.code} · ${sec.label}`,
              subtitle: `Jump to section in ${currentSchoolContext?.year} report`,
              callNumber: sec.code,
              href: `${base}${sec.anchor}`,
            });
          }
        }
      }
    }

    // 4. Default library index routes when query is empty or matches a surface
    const routes: CatalogItem[] = [
      {
        id: "route-browse",
        title: "Compare schools workbench",
        subtitle: "Filter admissions, SAT/ACT bands, retention, and net price side by side",
        callNumber: "§ /BROWSE",
        href: "/browse",
      },
      {
        id: "route-match",
        title: "Match list builder",
        subtitle: "Build Likely / Possible / Reach lists from CDS positioning",
        callNumber: "§ /MATCH",
        href: "/match",
      },
      {
        id: "route-schools",
        title: "All archived schools",
        subtitle: "Browse the Common Data Set archive and Title-IV directory",
        callNumber: "§ /SCHOOLS",
        href: "/schools",
      },
      {
        id: "route-coverage",
        title: "Institution CDS coverage ledger",
        subtitle: "Accountability status across 6,322 Title-IV institutions",
        callNumber: "§ /COVERAGE",
        href: "/coverage",
      },
      {
        id: "route-api",
        title: "Public API & MCP reference",
        subtitle: "No-auth REST, PostgREST, and Model Context Protocol endpoints",
        callNumber: "§ /API",
        href: "/api",
      },
    ];

    for (const r of routes) {
      if (
        !qLower ||
        r.title.toLowerCase().includes(qLower) ||
        r.callNumber.toLowerCase().includes(qLower)
      ) {
        list.push(r);
      }
    }

    return list.slice(0, 10);
  }, [currentSchoolContext, parsed, query, schoolHits]);

  function activateItem(item: CatalogItem) {
    closeDialog();
    setQuery("");
    router.push(item.href);
  }

  function handleInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, Math.max(0, items.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && items[selectedIndex]) {
      e.preventDefault();
      activateItem(items[selectedIndex]);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className="cd-chip cd-cmdk-trigger"
        aria-label="Open index call-number command palette (Command+K)"
        data-testid="cmdk-trigger"
        style={{ cursor: "pointer" }}
      >
        <span>⌘K</span>
        <span className="cd-cmdk-trigger__label">INDEX</span>
      </button>

      <dialog
        ref={dialogRef}
        {...({ closedby: "any" } as Record<string, unknown>)}
        aria-labelledby={titleId}
        className="cd-cmdk-dialog"
        data-testid="cmdk-dialog"
      >
        <div className="cd-cmdk-panel cd-card">
          <div className="cd-cmdk-header">
            <span id={titleId} className="meta">
              § Index Call Desk — Jump to school, year, section (§C9, §H2), or field (C.905)
            </span>
            <button
              type="button"
              className="cd-chip"
              onClick={closeDialog}
              style={{ cursor: "pointer" }}
            >
              ESC
            </button>
          </div>

          <div className="cd-cmdk-input-wrap">
            <span className="mono cd-cmdk-prompt" aria-hidden="true">
              §
            </span>
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              onKeyDown={handleInputKeyDown}
              placeholder="Try “bowdoin 2024 §c9”, “mit aid”, “C.905”, or “compare”…"
              className="cd-cmdk-input"
              aria-label="Catalog command query"
              autoComplete="off"
            />
          </div>

          <ul className="cd-cmdk-list" role="listbox" aria-label="Catalog matches">
            {loading && items.length === 0 && (
              <li className="cd-cmdk-empty mono">Searching catalog…</li>
            )}
            {!loading && items.length === 0 && (
              <li className="cd-cmdk-empty mono">No matching school, section, or field.</li>
            )}
            {items.map((item, idx) => {
              const active = idx === selectedIndex;
              return (
                <li
                  key={item.id}
                  role="option"
                  aria-selected={active}
                  className="cd-cmdk-item"
                  data-active={active ? "true" : "false"}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => activateItem(item)}
                >
                  <div className="cd-cmdk-item__main">
                    {item.glyph ? (
                      <SchoolGlyph size="sm" inks={item.glyph} />
                    ) : (
                      <span className="mono cd-cmdk-item__glyph">§</span>
                    )}
                    <div style={{ minWidth: 0 }}>
                      <div className="cd-cmdk-item__title">{item.title}</div>
                      <div className="cd-cmdk-item__sub">{item.subtitle}</div>
                    </div>
                  </div>
                  <span className="mono cd-cmdk-item__call">{item.callNumber}</span>
                </li>
              );
            })}
          </ul>

          <div className="cd-cmdk-footer mono">
            <span>↑↓ NAVIGATE</span>
            <span>↵ OPEN CALL NUMBER</span>
            <span>SYNTAX: [SCHOOL] [YEAR] [§SECTION | FIELD]</span>
          </div>
        </div>
      </dialog>
    </>
  );
}
