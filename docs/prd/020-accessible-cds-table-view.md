# PRD 020: Accessible reconstructed CDS table view

**Status:** Draft
**Created:** 2026-05-07
**Author:** Anthony + Codex
**Related:** [PRD 002](002-frontend.md), [PRD 005](005-full-schema-extraction.md), [PRD 010](010-queryable-data-browser.md), [PRD 012](012-browser-field-expansion-after-v03.md), [PRD 016](016-academic-positioning-card.md), [Architecture](../ARCHITECTURE.md)

---

## Context

The current school-year field view is honest and source-linked, but it renders
extracted CDS values mostly as grouped key/value rows. That is readable for
developers and analysts, but it does not look or behave like the Common Data Set
forms that institutional researchers, counselors, journalists, and accessibility
reviewers expect.

The CDS itself is table-shaped. Families such as B1, C1, C7, C9, H2A, and H6
communicate meaning through row headers, column headers, grouped subheaders,
units, and repeated dimensions. Reconstructing those tables in HTML would make
the site more useful and more credible.

This PRD makes accessibility a first-order requirement. The goal is not "pretty
tables that happen to pass axe." The goal is an HTML CDS view that a college
accessibility office could include in a procurement or public-facing review
without immediate remediation work.

## Standards baseline

Use current primary standards as the target bar:

- **WCAG 2.2 Level AA** as the product conformance target. WCAG 2.2 is the
  current W3C Recommendation and is backward-compatible with WCAG 2.1 and WCAG
  2.0 for covered success criteria.
- **WCAG 2.2 AAA where feasible** for table-specific reading quality, focus
  clarity, target size, and cognitive load. Do not claim full AAA conformance.
- **Section 508 / VPAT readiness.** The implementation should generate enough
  test evidence to complete an Accessibility Conformance Report using ITI VPAT
  2.5Rev. VPAT 2.5 INT includes Section 508, EN 301 549, and WCAG reporting
  tables; the WCAG and INT editions include WCAG 2.2 criteria.
- **ADA Title II compatibility.** The 2024 DOJ Title II web rule targets WCAG
  2.1 Level AA for state/local government web content. WCAG 2.2 AA should meet
  that technical bar while giving us a newer standard for product QA.

Primary references:

- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- W3C WCAG 2.2 publication history: https://www.w3.org/standards/history/WCAG22/
- W3C WCAG 2.2 ISO/IEC 40500:2025 announcement: https://www.w3.org/press-releases/2025/wcag22-iso-pas/
- ITI VPAT: https://lists.itic.org/policy/accessibility/vpat
- Section508.gov ACR/VPAT guidance: https://www.section508.gov/sell/how-to-create-acr-with-vpat/
- ADA.gov Title II web rule fact sheet: https://www.ada.gov/resources/2024-03-08-web-rule/

## Problem

There are three product problems.

### 1. Extracted fields lose table context

Key/value rendering hides important structure:

- C1 applicant/admit/enroll rows by gender/status.
- C7 importance levels as a matrix.
- C9 SAT/ACT percentile columns.
- B1 enrollment rows by student group and attendance status.
- H2A aid rows by recipient group and dollar amount.

The data is present, but users have to mentally reconstruct the table.

### 2. Accessibility cannot be inferred from visual polish

Complex data tables can be visually beautiful and still fail screen-reader,
keyboard, zoom, forced-colors, and cognitive accessibility review. Common failure
classes:

- div-based tables with no native semantics
- sticky headers that obscure focus
- responsive card transforms that destroy row/column relationships
- multi-level headers without `scope` or `headers`
- missing captions and summary context
- horizontal scrolling traps
- color-only state encoding
- virtualized table rows that disappear from assistive technology

### 3. VPAT review requires evidence, not intent

If the site becomes useful to colleges, school districts, public universities, or
state agencies, accessibility review will ask for documented test methods and
known exceptions. We need to build the feature so that evidence can be produced
as part of normal CI and release QA.

## Goals

1. Render the most-used CDS subsections as real HTML tables with faithful row,
   column, unit, and section structure.
2. Preserve a fallback key/value rendering for long-tail or unsupported
   subsections.
3. Meet WCAG 2.2 AA for the new view before launch.
4. Produce VPAT/ACR-ready test artifacts for the reconstructed table feature.
5. Improve usability for all users: fast scanning, copy/paste, print, source
   review, mobile reading, and high-zoom use.
6. Keep data provenance visible: every reconstructed table must point to the
   source CDS document and extraction metadata.

