"""H1 read from the text layer by column (issue #486).

The fixtures are synthetic layouts shaped like the ones that showed each
case: Trinity (a row whose need-based cell is blank), Iowa (a table across a
page break) and the instruction line "items H1, H2, H2A, and H6" that ended
the section before the table. The amounts are Trinity's.
"""
from __future__ import annotations

import unittest

from tier4_cleaner import _h_layout_h1_rows_by_column, clean

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


def line(label: str, need: str = "", non_need: str = "", at: int = 38, ends: tuple[int, int] = (NEED_END, NON_NEED_END)) -> str:
    out = " " * at + label
    for amount, end in ((need, ends[0]), (non_need, ends[1])):
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

def read(text: str, markdown: str = "", year: str = "2023-24") -> dict[str, str]:
    return {qn: rec["value"] for qn, rec in clean(markdown, supplemental_text=text, canonical_year=year).items()}


def h1(values: dict[str, str]) -> dict[str, str]:
    return {qn: v for qn, v in values.items() if qn.startswith("H.") and qn[2:].isdigit() and 105 <= int(qn[2:]) <= 128}


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
        # The grants rows are missing from the layout (an unreadable page);
        # only their total prints. The self-help block adds up on its own,
        # which must not replace the markdown reading.
        rows = (
            line("Total Scholarships/Grants", "$79,257,874", "$5,221,708", at=60)
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

    def test_a_lone_amount_far_from_both_columns_is_not_placed_but_the_printed_markdown_value_stays(self) -> None:
        # Dartmouth: Parent Loans' non-need-based amount sits 30 columns right
        # of the column's other amounts. It is within no column, so the text
        # reading does not place it; the markdown's value stands because the
        # row prints it.
        far = " " * 38 + "Parent Loans"
        far = far.ljust(170 - len("$3,104,361")) + "$3,104,361\n"
        rows = TRINITY_ROWS.replace(line("Parent Loans", "", "$3,104,361"), far)
        self.assertIn(far, rows)
        self.assertNotIn("H.126", h1(read(INSTRUCTIONS + HEADER + rows + AFTER)))
        markdown = "| Question | Value |\n|---|---|\n| H.126 | 3104361 |\n"
        self.assertEqual(h1(read(INSTRUCTIONS + HEADER + rows + AFTER, markdown))["H.126"], "3104361")

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

    def test_rows_whose_total_was_not_read_are_refused(self) -> None:
        # Lenoir-Rhyne prints "Total Self-Help" under the amounts that belong
        # to it, so the amounts land on the State and other row.
        rows = TRINITY_ROWS.replace(
            line("Total Self-Help", "$3,044,296", "$7,214,427", at=70) + line("Parent Loans", "", "$3,104,361"),
            line("Parent Loans", "", "$3,104,361"),
        ).replace(
            line("Federal Work-Study", "$735,526") + line("State and other (e.g., institutional) work-"),
            line("Federal Work-Study", "$735,526") + line("State and other (e.g., institutional) work-", "$3,044,296", "$7,214,427"),
        )
        self.assertIn("Total Self-Help", TRINITY_ROWS)
        self.assertNotIn("Total Self-Help", rows)
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_text_layer_clears_h1_ids_the_direct_question_number_path_filled(self) -> None:
        # A markdown Question/Value table fills H.113 before any resolver runs.
        markdown = "| Question | Value |\n|---|---|\n| H.113 | 735526 |\n"
        self.assertEqual(h1(read("", markdown))["H.113"], "735526")
        both = h1(read(INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER, markdown))
        self.assertNotIn("H.113", both)
        self.assertEqual(both["H.112"], "735526")

    def test_a_markdown_value_the_row_prints_but_the_text_did_not_read_is_kept(self) -> None:
        # Bare amounts below 1,000 are not read as amounts; the markdown's
        # 320 and 400 stand because the Tuition Waivers row prints them.
        markdown = "| Question | Value |\n|---|---|\n| H.116 | 320 |\n| H.127 | 400 |\n"
        rows = TRINITY_ROWS.replace(line("Tuition Waivers", "$320,758", "$426,282"), line("Tuition Waivers", "320", "400"))
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER, markdown))
        self.assertEqual((values["H.116"], values["H.127"]), ("320", "400"))
        self.assertEqual(values["H.110"], "79257874")  # the text reading was accepted
        # A markdown value the row does not print is not kept.
        wrong = "| Question | Value |\n|---|---|\n| H.116 | 999 |\n"
        self.assertNotIn("H.116", h1(read(INSTRUCTIONS + HEADER + rows + AFTER, wrong)))

    def test_a_row_name_after_excludes_does_not_hide_the_row_name_before_it(self) -> None:
        rows = TRINITY_ROWS.replace(
            line("Federal Work-Study", "$735,526"),
            line("Federal Work-Study (excludes state and other)", "$735,526"),
        )
        self.assertEqual(h1(read(INSTRUCTIONS + HEADER + rows + AFTER))["H.112"], "735526")

    def test_lone_amounts_need_separated_columns(self) -> None:
        # Columns 8 apart: the least that fits two short amounts, and less than
        # the 12 that count as separated.
        narrow = (110, 118)
        rows = "".join(
            line(label, need, non, ends=narrow)
            for label, need, non in (
                ("Federal", "$10,000", "$1,000"),
                ("State - all states, not only the state in which", "$20,000", "$2,000"),
                ("Instititutional - Endowed scholarships, annual", "$30,000", "$3,000"),
                ("Scholarships/grants from external sources", "$40,000", "$4,000"),
            )
        )
        rows += line("Total Scholarships/Grants", "$100,000", "$10,000", at=60, ends=narrow)
        rows += line("Student loans from all sources", "$5,000", "$500", ends=narrow)
        rows += line("Total Self-Help", "$5,000", "$500", at=70, ends=narrow)
        rows += line("Parent Loans", "", "$3,100", ends=narrow)
        rows += line("Tuition Waivers", "$320", "$426", ends=narrow)
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.110"], "100000")  # the table itself is accepted
        self.assertNotIn("H.126", values)  # the lone amount cannot be placed
        # Same layout with the columns apart: it is placed.
        apart = h1(read(INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER))
        self.assertEqual(apart["H.126"], "3104361")

    def test_a_number_inside_a_label_is_not_a_lone_amount(self) -> None:
        rows = TRINITY_ROWS.replace(
            line("Parent Loans", "", "$3,104,361"),
            line("Parent Loans (about 2,500 families)", "", "$3,104,361"),
        )
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertNotIn("H.115", values)  # 2,500 ends left of the need-based column
        self.assertEqual(values["H.126"], "3104361")

    def test_a_lone_amount_about_as_near_to_both_columns_is_dropped(self) -> None:
        # Columns 12 apart (the least that counts as separated); the lone
        # amount ends midway, 6 columns from each.
        ends = (110, 122)
        rows = "".join(
            line(label, need, non, ends=ends)
            for label, need, non in (
                ("Federal", "$1,973,493", "$265,723"),
                ("State - all states, not only the state in which", "$141,723", "$0"),
                ("Instititutional - Endowed scholarships, annual", "$75,746,654", "$4,204,069"),
                ("Scholarships/grants from external sources", "$1,396,004", "$751,916"),
            )
        )
        rows += line("Total Scholarships/Grants", "$79,257,874", "$5,221,708", at=60, ends=ends)
        rows += line("Student loans from all sources", "$2,308,770", "$7,214,427", ends=ends)
        rows += line("Federal Work-Study", "$735,526", ends=ends)
        rows += line("Total Self-Help", "$3,044,296", "$7,214,427", at=70, ends=ends)
        placed = h1(read(INSTRUCTIONS + HEADER + rows + line("Athletic Awards", "$5,000", ends=(110, 110)) + AFTER))
        self.assertEqual(placed["H.117"], "5000")  # control: at the need-based column
        midway = h1(read(INSTRUCTIONS + HEADER + rows + line("Athletic Awards", "$5,000", ends=(116, 116)) + AFTER))
        self.assertNotIn("H.117", midway)
        self.assertNotIn("H.128", midway)

    def test_a_missing_self_help_block_refuses_the_reading(self) -> None:
        start = TRINITY_ROWS.index(line("Student loans from all sources", "$2,308,770", "$7,214,427"))
        end = TRINITY_ROWS.index(line("Parent Loans", "", "$3,104,361"))
        rows = TRINITY_ROWS[:start] + TRINITY_ROWS[end:]
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_a_row_labelled_twice_is_refused(self) -> None:
        # The same amounts again, so the sums cannot tell.
        rows = TRINITY_ROWS + line("Federal", "$1,973,493", "$265,723")
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_2025_26_numbering_extracts_and_replaces(self) -> None:
        # 2025-26 ids start one lower: Federal need-based is H.105, work-study
        # H.111, state and other H.112.
        markdown = "| Question | Value |\n|---|---|\n| H.112 | 735526 |\n"
        text = INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER
        self.assertEqual(h1(read("", markdown, "2025-26"))["H.112"], "735526")
        values = h1(read(text, markdown, "2025-26"))
        self.assertEqual(values["H.105"], "1973493")
        self.assertEqual(values["H.111"], "735526")
        self.assertNotIn("H.112", values)
        self.assertEqual(values["H.127"], "0")  # Athletic Awards, non-need-based

    def test_a_lone_amount_the_column_reader_refuses_does_not_come_back_from_the_legacy_reader(self) -> None:
        # Instructions that do not name H2 let the older reader reach the table;
        # it would put Parent Loans' far-right non-need-based amount in the
        # need-based field. The column reader does not place it; only the
        # markdown's own value, if any, may stand, and not twice.
        instructions = INSTRUCTIONS.replace("items H1, H2, H2A, and H6", "the items below")
        far = " " * 38 + "Parent Loans"
        far = far.ljust(170 - len("$3,104,361")) + "$3,104,361\n"
        rows = TRINITY_ROWS.replace(line("Parent Loans", "", "$3,104,361"), far).replace(
            line("(excluding parent loans)"), line("(excluding PLUS)")
        )  # the older reader would take that label for the Parent Loans row
        empty = h1(read(instructions + HEADER + rows + AFTER))
        self.assertNotIn("H.115", empty)
        self.assertNotIn("H.126", empty)
        markdown = "| Question | Value |\n|---|---|\n| H.126 | 3104361 |\n"
        kept = h1(read(instructions + HEADER + rows + AFTER, markdown))
        self.assertEqual(kept["H.126"], "3104361")
        self.assertNotIn("H.115", kept)

    def test_a_trailing_continuation_line_is_not_a_row(self) -> None:
        # Federal Work-Study is blank; "Federal Work/Study captured above)"
        # wraps onto the line that carries State and other's amount.
        rows = TRINITY_ROWS.replace(
            line("Federal Work-Study", "$735,526")
            + line("State and other (e.g., institutional) work-")
            + line("study/employment (Note: excludes Federal")
            + line("Work/Study captured above)"),
            line("Federal Work-Study", "Not Applicable")
            + line("State and other (e.g., institutional) work-")
            + line("study/employment (Note:")
            + line("Federal Work/Study captured above)", "$2,309,770"),
        ).replace("$3,044,296", "$4,618,540")
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.113"], "2309770")  # State and other
        self.assertNotIn("H.112", values)  # not Federal Work-Study

    def test_a_row_name_before_which_are_reported_below_is_not_a_row(self) -> None:
        # The Institutional label wraps; its last line names Tuition Waivers
        # and carries the amounts.
        rows = TRINITY_ROWS.replace(
            line("gifts and tuition funded grants, awarded by", "$75,746,654", "$4,204,069")
            + line("the college, excluding athletic aid and tuition")
            + line("waivers (which are reported below)"),
            line("gifts and tuition funded grants, awarded by")
            + line("excluding athletic aid and tuition waivers (which are reported below)", "$75,746,654", "$4,204,069", at=5),
        )
        self.assertIn("(which are reported below)", rows)
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.108"], "75746654")
        self.assertEqual(values["H.116"], "320758")  # Tuition Waivers keeps its own row

    def test_columns_that_move_with_the_page_are_not_pooled(self) -> None:
        # Parent Loans sits at the foot of one page, in columns 105 and 125;
        # Tuition Waivers and Athletic Awards head the next, at 118 and 138.
        # Pooled, the lone Parent Loans amount at 125 would read as need-based.
        rows = TRINITY_ROWS.split(line("Parent Loans", "", "$3,104,361"))[0]
        rows += line("Parent Loans", "", "$3,104,361", ends=(105, 125))
        rows += "\n\n" + line("Common Data Set 2023-2024", at=10) + line("H. FINANCIAL AID", at=10)
        rows += line("Tuition Waivers", "$320,758", "$426,282", ends=(118, 138))
        rows += line("Athletic Awards", "$0", "$0", ends=(118, 138))
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.110"], "79257874")  # the table is accepted
        self.assertNotIn("H.115", values)
        self.assertNotIn("H.126", values)

    def test_a_page_without_a_text_layer_keeps_the_markdown_values_for_its_rows(self) -> None:
        # Only grants and self-help are in the text layer.
        rows = TRINITY_ROWS.split(line("Parent Loans", "", "$3,104,361"))[0]
        markdown = "| Question | Value |\n|---|---|\n| H.115 | 111 |\n| H.116 | 222 |\n| H.113 | 735526 |\n"
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER, markdown))
        self.assertEqual(values["H.110"], "79257874")
        self.assertEqual((values["H.115"], values["H.116"]), ("111", "222"))
        self.assertNotIn("H.113", values)  # a row the text layer has is replaced

    def test_a_number_in_a_label_does_not_set_a_sparse_blocks_median(self) -> None:
        # Parent Loans' label holds "2,500" and its row one real amount, so
        # the block's only two-amount row would put its median in the label.
        rows = TRINITY_ROWS.split(line("Parent Loans", "", "$3,104,361"))[0]
        rows += line("Parent Loans (2,500 families)", "", "$3,104,361")
        rows += line("Tuition Waivers", "$320,758")
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.110"], "79257874")
        self.assertNotIn("H.115", values)  # 2,500 is not a need-based amount
        self.assertEqual(values["H.126"], "3104361")

    def test_external_grants_row_named_with_not_awarded_by_on_one_line(self) -> None:
        rows = TRINITY_ROWS.replace(
            line("Scholarships/grants from external sources")
            + line("(e.g. Kiwanis, National Merit) not awarded by", "$1,396,004", "$751,916"),
            line("Scholarships/grants from external sources not awarded by", "$1,396,004", "$751,916"),
        )
        self.assertIn("external sources not awarded by", rows)
        self.assertEqual(h1(read(INSTRUCTIONS + HEADER + rows + AFTER))["H.109"], "1396004")

    def test_a_primary_label_that_ends_with_a_trailing_phrase_is_still_a_row(self) -> None:
        # Seen in two layouts: "State and other ... (Note: Excludes Federal
        # Work-Study captured above.)" on one line, with its amounts.
        label = "State and other work-study (Excludes Federal Work-Study captured above.)"
        rows = TRINITY_ROWS.replace(
            line("Federal Work-Study", "$735,526")
            + line("State and other (e.g., institutional) work-")
            + line("study/employment (Note: excludes Federal")
            + line("Work/Study captured above)"),
            line("Federal Work-Study", "Not Applicable") + line(label, "$2,309,770", "$0", at=0),
        ).replace("$3,044,296", "$4,618,540")
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.113"], "2309770")
        self.assertNotIn("H.112", values)

    def test_in_which_inside_a_primary_label_does_not_disqualify_it(self) -> None:
        rows = TRINITY_ROWS.replace(
            line("Federal Work-Study", "$735,526"), line("Federal Work-Study, the amount in which", "$735,526")
        )
        self.assertEqual(h1(read(INSTRUCTIONS + HEADER + rows + AFTER))["H.112"], "735526")

    def test_the_older_readers_values_do_not_stand_for_rows_the_text_layer_lacks(self) -> None:
        # The text layer ends at Total Self-Help. With no "H2" in the
        # instructions the older reader takes the label "(excluding parent
        # loans)" for the Parent Loans row and reads work-study into it.
        instructions = INSTRUCTIONS.replace("items H1, H2, H2A, and H6", "the items below")
        rows = TRINITY_ROWS.split(line("Parent Loans", "", "$3,104,361"))[0]
        self.assertEqual(h1(read(instructions + HEADER + rows + AFTER)).get("H.110"), "79257874")
        self.assertNotIn("H.115", h1(read(instructions + HEADER + rows + AFTER)))

    def test_rows_without_their_total_are_refused_with_the_missing_block_rule_satisfied(self) -> None:
        # Total Self-Help prints its need-based amount only: the non-need-based
        # loans have no total. Grants and self-help are both present.
        rows = TRINITY_ROWS.replace(line("Total Self-Help", "$3,044,296", "$7,214,427", at=70), line("Total Self-Help", "$3,044,296", at=70))
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_a_missing_grants_block_refuses_the_reading(self) -> None:
        rows = TRINITY_ROWS[TRINITY_ROWS.index(line("Student loans from all sources", "$2,308,770", "$7,214,427")) :]
        self.assertEqual(_h_layout_h1_rows_by_column(HEADER + rows), {})

    def test_a_markdown_value_the_text_placed_in_the_rows_other_field_is_not_kept(self) -> None:
        # Parent Loans prints a non-need-based amount only. The markdown put it
        # in the need-based field; the row prints the number, but the text
        # reading has taken it for H.126.
        markdown = "| Question | Value |\n|---|---|\n| H.115 | 3104361 |\n"
        values = h1(read(INSTRUCTIONS + HEADER + TRINITY_ROWS + AFTER, markdown))
        self.assertEqual(values["H.126"], "3104361")
        self.assertNotIn("H.115", values)

    def test_every_h1_id_of_a_row_the_text_has_is_cleared_in_the_documents_own_numbering(self) -> None:
        # 2023-24 ids run to H.128 and H.105 is the "Both FM and IM" box. A
        # stale H.128 goes with its row; H.105 is not an H1 amount.
        rows = TRINITY_ROWS.replace(line("Athletic Awards", "$0", "$0"), line("Athletic Awards", "$5,000"))
        markdown = "| Question | Value |\n|---|---|\n| H.105 | X |\n| H.128 | 999 |\n"
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER, markdown))
        self.assertEqual(values["H.117"], "5000")
        self.assertEqual(values["H.105"], "X")
        self.assertNotIn("H.128", values)

    def test_row_names_in_the_instructions_do_not_claim_rows_the_table_lacks(self) -> None:
        instructions = INSTRUCTIONS + "Athletic awards are optional.\n"
        rows = TRINITY_ROWS.split(line("Parent Loans", "", "$3,104,361"))[0]
        markdown = "| Question | Value |\n|---|---|\n| H.117 | 555 |\n"
        self.assertEqual(h1(read(instructions + HEADER + rows + AFTER, markdown))["H.117"], "555")

    def test_each_block_is_placed_against_its_own_columns(self) -> None:
        # The last block sits at 118 and 138, the others at 110 and 140. A lone
        # Parent Loans amount at 120 is 2 columns from its block's need-based
        # column and 10 from the table's.
        rows = TRINITY_ROWS.split(line("Parent Loans", "", "$3,104,361"))[0]
        rows += line("Parent Loans", "$3,000", ends=(120, 138))
        rows += line("Tuition Waivers", "$320,758", "$426,282", ends=(118, 138))
        rows += line("Athletic Awards", "$0", "$0", ends=(118, 138))
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.110"], "79257874")
        self.assertEqual(values["H.115"], "3000")

    def test_a_summed_row_amount_between_the_columns_goes_to_the_nearer(self) -> None:
        # Detroit Mercy: Federal's lone amount ends 14 columns from the
        # need-based column and 16 from the non-need-based one.
        rows = TRINITY_ROWS.replace(
            line("Federal", "$1,973,493", "$265,723"), line("Federal", "$1,973,493", ends=(124, 124))
        ).replace("$5,221,708", "$4,955,985")
        values = h1(read(INSTRUCTIONS + HEADER + rows + AFTER))
        self.assertEqual(values["H.106"], "1973493")

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
