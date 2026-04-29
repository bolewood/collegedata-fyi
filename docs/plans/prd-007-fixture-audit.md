# PRD 007 M0 — DOCX fixture audit

**Captured:** 2026-04-28
**Source corpus:** live `cds_documents` (3,924 rows), `cds_artifacts` source bytes
**Fixtures saved:** `.context/tier3-docx-fixtures/` (gitignored — 18 file copies, 8 distinct sha256)

> **Outcome (2026-04-28):** This audit drove the decision to *not* build Tier 3
> Lane A. Benchmarking on Kent State (the only SDT-preserving publisher) showed
> Tier 4 on a Word-rendered PDF reaches 450 canonical fields vs a Lane A
> prototype's 492 (9% gap). PRD 007 is paused; the M1 inner-ZIP sniffer landed
> because Stanford and JMU still need correct routing. If a second
> SDT-preserving DOCX publisher appears, revisit. The text below is the
> empirical audit that fed the decision and should be read as evidence, not as
> a forward plan.

## Headline

| Class | Distinct files | Schools / rows |
|---|---|---|
| SDT-preserving filled CDS (Lane A target) | 1 | 8 (Kent State campuses, share one file) |
| Table-only filled CDS (Lane B target) | 2 | 1 (James Madison, 2024-25 + 2025-26) |
| Wrong-file Summary of Changes (Lane A reject → `docx_not_cds`) | 4 | 7 rows (4 schools share `ed901a128aef`; 3 VT _Changes) |
| Misrouted PDF posing as docx (sniffer fix) | 1 | 1 (Stanford 2025-26) |

## Per-fixture detail

### Class A: SDT-preserving (Lane A primary target)

| File | sha256 | Size | `<w:sdt>` | Unique `w:tag` | Notes |
|---|---|---|---|---|---|
| `kent_state_family/kent-state-university-at-*_2025-26_9de3d32287ee.docx` | `9de3d32287ee…` | 271 KB | 828 | 827 | One physical file shared by 8 Kent campuses. First 8 tags: `a1_name_of_college_or_university`, `a1_street_address_line_1`, `a1_city`, `a1_state`, `a1_zip`, `a1_country`, `a1_main_institution_phone_number_area_code`, `a1_main_institution_phone_number` — exact match to schema `word_tag` values. Document body contains "Kent State" but no per-campus disambiguator like "Trumbull". |

**Expected extraction path:** Lane A SDT.
**Expected min mapped field count:** ≥ 750 (with ~70 expected unmapped due to schema-version drift to be quantified during M2).
**Hand-check candidates (will pin in M2 unit tests):** A.1 institution name, B.1 first-time first-year applicants by gender, C.1 admit yield, F.1 student services counts. We'll verify a sampler of 5-10 once Lane A reads.
**Discovery follow-up:** the 8 Kent campus rows all point at `https://www-s3-live.kent.edu/.../TU%20CDS_2025-2026-Final` (no extension, "TU" suggests Trumbull). Either the campuses each filed the same group-level CDS or the discovery pipeline mass-attributed one file to all 8. Tier 3 will produce one canonical extract; the multi-school attribution problem is a discovery PRD issue, not Tier 3's. Filing as backlog candidate.

### Class B: Table-only filled CDS (Lane B fallback target / M4 spike)

| File | sha256 | Size | `<w:sdt>` | `<w:tbl>` | `<w:tr>` |
|---|---|---|---|---|---|
| `candidate_real_cds/james-madison-university_2024-25_2b163f85be95.docx` | `2b163f85be95…` | 326 KB | 0 | 131 | — |
| `candidate_real_cds/james-madison-university_2025-26_a79bfa367730.docx` | `a79bfa367730…` | 905 KB | 0 | 48 | 371 |

Neither file has the literal string "Common Data Set" in `word/document.xml` (it likely lives in headers/footers — must check `word/header*.xml` for year detection). Confirms PRD 007 Saint Louis-style hypothesis: real CDS but SDTs stripped.

**Expected extraction path:** Lane A produces 0 mapped, falls through to `docx_no_sdts_but_tables`. Lane B (M4 spike) decides whether Docling DOCX → Tier 4 cleaner reaches usable field counts.

### Class C: Wrong-file Summary of Changes (Lane A → `docx_not_cds`)

| File | Size | Schools attributed |
|---|---|---|
| `wrong_file_changes/*_ed901a128aef.docx` | 326 KB | adams-state, aims-community-college, albany-state, upenn (4 schools) |
| `wrong_file_changes/virginia-tech_2016-17_e3260bff554b.docx` | 19 KB | virginia-tech |
| `wrong_file_changes/virginia-tech_2017-18_c0baf5359794.docx` | 18 KB | virginia-tech |
| `wrong_file_changes/virginia-tech_2019-20_8b33b6096a0b.docx` | 28 KB | virginia-tech |

All have 0 `<w:sdt>` and 0 `<w:tag>`. Source URLs end in `…Changes.docx` or `…Summary-of-Changes….docx`. Lane A should classify as `docx_not_cds` based on either filename pattern OR the body containing "Summary of Changes" without a CDS section header. Detection rule TBD in M2; safe default is "no SDTs + URL contains '_changes' or '-changes'".

### Class D: Sniffer fix needed (no DOCX action, M1 reroute)

| File | bytes magic | Real format |
|---|---|---|
| `candidate_real_cds/stanford_2025-26_609e69ef854b.docx` | `%PDF-1.7` | PDF (Tier 4 candidate) |

The discovery pipeline routed this as `source_format='docx'` despite the bytes being a PDF. The current `sniff_format_from_bytes` only runs when `source_format` is null. M1 sniffer fix should flag any disagreement between stored `source_format` and bytes magic; Stanford's row will reroute to `pdf_flat` once requeued.

## What this means for milestones

**M1 (next):** Inner-ZIP sniffer is the right fix and unlocks Stanford reroute as a free side effect. DOCX year detection should also read `word/header*.xml`, not only `word/document.xml`, since JMU's title isn't in the body.

**M2:** Kent State's 828-tag fixture is enough to validate Lane A end-to-end. Hand-check a slice; the 1 unmapped tag is a free signal that the schema mapping is essentially complete.

**M3:** Worker integration with `producer='tier3_docx'` will produce 1 canonical artifact applied to 8 Kent campus rows. Need to decide: emit one artifact tagged to each campus row (8 inserts of identical data), or only the lead campus (`kent-state-university-at-kent`). Recommend 8 inserts so each campus has its own canonical row — the upstream multi-school attribution problem is not Tier 3's to solve.

**M4 spike:** JMU 2024-25 (smaller, 131 tables) and JMU 2025-26 (larger, 48 tables / 371 rows) are the natural Lane B test set.

## Open questions to resolve before M2

1. Should `docx_not_cds` detection trust URL pattern (`*_changes.docx`) only, or require the negative SDT signal too? Recommend: require `sdt_count == 0 AND (url_pattern matches OR body contains "Summary of Changes")` to avoid false positives.
2. For Kent State multi-row attribution, write 8 canonical rows or 1? Recommend 8 (tier 3's job is bytes → canonical; downstream consumer logic can dedupe).
3. Year detection priority: does CDS DOCX always put the title in header XML, or sometimes body? Audit `word/header*.xml` content during M1 implementation.
