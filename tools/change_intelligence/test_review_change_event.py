from __future__ import annotations

import unittest

from review_change_event import event_update_payload, parse_source_pages, review_payload


class ReviewChangeEventTests(unittest.TestCase):
    def test_review_payload_records_source_pages(self):
        payload = review_payload(
            "event-1",
            "Anthony",
            "confirmed",
            "Checked C9 table in both PDFs.",
            ["2025 p. 12", "2024 p. 11"],
        )

        self.assertEqual(payload["event_id"], "event-1")
        self.assertEqual(payload["verdict"], "confirmed")
        self.assertEqual(payload["source_pages_checked"], ["2025 p. 12", "2024 p. 11"])

    def test_publish_requires_confirmed_verdict(self):
        with self.assertRaises(ValueError):
            event_update_payload("ambiguous", publish=True)

        self.assertEqual(
            event_update_payload("confirmed", publish=True),
            {"verification_status": "confirmed", "public_visible": True},
        )

    def test_parse_source_pages_accepts_repeated_or_comma_separated_args(self):
        self.assertEqual(
            parse_source_pages(["2025 p. 12, 2024 p. 11", "prior appendix"]),
            ["2025 p. 12", "2024 p. 11", "prior appendix"],
        )


if __name__ == "__main__":
    unittest.main()
