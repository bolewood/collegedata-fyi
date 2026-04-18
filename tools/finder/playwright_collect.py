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
    status: str          # "ok" | "no_anchors" | "nav_error" | "timeout"
    anchors: list[AnchorResult]
    error: str | None
    duration_ms: int


def collect_for_school(page, school_id: str, url: str) -> SchoolResult:
    t0 = time.monotonic()
    goto_error: str | None = None
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
    except Exception as e:
        msg = str(e)
        # "Navigation ... is interrupted by another navigation to ..." means
        # the page JS-triggered a redirect (often to a PDF). Playwright
        # raises, but the browser has already landed somewhere useful. Wait
        # briefly and inspect the current URL rather than failing.
        if "interrupted by another navigation" in msg or "ERR_ABORTED" in msg:
            goto_error = None
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass
        else:
            return SchoolResult(
                school_id=school_id, starting_url=url, final_url=None,
                status="nav_error", anchors=[], error=msg[:200],
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

    # Small wait for JS-rendered content to settle.
    try:
        page.wait_for_load_state("networkidle", timeout=6_000)
    except Exception:
        pass  # timeout here is OK

    final_url = page.url

    # If the browser landed directly on a PDF (redirect chain), that URL
    # alone is a valid CDS doc. Emit it as a single-anchor result so the
    # operator still gets value.
    if DOCUMENT_EXT_RE.search(final_url):
        parsed = urlparse(final_url)
        fname = parsed.path.rsplit("/", 1)[-1]
        if is_cds_like(final_url, fname):
            return SchoolResult(
                school_id=school_id, starting_url=url, final_url=final_url,
                status="ok", anchors=[AnchorResult(
                    url=final_url, text=fname,
                    year=normalize_year(final_url),
                    is_document=True,
                )], error=None,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
    # Pull every <a href> via DOM query (post-render).
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
    seen = set()
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

    status = "ok" if anchors else "no_anchors"
    return SchoolResult(
        school_id=school_id, starting_url=url, final_url=final_url,
        status=status, anchors=anchors, error=None,
        duration_ms=int((time.monotonic() - t0) * 1000),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--output", type=Path,
                    default=Path("tools/finder/manual_urls.yaml"))
    ap.add_argument("--school", help="Run one specific school only (by id)")
    ap.add_argument("--limit", type=int, help="Cap schools processed")
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
            print(f"         → status={r.status:<12} anchors={len(r.anchors):>3} "
                  f"{r.duration_ms}ms", file=sys.stderr, flush=True)
            results.append(r)
        browser.close()

    # Emit the YAML sidecar.
    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "tools/finder/playwright_collect.py",
        "note": (
            "Operator-reviewable list of CDS URLs collected via JS-rendered "
            "pages. Review each entry, then pipe through a small follow-up "
            "tool that archives the URLs. See PRD 004 Option C."
        ),
        "schools": {
            r.school_id: {
                "starting_url": r.starting_url,
                "final_url": r.final_url,
                "status": r.status,
                "error": r.error,
                "duration_ms": r.duration_ms,
                "anchors": [asdict(a) for a in r.anchors],
            }
            for r in results
        },
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
