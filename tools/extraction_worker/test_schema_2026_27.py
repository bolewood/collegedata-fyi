"""The 2026-27 template is the 2025-26 numbering plus twelve rows.

Three places rely on that (the tier 4 cleaner's `_NUMBERED_LIKE_2025_26`, the
projection's `_C1_NUMBERED_LIKE_2025_26` and the 2026-27 entries in
sanity_rules.py). These tests check the claim against the two schema files, so
a corrected 2026-27 template that renumbers anything fails here first.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import tier4_cleaner as tc  # noqa: E402
from tier4_cleaner import SchemaIndex, clean  # noqa: E402

SCHEMA_DIR = _THIS_DIR.parents[1] / "schemas"
ADDED = {
    "C.1T01", "C.1T02", "C.1T03",            # C1 Total row by sex
    "C.7A01",                                # generative AI policy
    "C.8A02",                                # test-optional / required / blind
    "C.9B01", "C.9B02", "C.9B03", "C.9B04",  # bachelor's-seeking test submitters
    "C.2207", "C.2208",                      # early action applied / admitted
    "G.0F01",                                # cost of attendance estimated or final
}
# The by-sex Total row took the form names the residency Total column had.
RETAGGED = {
    "C.116": ("AP_RECD_1ST_N", "AP_RECD_1ST_RES_N", "C.1T01"),
    "C.117": ("AP_ADMT_1ST_N", "AP_ADMT_1ST_RES_N", "C.1T02"),
    "C.118": ("EN_TOT_1ST_N", "EN_TOT_1ST_RES_N", "C.1T03"),
}
# Reworded with the same meaning: two typo fixes, "$B$1"/"$G$1" cell references
# written as B1/G1, and EFC renamed SAI in H2 lines I and J.
REWORDED = {
    "B.124", "B.149", "G.402",
    "H.201", "H.214", "H.227",
    "H.209", "H.210", "H.222", "H.223", "H.235", "H.236",
}
DIMENSIONS = ("section", "subsection", "category", "student_group", "cohort", "residency", "unit_load", "gender", "value_type")


def _fields(year: str) -> dict[str, dict]:
    schema = json.loads((SCHEMA_DIR / f"cds_schema_{year}.json").read_text())
    return {f["question_number"]: f for f in schema["fields"]}


def _wording(question: str) -> str:
    """Question text with the years it names masked."""
    return re.sub(r"20\d\d", "YYYY", re.sub(r"\s+", " ", question or "")).strip().lower()


class Schema2026NumberingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old, cls.new = _fields("2025_26"), _fields("2026_27")

    def test_nothing_was_removed_and_exactly_twelve_fields_were_added(self):
        self.assertEqual(set(self.old) - set(self.new), set())
        self.assertEqual(set(self.new) - set(self.old), ADDED)
        self.assertEqual(len(self.new), 1117)

    def test_every_2025_26_number_keeps_its_dimensions(self):
        for qn, field in self.old.items():
            for key in DIMENSIONS:
                self.assertEqual(field.get(key), self.new[qn].get(key), (qn, key))

    def test_every_2025_26_number_keeps_its_question(self):
        reworded = {qn for qn, f in self.old.items() if _wording(f["question"]) != _wording(self.new[qn]["question"])}
        self.assertEqual(reworded, REWORDED)

    def test_only_the_c1_totals_changed_form_name(self):
        changed = {qn for qn, f in self.old.items() if f.get("pdf_tag") != self.new[qn].get("pdf_tag")}
        self.assertEqual(changed, set(RETAGGED))
        for qn, (old_tag, new_tag, by_sex_total) in RETAGGED.items():
            self.assertEqual(self.old[qn]["pdf_tag"], old_tag)
            self.assertEqual(self.new[qn]["pdf_tag"], new_tag)
            self.assertEqual(self.new[by_sex_total]["pdf_tag"], old_tag)

    def test_checkbox_options_are_unchanged_for_shared_fields(self):
        for qn, field in self.old.items():
            self.assertEqual(field.get("value_options"), self.new[qn].get("value_options"), qn)

    def test_new_option_fields_carry_the_printed_labels(self):
        labels = {qn: [o["label"] for o in self.new[qn]["value_options"]] for qn in ("C.7A01", "C.8A02", "G.0F01")}
        self.assertEqual(
            sorted(labels["C.7A01"]),
            ["Fully Allowed", "No Policy", "Permitted as an Editing Tool", "Prohibited", "Unmonitored"],
        )
        self.assertEqual(labels["C.8A02"], ["Test-Optional", "Test-Required", "Test-Blind/Test-Free"])
        self.assertEqual(labels["G.0F01"], ["Estimated", "Firm and Final"])


# A 2025-26-layout document (the five dated 2026-27 before the template came
# out are on this layout). Sections A and B1 and a C1 with full-time and
# part-time enrolled rows only, so each place the cleaner branches on the
# template year is exercised. Names and numbers are invented.
LAYOUT_2025 = """
## A. General Information

## A0 Respondent Information (Not for Publication)

First Name:

Robin

Last Name:

Example

Title:

Director of Institutional Research

Office:

Institutional Research

Address Line 1:

One College Place

Address Line 2:

Address Line 3:

City:

Springfield

State PA

Zipcode

17701

Country:

Phone:

555-010-4029

Email Address:

[research@example.edu](mailto:research@example.edu)

Are your responses to the CDS posted for reference on your institution's Website?

- [x] Y Yes or No

If yes, please provide the URL of the corresponding Web page:

