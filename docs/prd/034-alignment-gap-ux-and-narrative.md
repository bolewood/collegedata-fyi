# PRD 034: Alignment Gap UX and Narrative Overhaul

**Status:** Approved / In Implementation (2026-10-04)  
**Author:** Anthony Showalter (with Gemini)  
**URL:** `/recipes/alignment-gap`  
**Related:** [`docs/recipes/alignment-gap.md`](../recipes/alignment-gap.md), [`web/src/app/recipes/alignment-gap/page.tsx`](../../web/src/app/recipes/alignment-gap/page.tsx), [`web/src/components/AlignmentGapMeritChart.tsx`](../../web/src/components/AlignmentGapMeritChart.tsx), [`web/src/components/AlignmentGapChart.tsx`](../../web/src/components/AlignmentGapChart.tsx), [`web/src/lib/alignment-gap-recipe-analysis.ts`](../../web/src/lib/alignment-gap-recipe-analysis.ts)

---

## 1. Executive Summary

The Alignment Gap recipe brings together three disparate datasets—**College Scorecard** (graduate debt and 10-year earnings), **Common Data Set H2A** (non-need merit aid), and **IPEDS** (endowments and instructional spend).

The central finding is explosive:

> **At 61% of colleges where graduates carry above-average federal loan debt, the institution awards more in non-need merit scholarships per first-year student than it would take to eliminate the excess debt burden entirely.**

This exposes a fundamental choice in higher education enrollment management: colleges often prioritize discounting tuition for affluent or high-scoring applicants to drive admissions rankings and revenue, even while their graduating seniors accumulate burdensome debt.

