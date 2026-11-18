"""Unit tests for the pure selection and rendering logic in build_waitlist_recipe.py."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tools.scorecard import build_waitlist_recipe as b


def browser(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "document_id": "doc-1",
        "ipeds_id": "100001",
        "school_id": "example-college",
        "school_name": "Example College",
        "sub_institutional": None,
        "canonical_year": "2025-26",
        "year_start": 2025,
        "applied": 10000,
        "admitted": 2000,
        "enrolled_first_year": 800,
        "acceptance_rate": 0.2,
        "yield_rate": 0.4,
        "archive_url": "https://www.collegedata.fyi/schools/example-college/2025-26",
        "wait_list_policy": True,
        "wait_list_offered": 500,
        "wait_list_accepted": 400,
        "wait_list_admitted": 20,
        "admission_strategy_card_quality": "ok",
    }
    row.update(overrides)
    return row


DIRECTORY = {"100001": {"ipeds_id": "100001", "state": "MA", "control": 2, "undergraduate_enrollment": 3000}}
SCORECARD = {"100001": {"ipeds_id": "100001", "carnegie_basic": 21, "enrollment": 2900}}


def select(rows: list[dict[str, object]], directory=DIRECTORY, scorecard=SCORECARD):
    return b.select_rows(rows, directory, scorecard)


class ImpossibleCountsTests(unittest.TestCase):
    def test_valid_and_partial_counts_pass(self) -> None:
        self.assertIsNone(b.impossible_counts_reason(500, 400, 20))
        self.assertIsNone(b.impossible_counts_reason(500, 500, 500))
        self.assertIsNone(b.impossible_counts_reason(None, None, 14))
        self.assertIsNone(b.impossible_counts_reason(0, 0, 0))
        self.assertIsNone(b.impossible_counts_reason(500, 400, None))

    def test_more_admitted_than_accepted_is_impossible(self) -> None:
        self.assertIn("accepted a spot", b.impossible_counts_reason(609, 21, 34) or "")

    def test_more_accepted_than_offered_is_impossible(self) -> None:
        self.assertIn("were offered", b.impossible_counts_reason(100, 150, None) or "")

    def test_more_admitted_than_offered_is_impossible_without_accepted(self) -> None:
        self.assertIsNotNone(b.impossible_counts_reason(100, None, 150))

    def test_negative_counts_are_impossible(self) -> None:
        self.assertEqual(b.impossible_counts_reason(-1, None, None), "negative offered count")


class YearLabelTests(unittest.TestCase):
    def test_consecutive_pairs_pass(self) -> None:
        self.assertTrue(b.valid_year_label("2024-25", 2024))
        self.assertTrue(b.valid_year_label("1999-00", 1999))
        self.assertTrue(b.valid_year_label("2026-27", None))

    def test_malformed_or_disagreeing_labels_fail(self) -> None:
        self.assertFalse(b.valid_year_label("2025-03", 2025))
        self.assertFalse(b.valid_year_label("2024-26", 2024))
        self.assertFalse(b.valid_year_label("2024-25", 2025))
        self.assertFalse(b.valid_year_label(None, 2025))
        self.assertFalse(b.valid_year_label("2024/25", 2024))


class BucketLabelTests(unittest.TestCase):
    def test_selectivity_boundaries(self) -> None:
        self.assertEqual(b.selectivity_label(None), "No admit rate")
        self.assertEqual(b.selectivity_label(0.0999), "Under 10% admit rate")
        self.assertEqual(b.selectivity_label(0.10), "10-20% admit rate")
        self.assertEqual(b.selectivity_label(0.20), "20-40% admit rate")
        self.assertEqual(b.selectivity_label(0.40), "40%+ admit rate")

    def test_size_boundaries(self) -> None:
        self.assertEqual(b.size_label(None), "Unknown size")
        self.assertEqual(b.size_label(2499), "Small (<2.5k undergrads)")
        self.assertEqual(b.size_label(2500), "Midsize (2.5k-10k)")
        self.assertEqual(b.size_label(10000), "Large (10k-25k)")
        self.assertEqual(b.size_label(25000), "Very large (25k+)")

    def test_control_and_carnegie(self) -> None:
        self.assertEqual(b.control_label(1), "Public")
        self.assertEqual(b.control_label("2"), "Private nonprofit")
        self.assertEqual(b.control_label(3), "Unknown control")
        self.assertEqual(b.control_label(None), "Unknown control")
        self.assertEqual(b.carnegie_label(15), "Doctoral universities")
        self.assertEqual(b.carnegie_label(19), "Master's colleges")
        self.assertEqual(b.carnegie_label(22), "Baccalaureate colleges")
        self.assertEqual(b.carnegie_label(29), "Unknown Carnegie")
        self.assertEqual(b.carnegie_label(None), "Unknown Carnegie")

    def test_every_label_is_listed(self) -> None:
        self.assertIn(b.selectivity_label(0.3), b.SELECTIVITY_LABELS)
        self.assertIn(b.size_label(5000), b.SIZE_LABELS)
        self.assertIn(b.control_label(1), b.CONTROL_LABELS)
        self.assertIn(b.carnegie_label(16), b.CARNEGIE_LABELS)


class DerivedRateTests(unittest.TestCase):
    def test_round4_rounds_half_up(self) -> None:
        self.assertEqual(b.round4(0.12345), 0.1235)
        self.assertIsNone(b.round4(None))
        self.assertIsNone(b.round4(float("nan")))

    def test_rates_for_a_complete_row(self) -> None:
        rates = b.derive_rates(944, 738, 32, 0.0475)
        self.assertEqual(rates["waitListOptInRate"], 0.7818)
        self.assertEqual(rates["waitListSuccessRate"], 0.0434)
        self.assertEqual(rates["waitListOfferSuccessRate"], 0.0339)
        self.assertEqual(rates["relativeToRegularAdmitRate"], 0.91)

    def test_zero_denominators_give_null_rates(self) -> None:
        rates = b.derive_rates(247, 0, 0, 0.3)
        self.assertEqual(rates["waitListOptInRate"], 0)
        self.assertIsNone(rates["waitListSuccessRate"])
        self.assertEqual(rates["waitListOfferSuccessRate"], 0)
        self.assertIsNone(rates["relativeToRegularAdmitRate"])
        none_rates = b.derive_rates(0, None, None, None)
        self.assertTrue(all(value is None for value in none_rates.values()))


class SelectRowsTests(unittest.TestCase):
    def test_complete_row_shape_and_enrichment(self) -> None:
        rows, report = select([browser()])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(
            list(row),
            [
                "documentId", "ipedsId", "schoolId", "schoolName", "year", "yearStart", "state",
                "control", "carnegie", "size", "selectivity", "applied", "admitted",
                "enrolledFirstYear", "acceptanceRate", "yieldRate", "undergradEnrollment",
                "waitListPolicy", "waitListOffered", "waitListAccepted", "waitListAdmitted",
                "quality", "schoolUrl", "archiveUrl", "complete", "waitListOptInRate",
                "waitListSuccessRate", "waitListOfferSuccessRate", "relativeToRegularAdmitRate",
            ],
        )
        self.assertEqual(row["state"], "MA")
        self.assertEqual(row["control"], "Private nonprofit")
        self.assertEqual(row["carnegie"], "Baccalaureate colleges")
        self.assertEqual(row["size"], "Midsize (2.5k-10k)")
        self.assertEqual(row["selectivity"], "20-40% admit rate")
        self.assertEqual(row["schoolUrl"], "/schools/example-college/2025-26")
        self.assertTrue(row["complete"])
        self.assertEqual(report["impossible"], [])

    def test_rows_without_any_count_are_skipped(self) -> None:
        rows, report = select(
            [browser(wait_list_offered=None, wait_list_accepted=None, wait_list_admitted=None)]
        )
        self.assertEqual(rows, [])
        self.assertEqual(report["noWaitListCounts"], 1)

    def test_partial_row_is_kept_and_not_complete(self) -> None:
        rows, _ = select([browser(wait_list_offered=None, wait_list_accepted=None, wait_list_admitted=14)])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["complete"])
        self.assertIsNone(rows[0]["waitListSuccessRate"])

    def test_zero_counts_are_counts_not_missing(self) -> None:
        rows, _ = select([browser(wait_list_offered=0, wait_list_accepted=0, wait_list_admitted=0)])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["complete"])

    def test_sub_institutional_and_malformed_year_rows_are_skipped(self) -> None:
        rows, report = select(
            [
                browser(document_id="a", sub_institutional="general-studies"),
                browser(document_id="b", canonical_year="2025-03"),
            ]
        )
        self.assertEqual(rows, [])
        self.assertEqual(report["subInstitutional"], 1)
        self.assertEqual([item["documentId"] for item in report["malformedYear"]], ["b"])

    def test_impossible_rows_are_excluded_and_reported(self) -> None:
        rows, report = select(
            [
                browser(document_id="ok"),
                browser(document_id="bad", wait_list_offered=609, wait_list_accepted=21, wait_list_admitted=34),
            ]
        )
        self.assertEqual([row["documentId"] for row in rows], ["ok"])
        self.assertEqual(len(report["impossible"]), 1)
        self.assertEqual(report["impossible"][0]["documentId"], "bad")
        self.assertEqual(report["impossible"][0]["admitted"], 34)

    def test_no_slug_fallback_for_federal_facts(self) -> None:
        rows, _ = select([browser(ipeds_id=None)])
        self.assertEqual(rows[0]["control"], "Unknown control")
        self.assertEqual(rows[0]["carnegie"], "Unknown Carnegie")
        self.assertIsNone(rows[0]["state"])
        self.assertNotIn("ipedsId", rows[0])

    def test_enrollment_falls_back_to_scorecard(self) -> None:
        directory = {"100001": {"state": "MA", "control": 2, "undergraduate_enrollment": None}}
        rows, _ = select([browser()], directory=directory)
        self.assertEqual(rows[0]["undergradEnrollment"], 2900)

    def test_canonical_slug_replaces_alias_in_id_and_urls(self) -> None:
        rows, _ = b.select_rows(
            [browser(school_id="old-name")],
            DIRECTORY,
            SCORECARD,
            canonical_by_ipeds={"100001": "new-name"},
            canonical_by_alias={"old-name": "new-name"},
        )
        self.assertEqual(rows[0]["schoolId"], "new-name")
        self.assertEqual(rows[0]["schoolUrl"], "/schools/new-name/2025-26")
        self.assertEqual(rows[0]["archiveUrl"], "https://www.collegedata.fyi/schools/new-name/2025-26")

    def test_order_is_newest_year_then_name_descending_then_document_id(self) -> None:
        rows, _ = select(
            [
                browser(document_id="3", school_name="Alpha", canonical_year="2024-25", year_start=2024),
                browser(document_id="2", school_name="Alpha"),
                browser(document_id="1", school_name="Zulu"),
                browser(document_id="0", school_name="Alpha"),
            ]
        )
        self.assertEqual([r["documentId"] for r in rows], ["1", "0", "2", "3"])


def _rows_for_stats() -> list[dict[str, object]]:
    inputs = [
        ("a", 100, 80, 8),
        ("b", 100, 50, 25),
        ("c", 100, 40, 0),
        ("d", 50, 0, 0),
    ]
    rows, _ = select(
        [
            browser(document_id=doc, wait_list_offered=o, wait_list_accepted=a, wait_list_admitted=d)
            for doc, o, a, d in inputs
        ]
        + [browser(document_id="p", wait_list_offered=None, wait_list_accepted=None, wait_list_admitted=3)]
    )
    return rows


class SummaryTests(unittest.TestCase):
    def test_summary_counts_and_statistics(self) -> None:
        summary = b.build_summary(_rows_for_stats(), "2026-11-18")
        self.assertEqual(summary["allVisibleRows"], 5)
        self.assertEqual(summary["completeRows"], 3)  # zero-accepted row is not a rate row
        self.assertEqual(summary["partialRows"], 2)
        self.assertEqual(summary["medianSuccessRate"], 0.1)
        self.assertEqual(summary["weightedSuccessRate"], round(33 / 170, 4))
        self.assertEqual(summary["zeroishRows"], 1)
        self.assertEqual(summary["largestAcceptedWaitList"], 80)
        self.assertEqual(summary["medianAcceptedWaitList"], 50)
        self.assertEqual(summary["generatedAt"], "2026-11-18")
        self.assertEqual(list(summary)[-2:], ["generatedFrom", "generatedAt"])

    def test_buckets_skip_empty_labels_and_summarize_the_rest(self) -> None:
        buckets = b.build_buckets(_rows_for_stats())
        self.assertEqual(list(buckets), ["selectivity", "control", "size", "carnegie"])
        self.assertEqual([x["label"] for x in buckets["control"]], ["Private nonprofit"])
        self.assertEqual(buckets["selectivity"][0]["label"], "20-40% admit rate")
        self.assertEqual(buckets["selectivity"][0]["rows"], 3)
        self.assertEqual(buckets["selectivity"][0]["schools"], 1)
        self.assertEqual(buckets["selectivity"][0]["medianAccepted"], 50)


class CaseAndRenderTests(unittest.TestCase):
    def test_missing_case_pairs_are_reported_not_replaced(self) -> None:
        rows, _ = select([browser()])
        cases, missing = b.pick_cases(rows, [("example-college", "2025-26"), ("gone", "2024-25")])
        self.assertEqual([c["schoolId"] for c in cases], ["example-college"])
        self.assertEqual(missing, [("gone", "2024-25")])

    def test_render_has_generated_header_exclusions_and_parseable_blocks(self) -> None:
        rows, report = select(
            [browser(), browser(document_id="bad", wait_list_offered=10, wait_list_accepted=5, wait_list_admitted=9)]
        )
        summary = b.build_summary(rows, "2026-11-18")
        text = b.render_typescript(rows, summary, b.build_buckets(rows), rows[:1], report)
        self.assertTrue(text.startswith("// Generated by tools/scorecard/build_waitlist_recipe.py. Do not edit by hand."))
        self.assertIn("Generated at 2026-11-18.", text)
        self.assertIn("Excluded as internally impossible: 1 row(s).", text)
        self.assertIn("export type WaitlistRecipeRow = {", text)
        for name in ("WAITLIST_RECIPE_SUMMARY", "WAITLIST_BUCKETS", "WAITLIST_CASES", "WAITLIST_ROWS"):
            start = text.index(f"export const {name} = ") + len(f"export const {name} = ")
            json.JSONDecoder().raw_decode(text[start:])

    def test_build_artifact_requires_enough_rows(self) -> None:
        inputs = {"browser": [browser()], "directory": [], "scorecard": []}
        with self.assertRaises(ValueError):
            b.build_artifact(inputs, generated_at="2026-11-18")

    def test_postgrest_pages_until_short_page(self) -> None:
        pages = [[{"i": n} for n in range(b.PAGE_SIZE)], [{"i": 0}]]
        calls: list[str] = []

        class Response:
            def __init__(self, payload: list[dict[str, int]]) -> None:
                self.payload = payload

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def read(self, *_: object) -> bytes:
                return json.dumps(self.payload).encode()

        def fake_urlopen(request, timeout=0):
            calls.append(request.full_url)
            return Response(pages[len(calls) - 1])

        with patch("tools.scorecard.build_waitlist_recipe.urllib.request.urlopen", fake_urlopen):
            rows = b.postgrest_get_all("https://example.test", "key", "t", {"select": "i"})
        self.assertEqual(len(rows), b.PAGE_SIZE + 1)
        self.assertEqual(len(calls), 2)
        self.assertIn("offset=1000", calls[1])


if __name__ == "__main__":
    unittest.main()