## Non-goals

- No claim of full WCAG AAA conformance.
- No legal certification or "VPAT certified" claim. VPAT is a reporting format,
  not a certification.
- No custom ARIA grid for static data tables.
- No spreadsheet editor or inline editing.
- No PDF recreation of the CDS.
- No attempt to reconstruct every CDS subsection in v1.
- No hiding of missing data to make tables look complete.

## User stories

1. A screen-reader user can navigate C1 admissions rows and hear the correct row
   and column context for each value.
2. A keyboard-only user can move through a long school-year page without focus
   being hidden by sticky UI or trapped in horizontal scrolling.
3. A low-vision user at 400% zoom can read every table without two-dimensional
   scrolling becoming the only path.
4. A college accessibility reviewer can inspect the page and see native table
   semantics, captions, keyboard behavior, and automated/manual test evidence.
5. A journalist can copy a reconstructed table into a spreadsheet and preserve
   row/column meaning.
6. A maintainer can add a new subsection layout descriptor without inventing new
   rendering code.

## Product principles

1. **Native semantics first.** Use `<table>`, `<caption>`, `<thead>`,
   `<tbody>`, `<th scope>`, and `headers/id` before considering ARIA.
2. **Source fidelity without PDF mimicry.** Recreate the meaning of the CDS
   table, not the exact PDF typography.
3. **Accessibility is a release gate.** A table layout descriptor is not done
   until it has automated and manual accessibility coverage.
4. **No responsive semantic collapse.** Mobile layouts may become vertically
   stacked, but they must preserve header associations and reading order.
5. **Missing means visible.** Known-but-missing values render as "Not reported"
   or "Not provided" with schema-aware reasoning.
6. **Evidence travels with the feature.** CI output, manual SR notes, and known
   exceptions should be enough to draft an ACR section later.

## What ships in v1

### Year and schema scope

V1 is strongest for **2024-25 and 2025-26** because those are the years with
canonical Answer Sheet schemas and stable question numbers in this repo.

Older years should not be blocked from the feature, but they launch with a lower
contract:

- If a document's extracted values have enough section/subsection and field
  metadata, render observed values in accessible table or list form.
- Do not render schema-known missing cells for older years until that year's
  structural schema has been mapped to canonical field identity.
- Do not imply that an older reconstructed table is complete just because a cell
  is absent.

Schema work that improves older-year support:

- Completed: generate the missing 2024-25 structural schema from the template
  already in `schemas/templates/`.
- Completed: add conservative canonical overlays for 2019-20 through 2023-24
  C1/C9 by matching structural row/column labels against the 2025-26 canonical
  schema and preserving ambiguous drift as explicit unmapped QA reasons.
- Add any older official XLSX templates only when they expand the historical
  product surface we actually intend to render.

### Reconstructed table renderer

Add a reusable table reconstruction layer for high-value CDS subsections:

- B1: enrollment by attendance status and gender
- B2/B3: race/ethnicity and degree-seeking cohorts where extraction dimensions
  are reliable
- C1: first-year applicants, admits, and enrolled students
- C7: application-factor importance matrix
- C9: SAT/ACT percentile and score-submission rows
- C10/C11/C12: class rank and GPA summary rows
- H1/H2/H2A/H6: financial aid recipient/dollar grids
- J1: degrees conferred by discipline, if current dimensions support it cleanly

Long-tail subsections continue to render as accessible key/value groups.

### Layout descriptor model

Introduce table layout descriptors keyed by subsection:

```ts
type CdsTableLayout = {
  subsection: string;
  title: string;
  caption: string;
  sourceNote?: string;
  rows: DimensionSelector[];
  columns: DimensionSelector[];
  cells: CellSelector[];
  missingPolicy: "schema_known" | "only_observed";
  accessibility: {
    complexity: "simple" | "multi_header";
    requiresHeadersId: boolean;
    testFixtureSchoolIds: string[];
  };
};
```

The renderer consumes normalized field values plus schema metadata. It does not
hard-code Harvard/Yale/Dartmouth table shapes.

### Field metadata threading

Thread existing schema dimensions through the frontend field model:

- section
- subsection
- question number
- row label
- column header
- category
- cohort
- student group
- gender
- residency
- unit load
- value type/unit
- source producer and producer version

If the extractor has the dimension but the frontend type drops it, this PRD
should fix the frontend type. If the extractor does not yet populate the
dimension consistently, that subsection stays out of reconstructed v1.

### Accessible missing-data rendering

