# S1.2 Boundary assertions (per-entity, replaces global max timestamps)

Each arrow tested per document; global `max(created_at) > max(updated_at)` removed.

```
finder hint / URL  → archived bytes → cds_documents (detected_year at archive time)
  → selected canonical artifact (current SHA + producer/schema)
  → cds_fields + school_browser_rows → public API + UI quality flags
  → IPEDS: release manifest → ipeds_raw_rows → ipeds_facts → ipeds_current_facts_cache
```

## Per-document freshness (R)
For each cds_documents.current source (SHA + producer 0.3.14 + schema_version):
- Is selected canonical projected?
- Does school_browser_rows row reflect that artifact identity/refresh?

Stale-by-document count, not global timestamp.

## API flag parity (R/O)
- `web/src/lib/public-data.ts:566 hasIncoherentAdmissionsCounts` withholds admissions counts but emits `low_confidence_extract` with reason; browser row remains queryable. Audit counts withholdings — v1 "signal destruction" framing corrected.
- `FRIENDLY_FACT_FIELDS` does not silently drop finance; finance served via `categories=finance` (public-data.ts:392). Compare endpoint rejecting finance is intentional (compare/route.ts:41).
- Spreadsheet (`spreadsheet-source.ts:6`) vs browser_rows equality invalid — different projections.

## Specified queries (run with as_of cutoff)
```sql
-- S1.2a: selected canonical not projected
-- S1.2b: API flag parity — withheld vs flagged counts
```
