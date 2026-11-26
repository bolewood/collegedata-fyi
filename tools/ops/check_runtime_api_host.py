#!/usr/bin/env python3
"""Gate: no runtime code calls the custom API host.

At the rename the API host moves and the old host becomes a redirect. A
runtime call that depends on that redirect loses its Authorization header
(Python requests drops it on a cross-host redirect). Runtime code therefore
reads SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL and defaults to PROJECT_ORIGIN
(tools/common/site.py, web/src/lib/site.ts).

This scans tracked code files and exits non-zero if one contains the literal
`api.quadfile.org` or `api.collegedata.fyi` (any case), or the identifiers API_ORIGIN or API_HOST
(everywhere except web pages and components outside web/src/lib and
web/src/app/api, which use them for display strings), unless the file is on
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
LITERAL = re.compile(r"api\.(quadfile\.org|collegedata\.fyi)", re.I)
IDENTIFIER = re.compile(r"\b(API_ORIGIN|API_HOST)\b")
WEB_RUNTIME_DIRS = ("web/src/lib/", "web/src/app/api/")
MAX_PRINT = 160

# path -> (reason, regex the WHOLE stripped line must match).
# Line-level on purpose: a new runtime use inside an allowlisted file is still
# flagged. Several entries per file are written as alternatives.
_BUILDER = (
    r"from tools\.common\.site import API_ORIGIN(, runtime_api_origin)?"
    r"|SOURCE_API_URL = API_ORIGIN(\s+#.*)?"
)
_GENERATED = (
    r'"sourceApiUrl": "https://api\.(quadfile\.org|collegedata\.fyi)",'
    r"|// Source: .*\(https://api\.(quadfile\.org|collegedata\.fyi)\)\."
)
ALLOWLIST: dict[str, tuple[str, str]] = {
    "tools/common/site.py": (
        "defines API_ORIGIN, the display origin; runtime uses runtime_api_origin()",
        r'API_ORIGIN = "https://api\.quadfile\.org"'
        r"|# Runtime default only; display \(docs, examples, generated data\) uses API_ORIGIN\.",
    ),
    "web/src/lib/site.ts": (
        "defines API_ORIGIN and API_HOST, the display origin",
        r'export const API_(ORIGIN|HOST) = "(https://)?api\.quadfile\.org";'
        r"|\* Runtime default only; display uses API_ORIGIN\. A runtime call that falls back",
    ),
    "web/src/lib/client-info.ts": (
        "own-host check accepts both API hosts (stored links use either)",
        r'const ARCHIVE_FILE_HOSTS = new Set\(\["api\.quadfile\.org", "api\.collegedata\.fyi"\]\);',
    ),
    "web/src/lib/old-api-host.ts": (
        "the old-host handler names both API hosts by design",
        r"\* Today no request reaches the app with these hosts \(api\.collegedata\.fyi is a"
        r'|"api\.collegedata\.fyi": "https://api\.quadfile\.org",',
    ),
    "web/src/lib/llms-txt.ts": (
        "display: llms.txt names the API host for readers",
        r'import \{ API_HOST, SITE_NAME \} from "\./site";'
        r"|- \[PostgREST archive docs\]\(\$\{SITE_URL\}/api\): The full read-only database API at \$\{API_HOST\} .*",
    ),
    "web/src/lib/spreadsheet.ts": (
        "display: README sheet of the downloadable workbook shows the API URL",
        r'import \{ API_ORIGIN, SITE_ORIGIN \} from "\./site";'
        r"|`\$\{API_ORIGIN\}/rest/v1/cds_fields\?school_id=eq\.\$\{input\.schoolId\}&canonical_year=eq\.\$\{input\.year\}`,",
    ),
    "web/src/app/api/page.tsx": (
        "display: the API docs page",
        r'import \{ API_HOST, API_ORIGIN, SITE_ORIGIN \} from "@/lib/site";'
        r"|const BASE = API_ORIGIN;|\{API_HOST\}",
    ),
    "tools/api_usage/classify.py": (
        "classifies gateway log lines by request host; the old host stays in the list",
        r'"api\.collegedata\.fyi", "api\.quadfile\.org", "isduwmygvmdozhpvzaix\.supabase\.co",',
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
    # Pages and components outside lib/ and app/api/ use API_ORIGIN for display
    # strings; only the literal is checked there.
    scan_identifiers = not path.startswith("web/src/") or path.startswith(WEB_RUNTIME_DIRS)
    patterns = [LITERAL, IDENTIFIER] if scan_identifiers else [LITERAL]
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(p.search(line) for p in patterns):
            found.append((n, line.strip()))
    return found


def shorten(text: str) -> str:
    """Truncate for printing only, with a visible marker."""
    return text if len(text) <= MAX_PRINT else text[:MAX_PRINT] + " [...truncated]"


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
            hits = [(n, text) for n, text in hits if not allowed.fullmatch(text)]
        violations.extend(f"{path}:{n}: {shorten(text)}" for n, text in hits)
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
