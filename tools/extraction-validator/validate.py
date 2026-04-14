#!/usr/bin/env python3
"""Score a Docling markdown extract against a ground-truth YAML.

Each ground-truth field provides a regex `capture` with one capture group.
The validator applies it (case-insensitive, DOTALL) to the markdown, strips
commas/whitespace from the captured value, and compares to `expected`.

Exit code 0 if every critical field matched; 1 otherwise. Prints a summary
and a list of failures with expected vs actual (or "not found").
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class FieldResult:
    id: str
    section: str
    label: str
    expected: str
    actual: str | None
    passed: bool
    critical: bool


def normalize(value: str) -> str:
    return value.replace(",", "").replace(" ", "").strip()


def score(markdown: str, ground_truth: dict) -> list[FieldResult]:
    results: list[FieldResult] = []
    flags = re.IGNORECASE | re.DOTALL
    for field in ground_truth["fields"]:
        pattern = field.get("capture")
        expected = str(field["expected"])
        actual: str | None = None
        if pattern:
            m = re.search(pattern, markdown, flags)
            if m and m.groups():
                actual = normalize(m.group(1))
        passed = actual is not None and normalize(actual) == normalize(expected)
        results.append(
            FieldResult(
                id=field["id"],
                section=field.get("section", ""),
                label=field.get("label", field["id"]),
                expected=expected,
                actual=actual,
                passed=passed,
                critical=bool(field.get("critical", False)),
            )
        )
    return results


def summarize(results: list[FieldResult], label: str) -> tuple[int, int, int, int]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    crit_total = sum(1 for r in results if r.critical)
    crit_passed = sum(1 for r in results if r.critical and r.passed)
    print(f"\n== {label} ==")
    print(f"  {passed}/{total} fields matched  ({crit_passed}/{crit_total} critical)")
    failures = [r for r in results if not r.passed]
    if failures:
        print(f"  Failures:")
        for r in failures:
            marker = "!" if r.critical else " "
            actual = r.actual if r.actual is not None else "<not found>"
            print(
                f"   {marker} [{r.section:<4}] {r.id:<28} expected={r.expected!r:<10} actual={actual!r}"
            )
    return passed, total, crit_passed, crit_total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground-truth", required=True, type=Path)
    ap.add_argument("--markdown", required=True, type=Path)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    gt = yaml.safe_load(args.ground_truth.read_text())
    md = args.markdown.read_text()
    results = score(md, gt)
    label = args.label or f"{gt.get('school')} {gt.get('cds_year')} — {args.markdown.parent.name}"
    passed, total, crit_passed, crit_total = summarize(results, label)
    return 0 if crit_passed == crit_total else 1


if __name__ == "__main__":
    sys.exit(main())
