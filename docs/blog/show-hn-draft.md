# Show HN draft

> **Status:** Draft, not posted. Edit and post when ready. See ADR 0008 for
> takedown protocol — having this live before the launch means the
> response process exists if the post goes viral.

---

## Post title options (pick one)

1. Show HN: I archived every US college's Common Data Set so the data doesn't get memory-holed
2. Show HN: An open, reproducible archive of every US college's Common Data Set
3. Show HN: collegedata.fyi — open Common Data Set archive, queryable API, 6,322-school directory

Recommended: option 1. Preservation-archive framing is the emotional hook; "data doesn't get memory-holed" is the part that generates discussion.

## Post body

Hi HN. I built [collegedata.fyi](https://collegedata.fyi), an open archive of every US college's Common Data Set document.

The Common Data Set is a beautiful, almost-forgotten data standard. Nearly thirty years ago, three college-guide publishers (the College Board, Peterson's, and U.S. News) sat down with a bunch of college institutional research offices and agreed on a single 1,105-field template for reporting the numbers that matter about a school: enrollment, admissions, retention, tuition, financial aid, faculty composition. Almost every US college fills one out every year. They publish it on their IR office's website as a PDF.

There's one problem: there is no central index. Every school publishes to its own URL, in its own format, with no standard filename convention. If you want to compare admissions statistics across schools, your options today are "write a custom scraper for each institution," "pay a commercial data provider," or "give up and use federal IPEDS data instead" (which is compliance-reporting data lacking the CDS's admissions granularity).

I fixed that.

**What shipped:**

- 6,322 institutions indexed, 3,950 archived CDS documents, 3,792 extracted to a canonical 1,105-field schema
- Five of six extraction tiers running: filled XLSX (template cell-position map), fillable PDF (AcroForm direct read), flat PDF (Docling + schema-targeting cleaner), image-only scan (force-OCR), and structured HTML (normalizer that reuses the flat-PDF cleaner). DOCX is the only tier still pending
- Public read-only REST API at `api.collegedata.fyi` — query the whole corpus with a public anon key, no account required
- Queryable browser, coverage dashboard, academic positioning, admission strategy, match list builder, and merit profile data built on top of the archive
- Public LLM-citable endpoint at `/api/facts/{school_id}` with the most-asked fields in a flat JSON shape
- 94% accuracy on hand-audited schools (Harvard, Yale, Dartmouth, Harvey Mudd)
- Source files archived on first discovery. If a school removes their CDS, the archive retains the original

**Why the archive angle matters:** schools occasionally remove historical CDS PDFs during site migrations, domain changes, or because IR staff thinks "nobody looks at these anyway." MIT removed every CDS older than 2021 during a 2024 domain migration; the archive has those years because discovery ran before the migration. That's the part that makes this a preservation project, not just a scraping project.

**The trick that made this cheap:** the CDS Initiative publishes a canonical machine-readable schema in the 2025-26 Excel template. I extract it programmatically (1,105 fields, stable question numbers, cross-year-consistent) so every school's data lands in the same shape. No schema design work; the Common Data Set Initiative already did it. A meaningful minority of schools publish their CDS as unflattened fillable PDFs — for those, extraction is a 20-line job via `pypdf.get_fields()`. For the rest (flat PDFs, most common), Docling + a schema-targeting cleaner handles the high-value sections, with deterministic layout overlays and an LLM fallback for thin structural-failure cases.

**Try it:**

- Browse: https://collegedata.fyi
- A big-name example: https://www.collegedata.fyi/schools/mit (four years of CDS, all HTML-sourced)
- API docs and key: https://www.collegedata.fyi/api
- LLM-friendly facts: `curl 'https://www.collegedata.fyi/api/facts/mit'`
- Code: https://github.com/bolewood/collegedata-fyi (MIT license)

**What's next:** the project is at "done for now" for me personally. I'd love contributors for (a) cleaners that target specific section patterns we don't handle yet, (b) adding your school if we missed it, (c) submitting ground-truth data for regression testing. See CONTRIBUTING.md.

Happy to answer questions about the extraction pipeline (tiered routing, the Docling cleaner, the LLM fallback for thin sections), the preservation-archive posture, or the CDS standard itself.

---

## Supporting materials

- **Screenshot to attach:** MIT school page showing the 4-year span (https://www.collegedata.fyi/schools/mit) or the acceptance-vs-yield recipe visualization (https://collegedata.fyi/recipes)
- **The "one surprising number":** MIT 2023-24 jumped from 38 fields extracted to 159 fields after we added Tier 6 HTML extraction — a 4× improvement from a ~150-line normalizer that reuses the existing Tier 4 cleaner
- **The "how did you do this" hook:** Tier 6 took 2 hours end-to-end from spike to production because the cleaner already handled the hard part (table parsing + row-label normalization + schema binding); the new code was just HTML → markdown

## Pre-launch checklist

- [ ] ADR 0008 takedown process exists and is linked from CONTRIBUTING.md
- [ ] `participation_status='withdrawn'` filter applied to frontend queries
- [ ] At least one IR-facing blog or newsletter has been notified (optional but multiplies the organic reach; email 3-5 IR directors you've interacted with before posting)
- [ ] Test `curl 'https://www.collegedata.fyi/api/facts/mit'` returns valid flat JSON
- [ ] Test the homepage loads in under 3 seconds uncached (Show HN is unforgiving about slow sites)
- [ ] Prepare a sorry-we-got-hugged-to-death contingency: Vercel scales automatically but Supabase free tier has connection limits. Monitor `cds_manifest` query latency for the first hour post-launch

## Timing

Best times for Show HN are Tuesday-Thursday, 8-10am PT / 11am-1pm ET. Avoid
Mondays (everyone catching up), Fridays (weekend dead zone), and
tech-conference weeks (drowned out). The first two hours determine whether
the post hits the front page; be available to respond to comments during
that window.
