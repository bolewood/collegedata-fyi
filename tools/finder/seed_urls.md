# Seed URLs for the CDS Finder (V1a)

Discovery sources for the V1a CDS Finder scraper. When the finder launches, these are the first places it looks before falling back to generic Google dorks.

## Primary sources

### 1. Common Data Set Initiative

- **https://commondataset.org** — the official home of the Common Data Set Initiative. Does not aggregate institutional submissions. Hosts the current-year blank templates in three formats:
  - `https://commondataset.org/wp-content/uploads/2025/11/CDS-PDF-2025-2026_PDF_Template.pdf`
  - `https://commondataset.org/wp-content/uploads/2025/11/CDS_2025-2026-Word_Template.docx`
  - `https://commondataset.org/wp-content/uploads/2025/11/CDS-2025-2026-Summary-of-Changes-1.docx`
- **No terms of service published.** Schools own the data in their own filled CDS files. See [`schemas/`](../../schemas/) for the canonical field list extracted from the official Excel template.

### 2. College Lists Wiki (pbworks)

- **http://collegelists.pbworks.com/w/page/30192726/Common%20Data%20Sets** — a crowdsourced index of institutional CDS hosting URLs. Most entries are circa-2005 paths and many are now broken, but the school names are still right and the URL patterns give the scraper a starting template. Run this list through a URL-probe pass, follow 301 redirects, and record the landing page as the school's starting point. For dead entries, fall back to the URL pattern probe below.

### 3. Fairfield University Digital Commons

- **https://digitalcommons.fairfield.edu/archives-cds/** — a single-institution archive of historical Fairfield CDS going back to 2003, with RSS feeds for new publications. Worth using as a model for what good institutional archiving looks like and as a data source for at least Fairfield's complete back catalog.

### 4. Targeted Google dorks

For schools not in the wiki seed list, or where the wiki URL is broken, fall back to search-engine operators:

```
site:.edu filetype:pdf "Common Data Set 2024-2025"
site:.edu filetype:pdf "Common Data Set 2025-2026"
site:<school-domain>.edu "Common Data Set" filetype:pdf
```

Run these against a recent year first, not the oldest year, because the most recent document is the one most likely to still be live on the school's website.

## URL pattern fallback probes

When a school is not in the wiki seed list and the school-scoped dork returns nothing, try these common path patterns against the school's primary `.edu` domain. They are ordered roughly by observed frequency in the wild:

| Pattern | Structural intent |
|---|---|
| `/ir/cds/` | Dedicated subdirectory within the Institutional Research office |
| `/institutional-research/common-data-set/` | Fully spelled-out path, common in modern CMS deployments |
| `/facts-and-figures/common-data-set/` | Marketing-adjacent data hosting, often linked from "About Us" |
| `/about/offices/provost/oir/cds.pdf` | Deeply nested file within the Provost's administrative hierarchy |
| `/data/campus/general/cds.html` | Generalized campus data portal using HTML rendering |
| `/oir/cds/` | Office of Institutional Research, short form |
| `/registrar/cds.pdf` | Registrar-hosted, uncommon but present at some older schools |
| `/budget/cds/` | Budget/Planning office, occasionally used by large state schools |

When you find a working path for a school, write it back to this file (or to `schools.yaml`, once the scraper adopts per-school overrides) so future runs skip the probe loop.

## Seed institution list

The following list is reconstructed from the pbworks wiki (reference 31 in `docs/research/` and `scratch/Common Data Set Ecosystem Research.md`). URLs are the historical hosting patterns that were live circa 2005, and most of them are now dead or redirected. Use the school names as the seed corpus; re-discover the current URLs via the probe sequence above.

