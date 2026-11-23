"""2023-24 and 2024-25 documents: policy and date tables keep the older
forms' numbers (issue #421)."""
import unittest

from tier4_cleaner import (
    _OLDER_FORM_DATE,
    _OLDER_FORM_ROTC_PLACE,
    _OLDER_FORM_SAME_VALUE,
    _claims_in_older_form,
    _get_schema,
    clean,
)


def _claims(**values):
    return {qn.replace("_", "."): {"value": v, "source": "tier4_cleaner"} for qn, v in values.items()}


def _values(claims):
    return {qn: rec["value"] for qn, rec in claims.items()}


class OlderFormNumberingTests(unittest.TestCase):
    def test_every_mapped_field_exists_in_the_schema_it_names(self):
        reference = {f["question_number"]: f for f in _get_schema("2025-26").fields}
        for year in ("2023-24", "2024-25"):
            own = {f["question_number"]: f for f in _get_schema(year).fields}
            for source, target in _OLDER_FORM_SAME_VALUE.items():
                self.assertIn(source, reference, source)
                self.assertIn(target, own, f"{source} -> {target} ({year})")
            for target, (month, day) in _OLDER_FORM_DATE.items():
                self.assertEqual(own[target]["value_type"] in ("MM-DD", "YN"), True, target)
                self.assertEqual(reference[month]["value_type"], "MM", month)
                self.assertEqual(reference[day]["value_type"], "DD", day)
            for source, places in _OLDER_FORM_ROTC_PLACE.items():
                self.assertIn(source, reference)
                self.assertEqual([own[qn]["question"] for qn in places], ["On Campus", "At Cooperating Institution"])

    def test_same_question_keeps_its_label_across_the_move(self):
        # The entries that are not listed here are rewordings checked by hand
        # (Males/Men, "Specify:" under "Other (specify):", and so on).
        reference = {f["question_number"]: f for f in _get_schema("2025-26").fields}
        own = {f["question_number"]: f for f in _get_schema("2024-25").fields}
        for source, target in {
            "C.1305": "C.1307", "C.1604": "C.1603", "C.1607": "C.1605", "C.1704": "C.1702",
            "C.1705": "C.1703", "C.1707": "C.1704", "C.1711": "C.1707", "C.2206": "C.2204",
            "D.2201": "D.2202",
            "G.602": "G.603", "G.603": "G.604", "G.604": "G.605", "G.605": "G.606",
            "H.701": "H.7101", "H.907": "H.903", "H.1103": "H.1102",
        }.items():
            self.assertEqual(_OLDER_FORM_SAME_VALUE[source], target)
            self.assertEqual(reference[source]["question"], own[target]["question"], source)

    def test_month_and_day_become_one_date(self):
        schema = _get_schema("2024-25")
        out = _values(_claims_in_older_form(
            _claims(H_901="X", H_902="3", H_903="02", H_907="X", H_1101="05", H_1102="1", H_1103="2"), schema,
        ))
        # H.901 is the priority date itself there; "X" (a date is given) has no field.
        self.assertEqual(out, {"H.901": "3/2", "H.903": "X", "H.1101": "5/1", "H.1102": "2"})
        # A month with no day is not a date.
        self.assertEqual(_values(_claims_in_older_form(_claims(C_1402="11"), schema)), {})
        self.assertEqual(
            _values(_claims_in_older_form(_claims(C_1402="11", C_1403="30", C_1404="1", C_1405="15"), schema)),
            {"C.1402": "11/30", "C.1403": "1/15"},
        )

    def test_transfer_dates(self):
        schema = _get_schema("2023-24")
        out = _values(_claims_in_older_form(
            _claims(D_201="100", D_909="3", D_910="1", D_917="5", D_918="15", D_933="X", D_935="X",
                    D_913="15", D_914="30"),
            schema,
        ))
        self.assertEqual(out, {
            "D.201": "100",                     # D2 is numbered where it is read
            "D.905": "3/1", "D.909": "5/15",    # fall closing, fall notification
            "D.917": "X", "D.919": "X",         # rolling: fall, spring
        })                                      # "15/30" is not a date and is dropped

    def test_transfer_counts_are_numbered_by_the_documents_form(self):
        text = (
            "D. TRANSFER ADMISSION\n"
            "D2 Provide the number of students who applied, were admitted, and enrolled as degree-seeking\n"
            "                    Applicants   Admitted Applicants   Enrolled Applicants\n"
            "Men                 100          60                    30\n"
            "Women               120          70                    40\n"
            "Another Gender      3            1                     1\n"
            "Unknown             7            2                     0\n"
            "Total               230          133                   71\n"
            "D3-D11\n"
        )
        def d2(year):
            return {k: v["value"] for k, v in clean(text, canonical_year=year).items() if k.startswith("D.2")}
        self.assertEqual(d2("2024-25"), {
            "D.201": "100", "D.206": "60", "D.211": "30", "D.202": "120", "D.207": "70", "D.212": "40",
            "D.203": "3", "D.208": "1", "D.213": "1", "D.204": "7", "D.209": "2", "D.214": "0",
            "D.205": "230", "D.210": "133", "D.215": "71",
        })
        # 2023-24 has no "Unknown" row.
        self.assertEqual(sorted(set(d2("2024-25")) - set(d2("2023-24"))), ["D.204", "D.209", "D.214"])
        # 2025-26: four rows per column, numbered as before.
        self.assertEqual(d2("2025-26")["D.204"], "230")
        self.assertEqual(d2("2025-26")["D.212"], "71")

        table = (
            "## D2. Transfer applicants\n\n"
            "| Transfer | Men | Women | Another Gender | Unknown | Total |\n"
            "|---|---|---|---|---|---|\n"
            "| Total applicants | 100 | 120 | 3 | 7 | 230 |\n"
            "| Total admitted | 60 | 70 | 1 | 2 | 133 |\n"
            "| Total enrolled | 30 | 40 | 1 | 0 | 71 |\n"
        )
        got = {k: v["value"] for k, v in clean(table, canonical_year="2024-25").items() if k.startswith("D.2")}
        self.assertEqual(got.get("D.202"), "120")   # the Women column is its own column
        self.assertEqual(got.get("D.203"), "3")
        self.assertEqual(got.get("D.204"), "7")
        self.assertEqual(got.get("D.215"), "71")

    def test_boxes_that_became_other_kinds_of_field(self):
        schema = _get_schema("2024-25")
        out = _values(_claims_in_older_form(
            _claims(F_301="At cooperating institution", F_302="Hofstra University", F_306="On campus",
                    H_1004="X", H_1005="4", H_1006="1", E_119="X", E_120="3-2 Engineering", E_313="X",
                    H_701="X", H_703="X", H_704="State form", C_1712="X", B_2203="91.5", G_602="347"),
            schema,
        ))
        self.assertEqual(out, {
            "F.302": "X", "F.303": "Hofstra University", "F.308": "X",
            "H.1002": "Yes", "H.1003": "4/1",
            "E.119": "3-2 Engineering",       # the text; a bare "X" in E.313 has no field
            "H.7101": "X", "H.7103": "State form",
            "C.1708": "X", "B.2201": "91.5", "G.603": "347",
        })

    def test_other_tables_and_other_years_are_left_alone(self):
        claims = _claims(H_801="X", H_106="1000", C_2104="1/15", H_902="3", H_903="2")
        for year in ("2025-26", "2026-27"):
            self.assertIs(_claims_in_older_form(claims, _get_schema(year)), claims)
        out = _values(_claims_in_older_form(claims, _get_schema("2024-25")))
        self.assertEqual(out, {"H.801": "X", "H.106": "1000", "C.2104": "1/15", "H.901": "3/2"})

    def test_retention_rate_lands_on_the_documents_own_field(self):
        markdown = "## B22. Retention Rates\n\nFor the cohort of all full-time bachelor's students: 91.5%\n\n## C. ADMISSION\n"
        older = clean(markdown, canonical_year="2024-25")
        self.assertEqual(older["B.2201"]["value"], "91.5")
        self.assertNotIn("B.2203", older)
        self.assertEqual(clean(markdown, canonical_year="2025-26")["B.2203"]["value"], "91.5")


if __name__ == "__main__":
    unittest.main()
