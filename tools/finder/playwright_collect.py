"""
Playwright-driven URL collection for the top-100 schools.

For each school in the target list, visits the best-guess CDS landing page
with a real headless Chromium (waits for JS to render), collects every
PDF/XLSX/DOCX <a href> that looks CDS-ish, and emits a YAML sidecar file
the operator can review before bulk-archiving.

This is the Week 2 "spike" from PRD 004's Option C: use Playwright as a
URL-COLLECTION TOOL (low risk, one-off), not as a PRODUCTION COMPONENT
(high risk, permanent). The output is a human-reviewable manual_urls.yaml;
from there, a separate command fires archive-process's `force_school` +
well-known-paths fallback to do the actual archiving.

Usage:
    tools/extraction_worker/.venv/bin/python \\
        tools/finder/playwright_collect.py \\
        --output tools/finder/manual_urls.yaml

The output file structure:
    generated_at: ISO8601
    schools:
      princeton:
        starting_url: https://...
        status: ok | no_anchors | nav_error | timeout
        anchors:
          - url: https://...CDS_2024-25.pdf
            text: "Common Data Set 2024-25"
            year: "2024-25"
            is_pdf: true
        error: null
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import yaml
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse


# Hand-compiled starting URLs for the top-100 schools. For schools already in
# schools.yaml we prefer a LANDING-page URL (not a specific PDF) because we
# want Playwright to see the full directory listing. For schools not in
# schools.yaml we use the most common institutional-research path pattern.
# Every URL here was spot-checked during the PRD 004 discovery phase.
STARTING_URLS: dict[str, str] = {
    # Already-in-yaml, landing-page hints
    "mit": "https://ir.mit.edu/project-topic/common-data-set",
    "stanford": "https://irds.stanford.edu/data-findings/cds",
    "yale": "https://oir.yale.edu/common-data-set",
    "upenn": "https://ira.upenn.edu/penn-numbers/common-data-set",
    "columbia": "https://opir.columbia.edu/cds",
    "harvard": "https://oira.harvard.edu/common-data-set/",
    "dartmouth": "https://dartmouth.edu/oir/cds/",
    "carnegie-mellon": "https://www.cmu.edu/ira/CDS/",
    "case-western-reserve-university": "https://case.edu/ir/common-data-set/",
    "rochester-institute-of-technology": "https://rit.edu/institutionalresearch/common-data-set/",
    "auburn-university": "https://ir.auburn.edu/common-data-set/",
    "texas-christian-university": "https://ir.tcu.edu/institutional-research/common-data-set/",
    "university-of-connecticut": "https://oir.uconn.edu/institutional-research/common-data-set",
    "michigan-state-university": "https://ir.msu.edu/cds",
    "washington-university-in-st-louis": "https://wustl.edu/about/compliance-policies/registrar/student-consumer-information/",

    # Already-in-yaml with direct-PDF hints — swap to the known landing page
    "princeton": "https://registrar.princeton.edu/common-data-set",
    "duke": "https://provost.duke.edu/about/administration/office-of-institutional-research/common-data-set/",
    "northwestern": "https://enrollment.northwestern.edu/data/",
    "university-of-notre-dame": "https://www3.nd.edu/~instres/CDS/2022-2023/CDS_2022-2023.pdf",
    "university-of-rochester": "https://www.rochester.edu/provost/ir/data-reports/common-data-set/",
    "university-of-miami": "https://irsa.miami.edu/facts-and-information/common-data-set/",
    "university-of-illinois-urbana-champaign": "https://www.dmi.illinois.edu/stuenr/",
    "penn-state": "https://opair.psu.edu/common-data-set/",
    "university-of-massachusetts-amherst": "https://www.umass.edu/uair/reports/common-data-set",
    "pepperdine-university": "https://www.pepperdine.edu/oie/institutional-research/common-data-set.htm",
    "fordham-university": "https://www.fordham.edu/about/leadership-and-administration/administrative-offices/office-of-the-provost/provost-office-units/institutional-research-and-assessment/consumer-information/common-data-set/",
    "villanova-university": "https://www1.villanova.edu/university/about/facts-figures/common-data-set.html",
    "american-university": "https://www.american.edu/provost/oira/common-data-set.cfm",
    "southern-methodist-university": "https://www.smu.edu/ir/common-data-sets",
    "baylor-university": "https://ir.web.baylor.edu/common-data-sets",
    "university-of-iowa": "https://provost.uiowa.edu/common-data-set",
    "stevens-institute-of-technology": "https://www.stevens.edu/institutional-research-and-analytics/common-data-set",
    "marquette-university": "https://www.marquette.edu/institutional-research-analysis/common-data-set.php",
    "boston-college": "https://www.bc.edu/bc-web/offices/institutional-research-planning.html",
    "boston-university": "https://www.bu.edu/asir/bu-institutional-datasets/common-data-set/",
    "william-and-mary": "https://www.wm.edu/offices/ir/university_data/cds/",
    "pomona-college": "https://www.pomona.edu/administration/institutional-research/common-data-sets",
    "wellesley-college": "https://www.wellesley.edu/institutionalplanningandassessment/institutional-research/common-data-set",
    "carleton-college": "https://www.carleton.edu/ir/common-data-set/",
    "middlebury-college": "https://www.middlebury.edu/office/institutional-research-and-analysis/common-data-sets",
    "vassar-college": "https://offices.vassar.edu/institutional-research/common-data-set/",
    "smith-college": "https://www.smith.edu/about-smith/institutional-research/reports",
    "haverford-college": "https://www.haverford.edu/institutional-research/common-data-set",
    "grinnell-college": "https://www.grinnell.edu/about/leadership/offices/analytic-support-institutional-research/common-data-set",
    "colgate-university": "https://www.colgate.edu/about/institutional-research/common-data-set",
    "wesleyan-university": "https://www.wesleyan.edu/ir/data-sets/cds.html",
    "university-of-richmond": "https://ifx.richmond.edu/cds",
    "macalester-college": "https://www.macalester.edu/institutional-research/common-data-set/",
    "williams-college": "https://www.williams.edu/institutional-research/files/2019/08/2010-2011_williams_common_data_set.pdf",

    # Not in schools.yaml at all — curated from public IR pages
    "university-of-chicago": "https://data.uchicago.edu/common-data-set/",
    "caltech": "https://finance.caltech.edu/Resources/cds",
    "johns-hopkins-university": "https://oira.jhu.edu/reports-2/",
    "university-of-california-berkeley": "https://opa.berkeley.edu/campus-data/common-data-set",
    "university-of-california-los-angeles": "https://apb.ucla.edu/campus-statistics/common-data-set",
    "rice-university": "https://ideas.rice.edu/reporting-analytics/common-data-set/",
    "vanderbilt-university": "https://www.vanderbilt.edu/data/public-data/common-data-sets/",
    "university-of-michigan": "https://obp.umich.edu/campus-statistics/common-data-set/",
    "georgetown-university": "https://oads.georgetown.edu/commondataset/",
    "university-of-north-carolina-at-chapel-hill": "https://oira.unc.edu/reports/institutional-reports/common-data-set/",
    "emory-university": "https://provost.emory.edu/planning-administration/data/common-data-set.html",
    "university-of-virginia-main-campus": "https://ira.virginia.edu/data-analytics/common-data-set-initiatve",
    "university-of-southern-california": "https://oir.usc.edu/statistics-data-visualization/common-data-set/",
    "new-york-university": "https://www.nyu.edu/employees/resources-and-services/administrative-services/institutional-research/self-service-reporting-resources/factbook.html?challenge=d06e90d7-4d8f-4b88-9d8c-10b73beb60f1",
    "university-of-florida": "https://ir.aa.ufl.edu/reports/cds-reports/",
    "university-of-texas-at-austin": "https://reports.utexas.edu/common-data-set",
    "university-of-wisconsin-madison": "https://data.wisc.edu/common-data-set-and-rankings/",
    "georgia-institute-of-technology-main-campus": "https://irp.gatech.edu/common-data-set",
    "university-of-california-san-diego": "https://ir.ucsd.edu/stats/undergrad/cds.html",
    "university-of-california-davis": "https://aggiedata.ucdavis.edu/common-data-set",
    "university-of-california-irvine": "https://irap.uci.edu/institutional-research/data-hub/common-data-set/",
    "university-of-california-santa-barbara": "https://bap.ucsb.edu/institutional-research",
    "tufts-university": "https://provost.tufts.edu/institutionalresearch/common-data-set/",
    "wake-forest-university": "https://ir.wfu.edu/common-data-set/",
    "tulane-university": "https://oair.tulane.edu/common-data-set",
    "university-of-washington-seattle-campus": "https://www.washington.edu/opb/common-data-set/",
    "ohio-state-university": "https://irp.osu.edu/institutional-data-and-reports",
    "purdue-university": "https://www.purdue.edu/idata/products-services/common-data-set/",
    "university-of-maryland-college-park": "https://www.irpa.umd.edu/InstitutionalData/cds.html",
    "lehigh-university": "https://data.lehigh.edu/common-data-set",
    "northeastern-university": "https://uds.northeastern.edu/university-facts/common-data-set/",
    "virginia-tech": "https://aie.vt.edu/analytics-and-ai/common-data-set.html",
    "texas-a-and-m-university-college-station": "https://abpa.tamu.edu/reports-catalog/student",
    "syracuse-university": "https://institutionaldata.syr.edu/key-data/",
    "university-of-minnesota-twin-cities": "https://idr.umn.edu/institutional-metrics-compliance-reporting/twin-cities-campus-factbook",
    "university-of-pittsburgh": "https://www.ir.pitt.edu/university-information/common-data-set",
    "rutgers-university-new-brunswick": "https://oirds.rutgers.edu/ReportingCommonDataSet.html",
    "indiana-university-bloomington": "https://iuapps.iu.edu/cds/index.html?i=home&p=index",
    "brandeis-university": "https://www.brandeis.edu/institutional-research/common-data-set/index.html",
    "george-washington-university": "https://irp.gwu.edu/common-data-set",
    "drexel-university": "https://drexel.edu/institutionalresearch/university-data/common_data",
    "university-of-delaware": "https://ire.udel.edu/common-data-set/",
    "amherst-college": "https://www.amherst.edu/offices/institutional-research/cds",
    "swarthmore-college": "https://www.swarthmore.edu/institutional-research/common-data-set",
    "bowdoin-college": "https://www.bowdoin.edu/ir/common-data/index.html",
    "claremont-mckenna-college": "https://www.cmc.edu/institutional-research/common-data-set",
    "washington-and-lee-university": "https://my.wlu.edu/accreditation-and-institutional-research/common-data-set",
    "hamilton-college": "https://www.hamilton.edu/offices/oir/common-data-sets",
    "colby-college": "https://www.colby.edu/oir/common-data-set/",
    "barnard-college": "https://barnard.edu/institutional-effectiveness/common-data-set/",
    "bates-college": "https://www.bates.edu/ir/common-data-set/",
}


# CDS-keyword regex mirrors the resolver's detection.
CDS_KEYWORDS_RE = re.compile(r"common\s*data\s*set|\bcds(?![a-z])", re.I)
DOCUMENT_EXT_RE = re.compile(r"\.(pdf|xlsx|docx)(\?|#|$)", re.I)
YEAR_RE = re.compile(r"(20\d\d)[-_](20\d\d|\d\d)")

COMMONDATASET_ORG_RE = re.compile(r"^https?://(?:[^/]+\.)?commondataset\.org", re.I)

# Mirror of resolve.ts parentLandingCandidates. When the starting URL is a
# direct document, walk up to 3 ancestor directories, but only those whose
# path contains a CDS-like segment (avoids Drupal/WordPress upload trees
# that happen to sit N levels below an IR page).
CDS_LIKE_PATH_SEGMENT_RE = re.compile(
    r"^(cds|common-data-set|common_data_set|institutional-research|"
    r"institutional_research|ir|oir|oira|iro|irp)$",
    re.I,
)
MAX_PARENT_LEVELS = 3

# Mirror of resolve.ts WELL_KNOWN_CDS_LANDING_PATHS (PR 1). Kept in sync by
# convention — if resolve.ts grows paths, update here too. Used only as a
# last-resort fallback when the parent walk yields nothing (covers cases
# where the direct-PDF hint lives under /wp-content/uploads/ or similar
# opaque trees with no CDS-like ancestor segment).
WELL_KNOWN_CDS_LANDING_PATHS: tuple[str, ...] = (
    "/common-data-set/", "/common-data-set", "/common-data-sets/",
    "/cds/", "/cds", "/commondataset/",
    "/institutional-research/common-data-set/",
    "/ir/common-data-set/", "/oir/common-data-set/",
    "/institutionalresearch/common-data-set/",
    "/institutional-research/cds/", "/ir/cds/",
    "/institutional-data/common-data-set",
    "/reports/common-data-set",
    "/reports/cds-reports/",
)


def parent_landing_candidates(hint: str) -> list[str]:
    """Python port of resolve.ts parentLandingCandidates."""
    parsed = urlparse(hint)
    if parsed.scheme not in ("http", "https"):
        return []
    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        return []
    without_filename = segments[:-1]
    if not without_filename:
        return []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    out: list[str] = []
    for i in range(min(MAX_PARENT_LEVELS, len(without_filename))):
        ancestor = without_filename[: len(without_filename) - i]
        if not ancestor:
            break
        if not any(CDS_LIKE_PATH_SEGMENT_RE.match(s) for s in ancestor):
            continue
        out.append(f"{origin}/{'/'.join(ancestor)}/")
    return out


def well_known_path_urls(hint: str) -> list[str]:
    """Python port of resolve.ts wellKnownPathUrls."""
    parsed = urlparse(hint)
    if parsed.scheme not in ("http", "https"):
        return []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return [origin + p for p in WELL_KNOWN_CDS_LANDING_PATHS]


def _build_walk_up_candidates(hint: str) -> list[str]:
    """Order walk-up candidates so the highest-signal ones probe first.

    Crucial for Cloudflare/Akamai-protected hosts (Williams, JHU, Fordham),
    which flip to a bot-challenge page after only ~4 suspicious requests
    in a row. Probing the wrong URLs first doesn't just waste time — it
    poisons the session so the correct URL then serves the challenge page
    instead of the CDS HTML we need.

    Order:
      1. Well-known paths that SHARE a CDS-like segment with the hint —
         e.g. hint has /institutional-research/ → try
         /institutional-research/common-data-set/ and /institutional-research/cds/
         FIRST. On Drupal/WordPress-hosted IR sites, these are the actual
         landing pages; the parent directories below return 403 and
         poison the session before we get here otherwise.
      2. Parent directories (restricted to CDS-like ancestors). These
         help for the minority of sites that expose auto-index pages, but
         on modern CMS they're usually 403s — so they come second.
      3. Remaining well-known paths (root-level: /common-data-set/, /cds/,
         etc.). Matter mostly for IR-subdomain hosts like ir.mit.edu or
         irp.dpb.cornell.edu where there's no CDS-like ancestor to match.
    """
    parents = parent_landing_candidates(hint)
    wk_all = well_known_path_urls(hint)

    parsed = urlparse(hint)
    hint_segments = [s for s in parsed.path.split("/") if s]
    hint_cds_ancestors = {
        s.lower() for s in hint_segments if CDS_LIKE_PATH_SEGMENT_RE.match(s)
    }

    prioritized: list[str] = []
    deferred: list[str] = []
    for wk in wk_all:
        wk_segments = [s.lower() for s in urlparse(wk).path.split("/") if s]
        shares_prefix = bool(hint_cds_ancestors) and bool(
            hint_cds_ancestors.intersection(wk_segments)
        )
        (prioritized if shares_prefix else deferred).append(wk)

    seen: set[str] = set()
    ordered: list[str] = []
    for u in (*prioritized, *parents, *deferred):
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def is_download_nav_error(msg: str) -> bool:
    """Chromium raises 'Download is starting' when goto() lands on a PDF
    whose server sends Content-Disposition: attachment. That's the main
    direct-doc signal; also match the variants Playwright emits."""
    if not msg:
        return False
    m = msg.lower()
    return ("download is starting" in m
            or "net::err_aborted" in m
            or "page.goto: net::err_download" in m)


def normalize_year(text: str) -> str | None:
    m = YEAR_RE.search(text)
    if not m:
        return None
    y1, y2 = m.group(1), m.group(2)
    if len(y2) == 2:
        y2 = y1[:2] + y2
    return f"{y1[:4]}-{y2[-2:]}"


def is_cds_like(href: str, text: str) -> bool:
    hay = (href + " " + text).lower()
    if not CDS_KEYWORDS_RE.search(hay):
        return False
    if COMMONDATASET_ORG_RE.match(href):
        return False
    return True


@dataclass
class AnchorResult:
    url: str
    text: str
    year: str | None
    is_document: bool


@dataclass
class SchoolResult:
    school_id: str
    starting_url: str
    final_url: str | None
    # URL of the landing page whose anchors populated `anchors`. Differs
    # from starting_url when the walk-up logic recovered from a direct-doc
    # hint by stepping up the path or probing well-known CDS landings.
    # `null` when the starting_url was itself the successful landing.
    landing_url_found: str | None
    status: str          # "ok" | "no_anchors" | "nav_error" | "timeout"
    anchors: list[AnchorResult]
    error: str | None
    duration_ms: int


@dataclass
class ProbeOutcome:
    """Single-URL probe result. Used by collect_for_school's orchestration
    to pick the best landing candidate across the original hint + ancestors
    + well-known paths."""
    final_url: str | None
    anchors: list[AnchorResult]
    error: str | None
    # Set when the browser landed on (or was redirected to) a document
    # itself — the caller can use this as a valid single-anchor fallback.
    landed_on_document: bool
    # Set when Chromium fired a download event during navigation. Strong
    # signal the target URL is a direct PDF and the caller should walk up.
    download_triggered: bool


def _probe_url(page, url: str, is_starting_hint: bool = False) -> ProbeOutcome:
    """Navigate to `url` and collect CDS-like anchors from its rendered DOM.

    Does NOT decide whether to walk up — that's the caller's job. Returns
    a ProbeOutcome the orchestrator can compare across candidates.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        error_msg: str | None = None
    except Exception as e:
        msg = str(e)
        # A JS-triggered redirect (often to the asset we wanted) — wait
        # briefly for whatever the browser landed on.
        if "interrupted by another navigation" in msg or "ERR_ABORTED" in msg:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
                error_msg = None
            except Exception:
                error_msg = msg[:200]
        elif is_download_nav_error(msg):
            # Direct-doc navigation — Chromium fired a download instead of
            # rendering. Caller (when this is the starting hint) should
            # walk up. Return no anchors; page.url is unreliable here.
            return ProbeOutcome(
                final_url=None, anchors=[], error=msg[:200],
                landed_on_document=True, download_triggered=True,
            )
        else:
            return ProbeOutcome(
                final_url=None, anchors=[], error=msg[:200],
                landed_on_document=False, download_triggered=False,
            )

    try:
        page.wait_for_load_state("networkidle", timeout=6_000)
    except Exception:
        pass  # expected when sites keep long-lived connections open

    final_url = page.url

    # If the browser landed on a PDF inline (rare — usually blocked by the
    # download dialog), emit it as a single-anchor CDS doc.
    if DOCUMENT_EXT_RE.search(final_url):
        parsed = urlparse(final_url)
        fname = parsed.path.rsplit("/", 1)[-1]
        if is_cds_like(final_url, fname):
            return ProbeOutcome(
                final_url=final_url,
                anchors=[AnchorResult(
                    url=final_url, text=fname,
                    year=normalize_year(final_url),
                    is_document=True,
                )],
                error=None, landed_on_document=True, download_triggered=False,
            )
        return ProbeOutcome(
            final_url=final_url, anchors=[], error=None,
            landed_on_document=True, download_triggered=False,
        )

    raw = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('a[href]').forEach(a => {
                out.push({href: a.href, text: (a.textContent || '').trim()});
            });
            return out;
        }"""
    )

    anchors: list[AnchorResult] = []
    seen: set[str] = set()
    for a in raw:
        href = a.get("href") or ""
        text = a.get("text") or ""
        if not href.startswith(("http://", "https://")):
            continue
        if not is_cds_like(href, text):
            continue
        key = href.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        anchors.append(AnchorResult(
            url=href, text=text[:120], year=normalize_year(href + " " + text),
            is_document=bool(DOCUMENT_EXT_RE.search(href)),
        ))

    return ProbeOutcome(
        final_url=final_url, anchors=anchors, error=error_msg,
        landed_on_document=False, download_triggered=False,
    )


def _count_doc_anchors(anchors: list[AnchorResult]) -> int:
    """Document anchors are the thing we actually want to archive; a
    landing page that lists 30 PDFs beats one that lists 2 PDFs + 10 HTML
    subpages."""
    return sum(1 for a in anchors if a.is_document)


def collect_for_school(page, school_id: str, url: str) -> SchoolResult:
    """Try the starting hint; if it's a direct-doc hint (by extension, by
    download event, or by 0-anchor result) walk up the path and fall back
    to well-known CDS landing paths on the same host. Return the best
    landing page found, tagged with `landing_url_found` when the original
    hint wasn't itself the winner.
    """
    t0 = time.monotonic()
    starting_is_direct_doc = bool(DOCUMENT_EXT_RE.search(url))

    # First pass: the operator-provided hint.
    first = _probe_url(page, url, is_starting_hint=True)
    best_url = url
    best = first

    # Walk-up trigger conditions:
    #   (a) starting URL has a document extension (always try, even if the
    #       first probe somehow returned anchors — a direct PDF URL rarely
    #       does, but if it did we want the sibling years too);
    #   (b) first probe fired a download event (Chromium's strongest
    #       "this is a direct doc" signal);
    #   (c) first probe returned zero CDS anchors — the hint may be a
    #       landing page that's since been moved, so try the well-known
    #       paths as a last resort.
    needs_walk_up = (
        starting_is_direct_doc
        or first.download_triggered
        or _count_doc_anchors(first.anchors) == 0
    )

    if needs_walk_up:
        for candidate in _build_walk_up_candidates(url):
            # Cheap safety: don't re-probe the original hint.
            if candidate == url:
                continue
            outcome = _probe_url(page, candidate)
            docs = _count_doc_anchors(outcome.anchors)
            if docs > _count_doc_anchors(best.anchors):
                best = outcome
                best_url = candidate
                # Early-out aggressively: 5+ document anchors is already a
                # multi-year CDS landing page. Stopping quickly matters
                # for WAF-protected hosts (Cloudflare starts challenging
                # after ~8-10 404s; every avoided probe preserves session
                # trust on hosts we haven't hit yet).
                if docs >= 5:
                    break

    # Final status classification.
    if best.anchors:
        status = "ok"
    elif best.download_triggered:
        status = "nav_error"
    elif best.error:
        status = "nav_error"
    else:
        status = "no_anchors"

    landing_url_found = best_url if best_url != url else None

    return SchoolResult(
        school_id=school_id,
        starting_url=url,
        final_url=best.final_url,
        landing_url_found=landing_url_found,
        status=status,
        anchors=best.anchors,
        error=best.error,
        duration_ms=int((time.monotonic() - t0) * 1000),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--output", type=Path,
                    default=Path("tools/finder/manual_urls.yaml"))
    ap.add_argument("--school", "--only", dest="school",
                    help="Run one specific school only (by id)")
    ap.add_argument("--limit", type=int, help="Cap schools processed")
    ap.add_argument("--merge", action="store_true",
                    help="Merge into existing --output file rather than overwriting. "
                         "Untouched schools keep their previous result.")
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--no-headless", dest="headless", action="store_false")
    args = ap.parse_args()

    targets = list(STARTING_URLS.items())
    if args.school:
        targets = [(k, v) for k, v in targets if k == args.school]
    if args.limit:
        targets = targets[: args.limit]

    from playwright.sync_api import sync_playwright

    results: list[SchoolResult] = []
    UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/131.0.0.0 Safari/537.36")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        for i, (sid, url) in enumerate(targets):
            print(f"  [{i+1:>3}/{len(targets)}]  {sid:<50} {url[:70]}",
                  file=sys.stderr, flush=True)
            r = collect_for_school(page, sid, url)
            walked = f" via {r.landing_url_found}" if r.landing_url_found else ""
            print(f"         → status={r.status:<12} anchors={len(r.anchors):>3} "
                  f"{r.duration_ms}ms{walked}", file=sys.stderr, flush=True)
            results.append(r)
        browser.close()

    def school_payload(r: SchoolResult) -> dict:
        return {
            "starting_url": r.starting_url,
            "landing_url_found": r.landing_url_found,
            "final_url": r.final_url,
            "status": r.status,
            "error": r.error,
            "duration_ms": r.duration_ms,
            "anchors": [asdict(a) for a in r.anchors],
        }

    # Merge mode: preserve untouched schools from the prior run so a
    # single-school re-probe (--only williams-college) doesn't wipe the
    # other 99 entries. Overwrite-mode (default) keeps the existing
    # behavior for full sweeps.
    schools_out: dict = {}
    if args.merge and args.output.exists():
        try:
            prior = yaml.safe_load(args.output.read_text()) or {}
            schools_out = dict(prior.get("schools") or {})
        except Exception as e:
            print(f"warn: could not parse existing {args.output}: {e}",
                  file=sys.stderr)

    for r in results:
        schools_out[r.school_id] = school_payload(r)

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "tools/finder/playwright_collect.py",
        "note": (
            "Operator-reviewable list of CDS URLs collected via JS-rendered "
            "pages. Review each entry, then pipe through a small follow-up "
            "tool that archives the URLs. See PRD 004 Option C."
        ),
        "schools": schools_out,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(output, sort_keys=False, width=120))

    # Summary.
    ok = sum(1 for r in results if r.status == "ok")
    total_anchors = sum(len(r.anchors) for r in results)
    print(f"\nDone: {ok}/{len(results)} schools yielded CDS anchors, "
          f"{total_anchors} total anchors collected.", file=sys.stderr)
    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