Render schema-known missing cells explicitly:

- `Not reported` for fields expected in that CDS year but absent.
- `Not applicable` when the source value or schema semantics support it.
- `Not available in this CDS version` when the field did not exist in that
  year's schema.

Do not use blank cells for meaningful absence.

### Table controls

Each reconstructed subsection gets:

- table caption visible or screen-reader-visible depending on design
- source/document link
- extraction provenance line
- copy table button
- CSV download for that subsection
- "View as list" fallback toggle for users who prefer linear reading
- print-friendly CSS

Controls must be keyboard reachable and have accessible names.

## Accessibility requirements

### Semantic HTML

- Use native `<table>` for all reconstructed tables.
- Use `<caption>` for table title/context.
- Use `<th scope="col">`, `<th scope="row">`, or `headers/id` for multi-level
  header tables.
- Do not use ARIA roles to imitate tables unless native table semantics are
  impossible.
- Do not virtualize reconstructed table rows.
- Preserve DOM order equal to reading order.

### Keyboard and focus

- Every interactive control is reachable by Tab and operable by keyboard.
- Focus indicators meet WCAG 2.2 AA and should satisfy 2.4.13 Focus Appearance
  where feasible.
- Sticky headers/toolbars must not obscure focused controls or cells.
- Horizontal overflow regions, if any, must be reachable, labeled, and escapable.
- No keyboard trap in table scrollers, copy controls, menus, or toggles.

### Zoom, reflow, and responsive behavior

- At 320 CSS px width and 400% zoom, content must reflow without loss of
  information or function.
- Prefer stacked row groups over mandatory two-axis scrolling on small screens.
- If horizontal scrolling remains for a specific complex table, provide an
  equivalent "View as list" mode that preserves row/column associations.
- Text spacing overrides must not clip or overlap table content.

### Color, contrast, and visual states

- Text and meaningful icons meet WCAG contrast requirements.
- Color is never the only cue for missing, changed, low-confidence, or derived
  values.
- Support `forced-colors: active`.
- Support dark mode only if it preserves contrast and visible focus.

### Screen-reader behavior

Manual smoke targets:

- VoiceOver + Safari on macOS
- NVDA + Firefox on Windows
- JAWS + Chrome where available through external review or a borrowed test pass

Required task checks:

- Navigate to a school-year page.
- Jump by heading to a reconstructed section.
- Read table caption.
- Move through C1 cells and hear row/column context.
- Move through C9 percentile cells and hear test/percentile context.
- Activate "View as list" and return to table view.
- Activate source link and copy/download controls.

### Cognitive and plain-language requirements

- Table captions must explain what the table is, not merely repeat "C1".
- Abbreviations such as CDS, SAT, ACT, and FAFSA get sensible expansion or
  surrounding context.
- Missing values use consistent language.
- Avoid dense explanatory prose inside the table itself; put methodology in a
  nearby details region or linked page.

## VPAT / ACR evidence requirements

Before launch, produce an accessibility evidence bundle under
`.context/reports/accessibility/` or `docs/accessibility/`:

- tested commit SHA
- tested URLs
- browser/assistive technology matrix
- automated axe/Playwright results
- keyboard walkthrough notes
- screen-reader walkthrough notes
- known exceptions
- screenshots at desktop, mobile, 200% zoom, 400% zoom, and forced-colors where
  feasible
- mapping from feature behavior to WCAG 2.2 AA criteria most likely implicated
  by data tables

This is not a formal ACR yet, but it should make a future VPAT 2.5Rev INT ACR
straightforward.

## Architecture

```
cds_artifacts canonical_json
   |
   | existing projection
   v
cds_fields long-form values + schema metadata
   |
   | new frontend typing / query helpers
   v
FieldValue[] with dimensions
   |
   | new pure reconstruction layer
   v
CdsTableModel[]
   |
   | new accessible renderer
   v
<CdsTableView>
   +- native table mode
   +- list mode
   +- copy / CSV / source controls
```

## Critical files

New:

- `web/src/lib/cdsTableLayouts.ts`
- `web/src/lib/cdsTableModel.ts`
- `web/src/lib/cdsTableModel.test.ts`
- `web/src/components/CdsTableView.tsx`
- `web/src/components/CdsTableListView.tsx`
- `web/src/components/CdsSectionView.tsx`
- `web/tests/accessibility/cds-table-view.spec.ts`
- `docs/accessibility/cds-table-view-test-plan.md`

Modified:

