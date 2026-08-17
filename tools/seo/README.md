# SEO operator tools (PRD 028)

- `generate_official_cds_pages.py` — rebuilds
  `web/src/data/official-cds-pages.json` from `tools/finder/schools.yaml`.
  Direct PDF/XLSX seeds are omitted. Curated overrides (Virginia Tech HTML
  gate, Harvey Mudd live IR path) always win. Run after seed-URL edits.
- `vt_shaped_inventory.py` — M2.5 worklist into `scratch/seo/`. Not a
  product page. Does not replace a Search Console query export.

## Remaining operator steps

GSC URL inspect and the CDS query/page exports are done. Memo:
[`docs/prd/028-gsc-cds-queries-2026-08.md`](../../docs/prd/028-gsc-cds-queries-2026-08.md).

Still off-page (PRD 028 M3): Show HN, citations, ask-for-links.

Confirm `curl -I https://collegedata.fyi/schools/virginia-tech` stays
**301** to the www host (true as of 2026-08-17; Next.js now pins it).
