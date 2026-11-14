from __future__ import annotations

import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus_audit as audit  # noqa: E402
import sanity_rules  # noqa: E402  (corpus_audit puts browser_backend on sys.path)


def browser(school, year="2024-25", applied=1000, admitted=500, enrolled=200, ipeds="100001"):
    return {
        "document_id": f"doc-{school}-{year}",
        "school_id": school,
        "ipeds_id": ipeds,
        "canonical_year": year,
        "year_start": int(year[:4]),
        "applied": applied,
        "admitted": admitted,
        "enrolled_first_year": enrolled,
    }


class SharedSourceFileTests(unittest.TestCase):
    def test_same_file_under_two_schools_is_one_finding_across_years(self):
        docs = [
            {"school_id": "whitman-college", "cds_year": "2024-25", "source_sha256": "a"},
            {"school_id": "worcester-polytechnic-institute", "cds_year": "2024-25", "source_sha256": "a"},
            {"school_id": "whitman-college", "cds_year": "2023-24", "source_sha256": "b"},
            {"school_id": "worcester-polytechnic-institute", "cds_year": "2023-24", "source_sha256": "b"},
        ]
        findings = audit.shared_source_files(docs)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0]["key"],
            "shared_source_file:whitman-college,worcester-polytechnic-institute",
        )
        self.assertEqual(findings[0]["files"], 2)
        self.assertEqual(findings[0]["years"], ["2023-24", "2024-25"])

    def test_one_school_reposting_a_file_and_hidden_documents_are_ignored(self):
        docs = [
            {"school_id": "mit", "cds_year": "2023-24", "source_sha256": "a"},
            {"school_id": "mit", "cds_year": "2024-25", "source_sha256": "a"},
            {"school_id": "uw-tacoma", "cds_year": "2018-19", "source_sha256": "c"},
            {"school_id": "uw-seattle", "cds_year": "2018-19", "source_sha256": "c", "removed_at": "2026-11-13"},
            {"school_id": "x", "cds_year": "2018-19", "source_sha256": None},
            {"school_id": "y", "cds_year": "2018-19", "source_sha256": None},
        ]
        self.assertEqual(audit.shared_source_files(docs), [])


class SharedAdmissionsNumbersTests(unittest.TestCase):
    def test_identical_counts_in_one_year_are_flagged(self):
        rows = [
            browser("bard-college", applied=11836, admitted=1046, enrolled=718),
            browser("barnard", applied=11836, admitted=1046, enrolled=718),
            browser("bowdoin", applied=11836, admitted=1046, enrolled=500),
        ]
        findings = audit.shared_admissions_numbers(rows)
        self.assertEqual(
            [f["key"] for f in findings],
            ["shared_admissions_numbers:2024-25:bard-college,barnard"],
        )

    def test_different_years_missing_counts_and_tiny_counts_do_not_match(self):
        rows = [
            browser("a", year="2024-25"),
            browser("b", year="2025-26"),
            browser("c", applied=None),
            browser("d", applied=None),
            browser("e", applied=12, admitted=12, enrolled=12),
            browser("f", applied=12, admitted=12, enrolled=12),
        ]
        self.assertEqual(audit.shared_admissions_numbers(rows), [])