| Institution | Historical URL pattern |
|---|---|
| American University | `american.edu/academic.depts/provost/oir/cds.pdf` |
| Amherst College | `amherst.edu/about_amh/cds/` |
| Barnard College | `barnard.edu/opir/cds/cds_main.htm` |
| Bates College | `bates.edu/x2294.xml` |
| Boston College | `bc.edu/about/bc-facts/` |
| Boston University | `bu.edu/oep/cds.html` |
| Bowdoin College | `academic.bowdoin.edu/ir/data/cds-table.shtml` |
| Brandeis University | `brandeis.edu/offices/IR/cds/CDS.html` |
| Brown University | `brown.edu/Administration/Institutional_Research/` |
| Bryn Mawr College | `brynmawr.edu/institutionalresearch/cds/index.shtml` |
| Bucknell University | `bucknell.edu/Offices_Resources/Offices/Institutional_Research/` |
| Carnegie Mellon University | `cmu.edu/ira/CDS/` |
| Case Western Reserve University | `cwru.edu/president/cir/cdsmain.htm` |
| Colby College | `colby.edu/ir/` |
| College of the Holy Cross | `holycross.edu/departments/planning/website/` |
| Colorado College | `coloradocollege.edu/dean/oir/comdata.htm` |
| Columbia University | `columbia.edu/cu/opir/abstract/` |
| Cornell University | `dpb.cornell.edu/irp/cds.htm` |
| Dartmouth College | `dartmouth.edu/~oir/dataset.html` |
| Davidson College | `davidson.edu/administration/adm/ir/ir_cds.asp` |
| Dickinson College | `dickinson.edu/departments/insres/publications.htm` |
| Drexel University | `drexel.edu/provost/ir/cds2005/` |
| Duke University | `ir.provost.duke.edu/facts/cds/` |
| Emory University | `emory.edu/PROVOST/IPR/ir_factbook.htm` |
| George Washington University | `gwu.edu/~ire/` |
| Georgetown University | `georgetown.edu/opir/` |
| Georgia Tech | `irp.gatech.edu/` |
| Grinnell College | `grinnell.edu/offices/institutionalresearch/cds/` |
| Hamilton College | `hamilton.edu/college/institutional_research/` |
| Johns Hopkins University | `webapps.jhu.edu/jhuniverse/information_about_hopkins/facts_and_statistics/` |
| Kenyon College | `ir.kenyon.edu/commondataset.php` |
| Lehigh University | `lehigh.edu/~oir/cds.htm` |
| Macalester College | `macalester.edu/ir/cds.htm` |
| MIT | `web.mit.edu/ir/cds/` |
| New York University | `nyu.edu/ir/cds/` |
| Northeastern University | `oupr.neu.edu/dataset/common.html` |
| Northwestern University | `ugadm.northwestern.edu/commondata/` |
| Oberlin College | `peacock.adm.oberlin.edu/www/cds/cds_explain.html` |
| Ohio State University | `oem.osu.edu/` |
| Penn State University | `budget.psu.edu/CDS/default.asp` |
| Princeton University | `registrar1.princeton.edu/data/common.cfm` |
| Purdue University | `purdue.edu/idn/CDS_Post/cdsmain.html` |
| Rensselaer Polytechnic Institute | `rpi.edu/about/cds/index.html` |
| Rice University | `ruf.rice.edu/~instresr/ricefacts/index.html` |
| Rutgers University | `oirap.rutgers.edu/instchar.html` |
| Stanford University | `find.stanford.edu/search?q=common+data+set&site=stanford` |
| Swarthmore College | `swarthmore.edu/Admin/institutional_research/cds.html` |
| Temple University | `temple.edu/factbook/` |
| Texas A&M University | `pie.tamucc.edu/cds/cdsmain.htm` |
| Tufts University | `tufts.edu/ir/inresearch.html` |
| UC Berkeley | `cds.vcbf.berkeley.edu/` |
| UC Davis | `sariweb.ucdavis.edu/` |
| UC Irvine | `oir.uci.edu/cds/` |
| UCLA | `aim.ucla.edu/data/campus/general/cds.html` |
| UC San Diego | `ugr8.ucsd.edu/sriweb/sri.htm` |
| UC Santa Barbara | `bap.ucsb.edu/IR/UG_Info_Guide.pdf` |
| University of Colorado | `colorado.edu/pba/cds/` |
| University of Delaware | `udel.edu/IR/cds/index.html` |
| University of Florida | `ir.ufl.edu/data.htm` |
| University of Georgia | `uga.edu/irp/cds/index.html` |
| University of Maryland | `oirp.umd.edu/public/commondataset.cfm` |
| University of Michigan | `obp.umich.edu/root/facts-figures/common-data-set/` |
| University of North Carolina (Chapel Hill) | `ais.unc.edu/ir/cds.html` |
| University of Pennsylvania | `upenn.edu/ir/` |
| University of Pittsburgh | `ir.pitt.edu/cds/cdshmpg200405.htm` |
| University of Southern California | `afaweb.esd.usc.edu/USC-AFA/` |
| University of Texas at Austin | `utexas.edu/academic/oir/cds/` |
| University of Virginia | `web.virginia.edu/IAAS/data_catalog/institutional/cds/` |
| University of Washington | `washington.edu/admin/factbook/ois.html` |
| University of Wisconsin | `wiscinfo.doit.wisc.edu/obpa/CDS_USNEWS/` |
| Vanderbilt University | `virg.vanderbilt.edu/virg/option1/virg1_flash.htm` |
| Wake Forest University | `wfu.edu/ir/factbook.html` |
| Washington and Lee University | `ir.wlu.edu/cds/` |
| Wellesley College | `wellesley.edu/InstResearch/surveyresults.html` |
| Williams College | `williams.edu/admin/provost/ir/` |
| Yale University | `yale.edu/oir/ComDatset.html` |

