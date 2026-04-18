# schools.yaml hint rewrite proposal

Generated: 2026-04-18T20:01:51Z  
Tool: `tools/finder/promote_landing_hints.py`

## Summary

- Direct-doc hints found in schools.yaml: **534**
- Rewrite proposals: **67** (high: 67, medium: 0, low: 0)
- Schools with no proposable landing: **467** (no manual_urls.yaml entry AND no shared parent in cds_documents)

To apply: `tools/extraction_worker/.venv/bin/python tools/finder/promote_landing_hints.py --apply`

High-confidence proposals come from Playwright probes that actually landed on a page with multiple CDS document anchors. Medium/low-confidence proposals are derived from shared parent directories across cds_documents.source_url — manually verify these are landing pages (not upload dirs) before applying.


## High confidence — 67 proposals

| school_id | source | evidence | current → proposed |
|---|---|---|---|
| `bowdoin` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://www.bowdoin.edu/ir/pdf/common-data-set-2020-21.pdf` → `https://www.bowdoin.edu/ir/` |
| `brown` | manual_urls:landing_url_found | Playwright probe: 5 document anchors | `https://oir.brown.edu/sites/default/files/2020-04/CDS2009_2010.pdf` → `https://oir.brown.edu/institutional-data/common-data-set` |
| `bucknell` | manual_urls:landing_url_found | Playwright probe: 15 document anchors | `https://www.bucknell.edu/sites/default/files/institutional_research/cds_2020-2021.pdf` → `https://www.bucknell.edu/commondataset/` |
| `cornell` | manual_urls:landing_url_found | Playwright probe: 27 document anchors | `https://irp.dpb.cornell.edu/wp-content/uploads/2025/02/CDS-2024-2025-v1.pdf` → `https://irp.dpb.cornell.edu/common-data-set/` |
| `gwu` | manual_urls:landing_url_found | Playwright probe: 7 document anchors | `https://irp.gwu.edu/sites/g/files/zaxdzs6056/files/downloads/CDS_2020-2021-FA2021.pdf` → `https://irp.gwu.edu/common-data-set/` |
| `georgia-tech` | manual_urls:landing_url_found | Playwright probe: 23 document anchors | `https://irp.gatech.edu/files/CDS/cds_2006.pdf` → `https://irp.gatech.edu/common-data-set/` |
| `johns-hopkins` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://oira.jhu.edu/wp-content/uploads/CDS_2021-2022.pdf` → `https://oira.jhu.edu/common-data-set/` |
| `lehigh` | manual_urls:landing_url_found | Playwright probe: 13 document anchors | `https://data.lehigh.edu/sites/data.lehigh.edu/files/1302026-CDS-2025-2026-FINAL.pdf` → `https://data.lehigh.edu/common-data-set/` |
| `oberlin` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://www.oberlin.edu/sites/default/files/content/office/institutional-research/documents/2023-24_oc_cds.pdf` → `https://www.oberlin.edu/institutional-research/cds/` |
| `penn-state` | manual_urls:landing_url_found | Playwright probe: 100 document anchors | `https://opair.psu.edu/files/2019/04/CDS-2019-2020-University-Park.pdf` → `https://opair.psu.edu/cds/` |
| `rice` | manual_urls:landing_url_found | Playwright probe: 16 document anchors | `https://oie.rice.edu/sites/g/files/bxs4401/files/inline-files/CDS_2023-24_WEBSITE.pdf` → `https://oie.rice.edu/common-data-set/` |
| `swarthmore` | manual_urls:landing_url_found | Playwright probe: 20 document anchors | `https://www.swarthmore.edu/sites/default/files/assets/documents/institutional-research/cds2011.pdf` → `https://www.swarthmore.edu/institutional-research/common-data-set/` |
| `tufts` | manual_urls:landing_url_found | Playwright probe: 10 document anchors | `https://provost.tufts.edu/institutionalresearch/wp-content/uploads/sites/5/CDS_2024-2025-1.pdf` → `https://provost.tufts.edu/institutionalresearch/common-data-set/` |
| `uc-davis` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://aggiedata.ucdavis.edu/sites/g/files/dgvnsk1841/files/media/documents/CDS_2020-2021_Davis.pdf` → `https://aggiedata.ucdavis.edu/common-data-set/` |
| `unc` | manual_urls:landing_url_found | Playwright probe: 26 document anchors | `https://oira.unc.edu/wp-content/uploads/sites/297/2024/02/CDS_2022-23_20240206.pdf` → `https://oira.unc.edu/common-data-set/` |
| `upitt` | manual_urls:landing_url_found | Playwright probe: 5 document anchors | `https://ir.pitt.edu/sites/default/files/assets/2023-2024%20Common%20Data%20Set%20Pgh%20Campus_9.pdf` → `https://ir.pitt.edu/common-data-set/` |
| `williams` | manual_urls:landing_url_found | Playwright probe: 29 document anchors | `https://www.williams.edu/institutional-research/files/2019/08/2010-2011_williams_common_data_set.pdf` → `https://www.williams.edu/institutional-research/common-data-set/` |
| `arkansas-tech-university` | manual_urls:landing_url_found | Playwright probe: 4 document anchors | `https://www.atu.edu/ir/docs/cds/CDS_fall_2022.pdf` → `https://www.atu.edu/ir/` |
| `austin-peay-state-university` | manual_urls:landing_url_found | Playwright probe: 18 document anchors | `https://www.apsu.edu/dsir/common_data_set/CDSforWeb1819v6.pdf` → `https://www.apsu.edu/institutional-research/cds/` |
| `brigham-young-university` | manual_urls:landing_url_found | Playwright probe: 8 document anchors | `https://assessmentandplanning.byu.edu/https:/brightspotcdn.byu.edu/d4/ef/781d4ba74c888a1f5be7f98406b3/common-data-set-2002-2003.pdf` → `https://assessmentandplanning.byu.edu/common-data-set/` |
| `citadel-military-college-of-south-carolina` | manual_urls:landing_url_found | Playwright probe: 28 document anchors | `https://www.citadel.edu/institutional-research/wp-content/uploads/sites/75/cds2021_2022.pdf` → `https://www.citadel.edu/institutional-research/common-data-set/` |
| `duquesne-university` | manual_urls:landing_url_found | Playwright probe: 6 document anchors | `https://www.duq.edu/documents/institutionalresearch/cds-2020-2021.pdf` → `https://www.duq.edu/commondataset/` |
| `hollins-university` | manual_urls:landing_url_found | Playwright probe: 12 document anchors | `https://registrar.press.hollins.edu/wp-content/uploads/sites/47/2025/04/CDS-2024-2025-Hollins.pdf` → `https://registrar.press.hollins.edu/common-data-set/` |
| `james-madison-university` | manual_urls:landing_url_found | Playwright probe: 8 document anchors | `https://www.jmu.edu/pair/ir/common-data-set/cds2024/cds-2024b.pdf` → `https://www.jmu.edu/oir/common-data-set/` |
| `kansas-state-university` | manual_urls:landing_url_found | Playwright probe: 11 document anchors | `https://www.k-state.edu/data/institutional-research/resources/common-data-set/CDS_2020-2021.pdf` → `https://www.k-state.edu/data/institutional-research/resources/` |
| `kennesaw-state-university` | manual_urls:landing_url_found | Playwright probe: 26 document anchors | `https://www.kennesaw.edu/data-strategy/institutional-research/publications/common-data-set/docs/cds-2024-2025-06102025.pdf` → `https://www.kennesaw.edu/data-strategy/institutional-research/publications/common-data-set/` |
| `lake-superior-state-university` | manual_urls:landing_url_found | Playwright probe: 17 document anchors | `https://www.lssu.edu/wp-content/uploads/2019/05/CommonDataSet2017-2018.pdf` → `https://www.lssu.edu/common-data-set/` |
| `louisiana-state-university-and-agricultural-and-mechanical` | manual_urls:landing_url_found | Playwright probe: 22 document anchors | `https://www.lsu.edu/data/common-data-set/2023/3_2324_admissions.pdf` → `https://www.lsu.edu/data/common-data-set/` |
| `loyola-university-chicago` | manual_urls:landing_url_found | Playwright probe: 12 document anchors | `https://www.luc.edu/media/lucedu/oie/CDS_2021-2022.pdf` → `https://www.luc.edu/institutional-data/common-data-set` |
| `montana-state-university` | manual_urls:landing_url_found | Playwright probe: 5 document anchors | `https://www.montana.edu/data/common-data-set/cds24.pdf` → `https://www.montana.edu/data/common-data-set/` |
| `north-carolina-state-university-at-raleigh` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://report.isa.ncsu.edu/ir/cds/pdfs/CDS_2022-23.v2.pdf` → `https://report.isa.ncsu.edu/ir/cds/` |
| `northern-arizona-university` | manual_urls:landing_url_found | Playwright probe: 26 document anchors | `https://in.nau.edu/wp-content/uploads/sites/129/2025/02/CDS-2024-2025.pdf` → `https://in.nau.edu/institutional-research/common-data-set/` |
| `oklahoma-state-university-main-campus` | manual_urls:landing_url_found | Playwright probe: 13 document anchors | `https://ira.okstate.edu/site-files/documents/cds/cds2425.pdf` → `https://ira.okstate.edu/cds/` |
| `rollins-college` | manual_urls:landing_url_found | Playwright probe: 16 document anchors | `https://rpublic.rollins.edu/sites/IR/Common%20Data%20Set%20CDS/CDS_2021-2022%20Rollins.pdf` → `https://rpublic.rollins.edu/sites/IR/Common%20Data%20Set%20CDS/` |
| `san-diego-state-university` | manual_urls:landing_url_found | Playwright probe: 17 document anchors | `https://asir.sdsu.edu/Documents/CommonDataSets/CDS_2022-23_rev_1.pdf` → `https://asir.sdsu.edu/common-data-set/` |
| `shenandoah-university` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://www.su.edu/wp-content/uploads/2014/11/CDS-2425-Final.pdf` → `https://www.su.edu/common-data-set/` |
| `skidmore-college` | manual_urls:landing_url_found | Playwright probe: 20 document anchors | `https://www.skidmore.edu/ir/facts/common/CDS_2022-2023.pdf` → `https://www.skidmore.edu/ir/facts/common/` |
| `st-marys-college-of-maryland` | manual_urls:landing_url_found | Playwright probe: 21 document anchors | `https://www.smcm.edu/ir/wp-content/uploads/sites/60/2023/02/CDS-2022-2023-final.pdf` → `https://www.smcm.edu/ir/cds/` |
| `stony-brook-university` | manual_urls:landing_url_found | Playwright probe: 12 document anchors | `https://www.stonybrook.edu/commcms/irpe/fact_book/common_data_set/_files/CDS_2024_2025.pdf` → `https://www.stonybrook.edu/commcms/irpe/fact_book/common_data_set/` |
| `texas-wesleyan-university` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://txwes.edu/media/twu/institutional-research/docs/CDS2015-2016.pdf` → `https://txwes.edu/common-data-set/` |
| `the-evergreen-state-college` | manual_urls:landing_url_found | Playwright probe: 6 document anchors | `https://www.evergreen.edu/sites/default/files/2024-07/The%20Evergreen%20State%20College_CDS_2023-2024.pdf` → `https://www.evergreen.edu/common-data-set/` |
| `the-university-of-tennessee-knoxville` | manual_urls:landing_url_found | Playwright probe: 11 document anchors | `https://irsa.utk.edu/wp-content/uploads/sites/107/2024/02/CDS_2023-2024_C.pdf` → `https://irsa.utk.edu/common-data-set/` |
| `the-university-of-texas-at-el-paso` | manual_urls:landing_url_found | Playwright probe: 4 document anchors | `https://www.utep.edu/planning/cierp/_files/docs/common-data-set/2024-25%20common%20data%20set.pdf` → `https://www.utep.edu/common-data-set/` |
| `university-of-alaska-fairbanks` | manual_urls:landing_url_found | Playwright probe: 28 document anchors | `https://www.uaf.edu/pair/pair_reports/common-data-set/CDS_2022-2023.pdf` → `https://www.uaf.edu/pair/pair_reports/common-data-set/` |
| `university-of-arkansas` | manual_urls:landing_url_found | Playwright probe: 34 document anchors | `https://osai.uark.edu/datasets/cds/cds24-25v1.pdf` → `https://osai.uark.edu/datasets/cds/` |
| `university-of-california-riverside` | manual_urls:landing_url_found | Playwright probe: 11 document anchors | `https://ir.ucr.edu/sites/default/files/2024-03/cds-2023-2024.pdf` → `https://ir.ucr.edu/cds/` |
| `university-of-houston` | manual_urls:landing_url_found | Playwright probe: 13 document anchors | `https://uh.edu/ir/reports/common-data-sets/cds-data/cds01-02_new.pdf` → `https://uh.edu/ir/reports/common-data-sets/` |
| `university-of-houston-system-administration` | manual_urls:landing_url_found | Playwright probe: 13 document anchors | `https://uh.edu/ir/reports/common-data-sets/cds-data/cds01-02_new.pdf` → `https://uh.edu/ir/reports/common-data-sets/` |
| `university-of-kansas` | manual_urls:landing_url_found | Playwright probe: 30 document anchors | `https://aire.ku.edu/sites/aire/files/files/CDS/2024-2025/C.pdf` → `https://aire.ku.edu/common-data-set/` |
| `university-of-kentucky` | manual_urls:landing_url_found | Playwright probe: 7 document anchors | `https://irads.uky.edu/sites/default/files/common_data_set/CDS_2022-2023%2004052023%20-%20not%20G.pdf` → `https://irads.uky.edu/common-data-set/` |
| `university-of-la-verne` | manual_urls:landing_url_found | Playwright probe: 14 document anchors | `https://laverne.edu/institutional-research/wp-content/uploads/sites/27/2011/10/CDS_2014-2015_University-of-La-Verne.pdf` → `https://laverne.edu/institutional-research/common-data-set/` |
| `university-of-maryland-baltimore-county` | manual_urls:landing_url_found | Playwright probe: 12 document anchors | `https://irads.umbc.edu/wp-content/uploads/sites/62/2013/11/CDS_2013-2014-.pdf` → `https://irads.umbc.edu/common-data-set/` |
| `university-of-massachusetts-lowell` | manual_urls:landing_url_found | Playwright probe: 8 document anchors | `https://www.uml.edu/docs/UMass-Lowell-CDS-2021-2022-4-27-2022_tcm18-357637.pdf` → `https://www.uml.edu/common-data-set/` |
| `university-of-miami` | manual_urls:landing_url_found | Playwright probe: 25 document anchors | `https://irsa.miami.edu/facts-and-information/common-data-set/cds2526.pdf` → `https://irsa.miami.edu/facts-and-information/common-data-set/` |
| `university-of-north-texas` | manual_urls:landing_url_found | Playwright probe: 24 document anchors | `https://institutionalresearch.unt.edu/sites/default/files/cds_2020-2021_unt.pdf` → `https://institutionalresearch.unt.edu/common-data-set` |
| `university-of-northern-colorado` | manual_urls:landing_url_found | Playwright probe: 3 document anchors | `https://www.unco.edu/app/uploads/2025/10/UNC-Common-Data-Set-2023-24.pdf` → `https://www.unco.edu/common-data-set/` |
| `university-of-south-carolina-columbia` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `http://oiraa.dw.sc.edu/cds/cds2024/cds_2024-2025.pdf` → `http://oiraa.dw.sc.edu/cds/cds2024/` |
| `university-of-wisconsin-la-crosse` | manual_urls:landing_url_found | Playwright probe: 3 document anchors | `https://www.uwlax.edu/globalassets/offices-services/institutional-research/ir-resources/cds_2022-2023.pdf` → `https://www.uwlax.edu/institutional-research/common-data-set/` |
| `valdosta-state-university` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://www.valdosta.edu/administration/institutional-research/documents/common-data-set/cds-2023.pdf` → `https://www.valdosta.edu/administration/institutional-research/` |
| `valparaiso-university` | manual_urls:landing_url_found | Playwright probe: 26 document anchors | `https://www.valpo.edu/wp-content/uploads/2025/09/CDS-2024-2025_v3_060425.pdf` → `https://www.valpo.edu/common-data-set/` |
| `vassar-college` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://offices.vassar.edu/institutional-research/wp-content/uploads/sites/23/2025/03/Vassar-College-CDS-2024-2025-1.pdf` → `https://offices.vassar.edu/institutional-research/common-data-set/` |
| `viterbo-university` | manual_urls:landing_url_found | Playwright probe: 1 document anchors | `https://www.viterbo.edu/sites/default/files/2025-05/viterbocds-2024-25-final05272025.pdf` → `https://www.viterbo.edu/institutional-research/common-data-set/` |
| `wayne-state-university` | manual_urls:landing_url_found | Playwright probe: 7 document anchors | `https://irda.wayne.edu/common-data-set/cds-2023-2024-final.pdf` → `https://irda.wayne.edu/institutional-research/cds/` |
| `wesleyan-university` | manual_urls:landing_url_found | Playwright probe: 2 document anchors | `https://www.wesleyan.edu/ir/data-sets/CDS_2021-2022.pdf` → `https://www.wesleyan.edu/ir/` |
| `western-washington-university` | manual_urls:landing_url_found | Playwright probe: 15 document anchors | `https://oie.wwu.edu/files/2022/05/CDS_2021-2022_.pdf` → `https://oie.wwu.edu/common-data-set/` |
| `william-and-mary` | manual_urls:landing_url_found | Playwright probe: 25 document anchors | `https://www.wm.edu/offices/ir/university_data/cds/cds-2024-2025_a.pdf` → `https://www.wm.edu/offices/ir/university_data/cds/` |
| `williams-college` | manual_urls:landing_url_found | Playwright probe: 29 document anchors | `https://www.williams.edu/institutional-research/files/2019/08/2010-2011_williams_common_data_set.pdf` → `https://www.williams.edu/institutional-research/common-data-set/` |
