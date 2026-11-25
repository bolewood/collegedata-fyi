"""H1 read from the text layer by column (issue #486).

The fixtures are synthetic layouts shaped like the ones that showed each
case: Trinity (a row whose need-based cell is blank), Iowa (a table across a
page break) and the instruction line "items H1, H2, H2A, and H6" that ended
the section before the table. The amounts are Trinity's.
"""
from __future__ import annotations

import unittest

from tier4_cleaner import SchemaIndex, _h_layout_h1_rows_by_column, clean, schema_path_for_year

NEED_END, NON_NEED_END = 110, 140

INSTRUCTIONS = """H1. Aid Awarded to Enrolled Undergraduates
Enter total dollar amounts awarded to enrolled full-time and less than full-time degree-seeking undergraduates.
Indicate the academic year for which data are reported for items H1, H2, H2A, and H6 below:

                           2023-2024 Estimated
"""

HEADER = (
    " " * 100 + "Need-Based".ljust(20) + "Non-Need-Based\n"
    + " " * 4 + "H1. Aid Awarded to Enrolled Undergraduates\n"
)

AFTER = "\nH2. Number of Enrolled Students Awarded Aid\nList the number of degree-seeking students.\n"


def line(label: str, need: str = "", non_need: str = "", at: int = 38) -> str:
    out = " " * at + label
    for amount, end in ((need, NEED_END), (non_need, NON_NEED_END)):
        if amount:
            out = out.ljust(end - len(amount)) + amount
    return out + "\n"


# Trinity: Federal Work-Study and Parent Loans each print one amount, in
# different columns, and the "State and other" row prints none.
TRINITY_ROWS = (
    line("Federal", "$1,973,493", "$265,723")
    + line("State - all states, not only the state in which", "$141,723", "$0")
    + line("your institution is located")
    + line("Instititutional - Endowed scholarships, annual", "", "")
    + line("gifts and tuition funded grants, awarded by", "$75,746,654", "$4,204,069")
    + line("the college, excluding athletic aid and tuition")
    + line("waivers (which are reported below)")
    + line("Scholarships/grants from external sources")
    + line("(e.g. Kiwanis, National Merit) not awarded by", "$1,396,004", "$751,916")
    + line("the college")
    + line("Total Scholarships/Grants", "$79,257,874", "$5,221,708", at=60)
    + line("Student loans from all sources", "$2,308,770", "$7,214,427")
    + line("(excluding parent loans)")
    + line("Federal Work-Study", "$735,526")
    + line("State and other (e.g., institutional) work-")
    + line("study/employment (Note: excludes Federal")
    + line("Work/Study captured above)")
    + line("Total Self-Help", "$3,044,296", "$7,214,427", at=70)
    + line("Parent Loans", "", "$3,104,361")
    + line("Tuition Waivers", "$320,758", "$426,282")
    + line("Athletic Awards", "$0", "$0")
)

SCHEMA = SchemaIndex(schema_path_for_year("2023-24"))


def read(text: str, markdown: str = "") -> dict[str, str]:
    return {qn: rec["value"] for qn, rec in clean(markdown, supplemental_text=text, canonical_year="2023-24").items()}


def h1(values: dict[str, str]) -> dict[str, str]:
    return {qn: v for qn, v in values.items() if qn.startswith("H.") and qn[2:].isdigit() and 106 <= int(qn[2:]) <= 126}


