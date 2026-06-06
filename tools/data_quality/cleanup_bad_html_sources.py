#!/usr/bin/env python3
"""Audit and quarantine archived HTML sources that are not CDS documents.

HTML is a valid source format for schools that publish CDS pages as static
tables. The bad cases are login walls, WAF challenges, and generic error pages
that were archived before the TypeScript guard rejected them. By default this
script only prints candidates. With --write, it marks the document removed and
flags it as wrong_file. With --delete-storage, it also removes the public
Storage object so the archived login/challenge page is no longer downloadable.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import requests
from supabase import create_client


SOURCES_BUCKET = "sources"
MAX_PREVIEW_BYTES = 64 * 1024


@dataclass
class Candidate:
    row: dict[str, Any]
    outcome: str
    markers: list[str]
    http_status: int | None


def env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


def supabase_client():
    url = env("SUPABASE_URL") or env("NEXT_PUBLIC_SUPABASE_URL")
    key = env("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key), url


def fetch_manifest(sb) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        batch = (
            sb.table("cds_manifest")
            .select(
                "document_id,school_id,school_name,canonical_year,cds_year,"
                "source_url,source_format,extraction_status,data_quality_flag,"
                "removed_at,source_storage_path"
            )
            .range(start, start + 999)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        start += 1000


def is_html_source(row: dict[str, Any]) -> bool:
    path = (row.get("source_storage_path") or "").lower().split("?", 1)[0]
    return row.get("source_format") == "html" or path.endswith((".html", ".htm"))


def storage_url(base_url: str, path: str) -> str:
    return f"{base_url}/storage/v1/object/public/{SOURCES_BUCKET}/{quote(path, safe='/')}"


def fetch_preview(base_url: str, row: dict[str, Any]) -> tuple[str, int | None]:
    path = row.get("source_storage_path")
    if not path:
        return row.get("source_url") or "", None
    response = requests.get(storage_url(base_url, path), timeout=15)
    text = response.content[:MAX_PREVIEW_BYTES].decode("utf-8", errors="ignore")
    return text, response.status_code


def has_any(value: str, needles: list[str]) -> list[str]:
    return [needle for needle in needles if needle in value]


def classify(row: dict[str, Any], text: str) -> tuple[str | None, list[str]]:
    host = urlparse(row.get("source_url") or "").netloc.lower()
    haystack = f"{host}\n{text.lower()}"

    marker_groups: list[tuple[str, str, list[str]]] = [
        (
            "auth_walled_microsoft",
            "auth_walled_microsoft",
            [
                "login.microsoftonline.com",
                "sign in to your account",
                "aadcdn",
                "samlrequest",
                "microsoft corporation. all rights reserved",
            ],
        ),
        (
            "auth_walled_google",
            "auth_walled_google",
            [
                "accounts.google.com",
                "service_login",
                "google accounts",
                "google sign in",
                "identifierid",
            ],
        ),
        (
            "auth_walled_okta",
            "auth_walled_okta",
            ["okta sign in", "okta-signin", ".okta.com"],
        ),
        (
            "bot_challenge",
            "bot_challenge",
            [
                "cloudflare",
                "just a moment",
                "cf-mitigated",
                "cf-chl-",
                "__cf_chl_",
                "captcha",
                "incapsula incident",
                "imperva",
                "perfdrive",
                "validate.perfdrive.com",
                "access denied",
                "request unsuccessful",
            ],
        ),
    ]

    for outcome, marker_label, needles in marker_groups:
        hits = has_any(haystack, needles)
        if hits:
            return outcome, [marker_label, *hits[:3]]

    cds_like = bool(
        re.search(
            r"common data set|common dataset|\bcds\b|first-time, first-year|degree-seeking undergraduate",
            haystack,
            re.I,
        )
    )
    has_table_markup = "<table" in haystack and ("<td" in haystack or "<th" in haystack)
    error_hits = has_any(
        haystack,
        [
            "404 not found",
            "404 error",
            "page not found",
            "file not found",
            "the page you requested could not be found",
            "server error",
            "temporarily unavailable",
            "please sign in",
            "single sign-on",
            "single sign on",
        ],
    )
    if error_hits:
        return "wrong_content_type", ["error_page", *error_hits[:3]]

    if cds_like and not has_table_markup:
        return "wrong_content_type", ["cds_landing_without_tables"]

    return None, []


def suspicious_html_rows(sb, base_url: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for row in fetch_manifest(sb):
        if row.get("removed_at") or not is_html_source(row):
            continue
        text, status = fetch_preview(base_url, row)
        outcome, markers = classify(row, text)
        if not outcome and row.get("extraction_status") == "failed":
            outcome = "failed_html_source"
            markers = ["extraction_failed"]
        if outcome:
            candidates.append(Candidate(row=row, outcome=outcome, markers=markers, http_status=status))
    return candidates


def mark_removed(sb, candidate: Candidate) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (
        sb.table("cds_documents")
        .update({"removed_at": now, "data_quality_flag": "wrong_file"})
        .eq("id", candidate.row["document_id"])
        .execute()
    )


def delete_storage(sb, path: str) -> None:
    sb.storage.from_(SOURCES_BUCKET).remove([path])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="mark suspicious rows removed/wrong_file")
    parser.add_argument(
        "--delete-storage",
        action="store_true",
        help="also delete the public Storage object; requires --write",
    )
    args = parser.parse_args()

    if args.delete_storage and not args.write:
        parser.error("--delete-storage requires --write")

    sb, base_url = supabase_client()
    candidates = suspicious_html_rows(sb, base_url)

    print(f"suspicious active HTML sources: {len(candidates)}")
    for candidate in candidates:
        row = candidate.row
        print(
            "|".join(
                [
                    row.get("school_id") or "",
                    row.get("canonical_year") or row.get("cds_year") or "",
                    row.get("source_format") or "",
                    row.get("extraction_status") or "",
                    candidate.outcome,
                    ",".join(candidate.markers),
                    str(candidate.http_status),
                    row.get("source_storage_path") or "",
                ]
            )
        )

    if not args.write:
        print("dry run only; pass --write to mark rows removed")
        return 0

    for candidate in candidates:
        mark_removed(sb, candidate)
        path = candidate.row.get("source_storage_path")
        if args.delete_storage and path:
            delete_storage(sb, path)

    print(
        f"updated {len(candidates)} row(s)"
        + (" and deleted storage objects" if args.delete_storage else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
