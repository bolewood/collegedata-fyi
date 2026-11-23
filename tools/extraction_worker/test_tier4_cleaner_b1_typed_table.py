"""B1 as Docling converts the 2023-24 CDS workbook grid: one table per student
group whose column headers name the sex and the load of every column
("Men - Full Time Enrollment - UNDERGRADUATE STUDENTS"). Cells are placed by
their own header.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import (
    SchemaIndex,
    _b1_sex_load_columns,
    _parse_markdown_tables,
    _resolve_b1_sex_load_table,
    clean,
    resolve_b1_enrollment,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_2023 = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2023_24.json")

SEXES = ("Men", "Women", "Another Gender")


def _header(corner: str, banner: str, sexes: tuple[str, ...] = SEXES) -> str:
    cells = [corner] + [
        f"{sex} - {load} Time Enrollment - {banner}"
        for sex in sexes
        for load in ("Full", "Part")
    ]
    return "| " + " | ".join(cells) + " |\n|" + "---|" * len(cells) + "\n"


def _row(label: str, *cells: str) -> str:
    return "| " + " | ".join((label,) + cells) + " |\n"


UNDERGRADUATE_ROWS = (
    _row("Degree-seeking, first-time, first-year students", "205", "12", "322", "13", "", "")
    + _row("Other first-year, degree-seeking students", "61", "3", "99", "11", "", "0")
    + _row("All other degree-seeking undergraduate students", "504", "45", "931", "81", "", "")
    + _row("Total degree-seeking undergraduate students", "770", "60", "1,352", "105", "", "0")
    + _row("All other undergraduates enrolled in credit courses", "2", "765", "5", "288", "", "")
    + _row("Total Undergraduate Students", "772", "825", "1,357", "393", "", "0")
)

GRADUATE_ROWS = (
    _row("Degree-seeking, first-time", "216", "39", "349", "83", "", "")
    + _row("All other degree-seeking", "461", "120", "713", "190", "", "")
    + _row("All other graduates enrolled in credit courses", "0", "2", "1", "2", "", "")
    + _row("Total Graduate Students", "677", "161", "1,063", "275", "", "")
)

MARKDOWN = (
    "## B1. Institutional Enrollment\n\n"
    + _header("Undergraduate", "UNDERGRADUATE STUDENTS")
    + UNDERGRADUATE_ROWS
    + "\n"
    + _header("Graduate", "GRADUATE STUDENTS")
    + GRADUATE_ROWS
    + "\n## B2. Enrollment by Racial/Ethnic Category\n"
)

# The same grid in the PDF's text layer. The sex line carries the corner
# label, so the grid reader does not take it for a sex-by-sex grid and the
# five-number total row is placed as if it had no blank cell.
LAYOUT = """\
B1. Institutional Enrollment
                 Undergraduate                              Men                         Women
                                                  Full Time      Part Time      Full Time      Part Time
                                                 Enrollment     Enrollment     Enrollment     Enrollment
                                                              UNDERGRADUATE STUDENTS
     Degree-seeking, first-time, first-year
     students                                         205            12            322            13
     Other first-year, degree-seeking students         61             3             99            11            0
     All other degree-seeking undergraduate
     students                                         504            45            931            81
  Total degree-seeking undergraduate students         770            60          1,352           105            0
     All other undergraduates enrolled in credit
     courses                                            2           765              5           288
                 Total Undergraduate Students         772           825          1,357           393            0
