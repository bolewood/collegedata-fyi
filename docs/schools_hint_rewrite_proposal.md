# schools.yaml hint rewrite proposal

Generated: 2026-04-19T12:03:40Z  
Tool: `tools/finder/promote_landing_hints.py`

## Summary

- Direct-doc hints found in schools.yaml: **467**
- Rewrite proposals: **0** (high: 0, medium: 0, low: 0)
- Schools with no proposable landing: **467** (no manual_urls.yaml entry AND no shared parent in cds_documents)

To apply: `tools/extraction_worker/.venv/bin/python tools/finder/promote_landing_hints.py --apply`

High-confidence proposals come from Playwright probes that actually landed on a page with multiple CDS document anchors. Medium/low-confidence proposals are derived from shared parent directories across cds_documents.source_url — manually verify these are landing pages (not upload dirs) before applying.

