"""tools/common/site.py must carry the same values as web/src/lib/site.ts."""

import importlib
import importlib.util
import re
import unittest
from pathlib import Path

from tools.common import site

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_TS = REPO_ROOT / "web" / "src" / "lib" / "site.ts"


def ts_string_constants() -> dict[str, str]:
    text = SITE_TS.read_text(encoding="utf-8")
    return dict(re.findall(r'^export const (\w+) = "([^"]*)";', text, re.M))


class SiteParityTests(unittest.TestCase):
    def test_python_constants_match_site_ts(self):
        ts = ts_string_constants()
        for name in ("SITE_NAME", "SITE_ORIGIN", "API_ORIGIN"):
            self.assertIn(name, ts, f"{name} not found in site.ts")
            self.assertEqual(getattr(site, name), ts[name], name)

    def test_report_m0_reads_the_directory_url_from_site(self):
        if importlib.util.find_spec("openpyxl") is None:
            self.skipTest("openpyxl not installed")
        m0 = importlib.import_module("tools.fsa.report_m0")
        self.assertEqual(m0.DIRECTORY_URL, f"{site.API_ORIGIN}/rest/v1/institution_directory")


if __name__ == "__main__":
    unittest.main()
