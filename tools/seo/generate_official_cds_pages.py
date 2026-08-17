"""Build the frontend lookup of official school CDS landing pages.

PRD 028 M1: school/year leads should link the school's own CDS page when we
have a usable HTML URL. Direct PDF/XLSX seeds are not landing pages and must
not be labeled as "the school's own CDS page."

Curated overrides win. Virginia Tech's yaml seed is a DAM PDF; the public
HTML page is the email-request gate we actually want to cite.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
OUT_PATH = REPO_ROOT / "web" / "src" / "data" / "official-cds-pages.json"

DIRECT_DOC_SUFFIXES = (".pdf", ".xlsx", ".xls", ".docx", ".doc", ".csv", ".zip")

# Only set access="request" when we have read the page. Do not guess.
CURATED: dict[str, dict[str, str]] = {
    "virginia-tech": {
        "url": "https://aie.vt.edu/analytics-and-ai/common-data-set.html",
        "access": "request",
        "ipeds_id": "233921",
        "also_school_ids": "virginia-polytechnic-institute-and-state-university",
    },
    "harvey-mudd": {
        "url": "https://www.hmc.edu/institutional-research/institutional-statistics/common-data-set/",
        "access": "public",
        "ipeds_id": "115409",
    },
}


def is_direct_document(url: str) -> bool:
    if not url:
        return True
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(DIRECT_DOC_SUFFIXES)


def landing_url(school: dict) -> str | None:
    for key in ("browse_url", "discovery_seed_url"):
        url = (school.get(key) or "").strip()
        if url and not is_direct_document(url):
            return url
    return None


def main() -> None:
    payload = yaml.safe_load(SCHOOLS_YAML.read_text())
    by_school_id: dict[str, dict[str, str]] = {}
    by_ipeds_id: dict[str, dict[str, str]] = {}

    for school in payload.get("schools") or []:
        school_id = school.get("id")
        ipeds_id = str(school.get("ipeds_id") or "").strip()
        url = landing_url(school)
        if not school_id or not url:
            continue
        entry = {"url": url, "access": "unknown"}
        by_school_id[school_id] = entry
        if ipeds_id:
            by_ipeds_id[ipeds_id] = entry

    for school_id, curated in CURATED.items():
        entry = {"url": curated["url"], "access": curated["access"]}
        by_school_id[school_id] = entry
        for extra in (curated.get("also_school_ids") or "").split(","):
            extra = extra.strip()
            if extra:
                by_school_id[extra] = entry
        ipeds_id = curated.get("ipeds_id")
        if ipeds_id:
            by_ipeds_id[ipeds_id] = entry

    OUT_PATH.write_text(
        json.dumps(
            {
                "generated_from": "tools/finder/schools.yaml",
                "bySchoolId": dict(sorted(by_school_id.items())),
                "byIpedsId": dict(sorted(by_ipeds_id.items())),
            },
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)} "
        f"({len(by_school_id)} school ids, {len(by_ipeds_id)} ipeds ids)"
    )


if __name__ == "__main__":
    main()
