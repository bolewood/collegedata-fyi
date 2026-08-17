"""Classify official CDS landing pages for the PRD 028 M2.5 worklist.

This is operator data, not a product page. It does not scrape IR pages on
every web request. Output: scratch/seo/vt-shaped-inventory.md

GSC query × position export is still an operator step (Search Console).
This script uses the seed URLs we already store, plus a short manual
fetch of the canaries named in the PRD.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
OFFICIAL_JSON = REPO_ROOT / "web" / "src" / "data" / "official-cds-pages.json"
OUT_PATH = REPO_ROOT / "scratch" / "seo" / "vt-shaped-inventory.md"

CANARIES = [
    {
        "label": "Virginia Tech",
        "school_id": "virginia-tech",
        "ipeds_id": "233921",
        "demand": "GSC head term already #2; Vercel top year page",
        "fetch_url": "https://aie.vt.edu/analytics-and-ai/common-data-set.html",
    },
    {
        "label": "Harvey Mudd",
        "school_id": "harvey-mudd",
        "ipeds_id": "115409",
        "demand": "Hard case: excellent official PDF index",
        "fetch_url": "https://www.hmc.edu/institutional-research/institutional-statistics/common-data-set/",
    },
    {
        "label": "Stanford",
        "school_id": "stanford",
        "ipeds_id": "243744",
        "demand": "Vercel top pages: hub + 2017-18 year page",
        "fetch_url": "https://irds.stanford.edu/data-findings/cds",
    },
    {
        "label": "Texas A&M College Station",
        "school_id": "texas-a-and-m-university-college-station",
        "ipeds_id": "228723",
        "demand": "Vercel top year page 2023-24",
        "fetch_url": None,
    },
    {
        "label": "Harvard",
        "school_id": "harvard",
        "ipeds_id": "166027",
        "demand": "High-demand; excellent official listing expected",
        "fetch_url": "https://oira.harvard.edu/common-data-set/",
    },
]


def classify_html(text: str) -> str:
    lower = text.lower()
    has_pdf_link = ".pdf" in lower
    requestish = (
        "available via request" in lower
        or "available by request" in lower
        or "available on request" in lower
        or "upon request" in lower
    )
    if requestish and not has_pdf_link:
        return "email-or-request gate"
    if requestish and has_pdf_link:
        return "public PDF index (older years on request)"
    if has_pdf_link or "common data set" in lower:
        return "public PDF index (or listing)"
    return "unknown"


def fetch(url: str) -> tuple[int | str, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "collegedata.fyi inventory (PRD 028 M2.5)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read(200_000).decode("utf-8", errors="replace")
            return response.status, classify_html(body)
    except urllib.error.HTTPError as exc:
        return exc.code, "http-error"
    except Exception as exc:  # noqa: BLE001 — operator script
        return "error", str(exc)


def main() -> None:
    payload = yaml.safe_load(SCHOOLS_YAML.read_text())
    schools = payload.get("schools") or []
    html = 0
    pdf = 0
    none = 0
    for school in schools:
        url = (school.get("browse_url") or school.get("discovery_seed_url") or "").strip()
        if not url:
            none += 1
        elif url.lower().split("?", 1)[0].endswith((".pdf", ".xlsx", ".docx")):
            pdf += 1
        else:
            html += 1

    official = json.loads(OFFICIAL_JSON.read_text())
    lines = [
        "# VT-shaped school inventory (PRD 028 M2.5)",
        "",
        "Generated from `tools/finder/schools.yaml` landing-page classification",
        "plus a short fetch of PRD canaries. **Not** a GSC export. Paste the",
        "Search Console `common data set|cds` query × page × position table",
        "into this folder when available.",
        "",
        "## Seed-URL shape (all yaml schools)",
        "",
        f"- HTML-like landing pages: **{html}**",
        f"- Direct document seeds (PDF/XLSX/DOCX): **{pdf}**",
        f"- No seed URL: **{none}**",
        f"- Frontend lookup rows: **{len(official['bySchoolId'])}** school ids",
        "",
        "Direct-document seeds are the first place to look for VT-shaped",
        "schools: Google may index a DAM PDF or nothing, while we have HTML.",
        "",
        "## Canary SERP / official-page checks",
        "",
        "| School | Our slug | Demand proxy | Official URL checked | Fetch | Class |",
        "|---|---|---|---|---|---|",
    ]

    for row in CANARIES:
        url = row["fetch_url"]
        if not url:
            ipeds = row["ipeds_id"]
            generated = official["byIpedsId"].get(ipeds) or official["bySchoolId"].get(
                row["school_id"]
            )
            url = (generated or {}).get("url")
        if not url:
            lines.append(
                f"| {row['label']} | `{row['school_id']}` | {row['demand']} | — | skipped | no HTML seed |"
            )
            continue
        status, klass = fetch(url)
        lines.append(
            f"| {row['label']} | `{row['school_id']}` | {row['demand']} | {url} | {status} | {klass} |"
        )

    lines.extend(
        [
            "",
            "## First-10 attention list (until GSC export lands)",
            "",
            "1. Virginia Tech — protect. Official page is an email gate.",
            "2. Stanford — already converting on year pages; check whether the IR listing is complete for historical years.",
            "3. Texas A&M College Station — Vercel 2023-24 year page; yaml seed is a direct attachment PDF (`texas-am` / IPEDS 228723).",
            "4. Other large publics whose yaml seed is a DAM/PDF rather than an HTML index.",
            "5. Harvey Mudd — cite, do not treat head-term rank as go/no-go.",
            "",
            "Freshness before copy tweaks on any of the above except HMC.",
            "",
        ]
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