[https://www.example.edu/research/cds-2026-2027.pdf](https://www.example.edu/research/cds-2026-2027.pdf)

## A1 Address Information

Name of College/University:

Example College

Street Address Line 1:

One College Place

City Springfield

State PA

Zip

17701

Main Phone Number (Area Code)

555

Main Phone Number:

010-4317

WWW Home Page Address:

https://www.example.edu/

Main Institution Email

## Admissions Office

Admissions Phone Number (Area Code):

555

Admissions Phone Number:

010-4318

Admissions Email Address:

admissions@example.edu

If there is a separate URL for your school's online application, please specify:

[https://www.example.edu/apply/](https://www.example.edu/apply/)

- A2 Source of institutional control (Check only one):

- [ ] Public

- [x] X Private (nonprofit)

- [ ] Proprietary

## B1 Institutional Enrollment - Males and Females

Provide numbers of students for each of the following categories as of the institution's official fall reporting date or as of October 15, 2026.

| Undergraduate Students: Full-Time                   | Males   | Females   | Unknown   |
|-----------------------------------------------------|---------|-----------|-----------|
| Degree-seeking, first-time first-year students      | 150     | 130       | 5         |
| Other first-year, degree-seeking                    | 2       | 6         |           |
| All other degree-seeking                            | 310     | 350       |           |
| Total degree-seeking                                | 462     | 486       | 5         |
| All other undergraduates enrolled in credit courses |         |           |           |
| Total Undergraduate Full-Time Students              | 462     | 486       | 5         |

## C. FIRST-TIME, FIRST-YEAR ADMISSION

## C1-C2: Applications

- C1 First-time, first-year students: Provide the number of degree-seeking, first-time, first-year students who applied, were admitted, and enrolled (full- or part-time) in Fall 2026.

| First-Time, First-Year Student Applicants                        |   Total |
|------------------------------------------------------------------|---------|
| Total first-time, first-year males who applied                   |    1400 |
| Total first-time, first-year females who applied                 |    1700 |
| Total first-time, first-year students of unknown sex who applied |      50 |

| First-Time, First-Year Student Admits                                  |   Total |
|------------------------------------------------------------------------|---------|
| Total first-time, first-year males who were admitted                   |    1000 |
| Total first-time, first-year females who were admitted                 |    1300 |
| Total first-time, first-year students of unknown sex who were admitted |      40 |

| First-Time, First-Year Student Enrollees by Status                           |   Total |
|------------------------------------------------------------------------------|---------|
| Total full-time, first-time, first-year males who enrolled                   |     148 |
| Total part-time, first-time, first-year males who enrolled                   |       2 |
| Total full-time, first-time, first-year females who enrolled                 |     127 |
| Total part-time, first-time, first-year females who enrolled                 |       3 |

| First-Time, First-Year Student Applicants                       |   In-State |   Out-of-State |   International | Unknown   |   Total |
|-----------------------------------------------------------------|------------|----------------|-----------------|-----------|---------|
| Total first-time, first-year (degree-seeking) who applied       |        900 |           1800 |             450 |           |    3150 |
| Total first-time, first-year (degree-seeking) who were admitted |        800 |           1400 |             140 |           |    2340 |
| Total first-time, first-year (degree-seeking) who enrolled      |        170 |            110 |               5 |           |     285 |

- C2 First-time, first-year wait-listed students
"""


def _values(result: dict) -> dict[str, str]:
    return {qn: rec["value"] for qn, rec in result.items()}


class Cleaner2026ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.under_2025 = _values(clean(LAYOUT_2025, schema=SchemaIndex(SCHEMA_DIR / "cds_schema_2025_26.json")))
        cls.under_2026 = _values(clean(LAYOUT_2025, schema=SchemaIndex(SCHEMA_DIR / "cds_schema_2026_27.json")))

    def test_a_2025_layout_file_reads_the_same_under_either_schema(self):
        self.assertEqual(self.under_2026, self.under_2025)

    def test_the_residency_total_stays_on_c116_to_c118(self):
        values = self.under_2026
        self.assertEqual((values["C.116"], values["C.117"], values["C.118"]), ("3150", "2340", "285"))
        self.assertEqual((values["C.101"], values["C.102"], values["C.103"]), ("1400", "1700", "50"))
        for qn in ("C.1T01", "C.1T02", "C.1T03"):
            self.assertNotIn(qn, values)

    def test_section_a_keeps_the_2025_26_numbers(self):
        # Under a schema that is not numbered like 2025-26 these are also
        # written to the 2024-25 numbers: the phone to A.006, "responses
        # posted" to A.009, its URL to A.010, the admissions email to A.112.
        values = self.under_2026
        self.assertEqual(values["A.012"], "555-010-4029")
        self.assertEqual(values["A.014"], "Yes")
        self.assertEqual(values["A.127"], "admissions@example.edu")
        for qn in ("A.006", "A.009", "A.010", "A.112", "A.113"):
            self.assertNotIn(qn, values)

    def test_b1_uses_the_2025_26_field_map(self):
        values = self.under_2026
        self.assertEqual((values["B.101"], values["B.126"], values["B.151"]), ("150", "130", "5"))
        self.assertEqual((values["B.103"], values["B.128"]), ("310", "350"))

    def test_enrolled_by_sex_is_filled_from_the_full_and_part_time_rows(self):
        values = self.under_2026
        self.assertEqual((values["C.110"], values["C.111"], values["C.112"], values["C.113"]), ("148", "2", "127", "3"))
        self.assertEqual((values["C.107"], values["C.108"]), ("150", "130"))


if __name__ == "__main__":
    unittest.main()