- `web/src/lib/types.ts`
- `web/src/lib/queries.ts`
- `web/src/app/schools/[school_id]/[year]/page.tsx`
- `web/src/app/tokens.css`
- `docs/ARCHITECTURE.md`
- `docs/backlog.md`

## Implementation plan

### Phase 0: accessibility design proof

Build static fixtures for C1, C7, C9, and H2A using known extracted data. Render
them in a sandbox route or Storybook-like local page. Validate semantics before
integrating with live data.

Exit gate:

- native table markup reviewed
- list fallback reviewed
- keyboard path clean
- VoiceOver/Safari smoke pass complete
- no axe violations in fixture route

### Phase 1: table model and descriptor layer

Implement pure table-model generation from `FieldValue[]`.

Exit gate:

- unit tests cover C1, C7, C9, H2A, missing values, and schema-version absence
- descriptors are data-only
- unsupported subsections fall back to existing key/value rendering

### Phase 2: production page integration

Replace selected FieldsView subsections with reconstructed tables on the
school-year page.

Exit gate:

- page works for at least Harvard, Yale, Dartmouth, Michigan, and one Tier 1 XLSX
  publisher
- no existing source/document links regress
- list fallback available per reconstructed table

### Phase 3: accessibility QA and evidence bundle

Run automated and manual accessibility checks.

Exit gate:

- Playwright + axe checks pass
- keyboard-only checklist passes
- VoiceOver/Safari pass
- NVDA/Firefox pass, or external/manual review issue filed as launch blocker
- evidence bundle committed or attached to release notes

### Phase 4: expand subsection coverage

Add descriptors for B1/B2/B3/C10/C11/C12/H1/H2/H6/J1 only after the first four
families pass accessibility QA.

## Test plan

Automated:

- unit tests for table model generation
- `@axe-core/playwright` checks for school-year pages with reconstructed tables
- Playwright keyboard traversal tests
- forced-colors screenshot smoke where Playwright/browser support allows
- mobile and 400% zoom visual regression checks
- CSV/copy output snapshot tests

Manual:

- VoiceOver/Safari task walkthrough
- NVDA/Firefox task walkthrough
- keyboard-only walkthrough
- browser zoom to 200% and 400%
- text-spacing bookmarklet or equivalent CSS override
- print preview smoke
- copy/paste into spreadsheet

Data-quality:

- compare reconstructed C1/C9/H2A tables against source PDFs for 10 schools
- include Tier 1 XLSX, Tier 2 fillable PDF, Tier 4 flat PDF, and Tier 6 HTML
  sources in the fixture set
- verify missing values are not introduced by the renderer

## Launch criteria

- WCAG 2.2 AA automated checks pass for representative school-year pages.
- Manual keyboard and screen-reader checks pass for C1, C7, C9, and H2A.
- No known critical or serious accessibility defects remain.
- Every reconstructed table has table mode and list mode.
- Every reconstructed table has source/provenance context.
- Evidence bundle exists and is linked from release notes.
- Existing school-year page performance remains acceptable.

## Risks

### Multi-level table complexity

Some CDS tables have nested or repeated headers. Use `headers/id` when `scope`
is insufficient. Avoid clever CSS that makes the DOM differ from the visual
order.

### Mobile two-axis scrolling

Complex tables may not fit small screens. The list fallback is required, not a
nice-to-have.

### False completeness

Reconstructed tables may look official enough that users assume every blank is
school-reported. Use explicit missing labels and schema-aware absence.

### Accessibility tooling blind spots

axe will not prove screen-reader usability. Manual assistive technology checks
are launch blockers.

### Design temptation

Do not trade semantic table markup for decorative card layouts. The reconstructed
tables are a data product, not a marketing surface.

## Open questions

1. Should list mode be the default on mobile for complex tables?
2. Should the accessibility evidence bundle live in `docs/accessibility/` or only
   as release artifacts under `.context/reports/`?
3. Do we want an explicit public accessibility statement page before this ships?
4. Which schools form the minimum fixture set for VPAT-style evidence?
5. Should "copy table" copy visible labels or canonical field IDs as an optional
   second format?

## Suggested first slice

Start with **C1 and C9 only**.

Reason:

- they are central to PRD 019 and high-search admissions use cases
- the tables are small enough to make accessibility review tractable
- row/column semantics matter a lot
- extraction coverage is already a focus area, so renderer bugs will be easy to
  distinguish from extractor gaps

Once C1/C9 pass the accessibility bar, add C7 and H2A.