## Known strategic non-publishers

Schools that are publicly known to refuse CDS publication, or that historically gamed the data via non-publication. Record these as `participation_status = verified_absent` in the manifest so consumers can distinguish "we haven't found it" from "they refuse to publish."

- **University of Chicago** — refuses to publish a Common Data Set. When queried for specific metrics (especially waitlist acceptance rate and yield), the university commands that those fields remain marked "not published." Widely understood as strategic opacity around yield protection practices.
- **Reed College** — boycotts US News rankings since the 1990s and does not publish a standard CDS. Publishes mission-centric data (future PhD productivity, etc.) instead.

## Known sub-institutional publishers

Schools that publish more than one CDS document in the same year, typically to separate traditional undergraduate populations from non-traditional ones.

- **Columbia University** — publishes two separate CDS files per year: one for traditional undergraduates (Columbia College + Fu School of Engineering) and one for the School of General Studies. The manifest needs to handle multiple documents per `(school, year)` keyed by a sub-institutional label.

## Known partial publishers

Schools that publish a CDS but intentionally leave specific sections blank to control narrative. Record these as `participation_status = verified_partial` with the absent sections noted per year.

- **Dartmouth College** and **Princeton University** — have historically omitted GPA breakdowns of admitted students (parts of Section C) to avoid deterring prospective applicants. Verify on the per-year file.

## Next steps

1. Promote this file to `schools.yaml` once the V1a finder is building for real. That YAML becomes the canonical per-school override table (working URL, sub-institutional label, participation_status, known issues).
2. Probe the pbworks wiki URLs through a headless browser to see how many still resolve vs 301-redirect vs 404. Record the distribution.
3. Cross-reference with the Fairfield Digital Commons archive (`https://digitalcommons.fairfield.edu/archives-cds/`) for historical data we can backfill for at least that school.

## Source attribution

The seed institution table and URL pattern ladder come from the Gemini Deep Research report stored at `docs/research/gemini-deep-research-cds-prompt.md` (the prompt) and `scratch/Common Data Set Ecosystem Research.md` (the full response, untracked because it lives in the scratch folder). The underlying citation in the Gemini research is the pbworks wiki listed under primary sources above.
