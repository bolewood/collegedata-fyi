# schools.yaml hint rewrite proposal

Generated: 2026-04-18T16:41:37Z  
Tool: `tools/finder/promote_landing_hints.py`

## Summary

- Direct-doc hints found in schools.yaml: **534**
- Rewrite proposals: **10** (high: 10, medium: 0, low: 0)
- Schools with no proposable landing: **524** (no manual_urls.yaml entry AND no shared parent in cds_documents)

To apply: `tools/extraction_worker/.venv/bin/python tools/finder/promote_landing_hints.py --apply`

High-confidence proposals come from Playwright probes that actually landed on a page with multiple CDS document anchors. Medium/low-confidence proposals are derived from shared parent directories across cds_documents.source_url — manually verify these are landing pages (not upload dirs) before applying.


## High confidence — 10 proposals

| school_id | source | evidence | current → proposed |
|---|---|---|---|
| `boston-university` | manual_urls:final_url | Playwright probe (no walk-up): 11 doc anchors | `https://www.bu.edu/asir/files/2020/02/cds-2018.pdf` → `https://www.bu.edu/asir/bu-facts/common-data-set/` |
| `american-university` | manual_urls:final_url | Playwright probe (no walk-up): 1 doc anchors | `https://www.american.edu/provost/oira/upload/cds_2024-2025_american-university_final.pdf` → `https://www.american.edu/provost/oira/common-data-set.cfm` |
| `james-madison-university` | cds_documents:most_common_parent+verified | 6/6 source_urls share this parent; verified: 8 doc anchors render | `https://www.jmu.edu/pair/ir/common-data-set/cds2024/cds-2024b.pdf` → `https://www.jmu.edu/pair/ir/common-data-set/` |
| `marquette-university` | manual_urls:final_url | Playwright probe (no walk-up): 11 doc anchors | `https://www.marquette.edu/institutional-research-analysis/documents/cds21-22.pdf` → `https://www.marquette.edu/academic-effectiveness/institutional-research-analysis/public-reports/common-data-set.php` |
| `southern-methodist-university` | manual_urls:final_url | Playwright probe (no walk-up): 10 doc anchors | `https://www.smu.edu/-/media/site/ir/commondatasets/2023/cds_2023-2024_part-a-general-information.pdf` → `https://www.smu.edu/ir/common-data-sets` |
| `university-of-illinois-urbana-champaign` | manual_urls:final_url | Playwright probe (no walk-up): 8 doc anchors | `https://www.dmi.illinois.edu/stuenr/misc/cds_2024_2025.xlsx` → `https://www.dmi.illinois.edu/stuenr/` |
| `university-of-miami` | manual_urls:final_url | Playwright probe (no walk-up): 25 doc anchors | `https://irsa.miami.edu/facts-and-information/common-data-set/cds2526.pdf` → `https://irsa.miami.edu/facts-and-information/common-data-set/` |
| `vassar-college` | manual_urls:final_url | Playwright probe (no walk-up): 1 doc anchors | `https://offices.vassar.edu/institutional-research/wp-content/uploads/sites/23/2025/03/Vassar-College-CDS-2024-2025-1.pdf` → `https://offices.vassar.edu/institutional-research/data/common-data-set-2022-23/` |
| `william-and-mary` | manual_urls:final_url | Playwright probe (no walk-up): 25 doc anchors | `https://www.wm.edu/offices/ir/university_data/cds/cds-2024-2025_a.pdf` → `https://www.wm.edu/offices/ir/university_data/cds/` |
| `williams-college` | manual_urls:landing_url_found | Playwright probe: 29 document anchors | `https://www.williams.edu/institutional-research/files/2019/08/2010-2011_williams_common_data_set.pdf` → `https://www.williams.edu/institutional-research/common-data-set/` |