However, the current page ([`/recipes/alignment-gap`](https://www.collegedata.fyi/recipes/alignment-gap)) falls short of its potential because:
1. **The narrative is defensive and academic:** The text leads with data disclaimers and mechanical definitions rather than the human reality of the trade-off.
2. **Figure 1 is visually distorted:** Plotting a logarithmic X-axis against a linear Y-axis warps the 1:1 parity line (`merit spend = gap`) into an exponential "hockey stick" rather than an intuitive diagonal boundary.
3. **Screen real estate is squandered:** Two-thirds (67%) of the vertical chart height is consumed by colleges with negative alignment gaps (i.e. colleges with healthy, below-median debt), compressing the 120 problem colleges into a narrow, crowded horizontal band.
4. **Interaction is janky:** Competing hover hit tests cause tooltips to jitter in dense dot clusters; search only opens an ephemeral tooltip without highlighting the dot; and the two charts operate in total isolation.

PRD 034 delivers a comprehensive overhaul of the copy, visual math, and interaction design.

---

## 2. Plain-English Editorial Strategy

### 2.1 The Lead Narrative
- **Current opening:** "College affordability data lives in several different places... The starting point is debt burden: the share of median earnings that would go toward federal student-loan payments each year..."
- **New opening:** Lead directly with the tension:
  > Many colleges leave their graduates with heavy debt. At the same time, many of those same colleges hand out thousands of dollars in "merit" scholarships to recruit students who don't have financial need.
  >
  > What if colleges used that merit money to lower debt for everyone instead?
  >
  > By joining federal student debt records with Common Data Set merit aid, we found that **at 61% of colleges with above-average debt, the freshman merit aid budget alone is larger than the entire debt gap.**

### 2.2 Plain-English Definition of the "Alignment Gap"
Replace dense formulas with a clear 3-step explanation:
1. **The Benchmark:** At a typical college in this dataset, federal loan payments consume **4.4%** of a graduate’s salary 10 years out.
2. **The Excess:** If a college’s grads pay 6% or 7% of their earnings toward debt, that is an above-average burden.
3. **The Alignment Gap:** How much less would each student need to borrow per year of college to bring loan payments back down to that 4.4% benchmark? If a school's gap is $2,000/year, its graduates leave with roughly $8,000 in excess debt.

### 2.3 De-jargoned Region and Quadrant Badging
- **Figure 1 Regions:**
  - *Region A:* **Merit aid could wipe out the debt gap** (73 schools; e.g. Quincy, DePauw, Beloit).
  - *Region B:* **Debt gap dwarfs merit aid** (47 schools; e.g. Kentucky State, Incarnate Word).
  - *Region C:* **No debt gap / Healthy burden** (103 schools; e.g. Bowdoin, Georgia Tech).
- **Figure 2 Quadrants:**
  - *Quadrant I:* **High Debt · Wealthy Endowment** (Hollins, Pratt).
  - *Quadrant II:* **High Debt · Low Endowment** (Bennington, Baker).
  - *Quadrant III:* **Low Debt · Wealthy Endowment** (Grinnell, Princeton, Stanford).
  - *Quadrant IV:* **Low Debt · Career / High-ROI** (Bentley, Babson).

### 2.4 Vivid Case Study: Bard vs. Grinnell
Frame Bard vs. Grinnell directly around their parallel SAT profiles (~1420) and wildly divergent balance sheets:
- Grinnell: $2.4M endowment per student, $22k net price, 3.1% debt burden.
- Bard: $48k endowment per student, $43k net price, 6.7% debt burden.
Highlight both schools visually on Figure 2 with dedicated callouts.

---

## 3. Visualization Architecture & UX Fixes

### 3.1 Figure 1: True Diagonal & Dedicated Baseline
1. **True 45° Parity Line:**
   - In the positive-gap region ($Gap > 0$), merit spend and alignment gap are plotted in synchronized log scale so that $y = x$ (`merit spend = annual gap`) renders as a clean, intuitive, straight 45-degree diagonal.
   - Points below the line: Merit Aid > Debt Gap.
   - Points above the line: Debt Gap > Merit Aid.
2. **Dedicated "No Debt Gap" Shelf:**
   - Instead of stretching the linear axis down to -$8,000, colleges with debt burden $\le 4.4\%$ (Gap $\le 0$) are anchored on a dedicated horizontal base shelf ("At or Below Median Debt Burden"), mirroring the vertical "$0 Merit Aid" rail on the left.
   - This expands the vertical height for positive-gap colleges from **33% to over 80%**, eliminating dot overcrowding.
3. **Semantic Color Scheme:**
   - Dots are colored by their narrative status:
     - **Forest Green:** Merit aid exceeds the debt gap.
     - **Ochre / Amber:** Debt gap exceeds merit aid.
     - **Slate Gray:** Zero merit aid awarded (on the $0 rail).
     - **Muted Ink:** Below-median debt burden (on the base shelf).
   - Legend glyphs are updated to match SVG dots (circles, not square blocks).

### 3.2 Figure 2: Endowment vs. Debt Burden
1. **Balanced Vertical Compression:**
   - Truncate the negative gap floor gracefully so high-debt colleges have substantial vertical resolution.
2. **Permanent Callout Anchors:**
   - Highlight Bard and Grinnell with distinct badge rings so the reader can visually verify the case study without hunting.

### 3.3 Interactive Upgrades
1. **Unified Cross-Chart School Selection:**
   - Selecting or searching a school highlights that school across **both Figure 1 and Figure 2** simultaneously.
2. **Interactive Worked Examples Table:**
   - Clicking or hovering a school in the worked examples table highlights its point on the scatter charts.
   - Standardize table columns across both groups (School, Debt Gap/yr, Merit Spend/yr, Merit Share, Avg Grant, Net Price).
3. **Click-to-Pin Tooltip:**
   - Allow users to click a dot or table row to pin the tooltip card open, preventing hover dismissal on mobile or trackpads.

---

## 4. Implementation Plan & Milestones

- **M0: Narrative & Editorial Rewrite**
  - Update [`page.tsx`](../../web/src/app/recipes/alignment-gap/page.tsx) with plain-English lede, 3-step alignment gap explainer, and rebadged takeaways.
- **M1: Figure 1 Chart Engine Overhaul**
  - Update [`AlignmentGapMeritChart.tsx`](../../web/src/components/AlignmentGapMeritChart.tsx) with true 45° diagonal parity, base shelf for zero-gap schools, and semantic coloring.
- **M2: Figure 2 & Case Study Callouts**
  - Update [`AlignmentGapChart.tsx`](../../web/src/components/AlignmentGapChart.tsx) with balanced axis scaling and Bard/Grinnell highlighting.
- **M3: Interactive Cross-Chart State & Table Sync**
  - Connect school search and worked example tables to chart selection state in [`page.tsx`](../../web/src/app/recipes/alignment-gap/page.tsx).
- **M4: Tests & Verification**
  - Update unit tests in [`alignment-gap-copy.test.ts`](../../web/src/lib/alignment-gap-copy.test.ts) and verify Playwright specs in [`alignment-gap-recipe.spec.ts`](../../web/tests/alignment-gap-recipe.spec.ts).
