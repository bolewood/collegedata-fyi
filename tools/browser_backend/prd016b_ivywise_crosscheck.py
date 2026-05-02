#!/usr/bin/env python3
"""Report-only IvyWise cross-check for PRD 016B.

This does not feed product data or gate math. It uses IvyWise's early-admission
round labels as a spot-check oracle for whether our CDS C.21/C.22 extraction is
missing obvious ED/EA policy signals.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_ROWS = REPO_ROOT / "scratch" / "admission-strategy-coverage" / "prd016b_phase0_rows.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "scratch" / "admission-strategy-coverage"
IVYWISE_URL = "https://www.ivywise.com/blog/college-early-admission-rates/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
STOPWORDS = {
    "at",
    "of",
    "the",
}
INSTITUTION_WORDS = {
    "and",
    "campus",
    "college",
    "colleges",
    "institute",
    "main",
    "polytechnic",
    "state",
    "technology",
    "university",
}
SCHOOL_ID_ALIASES = {
    "college william and mary": "william-and-mary",
    "georgia tech": "georgia-tech",
    "mit": "mit",
}


@dataclass
class IvyWiseRow:
    school: str
    normalized_school: str
    class_2030: str
    class_2029: str
    class_2028: str
    class_2027: str
    has_ed: bool
    has_ea: bool
    has_restrictive_ea: bool
    rounds_text: str


@dataclass
class CrosscheckRow:
    school_id: str | None
    school_name: str | None
    ivywise_school: str
    match_score: float | None
    applied_rank: int | None
    applied: int | None
    producer: str | None
    ivywise_ed: bool
    ivywise_ea: bool
    ivywise_restrictive_ea: bool
    our_ed: bool | None
    our_ea: bool | None
    our_restrictive_ea: bool | None
    ed_answerable: bool | None
    diagnosis: str
    ivywise_rounds: str


def normalize_name(name: str) -> str:
    text = name.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token not in STOPWORDS]
    return " ".join(tokens)


def distinctive_tokens(normalized_name: str) -> set[str]:
    return {
        token
        for token in normalized_name.split()
        if token not in INSTITUTION_WORDS and len(token) > 2
    }


def fetch_html() -> str:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--compressed",
            "-A",
            USER_AGENT,
            "-s",
            IVYWISE_URL,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def cell_text(cell: Any) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def parse_ivywise(html: str) -> list[IvyWiseRow]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("IvyWise page did not contain an early-admission table")

    rows: list[IvyWiseRow] = []
    for tr in table.find_all("tr")[1:]:
        cells = [cell_text(cell) for cell in tr.find_all(["th", "td"])]
        if len(cells) < 5:
            continue
        school, class_2030, class_2029, class_2028, class_2027 = cells[:5]
        rounds_text = " ".join(cells[1:])
        upper = rounds_text.upper()
        has_restrictive_ea = bool(re.search(r"\bREA\b|RESTRICTIVE|SINGLE[- ]CHOICE", upper))
        has_ed = bool(re.search(r"\bED\b|EARLY DECISION", upper))
        has_ea = bool(re.search(r"\bEA\b|EARLY ACTION|RESTRICTIVE|SINGLE[- ]CHOICE", upper))
        rows.append(
            IvyWiseRow(
                school=school,
                normalized_school=normalize_name(school),
                class_2030=class_2030,
                class_2029=class_2029,
                class_2028=class_2028,
                class_2027=class_2027,
                has_ed=has_ed,
                has_ea=has_ea,
                has_restrictive_ea=has_restrictive_ea,
                rounds_text=rounds_text,
            )
        )
    return rows


def best_match(ivywise: IvyWiseRow, audit_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float | None]:
    aliased_school_id = SCHOOL_ID_ALIASES.get(ivywise.normalized_school)
    if aliased_school_id:
        alias_row = next(
            (row for row in audit_rows if str(row.get("school_id")) == aliased_school_id),
            None,
        )
        if alias_row:
            return alias_row, 1.0

    best_row: dict[str, Any] | None = None
    best_score = 0.0
    ivywise_tokens = distinctive_tokens(ivywise.normalized_school)
    for row in audit_rows:
        candidate_name = normalize_name(str(row.get("school_name") or ""))
        candidate_tokens = distinctive_tokens(candidate_name)
        if ivywise_tokens and candidate_tokens and not ivywise_tokens.intersection(candidate_tokens):
            continue
        score = SequenceMatcher(
            None,
            ivywise.normalized_school,
            candidate_name,
        ).ratio()
        if score > best_score:
            best_row = row
            best_score = score
    if best_score < 0.82:
        return None, None
    return best_row, round(best_score, 3)


def applied_ranks(audit_rows: list[dict[str, Any]]) -> dict[str, int]:
    ranked = sorted(audit_rows, key=lambda row: row.get("applied") or -1, reverse=True)
    return {str(row["school_id"]): idx + 1 for idx, row in enumerate(ranked)}


def diagnose(ivywise: IvyWiseRow, row: dict[str, Any] | None) -> str:
    if row is None:
        return "unmatched_ivywise_school"

    issues: list[str] = []
    if ivywise.has_ed and row.get("ed_offered") is not True:
        issues.append("ivywise_ed_but_our_ed_not_true")
    if ivywise.has_ed and row.get("ed_answerable") is not True:
        issues.append("ivywise_ed_but_ed_counts_missing")
    if ivywise.has_ea and row.get("ea_offered") is not True:
        issues.append("ivywise_ea_but_our_ea_not_true")
    if ivywise.has_restrictive_ea and row.get("ea_restrictive") is not True:
        issues.append("ivywise_rea_but_our_restrictive_not_true")
    if row.get("ed_offered") is True and not ivywise.has_ed:
        issues.append("our_ed_true_but_ivywise_no_ed_label")
    if row.get("ea_offered") is True and not ivywise.has_ea:
        issues.append("our_ea_true_but_ivywise_no_ea_label")
    return ",".join(issues) if issues else "aligned"


def build_crosscheck(ivywise_rows: list[IvyWiseRow], audit_rows: list[dict[str, Any]]) -> list[CrosscheckRow]:
    ranks = applied_ranks(audit_rows)
    output: list[CrosscheckRow] = []
    for ivywise in ivywise_rows:
        row, score = best_match(ivywise, audit_rows)
        diagnosis = diagnose(ivywise, row)
        school_id = str(row["school_id"]) if row else None
        output.append(
            CrosscheckRow(
                school_id=school_id,
                school_name=str(row["school_name"]) if row else None,
                ivywise_school=ivywise.school,
                match_score=score,
                applied_rank=ranks.get(school_id) if school_id else None,
                applied=row.get("applied") if row else None,
                producer=row.get("producer") if row else None,
                ivywise_ed=ivywise.has_ed,
                ivywise_ea=ivywise.has_ea,
                ivywise_restrictive_ea=ivywise.has_restrictive_ea,
                our_ed=row.get("ed_offered") if row else None,
                our_ea=row.get("ea_offered") if row else None,
                our_restrictive_ea=row.get("ea_restrictive") if row else None,
                ed_answerable=row.get("ed_answerable") if row else None,
                diagnosis=diagnosis,
                ivywise_rounds=ivywise.rounds_text,
            )
        )
    return output


def summary(rows: list[CrosscheckRow]) -> dict[str, Any]:
    matched = [row for row in rows if row.school_id]
    issue_rows = [row for row in rows if row.diagnosis != "aligned"]
    top_200_issues = [
        row for row in issue_rows if row.applied_rank is not None and row.applied_rank <= 200
    ]
    return {
        "ivywise_rows": len(rows),
        "matched_rows": len(matched),
        "unmatched_rows": len(rows) - len(matched),
        "issue_rows": len(issue_rows),
        "top_200_issue_rows": len(top_200_issues),
        "ivywise_ed_rows": sum(row.ivywise_ed for row in rows),
        "ivywise_ea_rows": sum(row.ivywise_ea for row in rows),
        "ivywise_ed_missing_counts": sum(
            "ivywise_ed_but_ed_counts_missing" in row.diagnosis for row in rows
        ),
        "top_200_ivywise_ed_missing_counts": sum(
            "ivywise_ed_but_ed_counts_missing" in row.diagnosis
            and row.applied_rank is not None
            and row.applied_rank <= 200
            for row in rows
        ),
    }


def write_markdown(path: Path, data: dict[str, Any], rows: list[CrosscheckRow]) -> None:
    priority = sorted(
        [row for row in rows if row.diagnosis != "aligned"],
        key=lambda row: row.applied_rank or 999999,
    )[:40]
    lines = [
        "# PRD 016B IvyWise Cross-Check",
        "",
        f"Source: {IVYWISE_URL}",
        "",
        "Report-only QA artifact. IvyWise is not used as product data or gate input.",
        "",
        "## Summary",
        "",
    ]
    for key, value in data.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Highest-Priority Mismatches",
            "",
            "| Rank | School | IvyWise | Ours | Diagnosis |",
            "|---:|---|---|---|---|",
        ]
    )
    for row in priority:
        ours = (
            f"ED={row.our_ed}, EA={row.our_ea}, REA={row.our_restrictive_ea}, "
            f"ED counts={row.ed_answerable}, producer={row.producer}"
        )
        lines.append(
            f"| {row.applied_rank or ''} | {row.school_name or row.ivywise_school} "
            f"| ED={row.ivywise_ed}, EA={row.ivywise_ea}, REA={row.ivywise_restrictive_ea} "
            f"| {ours} | {row.diagnosis} |"
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-rows", type=Path, default=DEFAULT_AUDIT_ROWS)
    parser.add_argument("--ivywise-html", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    html = args.ivywise_html.read_text() if args.ivywise_html else fetch_html()
    ivywise_rows = parse_ivywise(html)
    audit_rows = json.loads(args.audit_rows.read_text())
    rows = build_crosscheck(ivywise_rows, audit_rows)
    data = summary(rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "prd016b_ivywise_crosscheck.json"
    md_path = args.output_dir / "prd016b_ivywise_crosscheck.md"
    json_path.write_text(
        json.dumps(
            {
                "summary": data,
                "rows": [asdict(row) for row in rows],
            },
            indent=2,
            sort_keys=True,
        )
    )
    write_markdown(md_path, data, rows)
    print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
