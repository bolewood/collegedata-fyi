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


RESIDENTIAL_ONLY_CAP = 5


def parse_only_ids(raw: str | list[str] | None) -> list[str]:
    """Split a comma list of school ids and canonicalize aliases.

    Empty tokens are dropped. Order is preserved. Duplicates collapse.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        parts = raw
    else:
        parts = str(raw).split(",")
    ids: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = str(part).strip()
        if not token:
            continue
        sid = canonical_waf_school_id(token)
        if sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids


def validate_only_ids(
    ids: list[str],
    *,
    require: bool = False,
    cap: int | None = None,
) -> list[str]:
    if require and not ids:
        raise SystemExit("residential phases require --only (empty targeting is rejected)")
    if cap is not None and len(ids) > cap:
        raise SystemExit(f"--only has {len(ids)} ids; cap is {cap}")
    return ids


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
