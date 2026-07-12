# PRD 025 — School spreadsheet download

**Status:** Shipped (v1)
**Owner:** frontend
**Surfaces:** `/schools/{school_id}/{year}` page, two new file routes

## Problem

The people this archive serves — counselors, journalists, students building
match lists — live in spreadsheets. Today, getting one school's CDS numbers
into a sheet means copy-pasting from the page, hand-rolling PostgREST calls
(the recipes docs walk through curl + JSON joins), or using the `/browse` CSV
export, which only covers the curated browser columns, not the full extract.
There is no one-click way to take everything we extracted from a school's CDS
home in a form Excel/Sheets can open.

## Solution

Every extracted school-year document gets two stable, shareable download URLs
served by Next.js route handlers:

- `/schools/{school_id}/{year}/cds.xlsx` — a real multi-tab workbook:
  - **README tab** — school, year, extraction stats, schema version, source
    document link, page URL, an API example, attribution/license note, and a
    note about LLM-fallback-sourced values when present.
  - **One tab per CDS section** (A–J, mirroring the document structure people
    already know): Table code, Field ID, Field label, Value, As published,
    Value type, Source (parser vs. LLM fallback), plus a Variant column when
    the school has sub-institutional variants.
- `/schools/{school_id}/{year}/cds.csv` — the same rows flat (one row per
  field), for scripts and pivot/VLOOKUP users. UTF-8 BOM + CRLF so Excel
  opens it clean.

The school-year page shows "Download spreadsheet" / "CSV" links next to the
existing source-document link whenever structured values exist, with Vercel
analytics click events (`spreadsheet_downloaded`, file_type + school + year),
mirroring how the `/browse` CSV export is tracked.

## Key decisions

- **Values as real numbers.** Cells whose schema `value_type` is numeric
  (`Nearest $1`, `Nearest 1%`, `Number`, …) and whose raw string parses
  cleanly are written as XLSX number cells so formulas work immediately.
  The "As published" column always preserves the exact source string.
  Guardrails: leading-zero strings (zip codes), and anything that isn't
  strictly `$`/digits/commas/decimal/`%` (phone numbers, "Required for
  some") stay strings. Percentages are written as published (98.5 for
  "98.5"), not rescaled — rescaling guesses wrong more than it helps.
- **No new dependency for XLSX.** SheetJS on npm is stale and CVE-flagged;
  exceljs is a heavy tree for one write path. XLSX is a zip of small XML
  parts, and Node's `zlib` does the compression — `web/src/lib/xlsx.ts` is a
  ~200-line dependency-free writer (inline strings, bold header style, column
  widths, deterministic output) with unit tests that re-parse the zip and
  verify CRCs, and validated against openpyxl.
- **Reuse the page's own grouping.** Rows come from the same
  `groupBySection` / `schema-labels` path FieldsView renders, so the
  spreadsheet always matches what the page shows — same labels, same
  section/subsection assignment, same canonical + LLM-fallback merge
  (`fetchExtract`, deterministic cleaner wins).
- **Page-space URLs, not `/api`.** `/schools/harvard/2024-25/cds.xlsx` is
  human-readable, shareable, and lives next to the page it exports.
  Server-side generation (vs. client-side blob like `/browse`) makes the
  link work without JS, curl-able, and cacheable (`revalidate = 3600`,
  same CDN cache headers as `/snapshots`).
- **Multi-variant schools** (sub-institutional documents) share one workbook;
  a Variant column appears only when there is more than one variant.

## Out of scope (v1) / follow-ups

- **All-years workbook per school** (`/schools/{id}/cds.xlsx`, one column per
  year) — the trend-analysis version; needs a year-pivot layout decision.
- **Server-side `/browse` export** — the backlog's export-pagination item;
  the xlsx writer built here is reusable for it.
- Match-list builder export to XLSX.
- Listing the download URLs in `llms.txt` / friendly-API docs.