class FederalMismatchTests(unittest.TestCase):
    FEDERAL = [
        {"ipeds_id": "1", "data_year": 2024, "value_numeric": 3005},
        {"ipeds_id": "2", "data_year": 2024, "value_numeric": 1000},
        {"ipeds_id": "3", "data_year": 2023, "value_numeric": 1000},
        {"ipeds_id": "4", "data_year": 2024, "value_numeric": 0},
    ]

    def test_flags_outside_the_band_in_both_directions_and_counts_the_denominator(self):
        rows = [
            browser("usc-aiken", applied=52703, ipeds="1"),
            browser("in-band-high", applied=1499, ipeds="2"),
            browser("no-federal-year", applied=9999, ipeds="3"),
            browser("zero-reference", applied=9999, ipeds="4"),
            browser("no-ipeds", applied=9999, ipeds=None),
        ]
        findings, compared = audit.federal_applicants_mismatch(rows, self.FEDERAL)
        self.assertEqual(compared, 2)
        self.assertEqual([f["schools"] for f in findings], [["usc-aiken"]])
        self.assertEqual(findings[0]["ratio"], "17.54")

        campus = dict(browser("uw-tacoma", applied=9999, ipeds="2"), sub_institutional="Tacoma")
        self.assertEqual(audit.federal_applicants_mismatch([campus], self.FEDERAL), ([], 0))

        both_releases = [
            {"ipeds_id": "5", "data_year": 2024, "release_type": "provisional", "value_numeric": 10},
            {"ipeds_id": "5", "data_year": 2024, "release_type": "final", "value_numeric": 1000},
        ]
        for order in (both_releases, both_releases[::-1]):
            self.assertEqual(
                audit.federal_applicants_mismatch([browser("s", applied=1000, ipeds="5")], order),
                ([], 1),
            )

        low, _ = audit.federal_applicants_mismatch(
            [browser("columbia", applied=516, ipeds="2")], self.FEDERAL
        )
        self.assertEqual(low[0]["key"], "federal_applicants_mismatch:columbia:2024-25")


class NameInFileTests(unittest.TestCase):
    @staticmethod
    def row(school_id, school_name, written):
        return {"school_id": school_id, "school_name": school_name,
                "canonical_year": "2024-25", "value_text": written}

    def test_a_different_institutions_name_is_flagged(self):
        findings = audit.name_in_file_mismatch([
            self.row("bard-college", "Bard College", "Barnard College"),
            self.row("winona-state-university", "Winona State University", "Iowa State University"),
        ])
        self.assertEqual(
            [f["key"] for f in findings],
            ["name_in_file_mismatch:bard-college:2024-25",
             "name_in_file_mismatch:winona-state-university:2024-25"],
        )
        self.assertEqual(findings[0]["name_in_file"], "Barnard College")

    def test_kerned_text_short_ids_and_non_names_are_not_flagged(self):
        rows = [
            self.row("pomona-college", "Pomona College", "Pom ona College"),
            self.row("the-university-of-texas-at-tyler", "The University of Texas at Tyler",
                     "T he University of T exas at T yler"),
            self.row("wayne-state-university", "Wayne State University", "WayneState University"),
            self.row("nyu", "New York University", "400 Lafayette Street"),
            self.row("worcester-state-university", "Worcester State University", "Massachusetts"),
            self.row("kenyon", "Kenyon College", "Mailing Address: City/State/Zip/Country: " * 4),
            self.row("mit", "Massachusetts Institute of Technology", "MIT"),
            self.row("the-university-of-texas-at-el-paso", "The University of Texas at El Paso",
                     "The University of"),
            self.row("x", "X College", None),
        ]
        self.assertEqual(audit.name_in_file_mismatch(rows), [])


class SanityRuleReplayTests(unittest.TestCase):
    def test_withheld_value_is_recovered_from_its_text(self):
        rows = [
            {"document_id": "d1", "schema_version": "2025-26", "school_id": "harvard",
             "canonical_year": "2025-26", "field_id": "H.605",
             "value_text": "$66,826,244", "value_num": None, "value_status": "parse_error"},
            {"document_id": "d2", "schema_version": "2025-26", "school_id": "duke",
             "canonical_year": "2025-26", "field_id": "H.605",
             "value_text": "83513", "value_num": 83513, "value_status": "reported"},
            {"document_id": "d3", "schema_version": "2025-26", "school_id": "x",
             "canonical_year": "2025-26", "field_id": "H.605",
             "value_text": "NaN", "value_num": None, "value_status": "parse_error"},
            {"document_id": "d4", "schema_version": "2025-26", "school_id": "y",
             "canonical_year": "2025-26", "field_id": "H.605",
             "value_text": "9000000", "value_num": None, "value_status": "missing"},
        ]
        hits = audit.sanity_rule_hits(rows)
        self.assertEqual(hits["values_flagged"]["per_student_average_is_a_total"], 1)
        self.assertEqual(hits["documents"]["per_student_average_is_a_total"], ["harvard/2025-26"])
        self.assertEqual(hits["values_flagged"]["ed_admitted_exceeds_applicants"], 0)

    def test_rules_read_only_the_fields_the_audit_fetches(self):
        # A rule may read a second field only when the first holds a certain
        # value, so every probe value is tried and the reads are pooled.
        class Recording(dict):
            def __init__(self, probe):
                super().__init__()
                self.probe = probe
                self.read: set[str] = set()

            def get(self, key, default=None):
                self.read.add(key)
                return self.probe

            def __getitem__(self, key):
                self.read.add(key)
                return self.probe

            def __contains__(self, key):
                self.read.add(key)
                return True

        versions = set(sanity_rules._ED_COUNT_FIELDS) | set(sanity_rules._H_SCHEMAS)
        read: set[str] = set()
        for schema_version in versions:
            for probe in (None, Decimal(0), Decimal(10), Decimal(2000), Decimal(10**9)):
                values = Recording(probe)
                for _name, rule in sanity_rules.RULES:
                    rule(schema_version, values)
                read |= values.read
        self.assertEqual(read, set(sanity_rules.FIELD_IDS))


