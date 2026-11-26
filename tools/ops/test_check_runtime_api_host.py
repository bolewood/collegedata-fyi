"""The runtime API host gate flags what it should and lets the allowlist through."""

import unittest

from tools.ops import check_runtime_api_host as gate


def run(files: dict[str, str]):
    return gate.check(list(files), read=files.__getitem__)


class GateTests(unittest.TestCase):
    def test_flags_the_literal_in_python_workflow_and_web_code(self):
        files = {
            "tools/x/a.py": 'API = "https://api.collegedata.fyi"\n',
            ".github/workflows/w.yml": "run: curl https://api.collegedata.fyi/rest/v1/x\n",
            "web/src/lib/q.ts": 'fetch("https://api.collegedata.fyi/rest/v1/x")\n',
            "supabase/functions/f/index.ts": 'const u = "https://api.collegedata.fyi";\n',
            "packages/cli/bin/c.js": 'const B = "https://api.collegedata.fyi";\n',
        }
        violations, _ = run(files)
        self.assertEqual(len(violations), len(files), violations)

    def test_flags_the_display_constant_used_in_tools_but_not_in_web_pages(self):
        violations, _ = run({"tools/x/a.py": "DEFAULT_API = API_ORIGIN\n"})
        self.assertEqual(len(violations), 1)
        violations, _ = run({"web/src/app/api/page.tsx": "const BASE = API_ORIGIN;\n"})
        self.assertEqual(violations, [])

    def test_ignores_tests_docs_and_unrelated_dirs(self):
        self.assertFalse(gate.is_scanned("tools/x/test_a.py"))
        self.assertFalse(gate.is_scanned("web/src/lib/a.test.ts"))
        self.assertFalse(gate.is_scanned("tools/x/README.md"))
        self.assertFalse(gate.is_scanned("tools/sheets/t.csv"))
        self.assertFalse(gate.is_scanned("docs/x.py"))
        self.assertTrue(gate.is_scanned("tools/x/a.py"))

    def test_allowlisted_file_passes_and_an_unmatched_entry_is_stale(self):
        listed = "tools/scorecard/build_waitlist_recipe.py"
        ok = "SOURCE_API_URL = API_ORIGIN  # display\n"
        violations, stale = gate.check([listed], read=lambda p: ok)
        self.assertEqual(violations, [])
        self.assertNotIn(listed, stale)
        _, stale = gate.check([listed], read=lambda p: "nothing here\n")
        self.assertIn(listed, stale)

    def test_an_allowlisted_file_is_still_flagged_for_a_new_runtime_line(self):
        listed = "tools/scorecard/build_waitlist_recipe.py"
        text = "SOURCE_API_URL = API_ORIGIN  # display\nurl = os.environ.get('X') or API_ORIGIN\n"
        violations, _ = gate.check([listed], read=lambda p: text)
        self.assertEqual(len(violations), 1, violations)
        self.assertIn(":2:", violations[0])
        listed = "web/src/lib/client-info.ts"
        text = (
            'const ownHost = host === "api.collegedata.fyi" || host.endsWith(".supabase.co");\n'
            'fetch("https://api.collegedata.fyi/x")\n'
        )
        violations, _ = gate.check([listed], read=lambda p: text)
        self.assertEqual(len(violations), 1, violations)

    def test_the_repository_is_clean(self):
        violations, stale = gate.check(gate.tracked_files())
        self.assertEqual(violations, [])
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