class H1TextLayerTest(unittest.TestCase):
    def test_blank_need_based_cell_does_not_shift_columns(self) -> None:
        values = read(INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER)
        # 2023-24 numbering: need-based H.106..114, non-need-based H.118..125.
        self.assertNotIn("H.115", h1(values))  # Parent Loans need-based cell is blank
        self.assertEqual(values["H.126"], "3104361")  # Parent Loans non-need-based
        self.assertEqual(values["H.112"], "735526")  # Federal Work-Study, need-based
        self.assertNotIn("H.113", h1(values))  # "State and other" printed nothing
        self.assertEqual(values["H.110"], "79257874")
        self.assertEqual(values["H.114"], "3044296")
        self.assertEqual(values["H.122"], "5221708")

    def test_instruction_line_does_not_end_the_section(self) -> None:
        values = h1(read(INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER))
        self.assertEqual(values["H.106"], "1973493")
        self.assertGreaterEqual(len(values), 15)

    def test_table_across_a_page_break(self) -> None:
        # Iowa: the table's second half starts a new page, with a page header
        # and blank lines in between.
        rows = TRINITY_ROWS
        cut = rows.index(line("Student loans from all sources", "$2,308,770", "$7,214,427"))
        page_break = "\n\n\f2023-2024 Common Data Set        Page 21\n\nH. FINANCIAL AID\n\n"
        values = h1(read(INSTRUCTIONS + HEADER + rows[:cut] + page_break + rows[cut:] + AFTER))
        self.assertEqual(values["H.110"], "79257874")
        self.assertEqual(values["H.111"], "2308770")
        self.assertEqual(values["H.114"], "3044296")

    def test_amounts_that_do_not_add_up_are_refused(self) -> None:
        # The total of the need-based grants is wrong: nothing is claimed by
        # the column reader (the caller keeps the old reading).
        wrong = TRINITY_ROWS.replace("$79,257,874", "$79,000,000")
        section = INSTRUCTIONS + HEADER + wrong + AFTER
        self.assertEqual(_h_layout_h1_rows_by_column(section.split("Aid Awarded", 1)[1].split("H2. Number")[0]), {})

    def test_a_total_with_none_of_its_rows_read_is_refused(self) -> None:
        # Michigan: the Federal and State rows print as one line of four
        # amounts, so none of the grant rows is read. The self-help rows add
        # up on their own, which must not replace the markdown reading.
        rows = (
            line("Federal  State", "$1,973,493 $141,723", "$265,723 $0")
            + line("Total Scholarships/Grants", "$79,257,874", "$5,221,708", at=60)
            + line("Student loans from all sources", "$2,308,770", "$7,214,427")
            + line("Federal Work-Study", "$735,526")
            + line("Total Self-Help", "$3,044,296", "$7,214,427", at=70)
            + line("Parent Loans", "", "$3,104,361")
            + line("Tuition Waivers", "$320,758", "$426,282")
            + line("Athletic Awards", "$0", "$0")
        )
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_state_row_worded_with_an_example_is_still_the_state_row(self) -> None:
        text = INSTRUCTIONS + HEADER + TRINITY_ROWS.replace(
            "State - all states, not only the state in which", "State (i.e., all states, not only the state in which"
        ) + AFTER
        self.assertEqual(h1(read(text))["H.107"], "141723")

    def test_a_grand_total_row_under_the_last_row_is_not_that_rows_amounts(self) -> None:
        # Colorado: "TOTAL $184,012,917 $158,841,334" follows Athletic Awards.
        text = INSTRUCTIONS + HEADER + TRINITY_ROWS + line("TOTAL", "$184,012,917", "$158,841,334", at=60) + AFTER
        values = h1(read(text))
        self.assertEqual(values["H.117"], "0")  # Athletic Awards need-based
        self.assertEqual(values["H.110"], "79257874")

    def test_bare_amounts_and_zeros_without_a_dollar_sign(self) -> None:
        # Lee and Florida A&M print "9,375,016" and "0" with no "$".
        bare = TRINITY_ROWS.replace("$", "")
        values = h1(read(INSTRUCTIONS + HEADER + bare + AFTER))
        self.assertEqual(values["H.110"], "79257874")
        self.assertEqual(values["H.117"], "0")

    def test_a_lone_amount_printed_beyond_the_non_need_column(self) -> None:
        # Dartmouth: Parent Loans' non-need-based amount sits further right
        # than the column's other amounts.
        far = " " * 38 + "Parent Loans"
        far = far.ljust(170 - len("$3,104,361")) + "$3,104,361\n"
        rows = TRINITY_ROWS.replace(line("Parent Loans", "", "$3,104,361"), far)
        self.assertIn(far, rows)
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.126"], "3104361")
        self.assertNotIn("H.115", values)

    def test_a_row_label_that_wraps_past_the_word_excludes_is_still_the_row(self) -> None:
        # Baruch: "State and other (e.g., institutional) work-study/employment
        # (Note: Excludes" is the row's first line and holds its amount.
        rows = TRINITY_ROWS.replace(
            line("State and other (e.g., institutional) work-") + line("study/employment (Note: excludes Federal") + line("Work/Study captured above)"),
            line("State and other (e.g., institutional) work-study (Excludes", "$2,309,770")
            + line("Work/Study captured above.)"),
        ).replace(line("Federal Work-Study", "$735,526"), line("Federal Work-Study", "Not Applicable"))
        text = INSTRUCTIONS + HEADER + rows.replace("$3,044,296", "$2,309,770").replace("$2,308,770", "$0") + AFTER
        values = h1(read(text))
        self.assertEqual(values["H.113"], "2309770")  # State and other, need-based
        self.assertNotIn("H.112", values)  # not Federal Work-Study

    def test_three_amounts_under_one_label_are_refused(self) -> None:
        # Boston College: Athletic Awards' amounts print above its label,
        # under Tuition Waivers.
        rows = TRINITY_ROWS.replace(
            line("Tuition Waivers", "$320,758", "$426,282") + line("Athletic Awards", "$0", "$0"),
            line("Tuition Waivers") + line("report them.", "$320,758", "$426,282") + line("elsewhere.", "$11,000", "$12,000") + line("Athletic Awards"),
        )
        self.assertIn("elsewhere.", rows)
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_text_layer_replaces_the_markdown_h1_block(self) -> None:
        # The markdown reading put the work-study amount in H.113 ("State and
        # other") where the text layer has it in H.112. Both would be summed
        # by the scoreboard if the stale one stayed.
        markdown = (
            "## H1. Aid Awarded to Enrolled Undergraduates\n\n"
            "| | Need-based | Non-need-based |\n|---|---|---|\n"
            "| Federal | $1,973,493 | $265,723 |\n"
            "| Student loans from all sources | $2,308,770 | $7,214,427 |\n"
            "| State and other (e.g., institutional) work-study/employment | $735,526 | |\n"
            "| Total Self-Help | $3,044,296 | $7,214,427 |\n\n"
            "## H2. Number of Enrolled Students Awarded Aid\n"
        )
        alone = h1(read("", markdown))
        self.assertEqual(alone.get("H.113"), "735526")
        both = h1(read(INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER, markdown))
        self.assertNotIn("H.113", both)
        self.assertEqual(both["H.112"], "735526")

    def test_markdown_h1_stays_when_the_text_layer_is_refused(self) -> None:
        markdown = (
            "## H1. Aid Awarded to Enrolled Undergraduates\n\n"
            "| | Need-based | Non-need-based |\n|---|---|---|\n"
            "| Federal | $1,973,493 | $265,723 |\n\n"
            "## H2. Number of Enrolled Students Awarded Aid\n"
        )
        wrong = TRINITY_ROWS.replace("$79,257,874", "$79,000,000")
        values = h1(read(INSTRUCTIONS + HEADER + wrong + AFTER, markdown))
        self.assertEqual(values.get("H.106"), "1973493")


if __name__ == "__main__":
    unittest.main()
