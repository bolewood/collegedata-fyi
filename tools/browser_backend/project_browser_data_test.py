import unittest
import hashlib
from decimal import Decimal

from tools.browser_backend.project_browser_data import (
    DIRECT_METRIC_ALIASES,
    DIRECT_METRIC_DEFINITIONS,
    FieldDefinition,
    build_projection_rows,
    metric_field_ids_for_year,
    metric_alias_rows,
    parse_field_value,
    project_document_id,
    replace_projection_rows,
    select_extraction_result,
)


def defs():
    return {
        "2024-25": {
            "C.101": FieldDefinition("2024-25", "C.101", "Men applied", "Admission", "Applications", "Number"),
            "C.102": FieldDefinition("2024-25", "C.102", "Women applied", "Admission", "Applications", "Number"),
            "C.103": FieldDefinition("2024-25", "C.103", "Another gender applied", "Admission", "Applications", "Number"),
            "C.104": FieldDefinition("2024-25", "C.104", "Unknown gender applied", "Admission", "Applications", "Number"),
            "C.105": FieldDefinition("2024-25", "C.105", "Men admitted", "Admission", "Applications", "Number"),
            "C.106": FieldDefinition("2024-25", "C.106", "Women admitted", "Admission", "Applications", "Number"),
            "C.107": FieldDefinition("2024-25", "C.107", "Another gender admitted", "Admission", "Applications", "Number"),
            "C.108": FieldDefinition("2024-25", "C.108", "Unknown gender admitted", "Admission", "Applications", "Number"),
            "C.109": FieldDefinition("2024-25", "C.109", "Men full-time enrolled", "Admission", "Applications", "Number"),
            "C.110": FieldDefinition("2024-25", "C.110", "Men part-time enrolled", "Admission", "Applications", "Number"),
            "C.111": FieldDefinition("2024-25", "C.111", "Women full-time enrolled", "Admission", "Applications", "Number"),
            "C.112": FieldDefinition("2024-25", "C.112", "Women part-time enrolled", "Admission", "Applications", "Number"),
            "C.113": FieldDefinition("2024-25", "C.113", "Another gender full-time enrolled", "Admission", "Applications", "Number"),
            "C.114": FieldDefinition("2024-25", "C.114", "Another gender part-time enrolled", "Admission", "Applications", "Number"),
            "C.115": FieldDefinition("2024-25", "C.115", "Unknown gender full-time enrolled", "Admission", "Applications", "Number"),
            "C.116": FieldDefinition("2024-25", "C.116", "Unknown gender part-time enrolled", "Admission", "Applications", "Number"),
            "C.117": FieldDefinition("2024-25", "C.117", "Total applied", "Admission", "Applications", "Number"),
            "C.118": FieldDefinition("2024-25", "C.118", "Total admitted", "Admission", "Applications", "Number"),
            "C.119": FieldDefinition("2024-25", "C.119", "Total enrolled", "Admission", "Applications", "Number"),
            "C.201": FieldDefinition("2024-25", "C.201", "Wait list policy", "Admission", "Wait List", "YN"),
            "C.202": FieldDefinition("2024-25", "C.202", "Wait list offered", "Admission", "Wait List", "Number"),
            "C.203": FieldDefinition("2024-25", "C.203", "Wait list accepted", "Admission", "Wait List", "Number"),
            "C.204": FieldDefinition("2024-25", "C.204", "Wait list admitted", "Admission", "Wait List", "Number"),
            "C.2101": FieldDefinition("2024-25", "C.2101", "ED offered", "Admission", "Early Decision", "YN"),
            "C.2104": FieldDefinition("2024-25", "C.2104", "Other ED closing date", "Admission", "Early Decision", "MM-DD"),
            "C.2106": FieldDefinition("2024-25", "C.2106", "ED applicants", "Admission", "Early Decision", "Number"),
            "C.2107": FieldDefinition("2024-25", "C.2107", "ED admitted", "Admission", "Early Decision", "Number"),
            "C.2201": FieldDefinition("2024-25", "C.2201", "EA offered", "Admission", "Early Action", "YN"),
            "C.2206": FieldDefinition("2024-25", "C.2206", "EA restrictive", "Admission", "Early Action", "YN"),
            "C.711": FieldDefinition("2024-25", "C.711", "First generation", "Admission", "Factors", "Text"),
            "C.712": FieldDefinition("2024-25", "C.712", "Legacy", "Admission", "Factors", "Text"),
            "C.713": FieldDefinition("2024-25", "C.713", "Geography", "Admission", "Factors", "Text"),
            "C.714": FieldDefinition("2024-25", "C.714", "State residency", "Admission", "Factors", "Text"),
            "C.718": FieldDefinition("2024-25", "C.718", "Interest", "Admission", "Factors", "Text"),
            "C.1302": FieldDefinition("2024-25", "C.1302", "Application fee", "Admission", "Application", "Number"),
            "C.1305": FieldDefinition("2024-25", "C.1305", "Fee waiver", "Admission", "Application", "YN"),
            "C.901": FieldDefinition("2024-25", "C.901", "Submitting SAT Scores", "Admission", "Profile", "Whole Number or Round to Nearest Tenths"),
        },
        "2025-26": {
            "C.101": FieldDefinition("2025-26", "C.101", "Males applied", "Admission", "Applications", "Number"),
            "C.102": FieldDefinition("2025-26", "C.102", "Females applied", "Admission", "Applications", "Number"),
            "C.103": FieldDefinition("2025-26", "C.103", "Unknown sex applied", "Admission", "Applications", "Number"),
            "C.104": FieldDefinition("2025-26", "C.104", "Males admitted", "Admission", "Applications", "Number"),
            "C.105": FieldDefinition("2025-26", "C.105", "Females admitted", "Admission", "Applications", "Number"),
            "C.106": FieldDefinition("2025-26", "C.106", "Unknown sex admitted", "Admission", "Applications", "Number"),
            "C.107": FieldDefinition("2025-26", "C.107", "Males enrolled", "Admission", "Applications", "Number"),
            "C.108": FieldDefinition("2025-26", "C.108", "Females enrolled", "Admission", "Applications", "Number"),
            "C.109": FieldDefinition("2025-26", "C.109", "Unknown sex enrolled", "Admission", "Applications", "Number"),
            "C.110": FieldDefinition("2025-26", "C.110", "Males full-time enrolled", "Admission", "Applications", "Number"),
            "C.111": FieldDefinition("2025-26", "C.111", "Males part-time enrolled", "Admission", "Applications", "Number"),
            "C.112": FieldDefinition("2025-26", "C.112", "Females full-time enrolled", "Admission", "Applications", "Number"),
            "C.113": FieldDefinition("2025-26", "C.113", "Females part-time enrolled", "Admission", "Applications", "Number"),
            "C.114": FieldDefinition("2025-26", "C.114", "Unknown sex full-time enrolled", "Admission", "Applications", "Number"),
            "C.115": FieldDefinition("2025-26", "C.115", "Unknown sex part-time enrolled", "Admission", "Applications", "Number"),
            "C.116": FieldDefinition("2025-26", "C.116", "Applied", "Admission", "Applications", "Number"),
            "C.117": FieldDefinition("2025-26", "C.117", "Admitted", "Admission", "Applications", "Number"),
            "C.118": FieldDefinition("2025-26", "C.118", "Enrolled", "Admission", "Applications", "Number"),
            "C.119": FieldDefinition("2025-26", "C.119", "Applied in-state", "Admission", "Applications", "Number"),
            "C.120": FieldDefinition("2025-26", "C.120", "Admitted in-state", "Admission", "Applications", "Number"),
            "C.121": FieldDefinition("2025-26", "C.121", "Enrolled in-state", "Admission", "Applications", "Number"),
            "C.122": FieldDefinition("2025-26", "C.122", "Applied out-of-state", "Admission", "Applications", "Number"),
            "C.123": FieldDefinition("2025-26", "C.123", "Admitted out-of-state", "Admission", "Applications", "Number"),
            "C.124": FieldDefinition("2025-26", "C.124", "Enrolled out-of-state", "Admission", "Applications", "Number"),
            "C.125": FieldDefinition("2025-26", "C.125", "Applied international", "Admission", "Applications", "Number"),
            "C.126": FieldDefinition("2025-26", "C.126", "Admitted international", "Admission", "Applications", "Number"),
            "C.127": FieldDefinition("2025-26", "C.127", "Enrolled international", "Admission", "Applications", "Number"),
            "C.128": FieldDefinition("2025-26", "C.128", "Applied unknown residency", "Admission", "Applications", "Number"),
            "C.129": FieldDefinition("2025-26", "C.129", "Admitted unknown residency", "Admission", "Applications", "Number"),
            "C.130": FieldDefinition("2025-26", "C.130", "Enrolled unknown residency", "Admission", "Applications", "Number"),
            "C.201": FieldDefinition("2025-26", "C.201", "Wait list policy", "Admission", "Wait List", "YesNo"),
            "C.202": FieldDefinition("2025-26", "C.202", "Wait list offered", "Admission", "Wait List", "Number"),
            "C.203": FieldDefinition("2025-26", "C.203", "Wait list accepted", "Admission", "Wait List", "Number"),
            "C.204": FieldDefinition("2025-26", "C.204", "Wait list admitted", "Admission", "Wait List", "Number"),
            "C.2101": FieldDefinition("2025-26", "C.2101", "ED offered", "Admission", "Early Decision", "YesNo"),
            "C.2106": FieldDefinition("2025-26", "C.2106", "Other ED closing month", "Admission", "Early Decision", "MM"),
            "C.2110": FieldDefinition("2025-26", "C.2110", "ED applicants", "Admission", "Early Decision", "Number"),
            "C.2111": FieldDefinition("2025-26", "C.2111", "ED admitted", "Admission", "Early Decision", "Number"),
            "C.2201": FieldDefinition("2025-26", "C.2201", "EA offered", "Admission", "Early Action", "YesNo"),
            "C.2206": FieldDefinition("2025-26", "C.2206", "EA restrictive", "Admission", "Early Action", "YesNo"),
            "C.711": FieldDefinition("2025-26", "C.711", "First generation", "Admission", "Factors", "Text"),
            "C.712": FieldDefinition("2025-26", "C.712", "Legacy", "Admission", "Factors", "Text"),
            "C.713": FieldDefinition("2025-26", "C.713", "Geography", "Admission", "Factors", "Text"),
            "C.714": FieldDefinition("2025-26", "C.714", "State residency", "Admission", "Factors", "Text"),
            "C.718": FieldDefinition("2025-26", "C.718", "Interest", "Admission", "Factors", "Text"),
            "C.1302": FieldDefinition("2025-26", "C.1302", "Application fee", "Admission", "Application", "Number"),
            "C.1305": FieldDefinition("2025-26", "C.1305", "Fee waiver", "Admission", "Application", "YesNo"),
            "C.901": FieldDefinition("2025-26", "C.901", "Percent Submitting SAT Scores", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.902": FieldDefinition("2025-26", "C.902", "Percent Submitting ACT Scores", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.905": FieldDefinition("2025-26", "C.905", "SAT Composite: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.906": FieldDefinition("2025-26", "C.906", "SAT Composite: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.907": FieldDefinition("2025-26", "C.907", "SAT Composite: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.908": FieldDefinition("2025-26", "C.908", "SAT EBRW: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.909": FieldDefinition("2025-26", "C.909", "SAT EBRW: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.910": FieldDefinition("2025-26", "C.910", "SAT EBRW: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.911": FieldDefinition("2025-26", "C.911", "SAT Math: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.912": FieldDefinition("2025-26", "C.912", "SAT Math: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.913": FieldDefinition("2025-26", "C.913", "SAT Math: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.914": FieldDefinition("2025-26", "C.914", "ACT Composite: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.915": FieldDefinition("2025-26", "C.915", "ACT Composite: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.916": FieldDefinition("2025-26", "C.916", "ACT Composite: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "B.2203": FieldDefinition("2025-26", "B.2203", "Retention percentage", "Enrollment", "Retention", "Whole Number or Round to Nearest Tenth"),
        }
    }


def doc(**overrides):
    base = {
        "document_id": "00000000-0000-0000-0000-000000000001",
        "school_id": "example",
        "school_name": "Example College",
        "sub_institutional": None,
        "ipeds_id": "123456",
        "canonical_year": "2024-25",
        "source_format": "pdf_fillable",
        "data_quality_flag": None,
    }
    base.update(overrides)
    return base


def artifact(
    producer="tier2_acroform",
    values=None,
    kind="canonical",
    created_at="2026-01-01T00:00:00Z",
    producer_version="0.1.0",
    notes_extra=None,
    schema_version="2025-26",
):
    notes = {"values": values or {}}
    if notes_extra:
        notes.update(notes_extra)
    return {
        "id": f"{producer}-{kind}",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "kind": kind,
        "producer": producer,
        "producer_version": producer_version,
        "schema_version": schema_version,
        "created_at": created_at,
        "notes": notes,
    }


class FakeResult:
    def __init__(self, data=None):
        self.data = data


class FakeQuery:
    def __init__(self, data=None):
        self.data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return FakeResult(self.data)


class FakeRpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return FakeQuery()


class FakeTableClient:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, name):
        return FakeQuery(self.table_data.get(name, []))


class BrowserProjectionTests(unittest.TestCase):
    def test_direct_aliases_exclude_derived_metrics(self):
        aliases = metric_alias_rows(defs())
        names = {row["canonical_metric"] for row in aliases}
        self.assertEqual(names, set(DIRECT_METRIC_ALIASES))
        self.assertNotIn("acceptance_rate", names)
        self.assertNotIn("yield_rate", names)
        self.assertIn("sat_composite_p50", names)
        self.assertIn("act_composite_p75", names)

        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.116": {"value": "100"},
                    "C.117": {"value": "20"},
                    "C.118": {"value": "10"},
                })
            ],
            defs(),
        )
        field_metrics = {row["canonical_metric"] for row in fields if row["canonical_metric"]}
        self.assertEqual(field_metrics, {"applied", "admitted", "first_year_enrolled"})
        self.assertEqual(browser["acceptance_rate"], "0.200000")
        self.assertEqual(browser["yield_rate"], "0.500000")

    def test_impossible_derived_rates_are_omitted_from_browser_row(self):
        _fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.116": {"value": "100"},
                    "C.117": {"value": "120"},
                    "C.118": {"value": "240"},
                })
            ],
            defs(),
        )

        # Admitted > applied and enrolled > admitted cannot both be true of
        # one funnel; the rows cannot say which side is wrong, so the browser
        # row publishes neither (issue #281).
        self.assertIsNone(browser["applied"])
        self.assertIsNone(browser["admitted"])
        self.assertIsNone(browser["enrolled_first_year"])
        self.assertIsNone(browser["acceptance_rate"])
        self.assertIsNone(browser["yield_rate"])

    def test_zero_admitted_or_enrolled_omits_derived_rates(self):
        _fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.116": {"value": "2477"},
                    "C.117": {"value": "0"},
                    "C.118": {"value": "836"},
                })
            ],
            defs(),
        )
        self.assertIsNone(browser["acceptance_rate"])
        self.assertIsNone(browser["yield_rate"])

    def test_2025_admissions_metrics_fall_back_to_gender_split_components(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(values={
                    "C.101": {"value": "22,819"},
                    "C.102": {"value": "27,445"},
                    "C.103": {"value": "0"},
                    "C.104": {"value": "1,189"},
                    "C.105": {"value": "1,198"},
                    "C.106": {"value": "0"},
                    "C.107": {"value": "799"},
                    "C.108": {"value": "834"},
                    "C.109": {"value": "0"},
                })
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 50264)
        self.assertEqual(browser["admitted"], 2387)
        self.assertEqual(browser["enrolled_first_year"], 1633)
        self.assertEqual(browser["acceptance_rate"], "0.047489")
        self.assertEqual(browser["yield_rate"], "0.684122")

    def test_2025_zero_total_fields_defer_to_positive_gender_components(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(values={
                    "C.101": {"value": "100"},
                    "C.102": {"value": "120"},
                    "C.104": {"value": "10"},
                    "C.105": {"value": "12"},
                    "C.116": {"value": "0"},
                    "C.117": {"value": "0"},
                })
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 220)
        self.assertEqual(browser["admitted"], 22)
        self.assertEqual(browser["acceptance_rate"], "0.100000")

    def test_2025_total_smaller_than_gender_component_uses_gender_sum(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(values={
                    "C.101": {"value": "2496"},
                    "C.104": {"value": "1424"},
                    "C.107": {"value": "264"},
                    "C.116": {"value": "911"},
                    "C.117": {"value": "657"},
                    "C.118": {"value": "185"},
                    "C.119": {"value": "741"},
                    "C.120": {"value": "519"},
                    "C.121": {"value": "56"},
                    "C.122": {"value": "844"},
                    "C.123": {"value": "248"},
                    "C.124": {"value": "23"},
                    "C.125": {"value": "2496"},
                    "C.126": {"value": "1424"},
                    "C.127": {"value": "264"},
                })
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 2496)
        self.assertEqual(browser["admitted"], 1424)
        self.assertEqual(browser["enrolled_first_year"], 264)
        self.assertEqual(browser["acceptance_rate"], "0.570513")
        self.assertEqual(browser["yield_rate"], "0.185393")

    def test_2025_residency_shift_fingerprint_uses_gender_sum(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(values={
                    "C.101": {"value": "5000"},
                    "C.102": {"value": "4958"},
                    "C.104": {"value": "2000"},
                    "C.105": {"value": "1900"},
                    "C.116": {"value": "8120"},
                    "C.117": {"value": "2500"},
                    "C.119": {"value": "1688"},
                    "C.120": {"value": "900"},
                    "C.122": {"value": "150"},
                    "C.123": {"value": "500"},
                    "C.125": {"value": "9958"},
                    "C.126": {"value": "3900"},
                })
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 9958)
        self.assertEqual(browser["admitted"], 3900)

    def test_2025_duplicate_gender_counts_do_not_replace_matching_total(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(values={
                    "C.101": {"value": "2070"},
                    "C.102": {"value": "2070"},
                    "C.104": {"value": "500"},
                    "C.105": {"value": "500"},
                    "C.116": {"value": "2070"},
                    "C.117": {"value": "500"},
                })
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 2070)
        self.assertEqual(browser["admitted"], 500)

    def test_sat_act_promoted_fields_project_to_browser_columns(self):
        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.901": {"value": "58%"},
                    "C.902": {"value": "31"},
                    "C.905": {"value": "1400"},
                    "C.906": {"value": "1450.0"},
                    "C.907": {"value": "1500"},
                    "C.914": {"value": "32"},
                    "C.915": {"value": "34"},
                    "C.916": {"value": "35"},
                })
            ],
            defs(),
        )
        metrics = {row["canonical_metric"]: row for row in fields if row["canonical_metric"]}
        self.assertEqual(metrics["sat_submit_rate"]["value_num"], "0.58")
        self.assertEqual(metrics["act_submit_rate"]["value_num"], "0.31")
        self.assertEqual(metrics["sat_composite_p50"]["value_num"], "1450.0")
        self.assertEqual(browser["sat_submit_rate"], "0.58")
        self.assertEqual(browser["act_submit_rate"], "0.31")
        self.assertEqual(browser["sat_composite_p25"], 1400)
        self.assertEqual(browser["sat_composite_p50"], 1450)
        self.assertEqual(browser["sat_composite_p75"], 1500)
        self.assertEqual(browser["act_composite_p25"], 32)
        self.assertEqual(browser["act_composite_p50"], 34)
        self.assertEqual(browser["act_composite_p75"], 35)

    def test_2024_admissions_metrics_derive_from_gender_split_fields(self):
        fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "10"},
                        "C.102": {"value": "20"},
                        "C.103": {"value": "3"},
                        "C.104": {"value": "2"},
                        "C.105": {"value": "5"},
                        "C.106": {"value": "10"},
                        "C.107": {"value": "1"},
                        "C.108": {"value": "1"},
                        "C.109": {"value": "2"},
                        "C.110": {"value": "1"},
                        "C.111": {"value": "4"},
                        "C.112": {"value": "1"},
                        "C.113": {"value": "1"},
                        "C.114": {"value": "0"},
                        "C.115": {"value": "1"},
                        "C.116": {"value": "0"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 35)
        self.assertEqual(browser["admitted"], 17)
        self.assertEqual(browser["enrolled_first_year"], 10)
        self.assertEqual(browser["acceptance_rate"], "0.485714")
        self.assertEqual(browser["yield_rate"], "0.588235")
        by_field = {row["field_id"]: row for row in fields}
        self.assertEqual(by_field["C.103"]["equivalence_kind"], "unmapped")
        self.assertIsNone(by_field["C.103"]["canonical_field_id"])

    def test_2024_admissions_derived_metrics_treat_missing_split_components_as_zero(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "10"},
                        "C.102": {"value": "20"},
                        "C.105": {"value": "5"},
                        "C.106": {"value": "10"},
                        "C.109": {"value": "2"},
                        "C.111": {"value": "4"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 30)
        self.assertEqual(browser["admitted"], 15)
        self.assertEqual(browser["enrolled_first_year"], 6)

    def test_2024_total_smaller_than_a_reported_component_uses_component_sum(self):
        # University of Akron 2024-25: gender rows 8,876 and 9,071 with a
        # misread total of 6,477 and two components missing.
        _fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "8876"},
                        "C.102": {"value": "9071"},
                        "C.117": {"value": "6477"},
                        "C.105": {"value": "4962"},
                        "C.106": {"value": "5736"},
                        "C.108": {"value": "21"},
                        "C.118": {"value": "921"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 17947)
        self.assertEqual(browser["admitted"], 10719)

    def _project(self, year, values):
        definitions = defs()
        for field_id, label in (
            ("H.201", "Full-time first-year students"),
            ("H.214", "All full-time undergraduates"),
            ("H.202", "First-year students who applied for aid"),
            ("H.401", "Graduating class size"),
            ("H.501", "Graduates who borrowed"),
            ("C.2106", "ED field 2106"),
            ("C.2107", "ED field 2107"),
            ("C.2110", "ED applicants"),
            ("C.2111", "ED admitted"),
        ):
            definitions[year].setdefault(
                field_id, FieldDefinition(year, field_id, label, "Section", "Subsection", "Number")
            )
        fields, browser = build_projection_rows(
            doc(canonical_year=year),
            [artifact(schema_version=year, values={k: {"value": v} for k, v in values.items()})],
            definitions,
        )
        return {row["field_id"]: row for row in fields}, browser

    def _project_with_hints(self, hints, values, year="2025-26"):
        definitions = defs()
        for field_id, hint in hints.items():
            definitions[year][field_id] = FieldDefinition(
                year, field_id, "A. Any loan program", "Financial Aid", "Aid", hint
            )
        fields, _browser = build_projection_rows(
            doc(canonical_year=year),
            [artifact(schema_version=year, values={k: {"value": v} for k, v in values.items()})],
            definitions,
        )
        return {row["field_id"]: row for row in fields}

    def test_dollar_format_hint_types_a_bare_number_as_currency(self):
        # Duke 2024-25 H.210 was stored as the text "76028" with no number.
        fields = self._project_with_hints(
            {"H.210": "Nearest $1", "H.211": "Nearest $1", "H.212": "Nearest $1"},
            {"H.210": "76028", "H.211": "$ 61,250", "H.212": "Nearest $1"},
        )
        self.assertEqual(fields["H.210"]["value_kind"], "currency")
        self.assertEqual(fields["H.210"]["value_num"], "76028")
        self.assertEqual(fields["H.210"]["value_status"], "reported")
        self.assertEqual(fields["H.211"]["value_num"], "61250")
        # The template's own format label is not an answer.
        self.assertEqual(fields["H.212"]["value_status"], "parse_error")
        self.assertIsNone(fields["H.212"]["value_num"])

    def test_percent_format_hint_stores_one_scale(self):
        # H.506 arrived as "56", "56%" and ".56" depending on the file.
        fields = self._project_with_hints(
            {"H.506": "Nearest 1%", "H.507": "Nearest 1%", "H.508": "Nearest 1%", "H.509": "Nearest 1%"},
            {"H.506": "56", "H.507": "56%", "H.508": ".56", "H.509": "0.56"},
        )
        for field_id in ("H.506", "H.507", "H.508", "H.509"):
            self.assertEqual(fields[field_id]["value_kind"], "percent")
            self.assertEqual(fields[field_id]["value_status"], "reported")
            self.assertEqual(Decimal(fields[field_id]["value_num"]), Decimal("0.56"))

    def test_average_award_in_the_millions_is_not_published(self):
        # Harvard 2025-26: H.605 held the H.606 total. Worcester State 2025-26:
        # H.210 held a column total.
        fields = self._project_with_hints(
            {"H.605": "Nearest $1", "H.606": "Nearest $1", "H.210": "Nearest $1", "H.211": "Nearest $1"},
            {"H.605": "66826244", "H.606": "66826244", "H.210": "14924610.5", "H.211": "83513"},
        )
        self.assertEqual(fields["H.605"]["value_status"], "parse_error")
        self.assertIsNone(fields["H.605"]["value_num"])
        self.assertEqual(fields["H.210"]["value_status"], "parse_error")
        # A total is allowed to be large, and a real average is kept.
        self.assertEqual(fields["H.606"]["value_status"], "reported")
        self.assertEqual(fields["H.211"]["value_num"], "83513")

    def test_hundredths_format_hint_is_a_number(self):
        fields = self._project_with_hints(
            {"C.1201": "Round to Nearest Hundredths", "C.1202": "Round to Nearest Hundredths"},
            {"C.1201": "3.85", "C.1202": "No minimum required"},
        )
        self.assertEqual(fields["C.1201"]["value_kind"], "number")
        self.assertEqual(fields["C.1201"]["value_num"], "3.85")
        self.assertEqual(fields["C.1202"]["value_status"], "parse_error")

    def test_ed_counts_read_from_a_date_are_not_published(self):
        # UNC 2025-26: a 3/15 date landed in the two Early Decision count cells.
        fields, browser = self._project(
            "2025-26", {"C.116": "76247", "C.117": "14000", "C.2110": "3", "C.2111": "15"}
        )
        for field_id in ("C.2110", "C.2111"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error")
            self.assertIsNone(fields[field_id]["value_num"])
        self.assertIsNone(browser["ed_applicants"])
        self.assertIsNone(browser["ed_admitted"])
        self.assertEqual(browser["applied"], 76247)

    def test_c1_total_row_funnel_that_cannot_be_true_is_not_published(self):
        # Salisbury 2024-25: applied total 299 beside 7,737 admitted.
        fields, browser = self._project(
            "2024-25",
            {"C.101": "3663", "C.102": "5182", "C.117": "299", "C.118": "7737", "C.119": "16"},
        )
        for field_id in ("C.117", "C.118"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error")
            self.assertIsNone(fields[field_id]["value_num"])
        # With admitted already blamed, a small enrolled count is not also
        # flagged for the 1% yield rule (it is the browser row that clears it).
        self.assertEqual(fields["C.119"]["value_status"], "reported")
        # The gender rows are consistent with each other and stay published.
        self.assertEqual(fields["C.101"]["value_status"], "reported")

    def test_c1_total_row_with_consistent_funnel_is_kept(self):
        # Lenoir-Rhyne 2024-25 after the extraction fix: 3661 / 3100 / 341.
        fields, browser = self._project(
            "2024-25",
            {"C.101": "1656", "C.102": "2005", "C.105": "1402", "C.106": "1698",
             "C.117": "3661", "C.118": "3100", "C.119": "341"},
        )
        for field_id in ("C.117", "C.118", "C.119"):
            self.assertEqual(fields[field_id]["value_status"], "reported")
        self.assertEqual(browser["applied"], 3661)
        self.assertEqual(browser["admitted"], 3100)

    def test_c1_zero_admitted_beside_enrolled_flags_only_the_zero(self):
        # Akron 2025-26: admitted total 0 beside 2,169 enrolled; the enrolled
        # count is the one the school filled in.
        fields, _browser = self._project(
            "2025-26", {"C.116": "0", "C.117": "0", "C.118": "2169"}
        )
        self.assertEqual(fields["C.117"]["value_status"], "parse_error")
        self.assertEqual(fields["C.118"]["value_status"], "reported")
        self.assertEqual(fields["C.118"]["value_num"], "2169")

    def test_c1_men_admitted_over_men_applied_is_not_published(self):
        # San Jose State 2024-25: the residency row landed in the gender rows.
        fields, _browser = self._project(
            "2024-25",
            {"C.101": "18545", "C.102": "18464", "C.105": "31419", "C.106": "29918", "C.103": "123"},
        )
        for field_id in ("C.101", "C.105", "C.102", "C.106"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error")
        self.assertEqual(fields["C.103"]["value_status"], "reported")

    def test_c1_men_and_women_rows_in_order_are_kept(self):
        # UNC 2025-26: 31,665 men applied, 5,305 admitted.
        fields, _browser = self._project(
            "2025-26",
            {"C.101": "31665", "C.102": "44582", "C.104": "5305", "C.105": "7446"},
        )
        for field_id in ("C.101", "C.102", "C.104", "C.105"):
            self.assertEqual(fields[field_id]["value_status"], "reported")

    def test_browser_funnel_admitted_over_applied_is_cleared(self):
        # San Jose State 2024-25 browser row: 37,132 applied, 62,266 admitted.
        _fields, browser = self._project(
            "2024-25",
            {"C.101": "18545", "C.102": "18464", "C.103": "123", "C.105": "31419",
             "C.106": "29918", "C.107": "929", "C.109": "2261", "C.111": "2140"},
        )
        self.assertIsNone(browser["applied"])
        self.assertIsNone(browser["admitted"])
        self.assertIsNone(browser["acceptance_rate"])
        self.assertEqual(browser["enrolled_first_year"], 4401)

    def test_browser_funnel_enrolled_over_admitted_is_cleared(self):
        # MIT 2024-25 (tier6_html): 29,278 enrolled beside 1,658 admitted.
        _fields, browser = self._project(
            "2025-26", {"C.116": "26791", "C.117": "1658", "C.118": "29278"}
        )
        self.assertEqual(browser["applied"], 26791)
        self.assertIsNone(browser["admitted"])
        self.assertIsNone(browser["enrolled_first_year"])

    def test_browser_funnel_zero_class_beside_thousands_of_admits(self):
        # UNC 2025-26: enrolled 0 beside 12,751 admitted.
        _fields, browser = self._project(
            "2025-26", {"C.116": "76247", "C.117": "12751", "C.118": "0"}
        )
        self.assertEqual(browser["admitted"], 12751)
        self.assertIsNone(browser["enrolled_first_year"])
        self.assertIsNone(browser["yield_rate"])

    def test_browser_funnel_real_low_yield_is_kept(self):
        # Manhattan College 2025-26: 464 enrolled of 11,970 admitted (3.9%),
        # the lowest real yield among the 762 published rows.
        _fields, browser = self._project(
            "2025-26", {"C.116": "14570", "C.117": "11970", "C.118": "464"}
        )
        self.assertEqual(browser["enrolled_first_year"], 464)
        self.assertIsNotNone(browser["yield_rate"])

    def _project_labeled(self, year, specs, values):
        """specs: {field_id: (label, value_type)}"""
        definitions = defs()
        for field_id, (label, hint) in specs.items():
            definitions[year][field_id] = FieldDefinition(
                year, field_id, label, "Section", "Subsection", hint
            )
        fields, _browser = build_projection_rows(
            doc(canonical_year=year),
            [artifact(schema_version=year, values={k: {"value": v} for k, v in values.items()})],
            definitions,
        )
        return {row["field_id"]: row for row in fields}

    def test_excel_serial_in_a_date_field_is_converted(self):
        # Austin Peay 2024-25 printed its spreadsheet dates as serials.
        fields = self._project_labeled(
            "2024-25",
            {
                "D.904": ("Summer", "MM-DD"),
                "G.003": ("Approximate date when final costs of attendance will be available", "MM-DD"),
                "H.901": ("Priority date for filing required financial aid forms:", "MM-DD"),
                "C.8E": ("Latest date by which SAT or ACT scores must be received for fall-term admission", "YN"),
                "D.905": ("Fall", "MM-DD"),
                "D.906": ("Spring", "MM-DD"),
            },
            {"D.904": "45437", "G.003": "45869", "H.901": "45931", "C.8E": "45509",
             "D.905": "3/15", "D.906": "99999"},
        )
        self.assertEqual(fields["D.904"]["value_text"], "2024-05-25")
        self.assertEqual(fields["G.003"]["value_text"], "2025-07-31")
        self.assertEqual(fields["H.901"]["value_text"], "2025-10-01")
        self.assertEqual(fields["C.8E"]["value_text"], "2024-08-05")
        for field_id in ("D.904", "G.003", "H.901", "C.8E"):
            self.assertEqual(fields[field_id]["value_status"], "reported")
        # A written date is left as the school wrote it.
        self.assertEqual(fields["D.905"]["value_text"], "3/15")
        # A 5-digit number outside the CDS window is left as the school wrote it.
        self.assertEqual(fields["D.906"]["value_text"], "99999")
        self.assertEqual(fields["D.906"]["value_status"], "reported")

    def test_serial_one_year_before_the_cds_year_converts(self):
        # A 2024-25 form lists early-decision deadlines in November 2023.
        fields = self._project_labeled(
            "2024-25", {"D.904": ("Summer", "MM-DD")}, {"D.904": "45231"}
        )
        self.assertEqual(fields["D.904"]["value_text"], "2023-11-01")

    def test_numeric_cell_with_date_in_its_label_is_not_a_date(self):
        # Texas A&M 2025-26 B.2202: students still enrolled "as of the official
        # enrollment date". Also the split Month cells of 2025-26.
        fields = self._project_labeled(
            "2025-26",
            {
                "B.2202": ("From this group, identify how many were still enrolled as of the official enrollment date", "Number"),
                "C.2102": ("First or only early decision plan closing date: Month", "MM"),
            },
            {"B.2202": "10364", "C.2102": "45509"},
        )
        self.assertEqual(fields["B.2202"]["value_status"], "reported")
        self.assertEqual(fields["B.2202"]["value_num"], "10364")
        self.assertEqual(fields["C.2102"]["value_text"], "45509")

    def test_five_digit_number_outside_a_date_field_is_untouched(self):
        fields = self._project_labeled(
            "2024-25",
            {"B.101": ("Total students", "Number"), "A.103": ("City/State/Zip/Country:", "Text")},
            {"B.101": "45509", "A.103": "45509"},
        )
        self.assertEqual(fields["B.101"]["value_num"], "45509")
        self.assertEqual(fields["A.103"]["value_text"], "45509")

    def test_zip_code_in_a_web_address_field_is_not_published(self):
        # Kenyon 2024-25: 43022 landed in A.010 (CDS web page URL) and A.107
        # (WWW home page) under the 2025-26 numbering of section A.
        fields = self._project_labeled(
            "2024-25",
            {
                "A.010": ("If yes, please provide the URL of the corresponding Web page:", "URL"),
                "A.107": ("WWW Home Page Address:", "Text"),
                "A.008": ("E-mail Address:", "Email Address"),
                "A.112": ("Admissions E-mail Address:", "Email Address"),
            },
            {"A.010": "43022", "A.107": "43022", "A.008": "43022", "A.112": "admissions@kenyon.edu"},
        )
        for field_id in ("A.010", "A.107", "A.008"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error")
        self.assertEqual(fields["A.112"]["value_status"], "reported")
        # In the 2025-26 form A.010 really is the ZIP code.
        current = self._project_labeled(
            "2025-26", {"A.010": ("Zipcode", "Numbers")}, {"A.010": "43022"}
        )
        self.assertEqual(current["A.010"]["value_status"], "reported")

    def test_c7_ratings_use_the_four_label_vocabulary(self):
        specs = {f"C.70{n}": ("Rigor of secondary school record", "Text") for n in range(1, 10)}
        values = {
            "C.701": "VI",  # Barnard 2025-26 legend
            "C.702": "NC",  # Aquinas 2024-25, beside spelled-out ratings
            "C.703": "NotConsidered",  # Reed 2024-25
            "C.704": "Not Considered Not Considered",  # North Alabama 2024-25, doubled cell
            "C.705": "Very Important",
            "C.706": "nc",  # lower-case legend
            "C.707": "Not considered for admission, even if submitted",  # Virginia Tech
            "C.708": "C",
            "C.709": "I",
        }
        fields = self._project_labeled("2025-26", specs, values)
        self.assertEqual(fields["C.701"]["value_text"], "Very Important")
        self.assertEqual(fields["C.702"]["value_text"], "Not Considered")
        self.assertEqual(fields["C.703"]["value_text"], "Not Considered")
        self.assertEqual(fields["C.704"]["value_text"], "Not Considered")
        self.assertEqual(fields["C.705"]["value_text"], "Very Important")
        self.assertEqual(fields["C.707"]["value_text"], "Not Considered")
        self.assertEqual(fields["C.708"]["value_text"], "Considered")
        self.assertEqual(fields["C.709"]["value_text"], "Important")
        self.assertEqual(fields["C.706"]["value_text"], "Not Considered")
        for field_id in values:
            self.assertEqual(fields[field_id]["value_status"], "reported")

    def test_c7_cells_that_are_not_ratings_are_not_published(self):
        specs = {f"C.70{n}": ("Class rank", "Text") for n in range(1, 10)}
        values = {
            "C.709": "X",  # a bare mark does not say which rating was ticked
            "C.701": "Text",  # Hiram 2024-25: template header
            "C.702": "25th Percentile",  # Fullerton 2024-25: C9 heading in a C7 cell
            "C.703": "SAT Evidence-Based Reading and Writing",
            "C.704": "First-Time,",  # Evergreen 2024-25
            "C.705": "18",  # Westminster 2024-25: an ACT score
            "C.706": "0.3076923076923077",  # North Dakota State 2024-25
            "C.707": "/2",  # Spring Arbor 2025-26: radio button state
            "C.708": "Yes",  # Bethel 2024-25
        }
        fields = self._project_labeled("2024-25", specs, values)
        for field_id in ("C.701", "C.702", "C.703", "C.704", "C.705", "C.706", "C.707", "C.708", "C.709"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error", field_id)
            self.assertIsNone(fields[field_id]["value_num"])
        na = self._project_labeled(
            "2024-25", {"C.701": ("Class rank", "Text")}, {"C.701": "n/a"}
        )
        self.assertEqual(na["C.701"]["value_status"], "not_applicable")

    def test_c801_yes_no_vocabulary(self):
        question = "Does your institution make use of SAT or ACT scores in admission decisions"
        fields = self._project_labeled(
            "2024-25",
            {
                "C.801": (question, "YN"),
                "C.8D": ("In addition, does your institution use applicants' test scores for academic advising?", "YN"),
                "C.8F": ("If necessary, use this space to clarify your test policies", "YN"),
                "C.1402": ("Application closing date (fall)", "YN"),
                "C.201": ("Do you have a policy of placing students on a waiting list?", "YN"),
                "C.205": ("Is your waiting list ranked?", "YN"),
                "C.206": ("If yes, do you release that information to students?", "YN"),
            },
            {"C.801": "Y", "C.8D": "N", "C.8F": "Tests are optional for most applicants.",
             "C.1402": "Mar 1", "C.201": "YN", "C.205": "0.0283", "C.206": "Y Response 'Y' or 'N'"},
        )
        self.assertEqual(fields["C.801"]["value_kind"], "yesno")
        self.assertIs(fields["C.801"]["value_bool"], True)
        self.assertIs(fields["C.8D"]["value_bool"], False)
        # Date and free-text cells that the form also marks YN are not yes/no.
        self.assertEqual(fields["C.8F"]["value_kind"], "text")
        self.assertEqual(fields["C.8F"]["value_status"], "reported")
        self.assertEqual(fields["C.1402"]["value_text"], "Mar 1")
        # Template echoes and fractions are not answers.
        for field_id in ("C.201", "C.205", "C.206"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error", field_id)

    def test_c802_to_c804_radio_export_names_are_decoded(self):
        specs = {f"C.80{n}": ("SAT or ACT", "Text") for n in (2, 3, 4)}
        fields = self._project_labeled(
            "2024-25",
            specs,
            {"C.802": "/ADMS_CONSIDER", "C.803": "/ADMS_RFS", "C.804": "/ADMS_NOT_USED"},
        )
        self.assertEqual(fields["C.802"]["value_text"], "Considered")
        self.assertEqual(fields["C.804"]["value_text"], "Not Used")
        # RFS has no label in the schema, so it is left as exported.
        self.assertEqual(fields["C.803"]["value_text"], "/ADMS_RFS")

    def test_c7_radio_on_state_names_are_ratings(self):
        fields = self._project_labeled(
            "2025-26",
            {"C.701": ("Rigor of secondary school record", "Text")},
            {"C.701": "/VI"},
        )
        self.assertEqual(fields["C.701"]["value_text"], "Very Important")

    def test_c802_to_c804_template_text_and_fractions_are_not_published(self):
        specs = {f"C.80{n}": ("SAT or ACT", "Text") for n in (2, 3, 4)}
        fields = self._project_labeled(
            "2024-25",
            specs,
            {"C.802": "ACT Composite", "C.803": "0.3678", "C.804": "Required"},
        )
        self.assertEqual(fields["C.802"]["value_status"], "parse_error")
        self.assertEqual(fields["C.803"]["value_status"], "parse_error")
        self.assertEqual(fields["C.804"]["value_status"], "reported")

    def test_loan_category_borrowers_over_any_loan_borrowers_are_not_published(self):
        # Illinois Urbana-Champaign 2024-25: a dollar amount in H.503.
        hints = {f"H.50{n}": "Number" for n in (1, 2, 3, 4, 5)}
        fields = self._project_with_hints(
            hints,
            {"H.501": "2923", "H.502": "2800", "H.503": "40705", "H.504": "0", "H.505": "3500"},
            year="2024-25",
        )
        for field_id in ("H.501", "H.503"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error", field_id)
        # Federal and state counts at or under the any-loan count stay, and
        # private loans (H.505) are not compared.
        self.assertEqual(fields["H.502"]["value_status"], "reported")
        self.assertEqual(fields["H.504"]["value_status"], "reported")
        self.assertEqual(fields["H.505"]["value_status"], "reported")

    def test_loan_category_slightly_over_any_loan_is_the_schools_own_figure(self):
        # USC 2025-26: H.502 = 1,386 against H.501 = 1,334 (1.04x).
        hints = {f"H.50{n}": "Number" for n in (1, 2)}
        fields = self._project_with_hints(hints, {"H.501": "1334", "H.502": "1386"})
        self.assertEqual(fields["H.501"]["value_status"], "reported")
        self.assertEqual(fields["H.502"]["value_status"], "reported")

    def test_flagged_zero_any_loan_count_is_not_evidence_for_not_applicable(self):
        hints = {"H.501": "Number", "H.502": "Number", "H.511": "Nearest $1"}
        fields = self._project_with_hints(
            hints, {"H.501": "0", "H.502": "400", "H.511": "0"}
        )
        self.assertEqual(fields["H.501"]["value_status"], "parse_error")
        self.assertEqual(fields["H.511"]["value_status"], "reported")

    def test_funnel_rules_do_not_double_blame_enrolled(self):
        # applied 200, admitted 10000, enrolled 80: admitted is the wrong
        # figure; 80 is not also flagged as a tiny class.
        fields, browser = self._project(
            "2025-26", {"C.116": "200", "C.117": "10000", "C.118": "80"}
        )
        self.assertEqual(fields["C.118"]["value_status"], "reported")
        self.assertEqual(browser["enrolled_first_year"], 80)
        self.assertIsNone(browser["admitted"])
        # Admitted 0 beside 2,169 enrolled (Akron): only the zero is cleared.
        _fields, browser = self._project(
            "2025-26", {"C.116": "9000", "C.117": "0", "C.118": "2169"}
        )
        self.assertEqual(browser["enrolled_first_year"], 2169)

    def test_whole_number_rule_covers_only_headcount_cells(self):
        # H.1103 (weeks of notification) is a Number cell with real fractions.
        fields = self._project_labeled(
            "2025-26",
            {
                "H.1103": ("or within____weeks of notification.", "Number"),
                "H.604": ("If institutional financial aid is available for nonresident", "Number"),
                "B.101": ("Degree-seeking, first-time first-year men", "Number"),
            },
            {"H.1103": "2.5", "H.604": "12.5", "B.101": "12.5"},
        )
        self.assertEqual(fields["H.1103"]["value_status"], "reported")
        self.assertEqual(fields["H.604"]["value_status"], "reported")
        self.assertEqual(fields["B.101"]["value_status"], "parse_error")

    def test_yn_cells_not_phrased_as_questions_are_yes_no(self):
        fields = self._project_labeled(
            "2024-25",
            {"D.1801": ("American Council on Education (ACE)", "YN"),
             "H.1002": ("b) Students notified on a rolling basis:", "YN")},
            {"D.1801": "Y", "H.1002": "N"},
        )
        self.assertIs(fields["D.1801"]["value_bool"], True)
        self.assertIs(fields["H.1002"]["value_bool"], False)

    def test_zero_loan_average_beside_zero_borrowers_is_not_applicable(self):
        # Brigham Young 2025-26: no state-loan borrowers (H.504 = 0), so the
        # state-loan average (H.514) of 0 is the blank, not a $0 loan.
        hints = {f"H.{n}": "Nearest $1" if n >= 511 else "Number" for n in (501, 504, 513, 514, 515, 505)}
        fields = self._project_with_hints(
            hints,
            {"H.501": "2000", "H.504": "0", "H.514": "0", "H.505": "10", "H.515": "0", "H.513": "8437"},
        )
        self.assertEqual(fields["H.514"]["value_status"], "not_applicable")
        self.assertEqual(fields["H.514"]["value_kind"], "not_applicable")
        self.assertIsNone(fields["H.514"]["value_num"])
        # Samford 2024-25: one state-loan borrower, average 0 -- left as reported.
        self.assertEqual(fields["H.515"]["value_status"], "reported")
        self.assertEqual(fields["H.515"]["value_num"], "0")
        # Yale 2025-26: a real institutional-loan average is untouched.
        self.assertEqual(fields["H.513"]["value_num"], "8437")

    def test_zero_loan_average_without_a_borrower_count_is_left_alone(self):
        fields = self._project_with_hints({"H.514": "Nearest $1"}, {"H.514": "0"})
        self.assertEqual(fields["H.514"]["value_status"], "reported")

    def test_zero_loan_average_with_zero_percent_and_no_count_is_not_applicable(self):
        # No borrower count, 0% borrowing, average 0: nobody borrowed.
        hints = {"H.509": "Nearest 1%", "H.514": "Nearest $1"}
        fields = self._project_with_hints(hints, {"H.509": "0", "H.514": "0"})
        self.assertEqual(fields["H.514"]["value_status"], "not_applicable")

    def test_zero_percent_with_a_borrower_count_does_not_make_the_average_not_applicable(self):
        # Belmont 2024-25 institutional loans: 1 borrower rounds to 0%. A zero
        # average beside that borrower is still a reported answer.
        hints = {"H.503": "Number", "H.508": "Nearest 1%", "H.513": "Nearest $1"}
        fields = self._project_with_hints(hints, {"H.503": "1", "H.508": "0", "H.513": "0"})
        self.assertEqual(fields["H.513"]["value_status"], "reported")

    def test_c1_first_year_class_under_one_percent_of_admits_is_not_published(self):
        # Salisbury 2024-25: 16 enrolled beside 7,737 admitted.
        fields, _browser = self._project(
            "2024-25", {"C.117": "10734", "C.118": "7737", "C.119": "16"}
        )  # applied is consistent with admitted, so only enrolled is suspect
        self.assertEqual(fields["C.119"]["value_status"], "parse_error")
        self.assertEqual(fields["C.118"]["value_status"], "reported")
        # Manhattan College 2025-26: 464 of 11,970 (3.9%) is a real low yield.
        fields, _browser = self._project(
            "2025-26", {"C.116": "14570", "C.117": "11970", "C.118": "464"}
        )
        self.assertEqual(fields["C.118"]["value_status"], "reported")

    def test_yes_no_question_about_a_date_is_not_read_as_a_date_serial(self):
        fields = self._project_labeled(
            "2024-25",
            {"C.1401": ("Does your institution have an application closing date?", "YN")},
            {"C.1401": "45509"},
        )
        self.assertEqual(fields["C.1401"]["value_status"], "parse_error")
        self.assertEqual(fields["C.1401"]["value_text"], "45509")

    def test_fractional_headcount_is_not_published(self):
        # Worcester State 2025-26: dollars and cents in an H2 count cell.
        # Colorado 2024-25: B.121 = 16.312 for the full-time men count.
        fields = self._project_labeled(
            "2025-26",
            {
                "H.204": ("D. Number of students in line c who were awarded any financial aid", "Number"),
                "H.205": ("E. Number of students in line d who were awarded any need-based aid", "Number"),
                "B.121": ("Total graduate Part-Time Students: males", "Number"),
                "I.202": ("based on ____ students", "Number"),
                "C.1201": ("Average high school GPA", "Round to Nearest Hundredths"),
                "B.429": ("Recipients of a Federal Pell Grant", "Whole Number or Round to Nearest Tenth"),
            },
            {"H.204": "3126429.42", "H.205": "1500", "B.121": "16.312",
             "I.202": "17070.67", "C.1201": "3.35", "B.429": "49.19"},
        )
        for field_id in ("H.204", "B.121"):
            self.assertEqual(fields[field_id]["value_status"], "parse_error", field_id)
            self.assertIsNone(fields[field_id]["value_num"])
        # B18/B19 two-year graduation cells ("2022 Cohort") may be counts or
        # rates, so they are not held to whole numbers (Purdue 2025-26).
        two_year = self._project_labeled(
            "2025-26", {"B.1801": ("2022 Cohort", "Number")}, {"B.1801": "0.8296261239943209"}
        )
        self.assertEqual(two_year["B.1801"]["value_status"], "reported")
        # Counter-examples: a whole count, FTE students (section I), a GPA and
        # a percent typed "Whole Number or Round to Nearest Tenth" stay.
        self.assertEqual(fields["H.205"]["value_status"], "reported")
        self.assertEqual(fields["I.202"]["value_num"], "17070.67")
        self.assertEqual(fields["C.1201"]["value_num"], "3.35")
        self.assertEqual(fields["B.429"]["value_num"], "49.19")

    def test_student_count_above_250k_is_a_dollar_column(self):
        # Worcester State 2025-26: H.218 = 448,174. A real large count stays.
        fields = self._project_labeled(
            "2025-26",
            {
                "H.218": ("E. Number of students in line d who were awarded any need-based aid", "Number"),
                "H.214": ("A. Number of degree-seeking undergraduate students", "Number"),
                "H.606": ("Total dollar amount", "Nearest $1"),
            },
            {"H.218": "448174", "H.214": "92000", "H.606": "448174"},
        )
        self.assertEqual(fields["H.218"]["value_status"], "parse_error")
        self.assertEqual(fields["H.214"]["value_status"], "reported")
        self.assertEqual(fields["H.606"]["value_status"], "reported")

    def test_ed_counts_from_the_2024_form_use_its_own_field_numbers(self):
        # Hofstra 2024-25: 20 applicants, 24 admitted.
        fields, browser = self._project("2024-25", {"C.2106": "20", "C.2107": "24"})
        self.assertEqual(fields["C.2106"]["value_status"], "parse_error")
        self.assertEqual(fields["C.2107"]["value_status"], "parse_error")
        self.assertIsNone(browser["ed_applicants"])

    def test_plausible_ed_counts_are_kept(self):
        fields, browser = self._project("2025-26", {"C.2110": "6013", "C.2111": "806"})
        self.assertEqual(fields["C.2110"]["value_status"], "reported")
        self.assertEqual(browser["ed_applicants"], 6013)
        self.assertEqual(browser["ed_admitted"], 806)

    def test_month_and_day_cells_of_the_2025_form_are_not_treated_as_ed_counts(self):
        # In 2025-26, C.2106/C.2107 are a month and a day, not counts.
        fields, _browser = self._project("2025-26", {"C.2106": "11", "C.2107": "15"})
        self.assertEqual(fields["C.2106"]["value_status"], "reported")
        self.assertEqual(fields["C.2107"]["value_status"], "reported")

    def test_graduating_class_that_is_a_calendar_year_is_not_published(self):
        # University of Alabama 2025-26: H.401 = 2025 with 2,334 borrowers.
        fields, _browser = self._project("2025-26", {"H.401": "2025", "H.501": "2334"})
        self.assertEqual(fields["H.401"]["value_status"], "parse_error")
        self.assertIsNone(fields["H.401"]["value_num"])
        self.assertEqual(fields["H.401"]["value_text"], "2025")
        self.assertEqual(fields["H.501"]["value_status"], "reported")

    def test_graduating_class_smaller_than_its_borrowers_is_not_published(self):
        # Georgia Tech 2025-26: H.401 = 25 with 1,186 borrowers.
        fields, _browser = self._project("2025-26", {"H.401": "25", "H.501": "1186"})
        self.assertEqual(fields["H.401"]["value_status"], "parse_error")
        self.assertEqual(fields["H.501"]["value_status"], "reported")

    def test_plausible_graduating_class_is_kept(self):
        fields, _browser = self._project("2025-26", {"H.401": "4120", "H.501": "1186"})
        self.assertEqual(fields["H.401"]["value_status"], "reported")

    def test_first_year_aid_count_above_all_undergraduates_is_not_published(self):
        # University of Florida 2025-26: H.201 = 32,857 against H.214 = 2,772.
        fields, _browser = self._project("2025-26", {"H.201": "32857", "H.214": "2772", "H.202": "5000"})
        self.assertEqual(fields["H.201"]["value_status"], "parse_error")
        self.assertEqual(fields["H.214"]["value_status"], "parse_error")
        self.assertEqual(fields["H.202"]["value_status"], "reported")

    def test_first_year_aid_count_below_all_undergraduates_is_kept(self):
        fields, _browser = self._project("2025-26", {"H.201": "6594", "H.214": "32857"})
        self.assertEqual(fields["H.201"]["value_status"], "reported")
        self.assertEqual(fields["H.214"]["value_status"], "reported")

    def test_2024_admissions_derived_metrics_use_total_fallback_when_available(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "10"},
                        "C.102": {"value": "20"},
                        "C.117": {"value": "35"},
                        "C.105": {"value": "5"},
                        "C.106": {"value": "10"},
                        "C.118": {"value": "17"},
                        "C.109": {"value": "2"},
                        "C.119": {"value": "10"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 35)
        self.assertEqual(browser["admitted"], 17)
        self.assertEqual(browser["enrolled_first_year"], 10)

    def test_2024_direct_alias_uses_canonical_field_id(self):
        fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={"C.901": {"value": "62"}},
                )
            ],
            defs(),
        )

        by_field = {row["field_id"]: row for row in fields}
        self.assertEqual(by_field["C.901"]["canonical_field_id"], "C.901")
        self.assertEqual(by_field["C.901"]["equivalence_kind"], "direct")
        self.assertEqual(by_field["C.901"]["canonical_metric"], "sat_submit_rate")
        self.assertEqual(browser["sat_submit_rate"], "0.62")

    def test_invalid_sat_act_values_are_parse_errors_and_not_browser_values(self):
        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.905": {"value": "399"},
                    "C.907": {"value": "1601"},
                    "C.914": {"value": "0"},
                    "C.916": {"value": "37"},
                })
            ],
            defs(),
        )
        by_field = {row["field_id"]: row for row in fields}
        for field_id in ("C.905", "C.907", "C.914", "C.916"):
            self.assertEqual(by_field[field_id]["value_status"], "parse_error")
            self.assertIsNone(by_field[field_id]["value_num"])
        self.assertIsNone(browser["sat_composite_p25"])
        self.assertIsNone(browser["sat_composite_p75"])
        self.assertIsNone(browser["act_composite_p25"])
        self.assertIsNone(browser["act_composite_p75"])

    def test_sat_act_decimal_scores_are_preserved_and_browser_rounded(self):
        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.906": {"value": "1450.5"},
                    "C.908": {"value": "477.5"},
                    "C.915": {"value": "33.5"},
                })
            ],
            defs(),
        )
        by_field = {row["field_id"]: row for row in fields}
        self.assertEqual(by_field["C.906"]["value_status"], "reported")
        self.assertEqual(by_field["C.906"]["value_num"], "1450.5")
        self.assertEqual(by_field["C.908"]["value_status"], "reported")
        self.assertEqual(by_field["C.908"]["value_num"], "477.5")
        self.assertEqual(by_field["C.915"]["value_status"], "reported")
        self.assertEqual(by_field["C.915"]["value_num"], "33.5")
        self.assertEqual(browser["sat_composite_p50"], 1451)
        self.assertEqual(browser["sat_ebrw_p25"], 478)
        self.assertEqual(browser["act_composite_p50"], 34)

    def test_admission_strategy_columns_project_from_2025_schema(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.118": {"value": "50"},
                        "C.2101": {"value": "Yes"},
                        "C.2106": {"value": "1"},
                        "C.2110": {"value": "200"},
                        "C.2111": {"value": "40"},
                        "C.2201": {"value": "Yes"},
                        "C.2206": {"value": "No"},
                        "C.201": {"value": "Yes"},
                        "C.202": {"value": "300"},
                        "C.203": {"value": "150"},
                        "C.204": {"value": "30"},
                        "C.711": {"value": "Important"},
                        "C.712": {"value": "Considered"},
                        "C.713": {"value": "Not Considered"},
                        "C.714": {"value": "Important"},
                        "C.718": {"value": "Very Important"},
                        "C.1302": {"value": "$85"},
                        "C.1305": {"value": "Yes"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["ed_offered"], True)
        self.assertEqual(browser["ed_applicants"], 200)
        self.assertEqual(browser["ed_admitted"], 40)
        self.assertEqual(browser["ed_has_second_deadline"], True)
        self.assertEqual(browser["ea_offered"], True)
        self.assertEqual(browser["ea_restrictive"], False)
        self.assertEqual(browser["wait_list_policy"], True)
        self.assertEqual(browser["wait_list_offered"], 300)
        self.assertEqual(browser["wait_list_accepted"], 150)
        self.assertEqual(browser["wait_list_admitted"], 30)
        self.assertEqual(browser["c711_first_gen_factor"], "Important")
        self.assertEqual(browser["c714_state_residency_factor"], "Important")
        self.assertEqual(browser["c718_demonstrated_interest_factor"], "Very Important")
        self.assertEqual(browser["app_fee_amount"], 85)
        self.assertEqual(browser["app_fee_waiver_offered"], True)
        self.assertEqual(browser["admission_strategy_card_quality"], "ok")

    def test_admission_strategy_quality_flags_ed_math(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.118": {"value": "50"},
                        "C.2101": {"value": "Yes"},
                        "C.2110": {"value": "40"},
                        "C.2111": {"value": "41"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["admission_strategy_card_quality"], "ed_math_inconsistent")
        self.assertIsNone(browser["ed_applicants"])
        self.assertIsNone(browser["ed_admitted"])

    def test_admission_strategy_infers_ed_offered_from_valid_counts(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.2110": {"value": "200"},
                        "C.2111": {"value": "40"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["ed_offered"], True)
        self.assertEqual(browser["admission_strategy_card_quality"], "ok")

    def test_admission_strategy_infers_wait_list_policy_from_valid_counts(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.202": {"value": "300"},
                        "C.203": {"value": "150"},
                        "C.204": {"value": "30"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["wait_list_policy"], True)
        self.assertEqual(browser["admission_strategy_card_quality"], "ok")

    def test_admission_strategy_app_fee_only_is_insufficient(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.1302": {"value": "$85"},
                        "C.1305": {"value": "Yes"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["app_fee_amount"], 85)
        self.assertEqual(browser["admission_strategy_card_quality"], "insufficient_data")

    def test_sub_institutional_is_preserved(self):
        fields, browser = build_projection_rows(
            doc(sub_institutional="general-studies"),
            [artifact(values={"C.116": {"value": "100"}})],
            defs(),
        )
        self.assertTrue(fields)
        self.assertEqual(fields[0]["sub_institutional"], "general-studies")
        self.assertEqual(browser["sub_institutional"], "general-studies")

    def test_percent_values_are_fractional(self):
        parsed = parse_field_value(
            {"value": "58%"},
            FieldDefinition("2025-26", "X.001", "Percent field", None, None, "Percent"),
        )
        self.assertEqual(parsed.value_kind, "percent")
        self.assertEqual(parsed.value_num, Decimal("0.58"))

        parsed_plain_percent = parse_field_value(
            {"value": "58"},
            FieldDefinition("2025-26", "B.2203", "Retention percentage", None, None, "Whole Number or Round to Nearest Tenth"),
        )
        self.assertEqual(parsed_plain_percent.value_kind, "percent")
        self.assertEqual(parsed_plain_percent.value_num, Decimal("0.58"))

    def test_percentile_is_not_treated_as_percent(self):
        parsed = parse_field_value(
            {"value": "1480"},
            FieldDefinition("2025-26", "C.905", "SAT 75th percentile", None, None, "Number"),
        )
        self.assertEqual(parsed.value_kind, "number")
        self.assertEqual(parsed.value_num, Decimal("1480"))

    def test_out_of_range_percent_is_parse_error(self):
        parsed = parse_field_value(
            {"value": "25457.5"},
            FieldDefinition("2025-26", "H.209", "Percentage of need met", None, None, "Nearest 1%"),
        )
        self.assertEqual(parsed.value_kind, "percent")
        self.assertEqual(parsed.value_status, "parse_error")
        self.assertIsNone(parsed.value_num)

    def test_tier4_fallback_overlay_fills_gaps_only(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={
                        "C.116": {"value": "100"},
                        "C.117": {"value": "20"},
                    },
                    notes_extra={"markdown": "current markdown"},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={
                        "C.117": {"value": "999"},
                        "C.118": {"value": "10"},
                    },
                    created_at="2026-01-02T00:00:00Z",
                    notes_extra={
                        "base_artifact_id": "tier4_docling-canonical",
                        "base_producer_version": "0.3.0",
                    },
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.values["C.117"]["value"], "20")
        self.assertEqual(selected.values["C.118"]["value"], "10")
        self.assertEqual(selected.value_sources["C.117"][0], "tier4_docling")
        self.assertEqual(selected.value_sources["C.118"][0], "tier4_llm_fallback")

    def test_tier4_fallback_overlay_requires_matching_schema_version(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={"C.116": {"value": "100"}},
                    schema_version="2025-26",
                    notes_extra={"markdown": "current markdown"},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={"C.118": {"value": "10"}},
                    created_at="2026-01-02T00:00:00Z",
                    schema_version="2024-25",
                    notes_extra={
                        "base_artifact_id": "tier4_docling-canonical",
                        "base_producer_version": "0.3.0",
                    },
                ),
            ],
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertIsNone(selected.fallback_artifact_id)
        self.assertNotIn("C.118", selected.values)

    def test_selected_result_prefers_year_matched_non_fallback_artifact(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    values={"C.116": {"value": "999"}},
                    created_at="2026-01-03T00:00:00Z",
                    notes_extra={"schema_fallback_used": True},
                    schema_version="2025-26",
                ),
                artifact(
                    values={"C.101": {"value": "10"}},
                    created_at="2026-01-01T00:00:00Z",
                    schema_version="2024-25",
                ),
            ],
            expected_schema_version="2024-25",
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.schema_version, "2024-25")
        self.assertIn("C.101", selected.values)
        self.assertNotIn("C.116", selected.values)

    def test_selected_result_skips_unusable_label_acroform_tier2(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier2_acroform",
                    values={},
                    schema_version="2024-25",
                    notes_extra={
                        "stats": {
                            "acroform_fields_total": 581,
                            "schema_fields_populated": 0,
                            "unmapped_acroform_fields": 581,
                        },
                    },
                ),
                artifact(
                    producer="tier4_docling",
                    values={"C.101": {"value": "5746"}},
                    schema_version="2024-25",
                    created_at="2026-01-02T00:00:00Z",
                ),
            ],
            expected_schema_version="2024-25",
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.base_producer, "tier4_docling")
        self.assertEqual(selected.values["C.101"]["value"], "5746")

    def test_selected_result_keeps_usable_tier2_over_tier4(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier2_acroform",
                    values={"C.101": {"value": "576"}},
                    schema_version="2024-25",
                    notes_extra={
                        "stats": {
                            "acroform_fields_total": 732,
                            "schema_fields_populated": 576,
                            "unmapped_acroform_fields": 156,
                        },
                    },
                ),
                artifact(
                    producer="tier4_docling",
                    values={"C.101": {"value": "999"}},
                    schema_version="2024-25",
                    created_at="2026-01-02T00:00:00Z",
                ),
            ],
            expected_schema_version="2024-25",
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.base_producer, "tier2_acroform")
        self.assertEqual(selected.values["C.101"]["value"], "576")

    def test_tier4_fallback_overlay_ignores_stale_base(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={"C.116": {"value": "100"}},
                    notes_extra={"markdown": "fresh v0.3 markdown"},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={"C.118": {"value": "10"}},
                    created_at="2026-01-02T00:00:00Z",
                    notes_extra={
                        "markdown_sha256": "not-the-fresh-markdown-hash",
                        "cleaner_version": "0.2.0",
                    },
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertIsNone(selected.fallback_artifact_id)
        self.assertNotIn("C.118", selected.values)

    def test_legacy_tier4_fallback_overlay_matches_markdown_hash(self):
        markdown = "legacy compatible markdown"
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={"C.116": {"value": "100"}},
                    notes_extra={"markdown": markdown},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={"C.118": {"value": "10"}},
                    created_at="2026-01-02T00:00:00Z",
                    notes_extra={
                        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                        "cleaner_version": "0.3.0",
                    },
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.values["C.118"]["value"], "10")

    def test_derived_metric_formula_requires_explicit_schema_year(self):
        metric = DIRECT_METRIC_DEFINITIONS["applied"]

        self.assertEqual(metric_field_ids_for_year(metric, "2025-26"), ("C.116",))
        self.assertIsNone(metric_field_ids_for_year(metric, "2026-27"))

    def test_replace_projection_rows_uses_atomic_rpc(self):
        client = FakeRpcClient()
        field_rows = [{"document_id": "00000000-0000-0000-0000-000000000001"}]
        browser_row = {"document_id": "00000000-0000-0000-0000-000000000001"}

        replace_projection_rows(
            client,
            "00000000-0000-0000-0000-000000000001",
            field_rows,
            browser_row,
        )

        self.assertEqual(len(client.calls), 1)
        name, params = client.calls[0]
        self.assertEqual(name, "replace_browser_projection_for_document")
        self.assertEqual(params["p_document_id"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(params["p_field_rows"], field_rows)
        self.assertEqual(params["p_browser_row"], browser_row)

    def test_project_document_id_no_manifest_row_is_noop(self):
        client = FakeTableClient({"cds_manifest": []})

        count, has_browser_row = project_document_id(
            client,
            "00000000-0000-0000-0000-000000000001",
            defs(),
        )

        self.assertEqual(count, 0)
        self.assertFalse(has_browser_row)


if __name__ == "__main__":
    unittest.main()
