# PRD 016B Miss Spot Audit

Generated after the 2026-05-02 Phase 0 rerun. IvyWise is used only as a
cross-check oracle, not as product data or gate input.

## Current Gate State

- Rows audited: `476`
- ED-count answerability: `90 / 476` (`18.9%`)
- ED-offered answerability: `58 / 69` (`84.1%`)
- Top-200 ED-offered answerability: `38 / 45` (`84.4%`)
- Verifier rejections: `4`, all `ed_admitted_gt_ed_applicants`

The draft 70% top-200 ED-offered gate is still cleared after suppressing
verifier-rejected count pairs and clearing stale Tier 4 C21/C22 values before
rerunning the cleaner.

## Fixes Applied During Spot Audit

- Cleared stale Tier 4 C21/C22 selected values before overlaying the refreshed
  cleaner output in the audit. Without this, old `C.2101=true` values survived
  when the improved cleaner intentionally emitted no ED flag.
- Stopped rejecting ED counts against browser `admitted=0`, because those rows
  represent missing/invalid C1 browser aggregates, not a real zero-admit class.
- Tightened the C21 value-only count fallback so schema years like `2024` /
  `2025` and boilerplate `2006-2007 cycle` text do not become ED counts.
- Confirmed valid count values in the low 2000s, such as Tulane's `2077 / 1209`,
  still extract.

## Top-200 ED-Offered Misses

| School | Producer | Audit Read | Spot-Audit Classification | Recommendation |
|---|---|---|---|---|
| Stanford University | tier4_docling | `ed_offered=true`, no counts | False-positive C21 caused by Docling section contamination from C13-C19. Stanford is an REA school, not institution-level ED. | Add a later C21-specific boundary/false-positive guard; not a gate blocker. |
| San Jose State University | tier4_docling | counts `3 / 15`, verifier rejected | Date-like values leaked into C21 count fallback. Suppressed correctly by verifier. | Keep suppressed; consider an additional "tiny pair with no ED evidence" guard. |
| UNC Chapel Hill | tier4_docling | counts `3 / 15`, verifier rejected | Same date-like leak class as SJSU. IvyWise cross-check shows EA, not ED. | Keep suppressed; likely should become `ed_offered=false/none` after stronger C21 boundary logic. |
| George Washington University | tier2_acroform | `ed_offered=true`, no counts | Not Tier 4. AcroForm extraction/mapping gap. | Track under Tier 2 C21 parity, not Tier 4 cleaner. |
| Texas Christian University | tier4_docling | ED yes, no counts | Docling markdown has ED yes and dates, but no applicant/admit values in the C21 block. | Needs source PDF text/table fallback or OCR; regex cleaner has no value to extract. |
| Lehigh University | tier4_docling | ED yes, no counts | Docling markdown has ED yes, but no count values. Appears twice in top-200 due duplicate browser rows. | Needs source PDF fallback; also inspect duplicate row/projection issue separately. |

## IvyWise Cross-Check Misses

These are useful QA leads, but not all are product misses because IvyWise can
include program-specific early rounds or prior-year rates.

| School | Classification | Notes |
|---|---|---|
| USC | Cross-check mismatch, likely not CDS product miss | IvyWise text says ED is Marshall School of Business only. CDS institution-level C21 appears no/blank, so do not force ED counts into product data. |
| UPenn | Source/OCR gap | Current Docling markdown does not expose a C21 section. Needs PDF text/OCR fallback. |
| Case Western Reserve | Source/OCR or layout gap | C21 has no clear ED answer/count values in markdown, while C22 values are visible. Needs PDF fallback. |
| Dartmouth | Layout-shift gap | ED labels appear before C22, but the value block lands under C22. Could be parser-salvageable, but source PDF/table fallback is safer. |
| American | Layout-shift + checkbox-font gap | Values appear after C22 with unusual glyphs. Could be parser-salvageable, but high risk without page/table geometry. |
| Fairfield | Layout-shift gap | ED value row appears before EA values but after a C22 header. Parser salvage possible with care. |
| Wellesley | Layout-shift gap | ED dates/counts appear after C22 header. Parser salvage possible, but needs geometry/page context. |
| Rochester | Source/OCR gap | Markdown has ED prose and image placeholders, but not the count values. Needs PDF/OCR fallback. |
| Oberlin | Source/OCR gap | Snippet hits table of contents, not actual C21 values. Needs better page localization/PDF fallback. |
| GWU | Tier 2 gap | Not Tier 4; AcroForm extraction/mapping needs C21 count parity. |
| TCU / Lehigh | Source value gap | ED offered is clear, counts are not present in markdown. Needs PDF text/table fallback. |

## Verifier Rejections

| School | Extracted Pair | Classification |
|---|---:|---|
| San Diego State University | `3 / 15` | Date-like false pair; suppressed. |
| San Diego State University duplicate | `3 / 15` | Same duplicate/source row class. |
| San Jose State University | `3 / 15` | Date-like false pair; suppressed. |
| UNC Chapel Hill | `3 / 15` | Date-like false pair; suppressed. |

The remaining verifier rejections are all suppressed and should not block the
card. The best cleanup is a conservative count fallback guard that avoids
inferring ED counts from tiny date-like pairs when C21 lacks a strong ED-count
value context.

## Recommendation

Proceed past Phase 0. The gate clears with conservative verifier suppression.
The next extraction-quality work should not be more broad regex inside Tier 4;
the remaining high-value misses mostly need page-localized PDF text/table
fallback or Tier 2 AcroForm C21 parity.
