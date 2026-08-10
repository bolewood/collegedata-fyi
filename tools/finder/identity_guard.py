#!/usr/bin/env python3
"""Fail closed when a schools.yaml IPEDS claim disagrees with NCES identity.

The finder corpus supplies stable public slugs, while IPEDS supplies the
institution identity behind each UNITID.  A structurally valid but incorrect
UNITID can otherwise poison the directory, coverage, federal facts, and every
derived recipe at once.  This module provides one pure audit used by CI and by
the Scorecard directory loader before it opens a database connection.

CI usage:
    python3 tools/finder/identity_guard.py

Refresh the checked-in NCES snapshot after reviewing a new HD release:
    python3 tools/finder/identity_guard.py \
      --build-snapshot tools/finder/.ipeds-cache/HD2024.zip \
      --data-year 2024
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
DEFAULT_SNAPSHOT = REPO_ROOT / "tools" / "finder" / "ipeds_identity_snapshot.csv"
DEFAULT_EXCEPTIONS = REPO_ROOT / "tools" / "finder" / "ipeds_identity_exceptions.json"
IPEDS_SOURCE_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"


def normalize_ipeds(value: Any) -> str | None:
    """Return the canonical six-digit UNITID representation."""
    if value is None:
        return None
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return f"{number:06d}"


def normalize_name(value: Any) -> str:
    """Normalize only orthographic differences, never semantic renames."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    # Preserve punctuation boundaries before ASCII folding; otherwise an en
    # dash in "A&M–University" disappears and accidentally joins two words.
    text = re.sub(r"[^\w&]+", " ", text, flags=re.UNICODE)
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    text = text.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def normalize_domain(value: Any) -> str:
    """Return a lowercase host without scheme, credentials, port, path, or www."""
    text = str(value or "").strip().casefold()
    if not text:
        return ""
    if "://" not in text:
        text = f"https://{text}"
    host = (urlsplit(text).hostname or "").rstrip(".")
    return host.removeprefix("www.")


def domains_related(left: Any, right: Any) -> bool:
    """Accept the same host or a direct subdomain relationship."""
    a = normalize_domain(left)
    b = normalize_domain(right)
    return bool(a and b and (a == b or a.endswith(f".{b}") or b.endswith(f".{a}")))


