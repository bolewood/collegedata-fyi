"""C9 percentiles when Docling joins a spanning header to each column's own:
"50th Percentile - 25th Percentile Score". The column is what its header
names last.
"""
from __future__ import annotations

import unittest

from tier4_cleaner import _c9_percentile_header_roles, _normalize_label, clean

C9 = """\
## C9. First-time, first-year Profile

| Assessment | 50th Percentile - 25th Percentile Score | 50th Percentile - Score (not used in BFCP) | 50th Percentile - 75th Percentile Score |
|---|---|---|---|
| SAT Composite (400 - 1600) | 1093 | 1170 | 1270 |
| SAT Evidence-Based Reading and Writing (200 - 800) | 520 | 570 | 625 |
| SAT Math (200 - 800) | 540 | 590 | 638 |
| ACT Composite (0 - 36) | 25 | 26 | 31 |

## C10. Class rank
"""

PLAIN = C9.replace("50th Percentile - 25th Percentile Score", "25th Percentile Score").replace(
    "50th Percentile - Score (not used in BFCP)", "50th Percentile Score"
).replace("50th Percentile - 75th Percentile Score", "75th Percentile Score")


def _scores(markdown: str) -> dict[str, str]:
    out = clean(markdown, canonical_year="2023-24")
    return {qn: str(out[qn]["value"]) for qn in sorted(out) if "C.905" <= qn <= "C.916"}


EXPECTED = {
    "C.905": "1093", "C.906": "1170", "C.907": "1270",
    "C.908": "520", "C.909": "570", "C.910": "625",
    "C.911": "540", "C.912": "590", "C.913": "638",
    "C.914": "25", "C.915": "26", "C.916": "31",
}


class SpanningPercentileHeaderTest(unittest.TestCase):
    def test_header_roles_take_the_last_percentile_named(self):
        headers = [
            _normalize_label(h)
            for h in (
                "Assessment",
                "50th Percentile - 25th Percentile Score",
                "50th Percentile - Score (not used in BFCP)",
                "50th Percentile - 75th Percentile Score",
            )
        ]
        self.assertEqual(_c9_percentile_header_roles(headers), {0: "p25", 1: "p50", 2: "p75"})

    def test_scores_under_a_joined_spanning_header(self):
        self.assertEqual(_scores(C9), EXPECTED)

    def test_plain_headers_read_as_before(self):
        self.assertEqual(_scores(PLAIN), EXPECTED)

    def test_columns_printed_25_75_50_keep_their_roles(self):
        reordered = (
            "## C9. First-time, first-year Profile\n\n"
            "| Assessment | 25th Percentile | 75th Percentile | 50th Percentile |\n|---|---|---|---|\n"
            "| SAT Composite (400 - 1600) | 1093 | 1270 | 1170 |\n\n## C10. Class rank\n"
        )
        got = _scores(reordered)
        self.assertEqual((got["C.905"], got["C.906"], got["C.907"]), ("1093", "1170", "1270"))


if __name__ == "__main__":
    unittest.main()
