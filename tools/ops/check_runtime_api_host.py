#!/usr/bin/env python3
"""Gate: no runtime code calls the custom API host.

At the rename the API host moves and the old host becomes a redirect. A
runtime call that depends on that redirect loses its Authorization header
(Python requests drops it on a cross-host redirect). Runtime code therefore
reads SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL and defaults to PROJECT_ORIGIN
(tools/common/site.py, web/src/lib/site.ts).

This scans tracked code files and exits non-zero if one contains the literal
`api.collegedata.fyi`, or (outside web/src, where pages use API_ORIGIN for
display strings) the identifiers API_ORIGIN or API_HOST, unless the file is on
ALLOWLIST with a reason. An allowlist entry whose file no longer matches also
fails, so the list cannot rot. Test files and non-code files (markdown, CSV,
SQL) are not scanned.

    python tools/ops/check_runtime_api_host.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ROOTS = ("tools/", "web/src/", "supabase/functions/", ".github/workflows/", "packages/", "tests/")
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".sh", ".yml", ".yaml"}
TEST_FILE = re.compile(r"(^|/)(test_[^/]*|[^/]*_test\.[a-z]+|[^/]*\.test\.[a-z]+|[^/]*\.spec\.[a-z]+)$")
LITERAL = re.compile(r"api\.collegedata\.fyi")
IDENTIFIER = re.compile(r"\b(API_ORIGIN|API_HOST)\b")

# path -> (reason, regex every matching line in that file must satisfy).
# Line-level on purpose: a new runtime use inside an allowlisted file is still
# flagged.
_BUILDER = r"^(from tools\.common\.site import API_ORIGIN\b.*|SOURCE_API_URL = API_ORIGIN\b.*)$"
_GENERATED = (
    r'^(\s*"sourceApiUrl": "https://api\.collegedata\.fyi",'
    r"|// Source: .*\(https://api\.collegedata\.fyi\)\.)$"
)
ALLOWLIST: dict[str, tuple[str, str]] = {
    "tools/common/site.py": (
        "defines API_ORIGIN, the display origin; runtime uses runtime_api_origin()",
        r'^(API_ORIGIN = "https://api\.collegedata\.fyi"|# .*API_ORIGIN.*)$',
    ),
    "web/src/lib/site.ts": (
        "defines API_ORIGIN and API_HOST, the display origin",
        r'^(export const API_(ORIGIN|HOST) = "(https://)?api\.collegedata\.fyi";|\*? ?.*API_ORIGIN.*)$',
    ),
    "web/src/lib/client-info.ts": (
        "own-host check must keep accepting the old host (links to it still exist)",
        r'^const ownHost = host === "api\.collegedata\.fyi" \|\| host\.endsWith\("\.supabase\.co"\);$',
    ),
    "tools/api_usage/classify.py": (
        "classifies gateway log lines by request host; the old host stays in the list",
        r'^"api\.collegedata\.fyi", "api\.quadfile\.org", "isduwmygvmdozhpvzaix\.supabase\.co",$',
    ),
    "tools/ipeds/build_endowment_draw_rate_recipe.py": ("display: records sourceApiUrl in generated recipe data", _BUILDER),
    "tools/ipeds/build_pricing_power_recipe.py": ("display: records sourceApiUrl in generated recipe data", _BUILDER),
    "tools/scorecard/build_alignment_gap_recipe.py": ("display: records sourceApiUrl in generated recipe data", _BUILDER),
    "tools/scorecard/build_waitlist_recipe.py": ("display: records the source URL in the generated header comment", _BUILDER),
    "web/src/lib/alignment-gap-recipe-data.ts": ("generated data; sourceApiUrl is shown to readers", _GENERATED),
    "web/src/lib/endowment-draw-rate-recipe-data.ts": ("generated data; sourceApiUrl is shown to readers", _GENERATED),
    "web/src/lib/pricing-power-recipe-data.ts": ("generated data; sourceApiUrl is shown to readers", _GENERATED),
    "web/src/lib/waitlist-recipe-data.ts": ("generated data; header comment names the source", _GENERATED),
}
# This file names the host in its own patterns.
SELF = "tools/ops/check_runtime_api_host.py"


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout
    return out.splitlines()


def is_scanned(path: str) -> bool:
    return (
        path != SELF
        and path.startswith(ROOTS)
        and Path(path).suffix in CODE_SUFFIXES
        and not TEST_FILE.search(path)
    )


def hits_in(path: str, text: str) -> list[tuple[int, str]]:
    patterns = [LITERAL] if path.startswith("web/src/") else [LITERAL, IDENTIFIER]
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(p.search(line) for p in patterns):
            found.append((n, line.strip()[:120]))
    return found


def check(files: list[str], read=lambda p: (REPO_ROOT / p).read_text(encoding="utf-8")):
    """Return (violations, stale allowlist entries)."""
    violations: list[str] = []
    matched: set[str] = set()
    for path in files:
        if not is_scanned(path):
            continue
        hits = hits_in(path, read(path))
        if not hits:
            continue
        if path in ALLOWLIST:
            matched.add(path)
            allowed = re.compile(ALLOWLIST[path][1])
            hits = [(n, text) for n, text in hits if not allowed.search(text)]
        violations.extend(f"{path}:{n}: {text}" for n, text in hits)
    stale = [p for p in ALLOWLIST if p not in matched]
    return violations, stale


def main() -> int:
    print("Allowlist (files that may name the custom API host):")
    for path, (reason, _) in ALLOWLIST.items():
        print(f"  {path}: {reason}")
    violations, stale = check(tracked_files())
    for v in violations:
        print(f"RUNTIME API HOST: {v}", file=sys.stderr)
    for p in stale:
        print(f"STALE ALLOWLIST ENTRY (no longer names the host): {p}", file=sys.stderr)
    if violations or stale:
        return 1
    print("ok: no runtime file names the custom API host")
    return 0


if __name__ == "__main__":
    sys.exit(main())
