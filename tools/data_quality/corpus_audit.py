#!/usr/bin/env python3
"""Read-only corpus audit: find wrong data ourselves, before a consumer does.

Every check here encodes a failure that reached production and was reported by
a downstream project (issues #277-#283). The audit never writes to the
database. It reads the public tables through PostgREST, lists findings with a
stable key, and separates the ones nobody has looked at yet ("new") from the
ones an operator has read and explained in ``corpus_audit_accepted.yaml``.

Checks
  shared_source_file           one archived file (same sha256) is published
                               under more than one school
  shared_admissions_numbers    different schools show identical applied /
                               admitted / enrolled counts for the same year
  federal_applicants_mismatch  CDS applicants differ from the IPEDS count for
                               the same fall by more than the tolerance
  name_in_file_mismatch        the institution named inside the file (A1) is
                               not the school the file is published under

Metrics (already withheld from the public tables; tracked for trend)
  sanity_rules                 values each projection sanity rule flags
  parse_errors                 parse_error rows by CDS section and producer

Usage:
    python tools/data_quality/corpus_audit.py \
      --out-json scratch/corpus-audit/report.json \
      --out-md scratch/corpus-audit/report.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for _path in (HERE, REPO_ROOT / "tools" / "browser_backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import sanity_rules  # noqa: E402
from run_data_integrity_audit import ReadOnlyPostgrest, load_env  # noqa: E402

DEFAULT_ACCEPTED = HERE / "corpus_audit_accepted.yaml"

# CDS and IPEDS count the same fall cohort but not always the same campuses or
# the same application types. In the 2024-25 corpus 396 of 417 matched schools
# agree within this band; the 21 outside it are wrong files, column slips or
# doubled totals.
FEDERAL_RATIO_TOLERANCE = Decimal("1.5")

# A triple this small can coincide between two real schools.
MIN_SHARED_APPLIED = 50

# Lines per check in the Markdown report. The JSON report is never truncated.
MARKDOWN_LIST_CAP = 60
# Schools named on one line, and the whole report, so the body always fits a
# GitHub issue (65,536 characters).
MARKDOWN_SCHOOLS_CAP = 8
MARKDOWN_MAX_CHARS = 60_000

# IPEDS release types, best first.
_RELEASE_RANK = {"final": 0, "revised": 0, "provisional": 1}

# Words that say "this text is an institution's name" rather than an address
# or a run of form labels read into the A1 name cell.
_INSTITUTION_WORDS = ("college", "university", "institute", "school", "academy", "conservatory")
# Words too common to tell one institution from another.
_NAME_STOPWORDS = frozenset(
    "the of at and in for a an main campus university college institute school "
    "state saint st".split()
)


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    # Decimal("NaN") and Decimal("Infinity") parse; a text cell can hold either.
    return number if number.is_finite() else None


def _finding(check: str, key_parts: Sequence[str], **detail: Any) -> dict[str, Any]:
    return {"check": check, "key": ":".join([check, *key_parts]), **detail}


def shared_source_files(documents: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One finding per set of schools that publish the same file."""
    schools_by_sha: dict[str, set[str]] = defaultdict(set)
    years_by_sha: dict[str, set[str]] = defaultdict(set)
    for doc in documents:
        sha = doc.get("source_sha256")
        if not sha or doc.get("removed_at"):
            continue
        schools_by_sha[sha].add(str(doc["school_id"]))
        years_by_sha[sha].add(str(doc.get("cds_year") or "unknown"))

    years_by_group: dict[tuple[str, ...], set[str]] = defaultdict(set)
    files_by_group: Counter[tuple[str, ...]] = Counter()
    for sha, schools in schools_by_sha.items():
        if len(schools) < 2:
            continue
        group = tuple(sorted(schools))
        years_by_group[group] |= years_by_sha[sha]
        files_by_group[group] += 1
    return [
        _finding(
            "shared_source_file",
            [",".join(group)],
            schools=list(group),
            years=sorted(years_by_group[group]),
            files=files_by_group[group],
        )
        for group in sorted(years_by_group)
    ]


