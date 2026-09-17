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
    from tools.finder.identity_guard import load_school_claims
except ModuleNotFoundError:  # python tools/finder/headless_archive.py
    from identity_guard import load_school_claims


class UnknownArchiveSchoolError(ValueError):
    """``school_id`` is not a curated schools.yaml slug."""


@lru_cache(maxsize=1)
def _claims_by_school_id() -> dict[str, dict[str, Any]]:
    return {claim["school_id"]: claim for claim in load_school_claims()}


def resolve_archive_identity(school_id: str) -> dict[str, str]:
    """Return the official display name and UNITID for a public slug.

    Raises ``UnknownArchiveSchoolError`` when the slug is missing, has
    no UNITID, or has no real name. Callers must not fall back to the
    slug as a display name.
    """
    sid = str(school_id or "").strip()
    if not sid:
        raise UnknownArchiveSchoolError("school_id must be non-empty")
    claim = _claims_by_school_id().get(sid)
    if claim is None:
        raise UnknownArchiveSchoolError(
            f"school_id {sid!r} is not in schools.yaml; "
            "refuse to archive under an unmapped slug"
        )
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
