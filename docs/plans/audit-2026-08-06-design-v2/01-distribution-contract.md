# S1.1 Distribution contract

## Corpus survey (existing tool, corrected path)
- Tool: `tools/extraction-validator/corpus_survey_tier4.py` (v1 incorrectly cited `tools/extraction_worker/corpus_survey_tier4.py`)
- Mode: reads `cds_artifacts(kind=canonical, producer=tier4_docling).notes.markdown` and re-runs `tier4_cleaner.clean()`
- Flag: `--include-fallback` merges `tier4_llm_fallback` (cleaner wins, fallback fills gaps). Must report cleaner-only vs merged deltas.

## Required stratification (replaces corpus-wide averages)
Dimensions: `academic_year x source_format x producer x schema_version x year_disagreement(hint vs detected_year) x field_count_tail`

## Section expectations (schemas/cds_schema_2025_26.json, 1105 fields)
C 278 | B 204 | H 165 | J 120 | D 88 | A 63 | F 58 | I 49 | G 46 | E 34
Suffixed QNs (e.g. C.8E01, A.0A): 24 entries — buckets collapse to top letter per _section_bucket.

## Query to run (R) — with as_of cutoff
```sql
-- per-document freshness + section distribution inputs
-- At execution time, record the actual as_of/capture window; this design has no snapshot.
```

Artifacts to emit under scratch/audit/s1-1/: histogram, per-QN top-60, per-section actual/expected, tail-10 docs.
