# PRD 035: Calibrated information density across school, year, and browse surfaces

**Status:** Draft  
**Created:** 2026-10-23  
**Author:** Anthony + Gemini  
**Related:** [PRD 002](002-frontend.md), [PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md), [PRD 016](016-academic-positioning-card.md), [PRD 020](020-accessible-cds-table-view.md), [PRD 021](021-ipeds-coverage-layer.md), [Design System](../../web/DESIGN_SYSTEM.md), [Voice](../../web/VOICE.md)

---

## Executive summary

`collegedata.fyi` already has the hardest parts of a high-density research product: canonical 1,105-field CDS extracts, reconstructed section tables ([PRD 020](020-accessible-cds-table-view.md)), a 6,322-school NCES/IPEDS federal baseline ([PRD 021](021-ipeds-coverage-layer.md)), and a queryable browser API ([PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md)).

Where the frontend still loses **Value Density** (time-to-decision) and **Design Density** (Gestalt grouping) is in the surface layer between prose summaries and raw tables:

1. **Year pages (`/schools/[school_id]/[year]`)** render headline admissions and score bands inside up to eight white bordered Tailwind cards ([`KeyStats.tsx`](../../web/src/components/KeyStats.tsx))—a known palette violation ([`DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md) Delta #3) that wastes viewport height, omits yield and test-submission rates, and clashes visually with [`OutcomesBand.tsx`](../../web/src/components/OutcomesBand.tsx) and [`FieldsView.tsx`](../../web/src/components/FieldsView.tsx) immediately below it.
2. **School hub pages (`/schools/[school_id]`)** open with prose ([`ArchiveLead.tsx`](../../web/src/components/ArchiveLead.tsx)) and a document list ([`SchoolDocumentsLedger.tsx`](../../web/src/components/SchoolDocumentsLedger.tsx)) before surfacing structured numbers, while wasting `<Sparkline />` on a synthetic document-count step series (`[1, 2, ... N]`) instead of real multi-year admissions or enrollment trajectories.
3. **The queryable browser (`/browse`, [`SchoolBrowser.tsx`](../../web/src/components/SchoolBrowser.tsx))** already receives `retention_rate`, `pell_rate`, `sat_submit_rate`, `act_submit_rate`, and 25th/50th/75th SAT/ACT percentiles in every `BrowserRow` payload—and exports them to CSV—but hides them from the HTML table, forcing users into a spreadsheet mid-comparison.
4. **Cross-corpus navigation** lacks a keyboard-first index spine (`Cmd+K`), requiring multi-page clicks to jump between schools, CDS years, sections (`§C`, `§H`), or canonical field IDs (`C.905`).

PRD 035 replaces those bottlenecks with four coordinated, brand-faithful upgrades built on **"paper, ink, and one quiet green"**:

- **M1 — Unified `<SchoolFactRibbon />` on year pages (replacing `KeyStats.tsx` and harmonizing `OutcomesBand.tsx`):** One full-width paper-and-ink ledger band with tabular numerals, derived yield, SAT/ACT 25th–75th ranges paired with submission rates, verified `#sec-*` / `#sub-*` anchors into `FieldsView`, and cleaned-up document badges.
- **M2 — High-density `SchoolBrowser` with column presets, 25th–75th score cells, and non-modal inspection drawer:** Surface the already-exported PRD 012 fields without blowing past the 10-column cognitive ceiling by introducing switchable column groups (`Overview` · `Testing & Academic` · `Cost & Aid` · `All`), compressed funnel cells, sticky headers, a `Compact (36px) / Standard (48px)` row density toggle, and a non-modal right-hand inspection drawer.
- **M3 — `<CmdKCatalog />` ("Index Call Desk"):** A global `Cmd+K` / `/` command palette styled like an index-card catalog drawer that fuzzy-jumps to any school (`name`, `alias`, `ipeds_id`), school + year + section (`yale 2025 §h2`), or canonical CDS field (`C.905`).
- **M4 — School hub `<SchoolFactRibbon />` with real multi-year sparklines and Carnegie-scoped federal percentiles:** Reuse the M1 ledger component under the school hub header, backed by real multi-year `yearFacts` sparklines, absolute test-scale range ticks, and (only where backed by the full PRD 021 IPEDS cohort) explicitly labeled Carnegie-peer percentiles.

---

## Problem

### 1. Card chrome and competing grammars on the year page
[`KeyStats.tsx`](../../web/src/components/KeyStats.tsx) renders up to eight `bg-white border-gray-200 rounded-lg` boxes. Besides breaking the warm-cream palette (`--paper: #f1ece1`, `--ink: #1c1e1b`), it:
- separates related funnel counts (`Applications`, `Admitted`, `Enrolled`, `Acceptance Rate`) into disconnected boxes instead of one horizontal calculation;
- omits **Yield** (`Enrolled / Admitted`) and **SAT/ACT submission rates** (`C.901`, `C.902`), even though `values` already holds them;
- sits directly above [`OutcomesBand.tsx`](../../web/src/components/OutcomesBand.tsx) (which uses 34px Newsreader serif KPIs) and [`Badge.tsx`](../../web/src/components/Badge.tsx) (`bg-gray-100 text-gray-700`), creating three incompatible visual grammars above `FieldsView`.

### 2. The browser hides fields it already fetches and filters on
[`SchoolBrowser.tsx`](../../web/src/components/SchoolBrowser.tsx) lets users filter by `Minimum retention` (`retentionMin`), yet **Retention is not a column in the table**. Meanwhile, `sat_composite_p25/p50/p75`, `act_composite_p25/p50/p75`, `sat_submit_rate`, `act_submit_rate`, and `pell_rate` are already returned by `searchBrowserRows` and written out by `downloadCsv()`, but invisible on screen.

However, simply appending 6 more columns to a 10-column table inside a `max-w-5xl` (`1024px`) wrapper creates a worse problem: a 16-column horizontal scroll trap where `Applied`, `Admitted`, and `First-years` consume 300px of horizontal space while repeating `Enroll`, `Accept`, and `Yield`.

### 3. Naive "peer percentile bars" and "filter-set rank shading" lie with skewed denominators
Two common high-density tropes fail on `collegedata.fyi`'s specific data shape:
- **Corpus-wide CDS percentiles are selection-biased:** Only ~558 schools currently populate `school_browser_rows`, heavily skewed toward selective institutions that publish clean CDS files. Ranking a school against "extracted CDS peers" makes a 28% acceptance rate or 1320 SAT look below-average.
- **Page-local or filter-local rank shading shifts under the user's feet:** Because [`SchoolBrowser.tsx`](../../web/src/components/SchoolBrowser.tsx) defaults to `acceptanceMax: "10"` and paginates at `PAGE_SIZE = 50`, coloring cells by rank within the current filter or page renders a 9.8% acceptance rate at the "least selective" end of the color ramp and changes a school's shading when the user clicks `Next`.
- **Polarity ambiguity:** Unlike baseball exit velocity, higher is not always "better" in college data (`avg_net_price`, `acceptance_rate`).

### 4. The school hub hides tabular facts below the fold and wastes `<Sparkline />`
On [`/schools/[school_id]`](../../web/src/app/schools/%5Bschool_id%5D/page.tsx), the only above-the-fold numbers live inside prose sentences in [`ArchiveLead.tsx`](../../web/src/components/ArchiveLead.tsx), and the header `<Sparkline />` plots `archiveHistory(docs)`—a synthetic `[1, 2, ... N]` step line of document counts. Visitors scanning for selectivity, yield, net price, testing, and retention must either parse prose or scroll past the document table.

---

## Goals

1. **Triple scannable above-the-fold information density** on year pages and school hubs while keeping visual groups $\le 4$ for first-time visitors.
2. **Eliminate the CSV round-trip on `/browse`** by surfacing retention, SAT/ACT 25th–75th intervals + submit rates, and Pell share directly in the browser table via calibrated column presets and row density modes.
3. **Preserve strict source provenance and denominator honesty:** never blend CDS (`§C`, `§B`, `§H`) and federal (`Scorecard`, `IPEDS`, `FSA`) numbers without an explicit source tag on the cell; never show a test score midpoint or range without its submission rate when available; never show a percentile without naming the peer group and $N$.
4. **Retire the remaining Tailwind white/gray card debt** in `KeyStats.tsx` and document-variant badges on the year page ([`DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md) Delta #3).
5. **Give power users zero-click navigation velocity** across 6,322 institutions, archived years, and 1,105 CDS field codes via a library-styled `Cmd+K` catalog spine.
6. **Maintain WCAG 2.2 Level AA conformance** across all new ledger, table, drawer, and command-palette interactions ([PRD 020](020-accessible-cds-table-view.md) standards baseline).

## Non-goals

- **No dark-mode-default Bloomberg terminal or neon red/green P&L palettes.** The brand is warm cream paper (`#f1ece1`), near-black ink (`#1c1e1b`), and one quiet forest green (`#3f5b3a`).
- **No black-box composite "School Score" or unlabelled 1–100 percentile sliders** computed against the 558-school CDS subset.
- **No client-side rank shading relative to the current 50-row page slice or active filter set.**
- **No Finviz treemap** in V1.
- **No AG Grid / heavy third-party virtualization bundle** that breaks native HTML `<table>` semantics or screen-reader row/column announcements.

---

## Product principles

1. **Read like a library, not a SaaS dashboard.** Use rules (`.rule`, `.rule-2`, `.rule-d`), tabular numerals (`.nums`, JetBrains Mono), and editorial hierarchy—never drop shadows, glassmorphism, or decorative gauges.
2. **One component grammar across Hub and Year pages.** The summary band at the top of `/schools/[school_id]` and `/schools/[school_id]/[year]` should share the same `<SchoolFactRibbon />` primitive so users learn the spatial layout once.
3. **Intervals over naked midpoints; denominators over naked rates.** Prefer `1470–1560 (68% sub)` over `1515`, and pair derived rates (`Accept`, `Yield`) with their underlying counts or YoY deltas.
4. **Selective compression, not column bloat.** Keep visible table columns $\le 9$ in any default preset; let users switch column lenses (`Overview`, `Testing & Academic`, `Cost & Aid`, `All`) or open a non-modal side drawer for full-record inspection.
5. **Every number links to its section or source.** CDS numbers link to `#sec-C`, `#sub-entrance-exams`, `#sec-B`, or `#sec-H`; federal numbers carry explicit `IPEDS` / `Scorecard` / `FSA` source labels.

---

## Detailed design

### 1. M1 — Year page: replace `KeyStats` + harmonize `OutcomesBand` via `<SchoolFactRibbon />`

#### 1.1 Fix subsection anchor wiring in `FieldsView.tsx`
Before linking summary cells into reconstructed tables, ensure [`FieldsView.tsx`](../../web/src/components/FieldsView.tsx) emits deterministic, documented anchors:
- Section headers already emit `id="sec-C"`, `id="sec-H"`, etc., plus `id="admissions"` and `id="aid"`.
- Wire `SUBSECTION_FRAGMENTS` (`#waitlist`, `#testing`) or stable `#sub-${sub.slug}` anchors (`#sub-c1-first-time-first-year-admission`, `#sub-c9-first-time-first-year-profile`, `#sub-c22-retention-rate`) onto the subsection headings with `scroll-margin-top: 24px`.

#### 1.2 `<SchoolFactRibbon />` layout on `/schools/[school_id]/[year]`
Replace [`KeyStats.tsx`](../../web/src/components/KeyStats.tsx) with a two-band ledger framed by `.rule-2` top/bottom borders and `.rule-d` internal dashed rules on `--paper` / `#faf6ec`:

- **Band A — `§C1 · First-Year Admissions Funnel & Rates` (links to `#sec-C`):**
  - **Acceptance Rate** (primary tabular figure, e.g., `4.8%`, plus YoY delta chip when `priorFacts` exists)
  - **Yield Rate** (`Enrolled / Admitted`, e.g., `69.2%` — newly surfaced from `c1`)
  - **Applied** (`54,563`, right-aligned `.nums`)
  - **Admitted** (`2,619`, right-aligned `.nums`)
  - **Enrolled** (`1,812`, right-aligned `.nums`)
- **Band B — `§C9 · Enrolled Score Bands (25th–75th)` (links to `#sub-entrance-exams`):**
  - **SAT Composite:** `1480–1570` + muted mono caption `72% SUBMITTED · MEDIAN 1530` (using `C.901`, `C.905`, `C.906`, `C.907`)
  - **SAT EBRW / Math split:** compact inline pair `EBRW 730–780 · MATH 750–800`
  - **ACT Composite:** `33–35` + muted mono caption `24% SUBMITTED · MEDIAN 34` (using `C.902`, `C.914`, `C.915`, `C.916`)
  - **Retention (`§B22`):** when extracted in `values`, surface full-time first-year retention (`98% · §B22`).

#### 1.3 Visual alignment with `OutcomesBand.tsx` and `Badge.tsx`
- Migrate the document-format [`Badge`](../../web/src/app/schools/%5Bschool_id%5D/%5Byear%5D/page.tsx) on [`schools/[school_id]/[year]/page.tsx`](../../web/src/app/schools/%5Bschool_id%5D/%5Byear%5D/page.tsx#L316-L319) from `className="bg-gray-100 text-gray-700"` to `.cd-chip`.
- Tighten [`OutcomesBand.tsx`](../../web/src/components/OutcomesBand.tsx) spacing and typography so that `§C` CDS metrics and `§ Federal outcomes` read as two coordinated chapters of the same ledger sheet rather than two unrelated UI kits.

---

### 2. M2 — Browse: high-density `SchoolBrowser.tsx` + non-modal inspection drawer

#### 2.1 Column group presets (respecting the 10-column cognitive threshold)
Add a segmented mono control bar right beside the `Sort` dropdown in [`SchoolBrowser.tsx`](../../web/src/components/SchoolBrowser.tsx):
- **`Overview` (default, 8 columns):** `School` (sticky left) · `Year` · `Enroll` · `Accept (with Applied/Admitted sub-caption in Standard mode)` · `Yield` · `Retention` · `SAT 25–75` · `Net Price` · `Source`
- **`Testing & Academic` (8 columns):** `School` · `Year` · `Accept` · `SAT 25–75` · `SAT Sub %` · `ACT 25–75` · `ACT Sub %` · `Retention` · `Source`
- **`Cost & Aid` (8 columns):** `School` · `Year` · `Enroll` · `Net Price` · `Pell %` · `Accept` · `Yield` · `Retention` · `Source`
- **`All Columns` (12 columns, horizontal scroll with frozen `School` column):** Full wide workbench for desktop analysts.

#### 2.2 Test-score micro-range cells with submit-rate provenance
- Render SAT and ACT columns as tabular `25th–75th` intervals (`1460–1550`, `33–35`) with `sat_composite_p50` / `act_composite_p50` available on hover or in `Testing & Academic` mode.
- Append a compact submit-rate indicator (`68%` in `--ink-3`, or an ochre warning glyph `◦` when `submit_rate < 0.35`) so test-optional distortion is visible pre-attentively without opening the school page.

#### 2.3 Table spatial mechanics & row density toggle
- **Widen container on `/browse`:** Allow the table section to expand to `max-w-7xl` (`1280px`) while keeping the editorial page header at `max-w-5xl`.
- **Row density toggle (`Compact` vs. `Standard`):**
  - `Compact` (default on desktop $\ge 1024\text{px}$): `38px` row height, `15px` serif school name on a single line with inline muted sub-institutional badge and icon-only quality flag tooltip.
  - `Standard`: current comfortable spacing for touch/tablet viewports.
- **Sticky header & horizontal tracking:** Freeze `<thead>` on vertical scroll (`position: sticky; top: 0; z-index: 10; background: var(--paper)`), freeze column 1 (`School`) on horizontal scroll with a `1px solid var(--rule-strong)` right border (no drop shadow), and add a subtle full-row hover tint (`background: var(--paper-2)`).
- **Click-to-sort column headers:** Make numerical `<th>` headers (`Enroll`, `Accept`, `Yield`, `Retention`, `SAT`, `ACT`, `Net price`, `Pell`) directly clickable to toggle sort direction, synced with the `Sort` select box.
- **No page-slice rank shading:** Do not shade cells by their rank within the current 50-row page or active filter set. Instead, apply a quiet `--paper-2` column tint to the **currently sorted column** so the user's eye tracks the active sort spine vertically.

#### 2.4 Non-modal school inspection drawer
Clicking an `Inspect` (`§`) action button in any row (or pressing `Space` when a row is focused) opens a **non-modal right-hand drawer (`360–420px` wide)** modeled on the Discover drawer:
- Displays `<SchoolFactRibbon />` for that row, full SAT/ACT 25–50–75 breakdown + submit rates, enrollment/funnel counts, data quality notes, and direct links to `Open school hub →`, `Open [year] CDS →`, and `Download original PDF/XLSX →`.
- Clicking another row updates the drawer in place without losing table scroll position or active filters.

---

### 3. M3 — `<CmdKCatalog />`: The Library Call-Number Command Spine

Add a global keyboard-first command palette (`Cmd+K` / `Ctrl+K`, plus a `[⌘K · INDEX]` button in `.cd-nav-links`):

1. **Zero-bundle-bloat index strategy:**
   - Preload or lazy-fetch a lightweight client manifest on first `Cmd+K` keydown (or idle prefetch): the active school directory (`school_id`, `school_name`, `state`, `ipeds_id`, `latest_cds_year`, aliases) plus the static 10-section CDS outline (`§A`–`§J`) and top ~60 canonical field queries (`C1`, `C7`, `C9`, `H2`, `H2A`, `B1`, `B22`, `G1`).
2. **Compound call-number grammar:**
   - Typing `bowdoin` → opens `/schools/bowdoin-college`
   - Typing `bowdoin 2024` → opens `/schools/bowdoin-college/2024-25`
   - Typing `bowdoin §h` or `bowdoin aid` → jumps straight to `/schools/bowdoin-college/2025-26#sec-H`
   - Typing `§c9` or `C.905` *while already on a school or year page* → scrolls directly to that section/field on the current page (or navigates to the latest year page at that anchor).
3. **Visual treatment:**
   - Rendered as an index-card catalog overlay (`background: #faf6ec`, `border: 1px solid var(--rule-strong)`, `border-radius: 2px`, no blur/glassmorphism). Results show the school glyph, serif institution name, and right-aligned JetBrains Mono call numbers (`IPEDS 161004 · 2025-26 CDS · §A–§J`).

---

### 4. M4 — School hub (`/schools/[school_id]`): `<SchoolFactRibbon />` with real multi-year sparklines & Carnegie context

1. **Place `<SchoolFactRibbon />` between the school header and `SchoolDocumentsLedger`:**
   - Cap at **6 headline cells**: `Acceptance · §C1`, `Yield · §C1`, `SAT 25–75 · §C9`, `ACT 25–75 · §C9`, `Retention · §B22`, and `Avg Net Price · Scorecard`.
   - Every cell carries an explicit source link: CDS cells link to `/schools/${school_id}/${latestFacts.canonical_year}#sec-C` (or `#sec-B`); Net Price links to `#outcomes` with a `SCORECARD` tag so federal and CDS numbers are never conflated.
2. **Real multi-year `<Sparkline />` trajectories:**
   - Compute 3-to-6-year sparkline arrays from `shownFacts` (gated via `gatedYearFacts` / `c1-hub-gate`) for `Acceptance`, `Yield`, and `Enrolled`.
   - Only render a metric’s `<Sparkline />` when $\ge 3$ comparable years exist for that school (matching [PRD 023](023-admission-visualization-upgrades.md)’s 3-year trend rule).
   - Replace or demote the header’s synthetic `archiveHistory(docs)` step-sparkline so sparklines on the hub always encode real longitudinal data.
3. **Honest peer context (Carnegie / IPEDS denominator only):**
   - Do **not** compute percentile bars against the 558-school `school_browser_rows` table.
   - Instead, for `SAT 25–75` and `ACT 25–75`, render a 48px ink range tick showing where the school's middle 50% sits on the absolute test scale (`400–1600` / `1–36`), paired with the submission rate (`68% sub`).
   - Where peer percentiles are shown (e.g., Acceptance Rate, Net Price, Retention), compute them against the school’s **IPEDS Carnegie classification bucket** from `school_facts_unified` ([PRD 021](021-ipeds-coverage-layer.md)) and print the denominator explicitly (`CARNEGIE R1 · N=146`).

---

## Milestones & shipping sequence

| Milestone | Scope | Key files touched | Why this order |
|---|---|---|---|
| **M1** | `<SchoolFactRibbon />` on year pages (replaces `KeyStats.tsx`, aligns `OutcomesBand.tsx`, fixes `FieldsView.tsx` anchors & `Badge.tsx` gray bug) | `web/src/components/KeyStats.tsx`, `web/src/components/SchoolFactRibbon.tsx`, `web/src/components/FieldsView.tsx`, `web/src/components/OutcomesBand.tsx`, `web/src/app/schools/[school_id]/[year]/page.tsx` | Zero backend dependencies; retires a tracked design-system bug while proving the shared ledger component. |
| **M2** | High-density `SchoolBrowser.tsx` (column presets, SAT/ACT 25–75 + submit %, Retention/Pell columns, Compact 38px mode, sticky header/column, non-modal drawer) | `web/src/components/SchoolBrowser.tsx`, `web/src/lib/browser-search.ts` | Highest immediate Value Density gain; all fields already exist in `school_browser_rows` and CSV export. |
| **M3** | `<CmdKCatalog />` global keyboard index spine (`Cmd+K`) | `web/src/components/CmdKCatalog.tsx`, `web/src/app/layout.tsx`, `web/src/app/api/schools/search/route.ts` | Unlocks resident-expert speed across the whole site while keeping visible nav chrome minimal. |
| **M4** | School hub `<SchoolFactRibbon />` with multi-year `shownFacts` sparklines, score-scale ticks, and IPEDS Carnegie peer context | `web/src/app/schools/[school_id]/page.tsx`, `web/src/lib/school-summary.ts`, `web/src/components/SchoolFactRibbon.tsx` | Builds on M1's component and gates peer context on honest longitudinal and federal denominators. |

---

## Verification & acceptance criteria

1. **Design system & palette audit:**
   - Zero occurrences of `bg-white`, `border-gray-200`, `text-gray-500`, `text-gray-900`, or `bg-gray-100` remain in `KeyStats.tsx` or `schools/[school_id]/[year]/page.tsx`.
   - All numeric cells in `<SchoolFactRibbon />` and `SchoolBrowser.tsx` compute `font-variant-numeric: tabular-nums` and right-align quantities in tables.
2. **Provenance & denominator integrity:**
   - Every metric in `<SchoolFactRibbon />` includes a clickable section anchor (`§C1`, `§C9`, `§B22`) or explicit federal source badge (`SCORECARD`, `IPEDS`, `FSA`).
   - Every SAT/ACT range cell in `<SchoolFactRibbon />` and `SchoolBrowser.tsx` displays or badges the corresponding submission rate (`sat_submit_rate` / `act_submit_rate`) when present, and explicitly prints `Sub % n/a` when absent.
   - `c1-hub-gate` and `gatedYearFacts` rules are respected identically between `<ArchiveLead />`, `<PositioningCard />`, and `<SchoolFactRibbon />` (one number everywhere).
3. **Table ergonomics & accessibility (WCAG 2.2 AA):**
   - Default `Overview` preset in `SchoolBrowser.tsx` fits within a `1280px` desktop viewport without horizontal scrolling.
   - In `All Columns` mode or narrower viewports, the `School` column remains sticky on horizontal scroll, `<thead>` remains sticky on vertical scroll, and keyboard `Tab` focus is never obscured by sticky headers (`scroll-padding` / `scroll-margin`).
   - Non-modal inspection drawer in `SchoolBrowser.tsx` supports `Escape` to close, preserves table scroll position, and announces updates to assistive technology.
   - Mobile viewports ($\le 560\text{px}$) continue to render `BrowserResultCard` cards without horizontal table overflow.
4. **Automated tests:**
   - Unit tests for `<SchoolFactRibbon />` covering full data, test-optional / missing SAT or ACT, missing `priorFacts`, and `administrativeUnit` C1 gating.
   - Playwright e2e specs for `/browse` column preset switching, Compact/Standard density toggle, non-modal drawer inspection, and `Cmd+K` school + section jump.