def school_claims_from_entries(
    entries: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse every curated identity claim or reject the whole corpus.

    Silently dropping a malformed row is unsafe: the Scorecard loader would
    then stop preserving that school's public slug while CI still appeared to
    pass. Curated UNITIDs therefore use a stricter parser than raw federal CSV
    values and every YAML row must survive parsing.
    """
    claims: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            errors.append(f"schools[{index}] must be a mapping")
            continue

        raw_ipeds = raw.get("ipeds_id")
        if isinstance(raw_ipeds, bool) or not re.fullmatch(
            r"[0-9]{6}", str(raw_ipeds or "").strip()
        ):
            ipeds_id = None
        else:
            ipeds_id = normalize_ipeds(raw_ipeds)
        school_id = str(raw.get("id") or "").strip()
        if not school_id:
            errors.append(f"schools[{index}].id must be non-empty")
        if not ipeds_id:
            errors.append(
                f"schools[{index}].ipeds_id must be a six-digit UNITID"
            )

        raw_redirects = raw.get("retired_aliases", [])
        retired_aliases: list[str] = []
        if not isinstance(raw_redirects, list):
            errors.append(f"schools[{index}].retired_aliases must be a list")
        else:
            for alias_index, alias_value in enumerate(raw_redirects):
                alias = str(alias_value or "").strip()
                if not alias:
                    errors.append(
                        f"schools[{index}].retired_aliases[{alias_index}] "
                        "must be non-empty"
                    )
                elif alias == school_id:
                    errors.append(
                        f"schools[{index}].retired_aliases[{alias_index}] "
                        "duplicates the canonical id"
                    )
                elif alias not in retired_aliases:
                    retired_aliases.append(alias)

        if not ipeds_id or not school_id:
            continue
        claims.append(
            {
                "school_id": school_id,
                "ipeds_id": ipeds_id,
                "claimed_name": str(raw.get("name") or "").strip(),
                "claimed_domain": normalize_domain(raw.get("domain")),
                "scrape_policy": str(raw.get("scrape_policy") or "unknown"),
                "retired_aliases": retired_aliases,
            }
        )
    if errors:
        raise ValueError("Invalid schools.yaml identity corpus: " + "; ".join(errors))
    return claims


def load_school_claims(path: Path = DEFAULT_SCHOOLS_YAML) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict) or not isinstance(data.get("schools"), list):
        raise ValueError("Invalid schools.yaml identity corpus: schools must be a list")
    return school_claims_from_entries(data["schools"])


def school_claim_slug_map(claims: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {claim["ipeds_id"]: claim["school_id"] for claim in claims}


def school_claim_retired_alias_map(
    claims: Iterable[dict[str, Any]],
) -> dict[str, list[str]]:
    """Return durable retired aliases keyed by their canonical UNITID."""
    return {
        claim["ipeds_id"]: list(claim.get("retired_aliases", []))
        for claim in claims
        if claim.get("retired_aliases")
    }


def unique_school_claim_slug_map(
    claims: Iterable[dict[str, Any]],
) -> dict[str, str]:
    """Return only unambiguous curated slugs; collision losers need the directory."""
    claim_rows = list(claims)
    slug_counts = Counter(claim["school_id"] for claim in claim_rows)
    return {
        claim["ipeds_id"]: claim["school_id"]
        for claim in claim_rows
        if slug_counts[claim["school_id"]] == 1
    }


def validated_unique_school_claim_slug_map(
    schools_path: Path = DEFAULT_SCHOOLS_YAML,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    exceptions_path: Path = DEFAULT_EXCEPTIONS,
) -> dict[str, str]:
    """Load canonical slugs only after the checked-in official audit passes."""
    claims = load_school_claims(schools_path)
    _, official_records = load_identity_snapshot(snapshot_path)
    audit = audit_school_identities(
        claims,
        official_records,
        load_identity_exceptions(exceptions_path),
    )
    if audit["errors"]:
        raise ValueError(
            "Refusing canonical school slug map: "
            f"{len(audit['errors'])} IPEDS identity claim(s) failed validation"
        )
    return unique_school_claim_slug_map(claims)


def load_identity_snapshot(
    path: Path = DEFAULT_SNAPSHOT,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Load snapshot metadata and UNITID-indexed official identity rows."""
    metadata: dict[str, str] = {}
    csv_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ") and "=" in line:
            key, value = line[2:].split("=", 1)
            metadata[key] = value
        elif not line.startswith("#"):
            csv_lines.append(line)

    records: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(csv_lines):
        ipeds_id = normalize_ipeds(row.get("ipeds_id"))
        if not ipeds_id:
            continue
        records[ipeds_id] = {
            "ipeds_id": ipeds_id,
            "official_name": str(row.get("official_name") or "").strip(),
            "official_domain": normalize_domain(row.get("official_domain")),
            "official_state": str(row.get("official_state") or "").strip(),
            "active": str(row.get("active") or "").strip(),
            "new_ipeds_id": normalize_ipeds(row.get("new_ipeds_id")) or "",
        }
    return metadata, records


def load_identity_exceptions(
    path: Path = DEFAULT_EXCEPTIONS,
) -> list[dict[str, str]]:
    data = json.loads(path.read_text()) if path.exists() else {"exceptions": []}
    return [dict(item) for item in data.get("exceptions", [])]


def official_records_from_directory_rows(
    rows: Iterable[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Adapt incoming Scorecard directory rows to the shared audit contract."""
    records: dict[str, dict[str, str]] = {}
    for row in rows:
        ipeds_id = normalize_ipeds(row.get("ipeds_id"))
        if not ipeds_id:
            continue
        records[ipeds_id] = {
            "ipeds_id": ipeds_id,
            "official_name": str(row.get("school_name") or "").strip(),
            "official_domain": normalize_domain(row.get("website_url")),
            "official_state": str(row.get("state") or "").strip(),
            "active": "1" if row.get("currently_operating") is not False else "0",
            "new_ipeds_id": "",
        }
    return records


def official_records_from_ipeds_rows(
    rows: Iterable[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Adapt raw NCES HD rows to the shared audit contract."""
    records: dict[str, dict[str, str]] = {}
    for row in rows:
        ipeds_id = normalize_ipeds(row.get("UNITID"))
        if not ipeds_id:
            continue
        records[ipeds_id] = {
            "ipeds_id": ipeds_id,
            "official_name": str(row.get("INSTNM") or "").strip(),
            "official_domain": normalize_domain(row.get("WEBADDR")),
            "official_state": str(row.get("STABBR") or "").strip(),
            "active": str(row.get("CYACTIVE") or "").strip(),
            "new_ipeds_id": normalize_ipeds(row.get("NEWID")) or "",
        }
    return records


def _exception_matches(
    exception: dict[str, str],
    claim: dict[str, str],
    official: dict[str, str],
) -> bool:
    required = (
        "school_id",
        "ipeds_id",
        "claimed_name",
        "claimed_domain",
        "official_name",
        "official_domain",
        "reason",
    )
    if any(not str(exception.get(key) or "").strip() for key in required):
        return False
    return all(
        (
            str(exception.get(key) or "").strip()
            == str(source.get(key) or "").strip()
        )
        for key, source in (
            ("school_id", claim),
            ("ipeds_id", claim),
            ("claimed_name", claim),
            ("claimed_domain", claim),
            ("official_name", official),
            ("official_domain", official),
        )
    )


def audit_school_identities(
    claims: Iterable[dict[str, str]],
    official_records: dict[str, dict[str, str]],
    exceptions: Iterable[dict[str, str]] = (),
) -> dict[str, Any]:
    """Return errors/warnings; any error must block CI and loader writes."""
    claim_rows = list(claims)
    exception_rows = list(exceptions)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    used_exceptions: set[int] = set()

    counts = Counter(claim["ipeds_id"] for claim in claim_rows)
    for ipeds_id, count in sorted(counts.items()):
        if count > 1:
            errors.append(
                {
                    "kind": "duplicate_ipeds_claim",
                    "ipeds_id": ipeds_id,
                    "school_ids": sorted(
                        claim["school_id"]
                        for claim in claim_rows
                        if claim["ipeds_id"] == ipeds_id
                    ),
                }
            )

    matched = 0
    excepted = 0
    for claim in claim_rows:
        official = official_records.get(claim["ipeds_id"])
        if official is None:
            issue = {
                "kind": "missing_official_record",
                "school_id": claim["school_id"],
                "ipeds_id": claim["ipeds_id"],
                "scrape_policy": claim["scrape_policy"],
            }
            if claim["scrape_policy"] == "active":
                errors.append(issue)
            else:
                warnings.append(issue)
            continue

        name_matches = (
            bool(normalize_name(claim["claimed_name"]))
            and normalize_name(claim["claimed_name"])
            == normalize_name(official["official_name"])
        )
        domain_matches = domains_related(
            claim["claimed_domain"], official["official_domain"]
        )
        if name_matches or domain_matches:
            matched += 1
            continue

        exception_index = next(
            (
                index
                for index, exception in enumerate(exception_rows)
                if _exception_matches(exception, claim, official)
            ),
            None,
        )
        if exception_index is not None:
            used_exceptions.add(exception_index)
            excepted += 1
            continue

        errors.append(
            {
                "kind": "identity_mismatch",
                "school_id": claim["school_id"],
                "ipeds_id": claim["ipeds_id"],
                "claimed_name": claim["claimed_name"],
                "claimed_domain": claim["claimed_domain"],
                "official_name": official["official_name"],
                "official_domain": official["official_domain"],
                "official_state": official.get("official_state", ""),
            }
        )

    for index, exception in enumerate(exception_rows):
        if index not in used_exceptions:
            errors.append(
                {
                    "kind": "unused_or_stale_exception",
                    "school_id": exception.get("school_id"),
                    "ipeds_id": exception.get("ipeds_id"),
                }
            )

    return {
        "claims": len(claim_rows),
        "official_records": len(official_records),
        "matched": matched,
        "excepted": excepted,
        "warnings": warnings,
        "errors": errors,
    }


def _decode_ipeds_csv(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def build_identity_snapshot(source_zip: Path, output: Path, data_year: int) -> int:
    """Write a deterministic, compact identity snapshot from an official HD ZIP."""
    archive = source_zip.read_bytes()
    digest = hashlib.sha256(archive).hexdigest()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        csv_name = next(
            (name for name in zf.namelist() if name.casefold().endswith(".csv")),
            None,
        )
        if csv_name is None:
            raise ValueError(f"No CSV found in {source_zip}")
        rows = list(csv.DictReader(io.StringIO(_decode_ipeds_csv(zf.read(csv_name)))))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# data_year={data_year}\n")
        handle.write(f"# source_url={IPEDS_SOURCE_URL.format(year=data_year)}\n")
        handle.write(f"# source_file={csv_name}\n")
        handle.write(f"# source_sha256={digest}\n")
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            (
                "ipeds_id",
                "official_name",
                "official_domain",
                "official_state",
                "active",
                "new_ipeds_id",
            )
        )
        normalized_rows = []
        for row in rows:
            ipeds_id = normalize_ipeds(row.get("UNITID"))
            if not ipeds_id:
                continue
            normalized_rows.append(
                (
                    ipeds_id,
                    str(row.get("INSTNM") or "").strip(),
                    normalize_domain(row.get("WEBADDR")),
                    str(row.get("STABBR") or "").strip(),
                    str(row.get("CYACTIVE") or "").strip(),
                    normalize_ipeds(row.get("NEWID")) or "",
                )
            )
        writer.writerows(sorted(normalized_rows))
    return len(normalized_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schools-yaml", type=Path, default=DEFAULT_SCHOOLS_YAML)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTIONS)
    parser.add_argument(
        "--build-snapshot",
        type=Path,
        help="Official HD<year>.zip to convert into --snapshot, then exit",
    )
    parser.add_argument("--data-year", type=int, default=2024)
    parser.add_argument("--json", action="store_true", help="Emit the full audit as JSON")
    args = parser.parse_args()

    if args.build_snapshot:
        count = build_identity_snapshot(
            args.build_snapshot.expanduser(), args.snapshot, args.data_year
        )
        print(f"Wrote {count:,} official identities to {args.snapshot}")
        return 0

    metadata, official_records = load_identity_snapshot(args.snapshot)
    claims = load_school_claims(args.schools_yaml)
    exceptions = load_identity_exceptions(args.exceptions)
    audit = audit_school_identities(claims, official_records, exceptions)
    audit["snapshot"] = metadata

    if args.json:
        print(json.dumps(audit, indent=2, sort_keys=True))
    else:
        print(
            "School identity audit: "
            f"{audit['matched']:,} matched, {audit['excepted']:,} excepted, "
            f"{len(audit['warnings']):,} warnings, {len(audit['errors']):,} errors"
        )
        for issue in audit["warnings"]:
            print(f"WARNING {json.dumps(issue, sort_keys=True)}", file=sys.stderr)
        for issue in audit["errors"]:
            print(f"ERROR {json.dumps(issue, sort_keys=True)}", file=sys.stderr)
    return 2 if audit["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
