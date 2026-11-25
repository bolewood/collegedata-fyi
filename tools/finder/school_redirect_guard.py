#!/usr/bin/env python3
"""Keep reviewed retired school aliases synchronized with Next.js redirects."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.finder.identity_guard import REPO_ROOT, load_school_claims
except ModuleNotFoundError:  # Direct `python tools/finder/...` execution.
    from identity_guard import REPO_ROOT, load_school_claims


DEFAULT_REDIRECTS = REPO_ROOT / "web" / "src" / "data" / "school-redirects.json"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def expected_redirects(claims: Iterable[dict[str, Any]]) -> dict[str, str]:
    claim_rows = list(claims)
    canonical_counts = Counter(claim["school_id"] for claim in claim_rows)
    canonical_ids = set(canonical_counts)
    redirects: dict[str, str] = {}
    for claim in claim_rows:
        school_id = claim["school_id"]
        if claim.get("retired_aliases") and canonical_counts[school_id] != 1:
            raise ValueError(
                f"redirect destination {school_id!r} is not a unique canonical claim"
            )
        for alias in claim.get("retired_aliases", []):
            if alias in canonical_ids:
                raise ValueError(
                    f"retired alias {alias!r} collides with a canonical school id"
                )
            existing = redirects.get(alias)
            if existing and existing != school_id:
                raise ValueError(
                    f"retired alias {alias!r} maps to both {existing!r} and {school_id!r}"
                )
            redirects[alias] = school_id
    return redirects


def load_redirects(path: Path = DEFAULT_REDIRECTS) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("school redirect manifest must be a list")
    redirects: dict[str, str] = {}
    for index, row in enumerate(raw):
        if not isinstance(row, dict) or set(row) != {"alias", "school_id"}:
            raise ValueError(f"school redirect row {index} must contain alias and school_id")
        alias = row["alias"]
        school_id = row["school_id"]
        if not isinstance(alias, str) or not isinstance(school_id, str):
            raise ValueError(f"school redirect row {index} values must be strings")
        if not SLUG.fullmatch(alias) or not SLUG.fullmatch(school_id):
            raise ValueError(f"school redirect row {index} contains an invalid slug")
        if alias in redirects:
            raise ValueError(f"school redirect alias {alias!r} is duplicated")
        redirects[alias] = school_id
    return redirects


def audit_redirect_manifest(
    claims: Iterable[dict[str, Any]], manifest: dict[str, str]
) -> list[str]:
    expected = expected_redirects(claims)
    errors = [
        f"missing redirect {alias!r} -> {school_id!r}"
        for alias, school_id in sorted(expected.items())
        if manifest.get(alias) != school_id
    ]
    errors.extend(
        f"unexpected redirect {alias!r} -> {school_id!r}"
        for alias, school_id in sorted(manifest.items())
        if expected.get(alias) != school_id
    )
    return errors


EDGE_ALIASES = REPO_ROOT / "supabase" / "functions" / "_shared" / "retired_aliases.ts"
_EDGE_ENTRY = re.compile(r'^\s*"([a-z0-9-]+)":\s*"([a-z0-9-]+)",?\s*$')


def load_edge_aliases(path: Path = EDGE_ALIASES) -> dict[str, str]:
    """Alias map copied into the Edge functions (they cannot import web/)."""
    return {
        match.group(1): match.group(2)
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := _EDGE_ENTRY.match(line))
    }


def audit_edge_aliases(manifest: dict[str, str], edge: dict[str, str]) -> list[str]:
    errors = [
        f"edge retired_aliases.ts is missing {alias!r} -> {school_id!r}"
        for alias, school_id in sorted(manifest.items())
        if edge.get(alias) != school_id
    ]
    errors.extend(
        f"edge retired_aliases.ts has unexpected {alias!r} -> {school_id!r}"
        for alias, school_id in sorted(edge.items())
        if manifest.get(alias) != school_id
    )
    return errors


def main() -> int:
    manifest = load_redirects()
    errors = audit_redirect_manifest(load_school_claims(), manifest)
    errors.extend(audit_edge_aliases(manifest, load_edge_aliases()))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Retired school redirect manifest verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
