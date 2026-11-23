"""Tables the converter gives an extra leading column: H1 with a group-name
column, and I1/H2 with "Letter" merged into the description (issue #428)."""
import unittest

from tier4_cleaner import (
    _h1_amounts_add_up,
    _parse_markdown_tables,
    _split_letter_description_column,
    _strip_group_label_column,
    clean,
)

_TITLE = "H1. Aid Awarded to Enrolled Undergraduates"
_INSTITUTIONAL = (
    "Instititutional - Endowed scholarships, annual gifts and tuition funded grants, awarded by the "
    "college, excluding athletic aid and tuition waivers (which are reported below)"
)


def _h1(rows):
    lines = [
        f"| {_TITLE} | {_TITLE} | Need-Based (Include non-need based aid use to meet need). | Non-Need-Based |",
        "|---|---|---|---|",
    ]
    lines += [f"| {group} | {label} | {need} | {non_need} |" for group, label, need, non_need in rows]
    # The form's own preamble names H2 before the table, as real files do.
    return (
        "## H1. Aid Awarded to Enrolled Undergraduates\n\n"
        "Indicate the academic year for which data are reported for items H1, H2, H2A, and H6 below.\n\n"
        + "\n".join(lines) + "\n"
    )


_GOOD = [
    ("", "Federal", "$1,828,734.00", "$153.00"),
    ("Scholarships / Grants", "State - all states, not only the state in which your institution is located",
     "$3,501,981.00", "$349,487.00"),
    ("Scholarships / Grants", _INSTITUTIONAL, "$16,342,192.00", "$6,178,149.00"),
    ("Scholarships / Grants", "Scholarships/grants from external sources (e.g. Kiwanis, National Merit) not awarded by the college",
     "$301,556.00", "$376,057.00"),
    ("Scholarships / Grants", "Total Scholarships/Grants", "$21,974,463.00", "$6,903,846.00"),
    ("Self Help", "Student loans from all sources (excluding parent loans)", "$1,154,390.00", "$1,572,109.00"),
    ("Self Help", "Federal Work-Study", "$407,361.00", ""),
    ("MISC.", "Tuition Waivers", "$115,449.00", "$193,901.00"),
]


def _h(values):
    return {k: v["value"] for k, v in values.items() if k.startswith("H.1") and len(k) == 5}


class GroupColumnTableTests(unittest.TestCase):
    def test_h1_with_a_group_column_is_read_when_it_adds_up(self):
        got = _h(clean(_h1(_GOOD), canonical_year="2025-26"))
        self.assertEqual(got["H.105"], "1828734.00")      # Federal, need-based
        self.assertEqual(got["H.107"], "16342192.00")     # Institutional, under the misspelled label
        self.assertEqual(got["H.109"], "21974463.00")     # Total Scholarships/Grants
        self.assertEqual(got["H.119"], "6178149.00")
        # The real tuition-waivers row, not the Institutional one that mentions waivers.
        self.assertEqual(got["H.115"], "115449.00")
        # The same table under the 2023-24 form's numbering: every row one higher.
        older = _h(clean(_h1(_GOOD), canonical_year="2023-24"))
        self.assertEqual(older["H.108"], "16342192.00")
        self.assertEqual(older["H.116"], "115449.00")

    def test_h1_with_a_group_column_is_left_alone_when_it_does_not_add_up(self):
        # The converter merged the External row into the Total row: External's
        # amount now sits on "Total Scholarships/Grants".
        merged = _GOOD[:3] + [
            ("", "Scholarships/grants from external sources Total Scholarships/Grants", "$301,556.00", "$376,057.00"),
        ] + _GOOD[5:]
        self.assertEqual(_h(clean(_h1(merged), canonical_year="2025-26")), {})
        # A row with an amount pulled into its label is skipped; the rest still adds up.
        shifted = _GOOD[:7] + [("MISC.", "Tuition Waivers $67,836", "$24,054", "$3,388,810")]
        got = _h(clean(_h1(shifted), canonical_year="2025-26"))
        self.assertEqual(got["H.109"], "21974463.00")
        self.assertNotIn("H.115", got)

    def test_arithmetic_gate(self):
        def claims(**kw):
            return {k.replace("_", "."): {"value": v} for k, v in kw.items()}
        self.assertTrue(_h1_amounts_add_up(claims(H_105="10", H_106="20", H_107="30", H_108="40", H_109="100")))
        # A blank row is zero.
        self.assertTrue(_h1_amounts_add_up(claims(H_105="10", H_107="90", H_109="100")))
        # A row unread: the parts fall short.
        self.assertFalse(_h1_amounts_add_up(claims(H_105="10", H_106="20", H_109="100")))
        # One block right and one wrong is wrong.
        self.assertFalse(_h1_amounts_add_up(claims(H_105="10", H_107="90", H_109="100",
                                                   H_110="5", H_111="5", H_113="50")))
        # Nothing that can be checked is not a pass.
        self.assertFalse(_h1_amounts_add_up(claims(H_105="10", H_114="7")))
        self.assertFalse(_h1_amounts_add_up({}))

    def test_group_column_is_dropped_only_from_a_table_that_has_one(self):
        lines = [l for l in _h1(_GOOD).splitlines() if l.startswith("|")]
        stripped, did = _strip_group_label_column(lines)
        self.assertTrue(did)
        self.assertTrue(stripped[2].startswith("| Federal |"))
        # An ordinary H1 table: first two header cells differ.
        ordinary = [
            "| Aid | Need-based | Non-need-based |", "|---|---|---|",
            "| Federal | $1 | $2 |", "| State all states | $1 | $2 |", "| Institutional | $1 | $2 |",
            "| Total Scholarships/Grants | $3 | $6 |", "| Parent Loans | $1 | $2 |",
        ]
        self.assertEqual(_strip_group_label_column(ordinary), (ordinary, False))
        self.assertFalse(_parse_markdown_tables("\n".join(ordinary))[0]["group_column_stripped"])
        # A first column of numbers is data, not group names.
        numbered = [
            "| Year | Year | Men | Women |", "|---|---|---|---|",
            "| 2019 | Applied | 10 | 12 |", "| 2020 | Applied | 11 | 13 |", "| 2021 | Applied | 12 | 14 |",
            "| 2022 | Applied | 13 | 15 |",
        ]
        self.assertEqual(_strip_group_label_column(numbered), (numbered, False))

    def test_letter_merged_into_the_description_is_split(self):
        lines = [
            "| Letter Description | Full- time | Part- time | Total |", "|---|---|---|---|",
            "| A Total number of instructional faculty | 1452 | 537 | 1989 |",
            "| B Total number who are members of minority groups | 300 | 80 | 380 |",
            "| C Total number who are women | 600 | 250 | 850 |",
            "| D Total number who are men | 852 | 287 | 1139 |",
            "| E Total number who are nonresidents (international) | 40 | 5 | 45 |",
        ]
        split = _split_letter_description_column(lines)
        self.assertEqual(split[0], "| Letter | Description | Full- time | Part- time | Total |")
        self.assertEqual(split[2], "| A | Total number of instructional faculty | 1452 | 537 | 1989 |")
        # Fewer than five lettered rows, or no "Letter ..." header: left as it is.
        self.assertEqual(_split_letter_description_column(lines[:5]), lines[:5])
        other = ["| Description | Full- time |", "|---|---|"] + lines[2:]
        self.assertEqual(_split_letter_description_column(other), other)


if __name__ == "__main__":
    unittest.main()
