"""Tool code names the repository as bolewood/quadfile.

The ops scripts fall back to a hardcoded repo name when GITHUB_REPOSITORY is
unset, and the fetchers put a repo URL in their User-Agent. A leftover old name
there would only show up when a script runs outside Actions. Tests may keep the
old name as a fixture; this scans non-test code only.
"""

from __future__ import annotations

import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
OLD_REPO = "bolewood/collegedata-fyi"


class RepoNameDefaultsTests(unittest.TestCase):
    def test_no_tool_code_names_the_old_repo(self) -> None:
        offenders = [
            str(p.relative_to(TOOLS))
            for p in sorted(TOOLS.rglob("*.py"))
            if not p.name.startswith("test_")
            and "node_modules" not in p.parts
            and OLD_REPO in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
