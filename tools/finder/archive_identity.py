"""Resolve archive writes onto the curated public slug and IPEDS UNITID.

``cds_documents.school_id`` is the public URL slug from ``schools.yaml``.
IPEDS UNITID is the institution identity behind that slug. The Python
headless archive path used to write the slug into ``school_name`` and
omit ``ipeds_id``, which is how University of Florida landed as ``uf``
with a null UNITID. Deno archive-process already fail-closes through
``resolveSchoolName`` / ``resolveSchoolIpedsId``; this module is the
same contract for Playwright ingest.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    from tools.finder.identity_guard import (
        host_matches_domain,
        load_school_claims,
        source_host,
    )
except ModuleNotFoundError:  # python tools/finder/headless_archive.py
    from identity_guard import host_matches_domain, load_school_claims, source_host


class UnknownArchiveSchoolError(ValueError):
    """``school_id`` is not a curated schools.yaml slug."""


class AmbiguousArchiveSchoolError(UnknownArchiveSchoolError):
    """``school_id`` names more than one institution in schools.yaml.

    schools.yaml still carries slugs shared by several UNITIDs (for example
    ``bethel-university`` for Indiana, Minnesota and Tennessee). A dict keyed
    by slug silently keeps the last entry, which stamped Bethel Tennessee's id
    on Bethel Minnesota's documents. Callers must say which institution they
    mean (``ipeds_id=``) or fix the slug.
    """


@lru_cache(maxsize=1)
def _claims_by_school_id() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in load_school_claims():
        grouped.setdefault(claim["school_id"], []).append(claim)
    return grouped


def resolve_archive_identity(
    school_id: str,
    ipeds_id: str | None = None,
    source_url: str | None = None,
    *,
    claims_by_school_id: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, str]:
    """Return the official display name and UNITID for a public slug.

    Raises ``UnknownArchiveSchoolError`` when the slug is missing, has
    no UNITID, or has no real name. Callers must not fall back to the
    slug as a display name.

    A slug shared by several UNITIDs resolves only when ``ipeds_id`` names one,
    or when the host of ``source_url`` matches the ``domain`` of exactly one
    schools.yaml row (host equals the domain or is a subdomain). Otherwise it
    raises ``AmbiguousArchiveSchoolError``: never a guess.
    """
    sid = str(school_id or "").strip()
    if not sid:
        raise UnknownArchiveSchoolError("school_id must be non-empty")
    table = claims_by_school_id if claims_by_school_id is not None else _claims_by_school_id()
    claims = table.get(sid, [])
    if not claims:
        raise UnknownArchiveSchoolError(
            f"school_id {sid!r} is not in schools.yaml; "
            "refuse to archive under an unmapped slug"
        )
    wanted = str(ipeds_id or "").strip()
    if wanted:
        claims = [c for c in claims if c["ipeds_id"] == wanted]
        if not claims:
            raise UnknownArchiveSchoolError(
                f"school_id {sid!r} has no schools.yaml row with ipeds_id {wanted}"
            )
    # Distinct UNITIDs, not rows: a slug listed twice with one id is not shared.
    distinct = {c["ipeds_id"] for c in claims}
    if len(distinct) > 1:
        host = source_host(source_url)
        matched = [c for c in claims if host_matches_domain(host, c.get("claimed_domain"))]
        if len({c["ipeds_id"] for c in matched}) == 1:
            claims = matched
        else:
            raise AmbiguousArchiveSchoolError(
                f"school_id {sid!r} is shared by ipeds_ids {sorted(distinct)} in "
                f"schools.yaml and source host {host or '(none)'!r} does not pick "
                "exactly one; pass the intended ipeds_id or make the slug unique"
            )
    claim = claims[0]
    name = str(claim.get("claimed_name") or "").strip()
    ipeds_id = str(claim.get("ipeds_id") or "").strip()
    if not name or name == sid:
        raise UnknownArchiveSchoolError(
            f"schools.yaml id {sid!r} has no official name distinct from the slug"
        )
    if not ipeds_id:
        raise UnknownArchiveSchoolError(
            f"schools.yaml id {sid!r} is missing ipeds_id"
        )
    return {
        "school_id": sid,
        "school_name": name,
        "ipeds_id": ipeds_id,
    }
