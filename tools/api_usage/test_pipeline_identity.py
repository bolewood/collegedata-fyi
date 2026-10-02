"""Pipeline tools that reach our public surfaces must identify themselves.

Calls with the service-role key are classified as internal by role. Calls
with the anon key, and plain fetches of public Storage URLs, look like
third-party traffic unless they send a collegedata-pipeline User-Agent, and
would inflate the public usage numbers (PRD 033).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
PUBLIC_SURFACE = re.compile(r"object/public|ANON_KEY")
MAKES_REQUESTS = re.compile(r"create_client\(|urlopen\(|requests\.(get|post|head|request)\(|httpx\.")
MARKER = "collegedata-pipeline/"


def offenders() -> list[str]:
    found = []
    for path in sorted(TOOLS.rglob("*.py")):
        if path.name.startswith("test_") or "api_usage" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if PUBLIC_SURFACE.search(text) and MAKES_REQUESTS.search(text) and MARKER not in text:
            found.append(str(path.relative_to(TOOLS.parent)))
    return found


class PipelineIdentityTest(unittest.TestCase):
    def test_public_surface_callers_send_pipeline_user_agent(self):
        self.assertEqual(offenders(), [])


if __name__ == "__main__":
    unittest.main()
