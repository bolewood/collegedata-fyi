"""Canonical school_id aliases for operator WAF YAML keys.

headless_download writes cds_documents.school_id from the YAML key, so a
stale alias (new-york-university vs nyu) would archive under the wrong slug.
"""

from __future__ import annotations

WAF_SCHOOL_ID_ALIASES = {
    "new-york-university": "nyu",
    "johns-hopkins-university": "johns-hopkins",
    "williams": "williams-college",
}


def canonical_waf_school_id(raw_sid: str) -> str:
    return WAF_SCHOOL_ID_ALIASES.get(raw_sid, raw_sid)


def select_waf_schools(schools: dict, only: str | None) -> dict:
    """Filter the YAML map to one school, accepting canonical or alias keys."""
    if not only:
        return schools
    if only in schools:
        return {only: schools[only]}
    canonical = canonical_waf_school_id(only)
    if canonical in schools:
        return {canonical: schools[canonical]}
    for raw, canon in WAF_SCHOOL_ID_ALIASES.items():
        if canon == only and raw in schools:
            return {raw: schools[raw]}
    return {}
