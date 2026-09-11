from __future__ import annotations

import textwrap
import unittest
from pathlib import Path

from tools.ops.lint_gha_heredocs import (
    extract_run_scripts,
    find_indented_terminators,
    lint_file,
)

ROOT = Path(__file__).resolve().parents[2]
FINDER = ROOT / ".github/workflows/ops-finder-probe.yml"


class LintGhaHeredocsTests(unittest.TestCase):
    def test_detects_indented_terminator(self) -> None:
        script = textwrap.dedent(
            """\
            if true; then
              python - <<'PY'
              print(1)
              PY
            fi
            """
        )
        # After the outer dedent above, PY is still indented relative to python? 
        # Reconstruct the exact failure shape GHA produces.
        script = (
            "if true; then\n"
            "  python - <<'PY'\n"
            "  print(1)\n"
            "  PY\n"
            "fi\n"
        )
        problems = find_indented_terminators(script)
        self.assertTrue(problems)
        self.assertIn("PY", problems[0])

    def test_accepts_column_zero_terminator(self) -> None:
        script = (
            "if true; then\n"
            "  python - <<'PY'\n"
            "print(1)\n"
            "PY\n"
            "fi\n"
        )
        self.assertEqual(find_indented_terminators(script), [])

    def test_finder_workflow_run_blocks_are_clean(self) -> None:
        self.assertTrue(FINDER.exists())
        errors = lint_file(FINDER, bash_n=True)
        self.assertEqual(errors, [])

    def test_extract_finds_run_blocks(self) -> None:
        yaml = textwrap.dedent(
            """\
            jobs:
              probe:
                steps:
                  - name: demo
                    run: |
                      echo hi
                      printf '%s\\n' ok
            """
        )
        blocks = extract_run_scripts(yaml)
        self.assertEqual(len(blocks), 1)
        self.assertIn("echo hi", blocks[0][1])


if __name__ == "__main__":
    unittest.main()
