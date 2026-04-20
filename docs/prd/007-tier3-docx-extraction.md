# PRD 007: Tier 3 DOCX Extraction

**Status:** Draft
**Created:** 2026-04-20

---

## Context

The Tier 3 path (filled DOCX → canonical JSON) is a stub. Schools that publish
their CDS as a filled Word document currently fail extraction. Two close observations
motivate building Tier 3 now:

1. **Clean template tags exist.** The CDS Initiative's Word template ships with
   **1,204 Structured Document Tags (SDTs)** whose `w:tag` values match the schema's
   `word_tag` field exactly (`a0_first_name`, `a0_last_name`, …). For schools that fill
   the template without destroying its structure, extraction is as deterministic as
   Tier 2 (AcroForm read): iterate SDTs, look up the tag in the schema, emit the
   value.
2. **There is meaningful real-corpus demand.** Measured on the current corpus:
   - Kent State (all 8 campuses × multiple years, ~14 docs): preserves SDTs.
     Sample doc has **769 populated SDTs out of 804** (70% of the 1,105-field
     schema). Cleaner-per-field fidelity exceeds Tier 4 Docling by 6× on the same
     documents.
   - James Madison, others: likely SDT-preserving (to be verified).
   - Saint Louis University: typed directly into the template, SDTs stripped but
     table structure intact (33 tables).

Per the extraction status snapshot: 183 documents remain failed after the full drain.
Of those, ~18 are real DOCX files and another ~90 are xlsx-extension files where
some unknown subset is actually DOCX content. A rough upper bound on Tier 3 addressable
corpus is **30–50 documents today**, with more to come as discovery expands.

## Premises

1. **The template is the key.** Every SDT tag in the CDS Word template corresponds
   directly to a `word_tag` in `schemas/cds_schema_2025_26.json`. This is an exact
   parallel to Tier 2's `pdf_tag` → `question_number` mapping. The extractor is
   essentially a 50-line script.
2. **SDT-preserving is the common case.** Schools that fill the template in Word
   and export as DOCX preserve SDTs. Kent State confirms this pattern (769/804
   populated). Schools that copy content into a blank Word doc or paste from another
   source will strip SDTs — those are the fallback case.
3. **Format detection needs a fix.** The current sniffer misroutes DOCX files with
   `.xlsx` extensions (UPenn, UW, Vanderbilt) because it only looks at the ZIP magic
   bytes. Tier 1 fails them, and they never reach Tier 3. The right fix is to peek
   at the inner file list before routing: `xl/workbook.xml` → xlsx, `word/document.xml`
   → docx.
4. **The corpus is small but growing.** Tier 3 won't unlock thousands of docs like
   Tier 4 did. But Kent State alone contributes 14 docs at higher fidelity than Tier
   4 can reach, and the broader "typed-in-Word" pattern will appear more as the
   discovery pipeline covers more smaller schools.

## What to build

### Primary path: SDT-based extraction (Tier 3a)

Create `tools/tier3_extractor/extract.py` following the Tier 2 shape exactly:

```
def read_sdts(docx_path: Path) -> dict:
    """Return {tag: value_string} for every SDT with a populated text value."""
    doc = Document(str(docx_path))
    sdts = doc.element.body.findall('.//' + qn('w:sdt'))
    result = {}
    for sdt in sdts:
        tag_elem = sdt.find('.//' + qn('w:tag'))
        if tag_elem is None:
            continue
        tag = tag_elem.get(qn('w:val'))
        # Skip placeholder-showing SDTs (user never typed)
        if sdt.find('.//' + qn('w:showingPlcHdr')) is not None:
            continue
        # Concatenate all w:t runs inside this SDT
        text = ''.join(t.text or '' for t in sdt.findall('.//' + qn('w:t'))).strip()
        if text and 'Click or tap' not in text:
            result[tag] = text
    return result

def extract(docx_path: Path, schema: dict) -> dict:
    sdts = read_sdts(docx_path)
    word_tag_to_field = {f['word_tag']: f for f in schema['fields'] if f['word_tag']}

    values = {}
    unmapped = []
    for tag, raw in sdts.items():
        field = word_tag_to_field.get(tag)
        if field is None:
            unmapped.append({"word_tag": tag, "value": raw})
            continue
        values[field["question_number"]] = {
            "value": raw,
            "word_tag": tag,
            "question": field.get("question"),
            # ... same shape as tier2 output
        }

    return {
        "producer": "tier3_docx",
        "producer_version": "0.1.0",
        "schema_version": schema["schema_version"],
        # ... stats, values, unmapped
    }
```

This is ~80 lines of real code plus the standard CLI wrapper. The schema's 1,080 unique
`word_tag` values make the mapping deterministic.

### Fallback path: table-position extraction (Tier 3b — deferred)

