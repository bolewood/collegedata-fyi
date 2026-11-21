from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import (
    SchemaIndex,
    _parse_markdown_tables,
    _strip_question_tag_column,
    clean,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2025_26.json")


def _lines(table: str) -> list[str]:
    return [ln.strip() for ln in table.strip().splitlines()]


class StripQuestionTagColumnTest(unittest.TestCase):
    def test_drops_a_column_that_repeats_one_tag(self):
        lines = _lines(
            """
| J1   | Category    | Associate   | Bachelor's   |
|------|-------------|-------------|--------------|
| J1   | Agriculture | 0           |              |
| J1   | Architecture | 0          | 0.043        |
"""
        )

        out, tag = _strip_question_tag_column(lines)

        self.assertEqual(tag, "J1")
        self.assertEqual(
            [[c.strip() for c in ln.split("|")[1:-1]] for ln in out],
            [
                ["Category", "Associate", "Bachelor's"],
                ["-------------", "-------------", "--------------"],
                ["Agriculture", "0", ""],
                ["Architecture", "0", "0.043"],
            ],
        )

    def test_drops_a_column_of_different_tags_without_naming_one(self):
        lines = _lines(
            """
| B5   | Of the initial cohort, how many did not persist | 0   |
| B6   | Final cohort, after adjusting for exclusions    | 656 |
| B7   | Completed the program in four years or less     | 324 |
"""
        )

        out, tag = _strip_question_tag_column(lines)

        self.assertIsNone(tag)
        self.assertTrue(out[0].lstrip("| ").startswith("Of the initial cohort"))

    def test_blank_cells_in_the_tag_column_are_allowed(self):
        lines = _lines(
            """
| H4   | Percent of the class who borrowed | 61% |
|      | through any loan program          |     |
| H4   | Average per-borrower debt         | $28,000 |
"""
        )

        out, tag = _strip_question_tag_column(lines)

        self.assertEqual(tag, "H4")
        self.assertEqual(
            [ln.split("|")[1].strip() for ln in out],
            [
                "Percent of the class who borrowed",
                "through any loan program",
                "Average per-borrower debt",
            ],
        )

    def test_leaves_a_mostly_blank_first_column_alone(self):
        lines = _lines(
            """
| C7   | Rigor of secondary school record | X |   |
|      | Class rank                       |   | X |
|      | Academic GPA                     | X |   |
|      | Standardized test scores         |   | X |
| C7   | Application essay                | X |   |
"""
        )

        self.assertIs(_strip_question_tag_column(lines)[0], lines)

    def test_tag_with_a_trailing_period_and_a_late_separator(self):
        lines = _lines(
            """
| C11. | Percent who had GPA of 3.75 and higher    | 32.00% |
| C11. | Percent who had GPA between 3.50 and 3.74 | 19.00% |
|------|-------------------------------------------|--------|
| C11. | Percent who had GPA between 3.25 and 3.49 | 20.00% |
"""
        )

        out, tag = _strip_question_tag_column(lines)

        self.assertEqual(tag, "C11")
        self.assertEqual(len(out), 4)
        self.assertRegex(out[2], r"^\|[\s\-:|]+\|$")
        self.assertTrue(all("C11" not in ln for ln in out))

    def test_leaves_compact_row_ids_alone(self):
        # Row-id exports key every row by its own field number; that column
        # is the label the direct-question-number path reads.
        lines = _lines(
            """
| C101 | Men who applied   | 872  |
| C102 | Women who applied | 1809 |
"""
        )

        self.assertIs(_strip_question_tag_column(lines)[0], lines)

    def test_leaves_labels_that_only_start_with_a_tag_alone(self):
        lines = _lines(
            """
| H1                     | Need-based $ | Non-need-based $ |
|------------------------|--------------|------------------|
| H1 Scholarships/Grants |              |                  |
| H1 Federal             | 100          | 200              |
"""
        )

        self.assertIs(_strip_question_tag_column(lines)[0], lines)

    def test_leaves_short_codes_with_numbers_beside_them_alone(self):
        # Visa types look like question tags; the numbers next to them are
        # values, not labels.
        lines = _lines(
            """
| F1 | 120 |
| J1 | 30  |
"""
        )

        self.assertIs(_strip_question_tag_column(lines)[0], lines)

    def test_leaves_a_single_tagged_row_alone(self):
        lines = _lines(
            """
|     | Yes | No |
| C8D | No  |    |
"""
        )

        self.assertIs(_strip_question_tag_column(lines)[0], lines)


class CleanWithQuestionTagColumnTest(unittest.TestCase):
    def test_parsed_table_matches_the_table_without_the_tag_column(self):
        tagged = """
| C11   | Percent who had GPA of 3.75 and higher     | 32.00% |
|-------|--------------------------------------------|--------|
| C11   | Percent who had GPA between 3.50 and 3.74  | 19.00% |
"""
        plain = """
| Percent who had GPA of 3.75 and higher     | 32.00% |
|--------------------------------------------|--------|
| Percent who had GPA between 3.50 and 3.74  | 19.00% |
"""

        tagged_tables = _parse_markdown_tables(tagged)
        plain_tables = _parse_markdown_tables(plain)

        self.assertEqual(tagged_tables[0]["question_tag"], "C11")
        self.assertIsNone(plain_tables[0]["question_tag"])
        strip = lambda rows: [(r["label"], r["values"]) for r in rows]
        self.assertEqual(strip(tagged_tables[0]["rows"]), strip(plain_tables[0]["rows"]))

    def test_j1_table_is_read_when_only_the_tag_names_the_question(self):
        # Concordia University Texas 2014-15: the heading above the table is
        # "J. DEGREES CONFERRED", and the header row is read as data because
        # "CIP 2010" contains digits. The tag is the only J1 signal left.
        markdown = """
## J. DEGREES CONFERRED

- J1 For each of the following discipline areas, provide the percentage of diplomas/certificates, associate, and bachelor's degrees awarded.

| J1   | Category                           | Diploma/Certificates   | Associate   | Bachelor's   | CIP 2010 Categories to Include   |
|------|------------------------------------|------------------------|-------------|--------------|----------------------------------|
| J1   | Agriculture                        |                        | 0           |              | 1                                |
| J1   | Natural resources and conservation |                        | 0           | 0.003        | 3                                |
| J1   | Communication/journalism           |                        | 0           | 0.043        | 9                                |
| J1   | Business/marketing                 |                        | 0           | 0.343        | 52                               |
"""

        values = clean(markdown, schema=SCHEMA)

        def qn(subsection: str, category: str) -> str:
            (field,) = [
                f
                for f in SCHEMA.filter(
                    section="Disciplinary Areas of Degrees Conferred",
                    subsection=subsection,
                )
                if str(f["category"]).strip() == category
            ]
            return field["question_number"]

        self.assertEqual(values[qn("Associate", "01")]["value"], "0")
        self.assertEqual(values[qn("Bachelors", "03")]["value"], "0.003")
        self.assertEqual(values[qn("Bachelors", "09")]["value"], "0.043")
        self.assertEqual(values[qn("Bachelors", "52")]["value"], "0.343")
        self.assertNotIn(qn("Bachelors", "01"), values)

    def test_c11_rows_are_read_through_the_tag_column(self):
        markdown = """
## C11 High school grade-point average

| C11   | Percent who had GPA of 3.75 and higher     | 32.00% |
|-------|--------------------------------------------|--------|
| C11   | Percent who had GPA between 3.50 and 3.74  | 19.00% |
| C11   | Percent who had GPA between 3.25 and 3.49  | 20.00% |
"""
        plain = markdown.replace("| C11   ", "").replace("|-------|", "|")

        tagged_values = clean(markdown, schema=SCHEMA)
        plain_values = clean(plain, schema=SCHEMA)

        self.assertEqual(tagged_values, plain_values)
        self.assertEqual(tagged_values["C.1103"]["value"], "19.00")
        self.assertEqual(tagged_values["C.1104"]["value"], "20.00")

    def test_tag_is_not_read_as_a_respondent_name(self):
        # "A2" normalizes to field A.002 (respondent last name); the mark in
        # the last cell used to be stored as that name.
        markdown = """
| A2   | Public              |     |
|------|---------------------|-----|
| A2   | Private (nonprofit) | x   |
| A2   | Proprietary         |     |
"""

        values = clean(markdown, schema=SCHEMA)

        self.assertNotIn("A.002", values)

    def test_address_is_not_read_as_a_respondent_first_name(self):
        # Seen in production: "A1" normalizes to field A.001 (respondent
        # first name), which then held the street address.
        markdown = """
| A1   | Name of College/University: | Example College |
|------|-----------------------------|-----------------|
| A1   | Mailing Address:            | PO Box 7000     |
"""

        values = clean(markdown, schema=SCHEMA)

        self.assertNotIn("A.001", values)


if __name__ == "__main__":
    unittest.main()
