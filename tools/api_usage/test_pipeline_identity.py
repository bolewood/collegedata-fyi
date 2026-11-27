"""Pipeline tools that reach our public surfaces must identify themselves.

Calls with the service-role key are classified as internal by role. Calls
with the anon key, and plain fetches of public Storage URLs, look like
third-party traffic unless they send a collegedata-pipeline or quadfile-pipeline User-Agent, and
would inflate the public usage numbers (PRD 033).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
PUBLIC_SURFACE = re.compile(r"object/public|ANON_KEY")
MAKES_REQUESTS = re.compile(r"create_client\(|urlopen\(|requests\.(get|post|head|request)\(|httpx\.")
MARKERS = ("collegedata-pipeline/", "quadfile-pipeline/")


def offenders() -> list[str]:
    found = []
    for path in sorted(TOOLS.rglob("*.py")):
        if path.name.startswith("test_") or "api_usage" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if PUBLIC_SURFACE.search(text) and MAKES_REQUESTS.search(text) and not any(marker in text for marker in MARKERS):
            found.append(str(path.relative_to(TOOLS.parent)))
    return found


# Any quadfile- product token: a malformed one (uppercase, underscore, unknown
# tool) must be found and fail rather than slip past a strict pattern.
QUADFILE_UA = re.compile(r"(?<![\w./-])(quadfile-[A-Za-z0-9_.-]+)(/[0-9A-Za-z._-]+)?")


def is_well_formed_internal(c, ua: str) -> bool:
    # ua_is_internal lower-cases; the sent token must already be lower-case [a-z0-9-].
    token = ua.split("/", 1)[0]
    return bool(re.fullmatch(r"quadfile-[a-z0-9-]+", token)) and c.ua_is_internal(ua)


def sent_user_agents() -> list[tuple[str, str]]:
    found = []
    for path in sorted(TOOLS.rglob("*.py")):
        if path.name.startswith("test_") or path.name == "classify.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in QUADFILE_UA.finditer(text):
            found.append((str(path.relative_to(TOOLS.parent)), m.group(0)))
    return found


class PipelineIdentityTest(unittest.TestCase):
    def test_every_quadfile_user_agent_is_classified_internal(self):
        # A tool token missing from INTERNAL_UA_TOOLS would be counted as third-party traffic.
        from tools.api_usage import classify as c

        sent = sent_user_agents()
        self.assertGreater(len(sent), 20)
        bad = [(path, ua) for path, ua in sent if not is_well_formed_internal(c, ua)]
        self.assertEqual(bad, [])

    def test_the_scan_finds_malformed_tokens(self):
        from tools.api_usage import classify as c

        for ua in ("quadfile-Pipeline/x", "quadfile-ipeds_loader/1.0", "quadfile-unknown/1"):
            self.assertIsNotNone(QUADFILE_UA.search(ua), ua)
            self.assertFalse(is_well_formed_internal(c, ua), ua)

    def test_polite_fetch_user_agents_are_classified_internal(self):
        from tools.api_usage import classify as c
        from tools.common.polite_fetch import make_user_agent

        for token in ("scholarships", "collegedata-fyi-scholarships", "quadfile-scholarships"):
            self.assertTrue(c.ua_is_internal(make_user_agent(token)), token)

    def test_public_surface_callers_send_pipeline_user_agent(self):
        self.assertEqual(offenders(), [])


if __name__ == "__main__":
    unittest.main()