For schools that strip SDTs (Saint Louis pattern), fall back to reading Word tables
by position. The CDS Word template has 75 tables in a known order. Each table maps
to a known CDS subsection. Saint Louis's 33 tables is a subset — the school likely
omitted the respondent-info and other text-only sections but kept the data tables.

This is its own parser design (similar complexity to the Tier 4 Docling cleaner) and
is **deferred to a follow-up PRD**. The SDT-based path unlocks the Kent State family
and most template-preserving schools without it.

### Format routing fix

Update `sniff_format_from_bytes` in `tools/extraction_worker/worker.py` to distinguish
DOCX from XLSX within ZIP-signatured files:

```python
if len(data) >= 4 and data[:4] == b"PK\x03\x04":
    # Both xlsx and docx are ZIPs. Peek at the inner file list to disambiguate.
    import zipfile
    from io import BytesIO
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            if any(n.startswith("word/") for n in names):
                return "docx"
            if any(n.startswith("xl/") for n in names):
                return "xlsx"
    except zipfile.BadZipFile:
        return "other"
    return "other"
```

This is a one-function change and fixes the UPenn/UW/Vanderbilt misrouting. The
existing xlsx fallback in Tier 1 already correctly rejects DOCX files at read time
with `"File contains no valid workbook part"` — but reclassifying them upstream lets
Tier 3 pick them up.

### Worker routing

Add `_run_tier3` following the `_run_tier2` shape. Route `source_format == "docx"` to
it. If Tier 3 finds zero SDTs (the Saint Louis case), mark the doc as failed with
reason `tier3_no_sdts` rather than trying to extract — the Tier 3b fallback will
handle those in a later PRD.

## Files modified

| File | Change |
|---|---|
| `tools/tier3_extractor/extract.py` | **New.** SDT-based reader, ~100 lines. |
| `tools/tier3_extractor/requirements.txt` | **New.** `python-docx>=1.0`. |
| `tools/tier3_extractor/README.md` | **New.** Usage, tier strategy. |
| `tools/extraction_worker/worker.py` | Fix `sniff_format_from_bytes` to peek at ZIP contents. Add `_run_tier3`. Route docx format. Update routing docstring. |

## Verification plan

1. **Unit test against Kent State docs.** Expect ≥700 fields populated on Kent State
   main campus 2025-26. Verify sample field values against the source DOCX opened
   in Word.
2. **Re-probe misrouted files.** Re-run the tier probe on the 91 failed-xlsx docs
   with the fixed sniffer. Confirm the UPenn/UW/Vanderbilt-class files reclassify as
   docx.
3. **Re-run extraction on all failed docx + newly-reclassified docs.** Expected
   outcomes:
   - Kent State family (14 docs): all succeed via SDT path, >700 fields each
   - Summary-of-changes false positives (Stanford/Georgetown/UPenn/Vanderbilt 2025-26):
     fail with `tier3_no_sdts` (correct — the archived file genuinely isn't a CDS).
     These should be flagged for re-discovery.
   - Saint Louis: fails with `tier3_no_sdts`, gets deferred to Tier 3b.
4. **Verify no regressions.** Existing Tier 1/2/4 extractions must remain unchanged.
   Run a 10-doc sample of each tier before and after.

## Risks

| Risk | Mitigation |
|---|---|
| Discovery pipeline wrongly archived non-CDS files (Summary of Changes) as 2025-26 CDS at multiple schools | Out of scope for this PRD. Flag as a discovery pipeline bug. Tier 3 correctly fails these with `tier3_no_sdts`; they get re-discovered later. |
| SDT nesting: some SDTs may contain other SDTs (nested tags) | Use `.findall(.//w:sdt)` which descends into nested SDTs. Schema lookup ensures only valid `word_tag` values create artifacts — nested/unknown tags land in `unmapped_fields`. |
| Value type coercion (YesNo, checkbox, date) | Mirror Tier 2's `decode_button_value` pattern if the schema has `value_options` for that field. Otherwise emit raw string. |
| python-docx dependency weight | Small (~200KB). Already a project dep — extraction_worker requirements mention it as Tier 3 target. Just needs to move from aspirational to actual. |
| Tier 3b (table-position fallback) is non-trivial | Explicitly deferred. This PRD ships the 80% case; the table-position fallback is its own PRD once we understand how common SDT-stripping is across the corpus. |

## Non-goals

- **Table-position extraction for SDT-stripped DOCX files** (the Saint Louis case).
  Deferred to a follow-up PRD.
- **Reconciling discovery pipeline errors** that archived non-CDS files at legit
  schools (Stanford 2025-26 is actually the CDS Initiative's summary doc). This is a
  discovery problem, not an extraction problem.
- **Schema versioning for older DOCX templates.** The 2025-26 `word_tag` values are
  the canonical ones; older CDS templates used different tag sets. If a pre-2024
  DOCX shows up with an older tag scheme, the unmapped tags get logged and we extend
  the schema. Not in scope here.
