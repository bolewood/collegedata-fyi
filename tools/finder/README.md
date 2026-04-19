# finder

Discovers CDS document URLs across the ~2,400-school US four-year higher-ed corpus and writes them back into a single YAML manifest.

## Why this exists

Every school publishes its Common Data Set to its own URL. There is no central index. If you want the CDS for Yale, you go to `oir.yale.edu`; for Harvey Mudd, `hmc.edu/institutional-research`; for Tulane, `oair.tulane.edu` (yes, the subdomain's `oair`, not `oir`). Hand-curating 2,400 of those is the original sin of every "open college data" project.

This directory turns that problem into a reproducible pipeline. You run one command once a month, and `schools.yaml` stays in sync with reality.

## What's in the directory

| File | Purpose |
|---|---|
| `schools.yaml` | The corpus. 2,434 schools keyed by IPEDS ID, with `discovery_seed_url` (the resolver's seed URL; renamed from `cds_url_hint` in PR 5 of the URL hint refactor), optional `browse_url` (human-friendly URL for contributor tools), `scrape_policy`, `probe_state`. |
| `school_overrides.yaml` | Operator-supplied per-school overrides keyed by `school_id`. Hand-curated `browse_url`, `direct_archive_urls` (year-tagged for Box/Drive/SharePoint-hosted schools), `hosting_override` (CMS/file_storage/auth_required/rendering/waf/notes). Read at edge-function runtime by `_shared/schools.ts`; NOT touched by `build_school_list.py`. |
| `build_school_list.py` | Rebuilds `schools.yaml` from IPEDS HD data, preserving hand-curated overrides. Run rarely (once per IPEDS release). |
| `probe_urls.py` | Discovers CDS URLs for schools where we don't have one. Run monthly. This is the workhorse. |
| `debug_brave.py` | Diagnostic for Brave Search API. Hits 5 hand-verified publishers × 4 query shapes, prints raw results. Used when a Brave run misbehaves. |
| `seed_urls.md` | Hand-curated seed list of elite schools known to publish, plus a known-absent list of schools that refuse (Reed? Not actually. Chicago? Yes — see story below.). |

## What `probe_urls.py` does

For every school in `schools.yaml` with `scrape_policy: unknown`, tries to find a CDS URL by:

1. **URL pattern ladder** (free, fast). DNS-short-circuit each candidate base (`www.X.edu`, `ir.X.edu`, `oair.X.edu`, etc.) so we only HTTP-probe hosts that actually resolve. Then for each live base, try ~30 known IR/provost paths (`/ir/cds/`, `/institutional-research/common-data-set/`, `/provost/oira/common-data-set.cfm`, …). First 200 with a CDS-shaped body wins.
2. **Brave Search API fallback** (cheap, $0.005/query). If no pattern hits, query `site:{domain} "Common Data Set"` and return the first PDF or CDS-titled landing page.
3. **Bing HTML scraping** and **Google Custom Search** (optional alternatives, not used by default).

When a URL is found, write it as `discovery_seed_url` and flip `scrape_policy` to `active`. On failure, write a `probe_state` with `last_result: not_found` so a 30-day cooldown skips the school on the next run.

## Usage

```bash
cd tools/finder

# Monthly cron run — pattern ladder + Brave fallback for unknowns, budget-safe
export BRAVE_API_KEY="..."
python probe_urls.py --brave-fallback

# Probe one school (bypasses cooldown)
python probe_urls.py --only yale --cooldown-days 0

# Force re-probe everything ignoring cooldown (costs ~$11 of Brave quota)
python probe_urls.py --brave-fallback --cooldown-days 0

# Rescue hand-curated seed-list entries that are "active" but have no URL
python probe_urls.py --include-active-no-hint --brave-fallback

# Dry-run a small sample to sanity-check changes
python probe_urls.py --limit 10 --name-contains university

# Shorter per-school budget (useful during development)
python probe_urls.py --school-budget-sec 30
```

SIGINT during a run triggers a partial save, so Ctrl-C is always safe.

## The story: how we got from 68 to 840 active-with-hint in one day

This is what the first 48 hours of finder development actually looked like, kept honest because every one of these bugs is a landmine someone else will step on later.

### Stage 1: the overnight pattern ladder run — 68 hits out of 2,323

First real run. Pattern ladder only, no search fallback. 2,323 schools probed (23 cooldown-skipped from a prior test), 68 found, 2,255 not found. **Hit rate: 2.9%.**

Hand-verifying the misses immediately surfaced two fixable cases: Tulane's CDS lives on `oair.tulane.edu` (we were only trying `ir`, `oir`, `www`); American University's CDS is a `.cfm` page at `/provost/oira/common-data-set.cfm` (we only tried trailing slashes). Patched both — added `oair` to `SUBDOMAINS` and the `.cfm` variant to `PATTERNS`.

But the pattern ladder has a hard ceiling. Most schools publish under custom paths (Villanova's DAM path, Babson's media bucket, Bentley's "business-intelligence-and-enrollment-systems") that you can't reach without search. The 2.9% was roughly the asymptote for pattern-only discovery.

Time to add Brave.

### Stage 2: the \$5 Brave run that found zero schools

Ran the pattern ladder + Brave fallback against all 2,278 not-founds. Script returned zero new active schools. Brave API dashboard showed 1,001 successful requests billed, $5.01 spent, 100.2% of quota burned, zero hits.

This is exactly the kind of failure that kills a side project: fast, quiet, expensive, and indistinguishable from "that school just doesn't publish CDS."

Wrote `debug_brave.py` to pit 4 query variants against 5 hand-verified publishers (Tulane, American, Villanova, Bentley, Babson). Found two bugs stacked on top of each other:

**Bug #1: `filetype:pdf` was killing the query.** The original Brave query was `site:{domain} filetype:pdf "Common Data Set"`. Hand-tested in Brave's web UI: `site:tulane.edu filetype:pdf "Common Data Set"` returns zero results, while `site:tulane.edu "Common Data Set"` returns `oair.tulane.edu/common-data-set` as result #1. Lots of schools publish CDS as HTML landing pages or `.cfm` pages, not raw PDFs, so the filetype restriction was eliminating most of the real answers.

Fix: dropped `filetype:pdf`. Expected this to solve it. It didn't.

**Bug #2: gzip responses were being silently parse-failed.** The Brave API request sends `Accept-Encoding: gzip`. The HTTP helper `_get_full()` returned raw response bytes without decompressing. Then `brave_search()` called `json.loads(gzipped_bytes)`, which raised `JSONDecodeError`, which was silently caught and returned None. **All 1,001 successful HTTP 200 responses from the first run were silently dropped as JSON parse failures.** The filetype bug was secondary; the gzip bug was the primary killer.

Found this by running `debug_brave.py` and hitting `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 1`. Byte 0x1f 0x8b is the gzip magic number. Once seen, obvious.

Fix: decompress transparently in `_get_full()` when `Content-Encoding: gzip`.

Also surfaced HTTP 402 and 429 errors in the Brave path (previously they silently returned None, indistinguishable from "no results"). Now they print `[brave] HTTP 402 — quota/rate limit hit` so the failure mode is visible.

### Stage 3: the real Brave run — 697 hits out of 2,278

With both fixes in, reran the full Brave fallback against the 2,278 pattern-misses. **Result: 697 found, 1,581 not found.** Total active corpus went from 68 to 697. Coverage jumped from 2.9% to 30.6% in a single overnight run.

Crucially, this roughly matches what the CDS wiki suggests is the actual "publishes publicly" ceiling for the 2,400-school addressable corpus — which told us we were near the natural asymptote for search-only discovery, not sitting on a pile of easy wins we were missing.

### Stage 4: the elite-school audit and the Reed / Oregon State mystery

Scanned the 1,581 not-founds for any "suspiciously high-quality schools that should definitely publish." Three real findings out of 126 fuzzy matches:

**University of Chicago: correctly `verified_absent`.** Chicago is famously refuses to publish CDS as part of their yield-protection strategy. The known-absent list was right. Zero action.

**Reed College: two entries in `schools.yaml`, one a ghost.** One labeled `id: reed` with IPEDS 209542 and a hand-curated note claiming Reed boycotts CDS (actually they just boycott US News — they do publish CDS sections). A second labeled `id: reed-college` with IPEDS 209922 which Brave had just found a real CDS URL for.

IPEDS 209542, it turns out, **is Oregon State University, not Reed.** Someone hand-curated the known-absent list with the wrong IPEDS ID on the Reed entry. And `build_school_list.py`'s merge logic, processing IPEDS row 209542, found it in the `existing` dict (the hand-curated Reed entry), and overlaid Reed's `name` and `domain` on top of Oregon State's IPEDS row. The flagship Pac-12 R1 was **silently renamed to "Reed College" in place during every build**, and the real OSU disappeared from the 2,434-school corpus entirely. Only OSU-Cascades (a satellite campus, IPEDS 440828) survived.

One wrong digit in a hand-curated entry was deleting a major R1 from the discovery pipeline forever. This is the kind of bug that only surfaces when you go looking for it.

Fix: deleted the bad `id: reed` entry, re-added a correct `id: oregon-state-university` entry with IPEDS 209542 + domain `oregonstate.edu`, kept the real `reed-college` entry. The merge() bug that lets this happen silently is still open as a follow-up — `build_school_list.py` should warn or abort when a hand-curated name doesn't match the IPEDS row it's overlaying. For now, keep an eye on hand-curated IPEDS IDs.

**University of Illinois Urbana-Champaign: real Brave miss, XLSX format.** Illinois's DMI publishes CDS as `.xlsx`, not PDF, at `https://www.dmi.illinois.edu/stuenr/misc/cds_2024_2025.xlsx`. Brave's index turned out to have effectively zero coverage of `www.dmi.illinois.edu` — `site:illinois.edu "Common Data Set"` returns zero results across every query variant we tried. Brave just doesn't crawl that subdomain. Subdomain coverage gaps in the search engine's index are rare but real. Manually set `cds_url_hint` to the XLSX URL and flipped `scrape_policy` to active. Tier 1 extraction path (openpyxl → Answer Sheet) will handle it directly.

### Stage 5: the silent dead-state audit — 71 elite schools marked "active" with no URL

Next audit: how many `scrape_policy: active` entries have no `cds_url_hint`? Result: **71.** The list was a who's-who of the corpus. Harvard, Princeton, MIT, Stanford, Duke, Cornell, Dartmouth, all eight UCs, every Ivy minus Penn, every top LAC. Yale had a hint. None of the others did.

These came from the original pbworks seed list. Someone (earlier me) had hand-curated them as "we know they publish" and added them to the active bucket. But `probe_urls.py` only probes entries with `scrape_policy: unknown`, so these 71 sat forever in silent dead state: marked active on paper, unreachable in practice, counting toward the coverage metric while being functionally broken.

Fix: added a `--include-active-no-hint` flag that lets the probe pick up active-hintless entries without touching their `scrape_policy`. If the probe finds a URL, it populates the hint. If it doesn't, the school stays active (we know it publishes) with a `probe_state` saying "tried, missed, come back next month."

Ran pattern ladder first. Found 6 via patterns (Bates, Brandeis, Case Western, Dartmouth, Colorado School of Mines, Barnard). Then ran Brave against the remaining 65. **Found 63 of 65 — 97% hit rate.** The Brave query shape is a very good match for elite-school IR office landing pages because those pages tend to have "Common Data Set" prominently in title or description.

### Stage 6: the last 2 — Box and the landing-page void

Two Brave misses left:

**Indiana University Bloomington.** CDS lives on `iuapps.iu.edu/cds/index.html?i=home&p=index` — an IU-wide app server with a query-param URL and a landing page that doesn't have "Common Data Set" in the crawlable body. Brave can't surface it because there's nothing for the crawler to match on.

**Rensselaer Polytechnic Institute.** CDS files are hosted on `rpi.box.com`. **Box files are served behind auth walls to search engine crawlers**, so the content is systematically unindexed. Any school hosting CDS on Box, Google Drive, Dropbox, or similar is invisible to Brave, Google, and Bing. This is a bounded but real blind spot. Unknown how many schools in the 1,581 tail do this — worth a manual sample pass at some point.

Both resolved manually. The elite-seed bucket went to zero.

### Stage 7: the false-positive sweep — 12 schools had the wrong kind of PDF

During the wedge-fix work, caught something concerning: Amherst's newly-Brave-discovered `cds_url_hint` was `Common+Data+Set+Definitions.pdf`. That's the CDS Initiative's template/glossary document, **not Amherst's actual filled-out data.** Brave's landing-page fallback had matched the title "Common Data Set Definitions" and returned it as a hit.

Swept all 852 active hints for this pattern. Found 12 contaminated entries (Amherst, UC San Diego, Berea, Butler, Community College of Denver, Emerson, Langston, Lenoir-Rhyne, Murray State, UT Martin, Utah, West Alabama) — all pointing at template PDFs instead of real data.

Fix: added a `looks_like_template()` filter in `brave_search()` that rejects URL paths containing `definition`, `definitions`, `template`, `instructions`, `blank`, `glossary`. Cleared all 12 polluted hints so the next cron run re-probes them cleanly. Centre College and Pace were correctly preserved — their URL paths contain "initiatives" or similar but point at real CDS landing pages.

### Stage 8: the wedge bug and the 60-second budget

While running pattern ladder against the 71 elite seeds, one worker wedged at position 19 and stopped progressing. 11 minutes later, still stuck. Turned out a single school's base URL was accepting TCP connections but never returning an HTTP response. The per-URL timeout (10 seconds) stacks across ~200 pattern × subdomain × year combinations, and the worker was cycling through dead URLs for what would have been **~33 minutes on a single school** before moving on. In an unattended monthly cron this could eventually finish, but your runtime becomes unpredictable.

Fix: added a per-school wall-clock budget to `probe_school()`. When `time.monotonic() - start >= max_seconds`, return whatever we have and move on. Default 60s — enough for a fully-live school to probe ~60 URLs at the default 1 rps cadence, short enough to cap the total cron runtime at 2,400 × 60s / workers = manageable. Exposed as `--school-budget-sec` for tuning. Tested with a forced 3-second budget on Amherst, confirmed bailout at ~3 seconds wall-clock.

## Current state

After one day of work:

| | Count |
|---|---:|
| Total corpus | 2,434 |
| Active (known publishers) | 852 |
| Active **with clean `discovery_seed_url`** | **840** |
| Active, hint cleared pending re-probe | 12 |
| `verified_absent` (known non-publishers) | 2 |
| Still `unknown` | 1,581 |

**~34.5% of the corpus now has a fetchable CDS URL.** For context, the biggest prior public attempt we're aware of indexed on the order of 80 schools. This is roughly 10× that.

The 1,581 `unknown` tail are Brave-confirmed misses — pattern ladder fails AND Brave returns no CDS-titled result. Candidates: schools that genuinely don't publish CDS, schools that publish under unusual keywords ("Institutional Fact Book"), schools hosting on Box/Drive, and schools whose IR subdomains are thinly indexed. Needs a different discovery strategy and is scoped for a later pass.

## Known blind spots

Things we know we don't catch, documented so they don't surprise anyone later.

- **Box / Drive / Dropbox hosting.** Third-party file services serve files behind auth walls to search crawlers. Any school hosting CDS there is invisible to Brave. RPI is the confirmed case (`rpi.box.com`). Unknown population — needs a manual sample.
- **Subdomain coverage gaps in Brave's index.** `dmi.illinois.edu` is effectively invisible to Brave; `site:illinois.edu "Common Data Set"` returns zero results. Rare but real. Only fix is per-school manual resolution.
- **Opaque file URLs without extension.** UCLA publishes CDS at `apb.ucla.edu/file/<uuid>` — no file extension in the URL, parser currently rejects because `endswith(".pdf")` fails. Needs a `Content-Type` header check during URL validation.
- **Landing pages that aren't direct files.** 289 of the 840 active hints are IR landing pages (like `irp.osu.edu/institutional-data-and-reports`), not direct file URLs. Downstream extraction will need a second-step HTML parse to find the actual PDF/XLSX link. Separate M2 concern.
- **`build_school_list.py` merge silent-overwrite.** If a hand-curated entry has a mismatched IPEDS ID (Reed/OSU bug), the IPEDS row for the wrong school gets silently renamed in place during every build. Low-frequency, high-consequence. `build_school_list.py` should warn when hand-curated name/domain disagrees with the IPEDS row it's overlaying. Open follow-up.

## Architecture notes

**Pattern ladder is free, Brave costs.** Pattern ladder is ~30 patterns × ~9 subdomains × 3 years × HTTP timeout, bounded by the DNS short-circuit and the 60s per-school budget. Zero API cost. Brave is $0.005/query and the free tier is 2,000/month. A full re-run of the 1,581 `unknown` tail costs ~$8 of quota. Order matters: patterns first, Brave for the misses. That's why `--search-only` is opt-in, not default.

**Cooldown is 30 days by default.** A school probed in the last 30 days gets skipped. Found schools stay found. Not-found schools come back for a re-probe on the next month's cron. This is why monthly is the natural cadence.

**Idempotent re-runs.** Running the monthly cron twice in a row is a no-op on the second run (everything's in cooldown). This is intentional and tested.

**SIGINT saves partial progress.** `Ctrl-C` triggers a finally-block save in `probe_urls.py`, so the fraction of schools probed before interrupt get committed to `schools.yaml`. Tested via an 11-minute wedge + SIGINT during the elite-seed pattern run.

## Recommended monthly cron command

```bash
cd /path/to/collegedata-fyi/tools/finder && \
  PYTHONUNBUFFERED=1 python probe_urls.py \
    --brave-fallback \
    --include-active-no-hint \
    2>&1 | tee logs/probe-$(date +%Y%m%d).log
```

`PYTHONUNBUFFERED=1` so `tee` sees output as it happens; `--brave-fallback` for URL discovery; `--include-active-no-hint` to keep rescuing any future seed-list entries that are marked active but lack a hint. Expected runtime: 5-15 minutes depending on how many schools have aged out of cooldown. Expected Brave spend: under $1 for a typical cron.

## See also

- [`schools.yaml`](schools.yaml) — the corpus this tool maintains
- [`seed_urls.md`](seed_urls.md) — hand-curated known publishers and non-publishers
- [`build_school_list.py`](build_school_list.py) — regenerates schools.yaml from IPEDS (run rarely)
- [`debug_brave.py`](debug_brave.py) — run when a Brave run misbehaves
- [`tools/tier2_extractor/`](../tier2_extractor/) — consumes the `discovery_seed_url` values this tool produces
