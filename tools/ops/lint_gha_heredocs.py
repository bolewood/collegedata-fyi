#!/usr/bin/env python3
"""Fail if GitHub Actions `run: |` blocks contain indented bash heredoc terminators.

GHA YAML keeps relative indentation inside `run: |`. A nested:

    python - <<'PY'
        ...
        PY

becomes a script whose terminator is indented, so bash never closes the
heredoc and the step fails at parse time — even on the branch that does
not execute the heredoc body. That silently broke the monthly stuck-PDF
re-probe on 2026-09-02.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HEREDOC_START = re.compile(r"""<<(-)?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)(\2)""")
RUN_HEADER = re.compile(r"^(\s*)run:\s*\|\s*$")


def extract_run_scripts(text: str) -> list[tuple[int, str]]:
    """Return (start_line_1based, dedented_script) for each `run: |` block."""
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        match = RUN_HEADER.match(lines[i])
        if not match:
            i += 1
            continue
        indent = len(match.group(1))
        start = i + 1
        i += 1
        body: list[str] = []
        while i < len(lines):
            line = lines[i]
            if line.strip() == "":
                body.append("")
                i += 1
                continue
            cur = len(line) - len(line.lstrip(" "))
            if cur <= indent:
                break
            body.append(line)
            i += 1
        nonempty = [line for line in body if line.strip()]
        if not nonempty:
            continue
        mind = min(len(line) - len(line.lstrip(" ")) for line in nonempty)
        script = "\n".join(line[mind:] if len(line) >= mind else line for line in body) + "\n"
        out.append((start, script))
    return out


def _active_code(line: str) -> str:
    """Strip a trailing `#` comment, respecting quotes."""
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and (in_single or in_double):
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
        i += 1
    return line


def find_indented_terminators(script: str) -> list[str]:
    problems: list[str] = []
    lines = script.splitlines()
    for lineno, line in enumerate(lines):
        code = _active_code(line)
        for match in HEREDOC_START.finditer(code):
            strip_tabs = match.group(1) == "-"
            delim = match.group(3)
            for term_line in lines[lineno + 1 :]:
                if strip_tabs:
                    candidate = term_line.lstrip("\t")
                else:
                    candidate = term_line
                if candidate == delim:
                    break
                if candidate.strip() == delim and candidate != delim:
                    problems.append(
                        f"heredoc terminator {delim!r} is indented "
                        f"(line content {term_line!r})"
                    )
                    break
            else:
                problems.append(
                    f"heredoc terminator {delim!r} never appears unindented"
                )
    return problems


def lint_file(path: Path, *, bash_n: bool = True) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for start_line, script in extract_run_scripts(text):
        for problem in find_indented_terminators(script):
            errors.append(f"{path}:{start_line}: {problem}")
        if bash_n:
            result = subprocess.run(
                ["bash", "-n"],
                input=script,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "bash -n failed").strip()
                errors.append(f"{path}:{start_line}: bash -n: {detail}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=list(Path(".github/workflows").glob("*.yml")),
    )
    parser.add_argument("--no-bash-n", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    for path in args.paths:
        if not path.exists():
            errors.append(f"missing {path}")
            continue
        errors.extend(lint_file(path, bash_n=not args.no_bash_n))
    if errors:
        print("GHA run-script heredoc lint failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print(f"ok: linted {len(args.paths)} workflow file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