class AcceptedFindingsTests(unittest.TestCase):
    def test_split_marks_accepted_and_reports_stale_keys(self):
        findings = [
            {"check": "c", "key": "c:one"},
            {"check": "c", "key": "c:two"},
        ]
        split = audit.split_findings(findings, {"c:two": "same institution", "c:gone": "old"})
        self.assertEqual([f["key"] for f in split["new"]], ["c:one"])
        self.assertEqual(split["accepted"][0]["accepted_reason"], "same institution")
        self.assertEqual(split["stale_accepted_keys"], ["c:gone"])

    def test_an_entry_without_a_reason_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accepted.yaml"
            path.write_text("accepted:\n  - key: 'c:one'\n")
            with self.assertRaises(ValueError):
                audit.load_accepted(path)
            path.write_text("accepted:\n  - key: 'c:one'\n    reason: one school, two ids\n")
            self.assertEqual(audit.load_accepted(path), {"c:one": "one school, two ids"})

    def test_the_checked_in_accepted_file_loads(self):
        audit.load_accepted(audit.DEFAULT_ACCEPTED)


class ReportTests(unittest.TestCase):
    def test_report_and_markdown_from_fixture_rows(self):
        report = audit.build_report(
            documents=[
                {"school_id": "a", "cds_year": "2024-25", "source_sha256": "s"},
                {"school_id": "b", "cds_year": "2024-25", "source_sha256": "s"},
            ],
            browser_rows=[browser("a", ipeds="2"), browser("b", ipeds="9")],
            federal_rows=FederalMismatchTests.FEDERAL,
            rule_field_rows=[],
            name_rows=[],
            parse_error_rows=[{"field_id": "H.401", "producer": "tier4_docling"}],
            accepted={"shared_source_file:a,b": "one institution"},
        )
        self.assertEqual(report["summary"]["new_findings"], 1)
        self.assertEqual(
            report["summary"]["findings"]["shared_source_file"], {"new": 0, "accepted": 1}
        )
        self.assertEqual(report["metrics"]["parse_errors"]["by_section"], {"H": 1})
        self.assertEqual(
            audit.heartbeat_summary(report),
            {"new_findings": 1, "accepted_findings": 1, "federal_rows_compared": 1,
             "values_withheld": 0, "parse_errors": 1},
        )
        markdown = audit.render_markdown(report)
        self.assertIn("New: `shared_admissions_numbers` (1)", markdown)
        self.assertNotIn("New: `shared_source_file`", markdown)

    def test_markdown_always_fits_a_github_issue(self):
        many = [{"school_id": f"school-{i:04d}", "cds_year": "2024-25", "source_sha256": "s"}
                for i in range(3000)]
        report = audit.build_report(
            documents=many, browser_rows=[], federal_rows=[], rule_field_rows=[],
            name_rows=[], parse_error_rows=[],
            accepted={f"gone:{i}" * 20: "old" for i in range(3000)},
        )
        markdown = audit.render_markdown(report)
        self.assertLess(len(markdown), 65_536)
        self.assertIn("and 2992 more", markdown)


if __name__ == "__main__":
    unittest.main()