def shared_admissions_numbers(
    browser_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """One finding per (year, school set) with identical C1 counts."""
    groups: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for row in browser_rows:
        applied, admitted = _decimal(row.get("applied")), _decimal(row.get("admitted"))
        if applied is None or admitted is None or applied < MIN_SHARED_APPLIED:
            continue
        enrolled = _decimal(row.get("enrolled_first_year"))
        signature = (
            str(row.get("canonical_year")),
            str(applied),
            str(admitted),
            str(enrolled),
        )
        groups[signature].add(str(row["school_id"]))
    findings = []
    for (year, applied, admitted, enrolled), schools in sorted(groups.items()):
        if len(schools) < 2:
            continue
        group = sorted(schools)
        findings.append(
            _finding(
                "shared_admissions_numbers",
                [year, ",".join(group)],
                schools=group,
                year=year,
                applied=applied,
                admitted=admitted,
                enrolled_first_year=None if enrolled == "None" else enrolled,
            )
        )
    return findings


def federal_applicants_mismatch(
    browser_rows: Iterable[Mapping[str, Any]],
    federal_rows: Iterable[Mapping[str, Any]],
    tolerance: Decimal = FEDERAL_RATIO_TOLERANCE,
) -> tuple[list[dict[str, Any]], int]:
    """CDS applicants against IPEDS applicants for the same fall.

    Returns the findings and the number of rows that had a federal figure to
    compare with (the denominator, so a report can say "21 of 417").
    """
    federal: dict[tuple[str, int], tuple[int, Decimal]] = {}
    for row in federal_rows:
        value = _decimal(row.get("value_numeric"))
        if value is None or value <= 0 or row.get("data_year") is None:
            continue
        rank = _RELEASE_RANK.get(str(row.get("release_type") or ""), 2)
        slot = (str(row["ipeds_id"]), int(row["data_year"]))
        if slot not in federal or rank < federal[slot][0]:
            federal[slot] = (rank, value)

    findings, compared = [], 0
    for row in browser_rows:
        applied = _decimal(row.get("applied"))
        if applied is None or applied <= 0:
            continue
        if not row.get("ipeds_id") or row.get("year_start") is None:
            continue
        # A campus-level document shares its parent's ipeds_id; the federal
        # figure is for the whole institution, so the comparison means nothing.
        if row.get("sub_institutional"):
            continue
        ranked = federal.get((str(row["ipeds_id"]), int(row["year_start"])))
        if ranked is None:
            continue
        reference = ranked[1]
        compared += 1
        ratio = applied / reference
        if ratio > tolerance or ratio < 1 / tolerance:
            findings.append(
                _finding(
                    "federal_applicants_mismatch",
                    [str(row["school_id"]), str(row.get("canonical_year"))],
                    schools=[str(row["school_id"])],
                    year=str(row.get("canonical_year")),
                    cds_applied=str(applied),
                    ipeds_applicants=str(reference),
                    ratio=str(ratio.quantize(Decimal("0.01"))),
                )
            )
    findings.sort(key=lambda f: f["key"])
    return findings, compared


def _name_tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return {t for t in re.split(r"[^a-z0-9]+", folded.replace("&", " and ")) if t}


def name_in_file_mismatch(name_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """A1 "Name of College/University" against the school the file is under.

    The file's name is compared with spaces removed, because PDF text often
    arrives kerned apart ("Pom ona College"). A cell that does not read as an
    institution's name (an address, a run of labels) is skipped, not flagged.
    """
    findings = []
    for row in name_rows:
        written = str(row.get("value_text") or "").strip()
        if not written or len(written) > 120:
            continue
        squashed = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", written).encode("ascii", "ignore").decode().lower())
        if not any(word in squashed for word in _INSTITUTION_WORDS):
            continue
        # A truncated read ("The University of") names nobody.
        if not _name_tokens(written) - _NAME_STOPWORDS:
            continue
        expected = (
            _name_tokens(str(row.get("school_name") or ""))
            | _name_tokens(str(row["school_id"]).replace("-", " "))
        ) - _NAME_STOPWORDS
        if not expected or any(token in squashed for token in expected):
            continue
        findings.append(
            _finding(
                "name_in_file_mismatch",
                [str(row["school_id"]), str(row.get("canonical_year"))],
                schools=[str(row["school_id"])],
                year=str(row.get("canonical_year")),
                name_in_file=written,
            )
        )
    findings.sort(key=lambda f: f["key"])
    return findings


def sanity_rule_hits(field_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Replay the projection sanity rules over the published field rows.

    A flagged value is published as ``parse_error`` with no number, so its
    number is recovered from ``value_text``. Rows that are ``parse_error`` for
    another reason can only add to the count when their text is a plain number
    that also breaks a rule, so treat the counts as an upper bound.
    """
    per_document: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(dict)
    labels: dict[tuple[str, str], tuple[str, str]] = {}
    for row in field_rows:
        status = row.get("value_status")
        if status == "reported":
            value = _decimal(row.get("value_num"))
        elif status == "parse_error":
            value = _decimal(row.get("value_text"))
        else:
            value = None
        if value is None:
            continue
        doc_key = (str(row["document_id"]), str(row.get("schema_version")))
        per_document[doc_key][str(row["field_id"])] = value
        labels[doc_key] = (str(row.get("school_id")), str(row.get("canonical_year")))

    counts: Counter[str] = Counter()
    documents: dict[str, list[str]] = defaultdict(list)
    for doc_key, values in per_document.items():
        flagged = sanity_rules.implausible_fields(doc_key[1], values)
        for rule in sorted(set(flagged.values())):
            counts[rule] += sum(1 for name in flagged.values() if name == rule)
            documents[rule].append("/".join(labels[doc_key]))
    return {
        "values_flagged": {name: counts.get(name, 0) for name, _ in sanity_rules.RULES},
        "documents": {name: sorted(docs) for name, docs in documents.items()},
    }


def parse_error_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    by_section: Counter[str] = Counter()
    by_producer: Counter[str] = Counter()
    total = 0
    for row in rows:
        total += 1
        by_section[str(row.get("field_id") or "?").split(".", 1)[0]] += 1
        by_producer[str(row.get("producer") or "?")] += 1
    return {
        "total": total,
        "by_section": dict(sorted(by_section.items())),
        "by_producer": dict(by_producer.most_common()),
    }


def load_accepted(path: Path) -> dict[str, str]:
    """``{finding key: reason}``. A key with no reason is rejected: the point
    of the file is the explanation."""
    if not path.exists():
        return {}
    import yaml  # local: only the CLI path needs pyyaml

    data = yaml.safe_load(path.read_text()) or {}
    accepted: dict[str, str] = {}
    for entry in data.get("accepted") or []:
        key, reason = entry.get("key"), (entry.get("reason") or "").strip()
        if not key or not reason:
            raise ValueError(f"{path.name}: every entry needs a key and a reason: {entry!r}")
        accepted[str(key)] = reason
    return accepted


def split_findings(
    findings: Sequence[Mapping[str, Any]], accepted: Mapping[str, str]
) -> dict[str, Any]:
    new = [f for f in findings if f["key"] not in accepted]
    known = [
        {**f, "accepted_reason": accepted[f["key"]]}
        for f in findings
        if f["key"] in accepted
    ]
    live = {f["key"] for f in findings}
    return {
        "new": new,
        "accepted": known,
        # An accepted key that no longer fires should be removed from the file.
        "stale_accepted_keys": sorted(key for key in accepted if key not in live),
    }


def _describe(finding: Mapping[str, Any]) -> str:
    check = finding["check"]
    names = finding.get("schools") or []
    schools = ", ".join(names[:MARKDOWN_SCHOOLS_CAP])
    if len(names) > MARKDOWN_SCHOOLS_CAP:
        schools += f" and {len(names) - MARKDOWN_SCHOOLS_CAP} more"
    if check == "shared_source_file":
        years = finding["years"]
        span = years[0] if len(years) == 1 else f"{years[0]} to {years[-1]}"
        return f"{schools}: {finding['files']} file(s), {span}"
    if check == "shared_admissions_numbers":
        return (
            f"{finding['year']} {schools}: applied {finding['applied']}, "
            f"admitted {finding['admitted']}, enrolled {finding['enrolled_first_year']}"
        )
    if check == "federal_applicants_mismatch":
        return (
            f"{finding['year']} {schools}: CDS {finding['cds_applied']} vs "
            f"IPEDS {finding['ipeds_applicants']} (x{finding['ratio']})"
        )
    if check == "name_in_file_mismatch":
        return f"{finding['year']} {schools}: the file says \"{finding['name_in_file']}\""
    return schools


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "## Corpus audit",
        "",
        f"Generated {report['generated_at']}. Read-only; nothing was changed.",
        "",
        "| Check | New | Accepted |",
        "|---|---:|---:|",
    ]
    for check, counts in summary["findings"].items():
        lines.append(f"| `{check}` | {counts['new']} | {counts['accepted']} |")
    lines += [
        "",
        f"Federal comparison covered {summary['federal_rows_compared']} school-years.",
        "",
    ]
    for check in summary["findings"]:
        items = [f for f in report["findings"]["new"] if f["check"] == check]
        if not items:
            continue
        lines += [f"### New: `{check}` ({len(items)})", ""]
        lines += [f"- {_describe(f)}" for f in items[:MARKDOWN_LIST_CAP]]
        if len(items) > MARKDOWN_LIST_CAP:
            lines.append(f"- and {len(items) - MARKDOWN_LIST_CAP} more in the JSON report")
        lines.append("")
    if report["findings"]["stale_accepted_keys"]:
        lines += ["### Accepted entries that no longer fire (remove them)", ""]
        stale = report["findings"]["stale_accepted_keys"]
        lines += [f"- `{key}`" for key in stale[:MARKDOWN_LIST_CAP]]
        if len(stale) > MARKDOWN_LIST_CAP:
            lines.append(f"- and {len(stale) - MARKDOWN_LIST_CAP} more in the JSON report")
        lines.append("")
    lines += [
        "### Withheld values (trend, no action needed)",
        "",
        "| Sanity rule | Values withheld |",
        "|---|---:|",
    ]
    for rule, count in report["metrics"]["sanity_rules"]["values_flagged"].items():
        lines.append(f"| `{rule}` | {count} |")
    lines += [
        "",
        f"`parse_error` rows in `cds_fields`: {report['metrics']['parse_errors']['total']}.",
        "",
        "To accept a finding, add its key and a reason to "
        "`tools/data_quality/corpus_audit_accepted.yaml`. Keys are in the JSON report.",
        "",
    ]
    text = "\n".join(lines)
    if len(text) > MARKDOWN_MAX_CHARS:
        text = text[:MARKDOWN_MAX_CHARS] + "\n\nTruncated. The full list is in the JSON report.\n"
    return text


def build_report(
    *,
    documents: Sequence[Mapping[str, Any]],
    browser_rows: Sequence[Mapping[str, Any]],
    federal_rows: Sequence[Mapping[str, Any]],
    rule_field_rows: Sequence[Mapping[str, Any]],
    name_rows: Sequence[Mapping[str, Any]],
    parse_error_rows: Sequence[Mapping[str, Any]],
    accepted: Mapping[str, str],
) -> dict[str, Any]:
    federal_findings, compared = federal_applicants_mismatch(browser_rows, federal_rows)
    by_check = {
        "shared_source_file": shared_source_files(documents),
        "shared_admissions_numbers": shared_admissions_numbers(browser_rows),
        "federal_applicants_mismatch": federal_findings,
        "name_in_file_mismatch": name_in_file_mismatch(name_rows),
    }
    all_findings = [f for findings in by_check.values() for f in findings]
    split = split_findings(all_findings, accepted)
    new_keys = {f["key"] for f in split["new"]}
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "new_findings": len(split["new"]),
            "federal_rows_compared": compared,
            "findings": {
                check: {
                    "new": sum(1 for f in findings if f["key"] in new_keys),
                    "accepted": sum(1 for f in findings if f["key"] not in new_keys),
                }
                for check, findings in by_check.items()
            },
        },
        "findings": split,
        "metrics": {
            "sanity_rules": sanity_rule_hits(rule_field_rows),
            "parse_errors": parse_error_summary(parse_error_rows),
        },
    }


def fetch_inputs(client: ReadOnlyPostgrest) -> dict[str, list[dict[str, Any]]]:
    def rows(identifier, table, params, key, page_size=1000):
        fetched, _evidence = client.paginate(
            identifier, table, params, unique_key=key, page_size=page_size, timeout=120
        )
        return fetched

    rule_fields = ",".join(sorted(sanity_rules.FIELD_IDS))
    browser_rows = rows(
        "browser_rows",
        "school_browser_rows",
        {
            "select": "document_id,school_id,sub_institutional,ipeds_id,canonical_year,"
            "year_start,applied,admitted,enrolled_first_year",
            "order": "document_id",
        },
        lambda r: r["document_id"],
    )
    first_year = min((int(r["year_start"]) for r in browser_rows if r.get("year_start")), default=0)
    return {
        "documents": rows(
            "documents",
            "cds_documents",
            {
                "select": "id,school_id,cds_year,source_sha256,removed_at",
                "removed_at": "is.null",
                "source_sha256": "not.is.null",
                "order": "id",
            },
            lambda r: r["id"],
        ),
        "browser_rows": browser_rows,
        # ipeds_facts keeps every loaded year; the serving view keeps only the
        # newest, which would drop a CDS year from the check on each release.
        "federal_rows": rows(
            "federal_applicants",
            "ipeds_facts",
            {
                "select": "ipeds_id,data_year,release_type,value_numeric",
                "field_key": "eq.applicants_total",
                "public_visible": "eq.true",
                "data_year": f"gte.{first_year}",
                "order": "ipeds_id,data_year,release_type",
            },
            lambda r: (r["ipeds_id"], r["data_year"], r["release_type"]),
        ),
        "name_rows": rows(
            "institution_names",
            "cds_fields",
            {
                "select": "document_id,schema_version,school_id,school_name,"
                "canonical_year,value_text",
                "field_id": "eq.A.101",
                "order": "document_id,schema_version",
            },
            lambda r: (r["document_id"], r["schema_version"]),
        ),
        "rule_field_rows": rows(
            "rule_fields",
            "cds_fields",
            {
                "select": "document_id,school_id,canonical_year,schema_version,"
                "field_id,value_text,value_num,value_status",
                "field_id": f"in.({rule_fields})",
                "order": "document_id,schema_version,field_id",
            },
            lambda r: (r["document_id"], r["schema_version"], r["field_id"]),
        ),
        "parse_error_rows": rows(
            "parse_errors",
            "cds_fields",
            {
                "select": "document_id,schema_version,field_id,producer",
                "value_status": "eq.parse_error",
                "order": "document_id,schema_version,field_id",
            },
            lambda r: (r["document_id"], r["schema_version"], r["field_id"]),
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out-json", type=Path, default=REPO_ROOT / "scratch/corpus-audit/report.json")
    parser.add_argument("--out-md", type=Path, default=REPO_ROOT / "scratch/corpus-audit/report.md")
    parser.add_argument("--accepted", type=Path, default=DEFAULT_ACCEPTED)
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument(
        "--fail-on-new",
        action="store_true",
        help="Exit 3 when a finding is not in the accepted file.",
    )
    args = parser.parse_args(argv)

    env = load_env(args.env)
    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2

    report = build_report(
        **fetch_inputs(ReadOnlyPostgrest(url, key)),
        accepted=load_accepted(args.accepted),
    )
    for path, text in (
        (args.out_json, json.dumps(report, indent=2, sort_keys=True) + "\n"),
        (args.out_md, render_markdown(report)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote {args.out_json} and {args.out_md}")
    if args.fail_on_new and report["summary"]["new_findings"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