B2. Enrollment by Racial/Ethnic Category
"""


def _b1(markdown: str, text: str | None = None) -> dict[str, str]:
    out = resolve_b1_enrollment(_parse_markdown_tables(markdown), text or markdown, SCHEMA_2023)
    return {qn: str(entry["value"]) for qn, entry in out.items()}


def _read_table(markdown: str, out: dict[str, str], prefer_table: bool = True) -> dict[str, str]:
    """Read the first table of ``markdown`` over fields already holding ``out``."""
    table = _parse_markdown_tables(markdown)[0]
    fields = {qn: {"value": value, "source": "text"} for qn, value in out.items()}
    _resolve_b1_sex_load_table(
        table, _b1_sex_load_columns(table["headers"]), SCHEMA_2023, fields, prefer_table
    )
    return {qn: str(entry["value"]) for qn, entry in fields.items()}


def _undergraduate_table(rows: str, banner: str = "UNDERGRADUATE STUDENTS") -> str:
    return "## B1. Institutional Enrollment\n\n" + _header("", banner) + rows


class TypedColumnsTest(unittest.TestCase):
    def test_sex_and_load_are_read_from_each_header(self):
        headers = ["UNDERGRADUATES"] + [
            f"{sex} - {load} Time Enrollment - UNDERGRADUATE STUDENTS"
            for sex in SEXES
            for load in ("Full", "Part")
        ]
        self.assertEqual(
            _b1_sex_load_columns(headers),
            [
                ("Males", "FT"), ("Males", "PT"),
                ("Females", "FT"), ("Females", "PT"),
                ("Another Gender", "FT"), ("Another Gender", "PT"),
            ],
        )

    def test_load_first_headers_and_other_gender(self):
        headers = ["", "FULL-TIME - Men - Undergraduate", "FULL-TIME - Women - Undergraduate",
                   "FULL-TIME - Other gender - Undergraduate", "PART-TIME - Men - Undergraduate",
                   "PART-TIME - Women - Undergraduate", "PART-TIME - Other gender - Undergraduate"]
        self.assertEqual(
            _b1_sex_load_columns(headers),
            [("Males", "FT"), ("Females", "FT"), ("Another Gender", "FT"),
             ("Males", "PT"), ("Females", "PT"), ("Another Gender", "PT")],
        )

    def test_males_and_females_headers(self):
        headers = ["", "Males - Full Time", "Males - Part Time", "Females - Full Time", "Females - Part Time"]
        self.assertEqual(
            _b1_sex_load_columns(headers),
            [("Males", "FT"), ("Males", "PT"), ("Females", "FT"), ("Females", "PT")],
        )

    def test_sex_only_headers_are_not_typed(self):
        self.assertEqual(_b1_sex_load_columns(["", "Men", "Women", "Another Gender"]), [])

    def test_a_repeated_pair_is_not_typed(self):
        headers = ["", "Men - Full Time", "Men - Full Time", "Women - Full Time", "Women - Part Time"]
        self.assertEqual(_b1_sex_load_columns(headers), [])


class TypedTableTest(unittest.TestCase):
    def test_cells_are_placed_by_header(self):
        got = _b1(MARKDOWN)
        # Full-time men, part-time men, full-time women, part-time women.
        self.assertEqual((got["B.101"], got["B.125"], got["B.102"], got["B.126"]),
                         ("205", "12", "322", "13"))
        self.assertEqual((got["B.105"], got["B.129"], got["B.106"], got["B.130"]),
                         ("61", "3", "99", "11"))
        self.assertEqual((got["B.113"], got["B.137"], got["B.114"], got["B.138"]),
                         ("770", "60", "1352", "105"))
        self.assertEqual((got["B.117"], got["B.141"], got["B.118"], got["B.142"]),
                         ("2", "765", "5", "288"))
        self.assertEqual((got["B.121"], got["B.145"], got["B.122"], got["B.146"]),
                         ("772", "825", "1357", "393"))
        # A blank Another Gender cell is not a value; a printed 0 is.
        self.assertNotIn("B.103", got)
        self.assertEqual(got["B.131"], "0")

    def test_graduate_table_takes_its_group_from_the_header(self):
        got = _b1(MARKDOWN)
        self.assertEqual((got["B.153"], got["B.169"], got["B.154"], got["B.170"]),
                         ("216", "39", "349", "83"))
        self.assertEqual((got["B.157"], got["B.173"], got["B.158"], got["B.174"]),
                         ("461", "120", "713", "190"))
        self.assertEqual((got["B.165"], got["B.181"], got["B.166"], got["B.182"]),
                         ("677", "161", "1063", "275"))

    def test_table_corrects_totals_the_text_layer_shifted(self):
        text_only = _b1(LAYOUT)
        self.assertEqual(text_only.get("B.122"), "825")  # part-time men, misplaced
        got = _b1(MARKDOWN, LAYOUT)
        self.assertEqual((got["B.121"], got["B.145"], got["B.122"], got["B.146"]),
                         ("772", "825", "1357", "393"))
        self.assertEqual(got["B.101"], "205")

    def test_a_blank_cell_does_not_shift_the_row(self):
        rows = UNDERGRADUATE_ROWS.replace(
            _row("All other undergraduates enrolled in credit courses", "2", "765", "5", "288", "", ""),
            _row("All other undergraduates enrolled in credit courses", "", "13", "", "27", "", ""),
        ).replace(
            _row("Total Undergraduate Students", "772", "825", "1,357", "393", "", "0"),
            _row("Total Undergraduate Students", "770", "73", "1,352", "132", "", "0"),
        )
        got = _b1("## B1. Institutional Enrollment\n\n" + _header("", "UNDERGRADUATE STUDENTS") + rows)
        self.assertEqual((got["B.141"], got["B.142"]), ("13", "27"))
        self.assertNotIn("B.117", got)
        self.assertNotIn("B.118", got)

    def test_whole_decimals_are_counts(self):
        rows = UNDERGRADUATE_ROWS.replace("| 770 |", "| 770.0 |").replace("| 1,352 |", "| 1,352.0 |")
        got = _b1("## B1. Institutional Enrollment\n\n" + _header("", "UNDERGRADUATE STUDENTS") + rows)
        self.assertEqual((got["B.113"], got["B.114"]), ("770", "1352"))

    def test_a_missing_column_leaves_the_others_in_place(self):
        sexes = ("Men", "Women")
        markdown = (
            "## B1. Institutional Enrollment\n\n"
            + _header("", "UNDERGRADUATE STUDENTS", sexes)
            + _row("Degree-seeking, first-time, first-year students", "205", "12", "322", "13")
            + _row("Total Undergraduate Students", "772", "825", "1,357", "393")
        )
        got = _b1(markdown)
        self.assertEqual((got["B.101"], got["B.125"], got["B.102"], got["B.126"]),
                         ("205", "12", "322", "13"))
        self.assertEqual((got["B.121"], got["B.145"], got["B.122"], got["B.146"]),
                         ("772", "825", "1357", "393"))

    def test_table_found_under_another_heading(self):
        # No "Another Gender" column and no B1 heading: only the typed
        # headers say this is the enrollment grid.
        markdown = (
            "## B. ENROLLMENT AND PERSISTENCE\n\n"
            + _header("", "GRADUATE STUDENTS", ("Men", "Women"))
            + _row("Degree-seeking, first-time", "216", "39", "349", "83")
            + _row("All other degree-seeking", "461", "120", "713", "190")
        )
        got = _b1(markdown)
        self.assertEqual((got["B.153"], got["B.169"], got["B.154"], got["B.170"]),
                         ("216", "39", "349", "83"))

    def test_cut_label_under_an_undergraduate_heading_is_the_first_year_row(self):
        rows = UNDERGRADUATE_ROWS.replace(
            "Degree-seeking, first-time, first-year students", "Degree-seeking, first-time"
        )
        got = _b1(_undergraduate_table(rows))
        self.assertEqual((got["B.101"], got["B.125"]), ("205", "12"))
        self.assertNotIn("B.153", got)

    def test_marker_rows_split_one_table_into_its_two_halves(self):
        blank = ("",) * 6
        markdown = (
            "## B1. Institutional Enrollment\n\n"
            + _header("", "Enrollment")
            + _row("Undergraduates", *blank)
            + UNDERGRADUATE_ROWS.replace(
                "Degree-seeking, first-time, first-year students", "Degree-seeking, first-time"
            )
            + _row("Graduate Students", *blank)
            + GRADUATE_ROWS
        )
        got = _b1(markdown)
        self.assertEqual((got["B.101"], got["B.153"]), ("205", "216"))
        self.assertEqual((got["B.109"], got["B.157"]), ("504", "461"))

    def test_old_form_total_labels(self):
        rows = UNDERGRADUATE_ROWS.replace("Total Undergraduate Students", "Total undergraduates")
        got = _b1(_undergraduate_table(rows))
        self.assertEqual((got["B.121"], got["B.145"]), ("772", "825"))

    def test_dash_and_not_applicable_are_blank_cells_and_two_decimals_are_counts(self):
        rows = (
            _row("Degree-seeking, first-time, first-year students", "205.00", "12", "322", "13", "-", "N/A")
            + _row("Total degree-seeking undergraduate students", "205", "12", "322", "13", "", "")
        )
        got = _b1(_undergraduate_table(rows))
        self.assertEqual((got["B.101"], got["B.125"]), ("205", "12"))
        self.assertNotIn("B.103", got)
        self.assertNotIn("B.127", got)


class RejectedTableTest(unittest.TestCase):
    def _undergraduate(self, rows: str) -> dict[str, str]:
        return _b1("## B1. Institutional Enrollment\n\n" + _header("", "UNDERGRADUATE STUDENTS") + rows)

    def test_rows_that_do_not_add_up_are_not_taken(self):
        rows = UNDERGRADUATE_ROWS.replace("| 205 | 12 |", "| 12 | 205 |")
        self.assertEqual(self._undergraduate(rows), {})

    def test_a_repeated_row_is_not_taken(self):
        markdown = (
            "## B1. Institutional Enrollment\n\n"
            + _header("", "GRADUATE STUDENTS")
            + _row("Degree-seeking, first-time", "1,100", "", "1,605", "672", "", "254")
            + _row("Degree-seeking, first-time", "1,822", "2,280", "", "2,152", "", "")
        )
        self.assertEqual(_b1(markdown), {})

    def test_a_cell_that_is_not_a_plain_count_is_not_taken(self):
        for cell in ("Women 322", "-322", "32%", "3.5"):
            rows = UNDERGRADUATE_ROWS.replace("| 322 |", f"| {cell} |")
            self.assertEqual(self._undergraduate(rows), {}, cell)

    def test_a_row_shorter_than_the_headers_is_not_taken(self):
        rows = UNDERGRADUATE_ROWS.replace(
            _row("Other first-year, degree-seeking students", "61", "3", "99", "11", "", "0"),
            _row("Other first-year, degree-seeking students", "61", "3", "99"),
        )
        self.assertEqual(self._undergraduate(rows), {})

    def test_a_label_inside_a_cell_is_not_taken(self):
        markdown = (
            "## B1. Institutional Enrollment\n\n"
            + _header("", "GRADUATE STUDENTS")
            + _row("Degree-seeking, first-time", "1,822", "2,280", "", "2,152", "",
                   "All other degree-seeking 1,024")
        )
        self.assertEqual(_b1(markdown), {})

    def test_a_banner_word_inside_a_cell_is_dropped(self):
        rows = GRADUATE_ROWS.replace("| 349 |", "| GRADUATE 349 |").replace("| 83 |", "| STUDENTS 83 |", 1)
        got = _b1("## B1. Institutional Enrollment\n\n" + _header("", "GRADUATE STUDENTS") + rows)
        self.assertEqual((got["B.154"], got["B.170"]), ("349", "83"))


class CorrectingTheTextReadingTest(unittest.TestCase):
    """What an accepted table may change in fields the text reading filled."""

    CREDIT_BLANK = UNDERGRADUATE_ROWS.replace(
        _row("All other undergraduates enrolled in credit courses", "2", "765", "5", "288", "", ""),
        _row("All other undergraduates enrolled in credit courses", "", "13", "", "27", "", ""),
    ).replace(
        _row("Total Undergraduate Students", "772", "825", "1,357", "393", "", "0"),
        _row("Total Undergraduate Students", "770", "73", "1,352", "132", "", "0"),
    )
    # Credit courses: full-time men B.117, part-time men B.141, part-time women B.142.
    SHIFTED = {"B.117": "13", "B.141": "27", "B.142": "0"}

    def test_checked_cells_replace_counts_and_a_checked_blank_removes_one(self):
        got = _read_table(_undergraduate_table(self.CREDIT_BLANK), dict(self.SHIFTED))
        self.assertNotIn("B.117", got)
        self.assertEqual((got["B.141"], got["B.142"]), ("13", "27"))

    def test_nothing_is_corrected_without_prefer_table(self):
        got = _read_table(_undergraduate_table(self.CREDIT_BLANK), dict(self.SHIFTED), prefer_table=False)
        self.assertEqual({qn: got[qn] for qn in self.SHIFTED}, self.SHIFTED)
        self.assertEqual(got["B.101"], "205")

    def test_table_without_totals_only_fills_empty_fields(self):
        rows = (
            _row("Degree-seeking, first-time, first-year students", "12", "205", "322", "13", "", "")
            + _row("Other first-year, degree-seeking students", "61", "3", "99", "11", "", "")
        )
        got = _read_table(_undergraduate_table(rows), {"B.101": "205", "B.125": "12"})
        self.assertEqual((got["B.101"], got["B.125"]), ("205", "12"))
        self.assertEqual((got["B.105"], got["B.129"]), ("61", "3"))

    def test_column_blank_from_top_to_bottom_removes_nothing(self):
        rows = "".join(
            _row(label, men, "", women, part, "", "")
            for label, men, women, part in (
                ("Degree-seeking, first-time, first-year students", "205", "322", "13"),
                ("Other first-year, degree-seeking students", "61", "99", "11"),
                ("All other degree-seeking undergraduate students", "504", "931", "81"),
                ("Total degree-seeking undergraduate students", "770", "1,352", "105"),
            )
        )
        text = {"B.125": "12", "B.129": "3", "B.133": "45", "B.137": "60"}
        got = _read_table(_undergraduate_table(rows), dict(text))
        self.assertEqual({qn: got[qn] for qn in text}, text)
        self.assertEqual(got["B.101"], "205")

    def test_total_row_cut_from_the_table_drops_a_total_that_cannot_be_right(self):
        rows = UNDERGRADUATE_ROWS.replace(
            _row("Total Undergraduate Students", "772", "825", "1,357", "393", "", "0"), ""
        )
        got = _b1(_undergraduate_table(rows), LAYOUT)
        # The text layer put 825 (part-time men) under full-time women.
        self.assertEqual(got["B.121"], "772")
        self.assertNotIn("B.122", got)
        self.assertEqual(got["B.114"], "1352")


class MarkdownOnlyTotalTest(unittest.TestCase):
    def test_scalar_total_read_only_from_markdown_survives_the_text_pass(self):
        # The total row sits in a table under another heading, so only the
        # markdown pass, which reads the table's lines as text, finds it.
        markdown = (
            MARKDOWN.replace("\n## B2.", "\n## B. ENROLLMENT AND PERSISTENCE\n\n| | |\n|---|---|\n"
                             "| Total of all graduate students enrolled | 2,176 |\n\n## B2.")
        )
        without_text = clean(markdown, canonical_year="2023-24")
        self.assertEqual(str(without_text["B.194"]["value"]), "2176")
        only_text_pass = resolve_b1_enrollment(_parse_markdown_tables(markdown), LAYOUT, SCHEMA_2023)
        self.assertNotIn("B.194", only_text_pass)
        with_text = clean(markdown, supplemental_text=LAYOUT, canonical_year="2023-24")
        self.assertEqual(str(with_text["B.194"]["value"]), "2176")
        self.assertEqual(str(with_text["B.122"]["value"]), "1357")


if __name__ == "__main__":
    unittest.main()
