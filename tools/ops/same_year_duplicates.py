#!/usr/bin/env python3
"""Two live documents of one school in one filed year (issue #467).

Docs/postmortems/2026-11-24-stale-discovery-seeds.md, action 8. 22 real
2025-26 documents were filed as 2024-25 because the 2025-26 form prints last
year's title. For 21 of them it was the school's second live 2024-25
document, and no check looked for two.

This module reads the live published documents and reports every
(school, sub-institution, filed year) with two or more. Each group is
classified, best effort, with the evidence that decided it:

  misfiled_year  a document's source URL names a different CDS year than the
                 year it is filed under, and nothing corrected the filing
  year_conflict  the content-detected year and the resolver's cds_year differ;
                 the site follows the content, so one document may belong to
                 the other year (see year_evidence)
  section_split  at least one document is a single-section file
  same_file      two documents have the same source_sha256
  duplicate      none of the above

When more than one class applies the first in the list above wins.

Groups whose filed year is not a valid `YYYY-YY` (`unknown`) are reported
separately as undated duplicates and never mixed into the main count: an
undated document is not evidence of a second document for a real year.

The classifier is a pure function over document rows (`find_groups`), so the
renewal report and the extraction scoreboard call the same code. The CLI
fails loudly: a short page, an empty result or a missing column is an error
and exits 1. Finding duplicates is not an error and exits 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.finder.academic_year import normalize_academic_year  # noqa: E402
from tools.common.site import API_ORIGIN  # noqa: E402
from tools.finder.stuck_pdf_seeds import is_section_seed  # noqa: E402

from tools.ops.discovery_renewal import (  # noqa: E402
    PAGE_SIZE,
    RenewalError as DuplicatesError,
    _headers,
    http_json,
    parse_content_range_total,
    parse_year,
)

DEFAULT_API = API_ORIGIN
DOCUMENT_COLUMNS = (
    "id,school_id,sub_institutional,cds_year,detected_year,source_url,source_sha256,"
    "source_format,discovered_at"
)
DOCUMENTS_QUERY = (
    f"select={DOCUMENT_COLUMNS}&removed_at=is.null&participation_status=eq.published&order=id.asc"
)
REQUIRED_KEYS = ("id", "school_id", "cds_year", "detected_year", "source_url", "source_sha256")

# Fewer live documents than this means the read is not what we think it is
# (an empty page, a filter that dropped rows). 5,835 on 2026-11-25.
MIN_DOCUMENTS = 1000

CLASSES = ("misfiled_year", "year_conflict", "section_split", "same_file", "duplicate")


# ---------------------------------------------------------------- classifying


def canonical_year(doc: dict[str, Any]) -> str | None:
    """The filed year the site uses: detected_year, else cds_year (the SQL
    `coalesce(detected_year, cds_year)` of `cds_manifest.canonical_year`)."""
    return doc.get("detected_year") or doc.get("cds_year")


def url_year(url: str | None) -> str | None:
    """The CDS year a source URL names. The filename wins over the folders:
    `/2025-26/CDS_2024-25.pdf` is a 2024-25 file in a 2025-26 folder."""
    if not url:
        return None
    path = unquote(urlparse(url).path)
    filename = path.rsplit("/", 1)[-1]
    return normalize_academic_year(filename) or normalize_academic_year(path)


def year_evidence(doc: dict[str, Any], filed: str) -> tuple[str, str] | None:
    """(class, evidence) when this document's filed year looks wrong, else None.

    `year_conflict`: the content-detected year and the resolver's `cds_year`
    are both valid and differ. The site follows the content (ADR 0007), so
    the document is filed under `detected_year`; the group exists because
    another document has that year too. A detected 2024-25 under a
    `cds_year` of 2025-26 is the stale-title pattern of #455 (the 2025-26
    form prints 2024-25), so that document is probably 2025-26.

    `misfiled_year`: nothing corrected the filing and the source URL still
    names a different year than the one the document is filed under.

    A `cds_year` of `unknown` means the detector filled in a missing year.
    That is a dated document, not a misfiled one.
    """
    ident = doc["id"][:8]
    detected, cds = doc.get("detected_year"), doc.get("cds_year")
    d, c = parse_year(detected), parse_year(cds)
    if d is not None and c is not None and d != c:
        note = "; likely the stale-title pattern of #455" if (d, c) == (2024, 2025) else ""
        return (
            "year_conflict",
            f"{ident} content says {detected} but its URL/resolver says {cds}{note}",
        )
    named = url_year(doc.get("source_url"))
    if named and named != filed:
        return "misfiled_year", f"{ident} is filed {filed} but its URL names {named}"
    return None


@dataclass
class Group:
    school_id: str
    sub_institutional: str | None
    year: str
    cls: str
    evidence: str
    documents: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "school_id": self.school_id,
            "sub_institutional": self.sub_institutional,
            "year": self.year,
            "class": self.cls,
            "evidence": self.evidence,
            "document_ids": [d["id"] for d in self.documents],
            "source_urls": [d.get("source_url") for d in self.documents],
        }


def classify(docs: list[dict[str, Any]], filed: str) -> tuple[str, str]:
    """(class, evidence) for one group of two or more documents."""
    found = [e for e in (year_evidence(d, filed) for d in docs) if e]
    for cls in ("misfiled_year", "year_conflict"):
        texts = [text for kind, text in found if kind == cls]
        if texts:
            return cls, "; ".join(texts)
    sections = [d for d in docs if is_section_seed(d.get("source_url"))]
    if sections:
        names = ", ".join(
            unquote(urlparse(d["source_url"]).path.rsplit("/", 1)[-1]) for d in sections
        )
        return "section_split", f"section file: {names}"
    by_sha: dict[str, list[str]] = defaultdict(list)
    for d in docs:
        if d.get("source_sha256"):
            by_sha[d["source_sha256"]].append(d["id"][:8])
    same = [(sha, ids) for sha, ids in by_sha.items() if len(ids) > 1]
    if same:
        sha, ids = same[0]
        return "same_file", f"{' and '.join(ids)} share sha256 {sha[:12]}"
    shas = [d.get("source_sha256") for d in docs]
    if all(shas) and len(set(shas)) == len(shas):
        return "duplicate", f"{len(docs)} distinct files, none misfiled or a section"
    # Without every hash the files may still be the same one.
    return "duplicate", f"{len(docs)} files (hashes not compared), none misfiled or a section"


@dataclass
class Report:
    documents_read: int
    groups: list[Group]
    undated: list[Group]

    @property
    def count(self) -> int:
        return len(self.groups)

    @property
    def by_class(self) -> dict[str, int]:
        counts = Counter(g.cls for g in self.groups)
        return {c: counts.get(c, 0) for c in CLASSES}

    def summary(self) -> dict[str, Any]:
        """Flat keys for the heartbeat summary (`same_year_duplicates` is in
        the station contract)."""
        return {
            "same_year_duplicates": self.count,
            "same_year_duplicates_by_class": self.by_class,
            "undated_duplicates": len(self.undated),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.summary(),
            "documents_read": self.documents_read,
            "groups": [g.as_dict() for g in self.groups],
            "undated": [g.as_dict() for g in self.undated],
        }


def find_groups(docs: Iterable[dict[str, Any]]) -> Report:
    """Every (school, sub-institution, filed year) with two or more live
    documents. `docs` must already be live and published; rows with a
    `removed_at` or a non-published `participation_status` are dropped here
    too, when those keys are present, so a caller cannot over-count by
    passing a wider read.

    A sub-institutional document (`general-studies`) is its own program, not
    a second copy of the school's, so it is part of the group key.
    """
    live = 0
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for doc in docs:
        if doc.get("removed_at"):
            continue
        if "participation_status" in doc and doc["participation_status"] != "published":
            continue
        school_id = doc.get("school_id")
        if not school_id:
            raise DuplicatesError(f"document {doc.get('id')} has no school_id")
        live += 1
        year = canonical_year(doc) or "unknown"
        buckets[(school_id, doc.get("sub_institutional") or "", year)].append(doc)

    groups: list[Group] = []
    undated: list[Group] = []
    for (school_id, sub, year), members in buckets.items():
        if len(members) < 2:
            continue
        if parse_year(year) is None:
            undated.append(
                Group(school_id, sub or None, year, "undated",
                      f"{len(members)} documents with no valid year ({year})", members)
            )
            continue
        cls, evidence = classify(members, year)
        groups.append(Group(school_id, sub or None, year, cls, evidence, members))

    def order(g: Group) -> tuple:
        return (CLASSES.index(g.cls) if g.cls in CLASSES else len(CLASSES), g.year, g.school_id)

    groups.sort(key=order)
    undated.sort(key=lambda g: g.school_id)
    return Report(documents_read=live, groups=groups, undated=undated)


# ---------------------------------------------------------------- rendering


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Report, *, heading: str = "Two documents in one year") -> str:
    lines = [
        f"## {heading}",
        "",
        f"{report.count} school-years have two or more live documents "
        f"({report.documents_read:,} live documents read). "
        + ", ".join(f"{n} {c}" for c, n in report.by_class.items())
        + ".",
        "",
    ]
    if report.groups:
        lines += ["| School | Year | Class | Documents | Evidence |", "|---|---|---|---|---|"]
        for g in report.groups:
            school = g.school_id + (f" ({g.sub_institutional})" if g.sub_institutional else "")
            ids = ", ".join(d["id"][:8] for d in g.documents)
            lines.append(f"| {_cell(school)} | {g.year} | {g.cls} | {ids} | {_cell(g.evidence)} |")
    else:
        lines.append("None.")
    lines += ["", f"### Undated duplicates ({len(report.undated)})", ""]
    if report.undated:
        lines += ["| School | Documents |", "|---|---|"]
        for g in report.undated:
            lines.append(f"| {_cell(g.school_id)} | {', '.join(d['id'][:8] for d in g.documents)} |")
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- reading


def check_rows(rows: list[dict[str, Any]], *, enforce_min: bool = True) -> None:
    if enforce_min and len(rows) < MIN_DOCUMENTS:
        raise DuplicatesError(
            f"only {len(rows)} live documents (minimum {MIN_DOCUMENTS}); the data does not look complete"
        )
    for row in rows[:50]:
        missing = [k for k in REQUIRED_KEYS if k not in row]
        if missing:
            raise DuplicatesError(f"documents are missing columns {missing}; the query changed")


def fetch_live_documents(
    api_url: str,
    anon_key: str,
    *,
    get: Callable[..., tuple[Any, dict[str, str]]] = http_json,
) -> list[dict[str, Any]]:
    """All live published `cds_documents` rows, paged. Raises unless every row arrived."""
    rows: list[dict[str, Any]] = []
    total: int | None = None
    while total is None or len(rows) < total:
        url = (
            f"{api_url.rstrip('/')}/rest/v1/cds_documents?{DOCUMENTS_QUERY}"
            f"&limit={PAGE_SIZE}&offset={len(rows)}"
        )
        page, headers = get(url, _headers(anon_key, Prefer="count=exact"))
        page_total = parse_content_range_total(headers.get("content-range"))
        if total is None:
            total = page_total
            if total == 0:
                raise DuplicatesError("cds_documents returned zero live rows")
        elif page_total != total:
            raise DuplicatesError(f"row count changed while paging ({total} -> {page_total})")
        if not isinstance(page, list):
            raise DuplicatesError("cds_documents page was not a list")
        if not page:
            break
        rows.extend(page)
    if total is None or len(rows) != total:
        raise DuplicatesError(f"short read: fetched {len(rows)} rows, Content-Range total {total}")
    return rows


def run(api_url: str, anon_key: str, *, get: Callable[..., Any] = http_json) -> Report:
    rows = fetch_live_documents(api_url, anon_key, get=get)
    check_rows(rows)
    return find_groups(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api-url", default=os.environ.get("CDS_API_URL", DEFAULT_API))
    parser.add_argument("--anon-key", default=os.environ.get("SUPABASE_ANON_KEY", ""))
    parser.add_argument("--from-json", type=Path, help="Classify a saved list of document rows instead of reading the API.")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.from_json:
            rows = json.loads(args.from_json.read_text(encoding="utf-8"))
            check_rows(rows)
            report = find_groups(rows)
        else:
            if not args.anon_key:
                raise DuplicatesError("no anon key: set SUPABASE_ANON_KEY or pass --anon-key")
            report = run(args.api_url, args.anon_key)
    except DuplicatesError as exc:
        print(f"same_year_duplicates: ERROR: {exc}", file=sys.stderr)
        return 1
    markdown = render_markdown(report)
    print(markdown)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
