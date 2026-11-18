"""Cross-field sanity rules applied at projection time.

Every producer (Tier 1 XLSX, Tier 2 AcroForm, Tier 4 Docling, the template
overlay) reaches the public tables through the projection, so a rule here
covers all of them. A rule never repairs a value: it names field ids whose
reported values cannot both be true, and the projection publishes those fields
as ``parse_error`` with no number. Missing is better than wrong.

These rules govern ``cds_fields`` rows. Columns on ``school_browser_rows`` are
derived separately and carry their own guards in ``project_browser_data.py``.

Rules are deliberately narrow. Each one encodes a relationship the CDS form
itself guarantees, and each was added for a failure seen in production (the
examples are in the tests). Add a rule only with a measured count of the
documents it flags.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Mapping, Optional

# field id -> numeric value, for fields that parsed as reported numbers.
ReportedNumbers = Mapping[str, Decimal]

# Early Decision applicants / admitted moved when the 2025-26 form split the
# closing and notification dates into month and day cells.
_ED_COUNT_FIELDS = {
    "2023-24": ("C.2106", "C.2107"),
    "2024-25": ("C.2106", "C.2107"),
    "2025-26": ("C.2110", "C.2111"),
}

_H_SCHEMAS = frozenset({"2023-24", "2024-25", "2025-26"})


def _ed_admitted_exceeds_applicants(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """C21: more students admitted under Early Decision than applied.

    Seen when a date such as 3/15 or 12/15 is read into the two count cells.
    """
    pair = _ED_COUNT_FIELDS.get(schema_version)
    if pair is None:
        return ()
    applicants, admitted = values.get(pair[0]), values.get(pair[1])
    if applicants is None or admitted is None:
        return ()
    if admitted > applicants:
        return pair
    return ()


def _graduating_class_is_not_a_count(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """H4: the graduating class size is a calendar year, or is smaller than
    the number of its members who borrowed (H5 line a).

    Seen when the "2025 undergraduate class" heading is read as the count.
    """
    if schema_version not in _H_SCHEMAS:
        return ()
    class_size = values.get("H.401")
    if class_size is None:
        return ()
    if Decimal(1990) <= class_size <= Decimal(2035):
        return ("H.401",)
    borrowers = values.get("H.501")
    if borrowers is not None and borrowers > class_size:
        return ("H.401",)
    return ()


def _first_year_aid_count_exceeds_all_undergraduates(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """H2 line a: full-time first-year students cannot outnumber all full-time
    undergraduates. Seen when the H2 columns are shifted or swapped.
    """
    if schema_version not in _H_SCHEMAS:
        return ()
    first_year, all_undergraduates = values.get("H.201"), values.get("H.214")
    if first_year is None or all_undergraduates is None:
        return ()
    if first_year > 0 and first_year > all_undergraduates:
        return ("H.201", "H.214")
    return ()


# H2 lines J-M and O/Q for the three cohorts, and H6's average award to
# nonresidents. Each is a dollar average per student.
_PER_STUDENT_AVERAGE_FIELDS = (
    "H.210", "H.211", "H.212", "H.213",
    "H.223", "H.224", "H.225", "H.226",
    "H.236", "H.237", "H.238", "H.239",
    "H.2A02", "H.2A04", "H.2A06", "H.2A08", "H.2A10", "H.2A12",
    "H.605",
)
# The largest real per-student average in the corpus is about $91,000. Values
# above this ceiling are a column total sitting in the average's cell.
_PER_STUDENT_AVERAGE_CEILING = Decimal(150_000)


def _per_student_average_is_a_total(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """H2/H6: an "average award" in the millions is the total, not the average.

    Seen when the neighbouring total lands in the average's cell (Harvard
    2025-26 H.605 = $66,826,244, the H.606 total).
    """
    if schema_version not in _H_SCHEMAS:
        return ()
    return tuple(
        field_id
        for field_id in _PER_STUDENT_AVERAGE_FIELDS
        if (value := values.get(field_id)) is not None
        and value > _PER_STUDENT_AVERAGE_CEILING
    )


# C1 first-time, first-year funnel, by template year. Totals are
# (applied, admitted, enrolled); the men and women pairs are
# (applied, admitted) for the two largest gender rows.
# 2023-24 is omitted: the projection starts at 2024-25 (MIN_YEAR_START), and
# the 2023-24 C1 numbering has not been checked against these field ids.
_C1_TOTAL_FIELDS = {
    "2024-25": ("C.117", "C.118", "C.119"),
    "2025-26": ("C.116", "C.117", "C.118"),
}
_C1_GENDER_PAIRS = {
    "2024-25": (("C.101", "C.105"), ("C.102", "C.106")),
    "2025-26": (("C.101", "C.104"), ("C.102", "C.105")),
}


def _c1_stage_pair(
    earlier: Optional[Decimal], later: Optional[Decimal], earlier_id: str, later_id: str
) -> tuple[str, ...]:
    """A later funnel stage cannot exceed the stage before it.

    A stage reported as 0 beside a positive later stage is the blank cell
    (filled with 0), so only the zero is flagged; any other pair is
    contradictory with no way to tell which side is wrong, so both are.
    """
    if earlier is None or later is None or later <= earlier:
        return ()
    if earlier == 0:
        return (earlier_id,)
    return (earlier_id, later_id)


def _c1_total_funnel_is_impossible(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """C1: admitted students outnumber applicants, or enrolled outnumber
    admitted, in the total rows.

    Seen in the total row when a residency or gender row lands in it (Chico
    2024-25 applied = 5 beside 21,623 admitted; Salisbury 2024-25 applied =
    299 beside 7,737 admitted; Akron 2025-26 admitted = 0 beside 2,169
    enrolled).
    """
    fields = _C1_TOTAL_FIELDS.get(schema_version)
    if fields is None:
        return ()
    applied_id, admitted_id, enrolled_id = fields
    applied, admitted, enrolled = (values.get(f) for f in fields)
    flagged = _c1_stage_pair(applied, admitted, applied_id, admitted_id) + _c1_stage_pair(
        admitted, enrolled, admitted_id, enrolled_id
    )
    # A first-year class under 1% of 500 or more admits is a gender row or a
    # blank-as-0 in the total cell (Salisbury 2024-25: 16 enrolled beside
    # 7,737 admitted; Chico 2024-25: 0 beside 21,623). Measured: 18 documents,
    # all tier4_docling, all 0-55 enrolled beside 677-22,660 admitted; the
    # lowest real yield among 762 browser rows is 3.9%.
    # Not applied when admitted already exceeds applied: then admitted is the
    # suspect figure, and a plausible enrolled count is not blamed for it.
    if (
        admitted is not None
        and enrolled is not None
        and admitted >= 500
        and enrolled * 100 < admitted
        and not (applied is not None and admitted > applied)
    ):
        flagged += (enrolled_id,)
    return flagged


def _c1_gender_admitted_exceeds_applied(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """C1: more men (or women) admitted than applied.

    Seen when the residency row (Total, In-State, ...) is read as gender
    columns: San Jose State 2024-25 men admitted 31,419 beside 18,545 men
    applied. Only the men and women rows are checked; the small another-gender
    and unknown rows can carry real school inconsistencies.
    """
    flagged: list[str] = []
    for applied_id, admitted_id in _C1_GENDER_PAIRS.get(schema_version, ()):
        applied, admitted = values.get(applied_id), values.get(admitted_id)
        if applied is not None and admitted is not None and admitted > applied:
            flagged.extend((applied_id, admitted_id))
    return tuple(flagged)


# H2 line counts ("Number of students in line ..."): the form's count cells.
_H2_COUNT_FIELDS = (
    "H.201", "H.202", "H.203", "H.204", "H.205", "H.206", "H.207", "H.208",
    "H.214", "H.215", "H.216", "H.217", "H.218", "H.219", "H.220", "H.221",
    "H.227", "H.228", "H.229", "H.230", "H.231", "H.232", "H.233", "H.234",
    "H.2A01", "H.2A03", "H.2A05", "H.2A07", "H.2A09", "H.2A11",
)
# No U.S. institution has 250,000 full-time degree-seeking undergraduates; the
# largest H2 count among the 79,000 measured B and H values is well under that.
# A larger value is a dollar column.
_H2_COUNT_CEILING = Decimal(250_000)


def _h2_count_is_a_dollar_total(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """H2: a student count above 250,000 is a dollar amount in a count cell.

    Seen when the dollar columns shift one row up a school's workbook:
    Worcester State 2025-26 H.218 = 448,174 and Purdue 2025-26 H.218 =
    142,890,663. Measured over 79,000 reported B and H number values: 16
    values in 2 documents exceed the ceiling, all dollar amounts.
    """
    if schema_version not in _H_SCHEMAS:
        return ()
    return tuple(
        field_id
        for field_id in _H2_COUNT_FIELDS
        if (value := values.get(field_id)) is not None and value > _H2_COUNT_CEILING
    )


def _loan_category_borrowers_exceed_any_loan(
    schema_version: str, values: ReportedNumbers
) -> tuple[str, ...]:
    """H5: borrowers in the federal (B), institutional (C) or state (D) loan
    category exceed 1.5 times the borrowers in any loan program (A).

    The 1.5 factor keeps a school's own small inconsistency (USC 2025-26 files
    H.502 = 1,386 against H.501 = 1,334 and its percentages agree).

    Seen as a dollar amount in a count cell (Illinois Urbana-Champaign 2024-25
    H.503 = 40,705 beside 2,923 any-loan borrowers) and as one row read from
    the wrong column (Chico 2024-25 H.502 = 404 beside H.501 = 27). The two
    cannot both be right, so both are flagged. Private loans (H.505) are left
    out: the school may not certify them. Measured: 2 documents of 420 (Chico
    2024-25, Illinois Urbana-Champaign 2024-25); USC 2025-26 is under 1.5x.
    """
    if schema_version not in _H_SCHEMAS:
        return ()
    any_loan = values.get("H.501")
    if any_loan is None:
        return ()
    flagged: list[str] = []
    for field_id in ("H.502", "H.503", "H.504"):
        count = values.get(field_id)
        if count is not None and count > any_loan * Decimal("1.5"):
            flagged.extend(("H.501", field_id))
    return tuple(flagged)


Rule = Callable[[str, ReportedNumbers], tuple[str, ...]]

RULES: tuple[tuple[str, Rule], ...] = (
    ("ed_admitted_exceeds_applicants", _ed_admitted_exceeds_applicants),
    ("graduating_class_is_not_a_count", _graduating_class_is_not_a_count),
    (
        "first_year_aid_count_exceeds_all_undergraduates",
        _first_year_aid_count_exceeds_all_undergraduates,
    ),
    ("per_student_average_is_a_total", _per_student_average_is_a_total),
    ("h2_count_is_a_dollar_total", _h2_count_is_a_dollar_total),
    ("loan_category_borrowers_exceed_any_loan", _loan_category_borrowers_exceed_any_loan),
    ("c1_total_funnel_is_impossible", _c1_total_funnel_is_impossible),
    ("c1_gender_admitted_exceeds_applied", _c1_gender_admitted_exceeds_applied),
)


# Every field id a rule reads. The corpus audit fetches exactly these to replay
# the rules over the published rows; a rule that reads a field missing from
# this set would be silently under-counted there (a test guards it).
FIELD_IDS: frozenset[str] = frozenset(
    {field_id for pair in _ED_COUNT_FIELDS.values() for field_id in pair}
    | {"H.401", "H.501", "H.201", "H.214"}
    | set(_PER_STUDENT_AVERAGE_FIELDS)
    | set(_H2_COUNT_FIELDS)
    | {"H.501", "H.502", "H.503", "H.504"}
    | {f for fields in _C1_TOTAL_FIELDS.values() for f in fields}
    | {f for pairs in _C1_GENDER_PAIRS.values() for pair in pairs for f in pair}
)


# H5 loan categories A-E: (average per borrower, borrower count, percent
# borrowing). The same field numbers in the 2024-25 and 2025-26 forms.
_LOAN_AVERAGE_TRIPLES = tuple(
    (f"H.{511 + i}", f"H.{501 + i}", f"H.{506 + i}") for i in range(5)
)


def averages_without_borrowers(
    schema_version: Optional[str], values: ReportedNumbers
) -> tuple[str, ...]:
    """H5: field ids of a loan average reported as 0 for a category that no
    one borrowed from.

    Nobody borrowed, so there is no average to report: the 0 is the form's
    blank, not a $0 loan. The projection publishes these as ``not_applicable``
    (not ``parse_error``: the school's answer is right, it just is not a
    dollar amount). "No one borrowed" is a borrower count of 0, or, when the
    count is absent, a percent borrowing of 0. Percent alone is not used when
    a count exists, because it rounds down (Belmont 2024-25 institutional
    loans: 1 borrower, 0%, a real average).

    Measured over 420 documents: 341 zero averages, 322 beside a zero
    borrower count (state 173, institutional 143, private 4, federal and any
    1 each) and 15 more with no count and 0% (institutional 13, state 2). A
    zero average beside borrowers (Samford 2024-25 state loans, 1 borrower)
    is left alone.
    """
    if schema_version not in _H_SCHEMAS:
        return ()
    flagged = []
    for average_id, borrowers_id, percent_id in _LOAN_AVERAGE_TRIPLES:
        if values.get(average_id) != 0:
            continue
        borrowers = values.get(borrowers_id)
        if borrowers == 0 or (borrowers is None and values.get(percent_id) == 0):
            flagged.append(average_id)
    return tuple(flagged)


def implausible_funnel(
    applied: Optional[int], admitted: Optional[int], enrolled: Optional[int]
) -> dict[str, str]:
    """Return ``{metric: rule_name}`` for browser-row funnel counts to drop.

    ``school_browser_rows`` derives applied / admitted / enrolled_first_year
    from several fields, so a failing pair is cleared (NULL) rather than
    guessed at. Measured over 762 published rows: 8 flagged, all genuinely
    impossible; the lowest real enrolled / admitted ratio is 3.9%.
    """
    flagged: dict[str, str] = {}
    # Same stage logic as the cds_fields rule (_c1_stage_pair): a stage of 0
    # beside a positive later stage is the blank cell, so only the 0 goes.
    if applied is not None and admitted is not None and admitted > applied:
        name = "admitted_exceeds_applied"
        flagged["applied"] = name
        if applied != 0:
            flagged["admitted"] = name
    if admitted is not None and enrolled is not None and enrolled > admitted:
        name = "enrolled_exceeds_admitted"
        flagged["admitted"] = name
        if admitted != 0:
            flagged["enrolled_first_year"] = name
    if (
        admitted is not None
        and enrolled is not None
        and admitted >= 500
        and enrolled * 100 < admitted
        and not (applied is not None and admitted > applied)
    ):
        flagged.setdefault("enrolled_first_year", "enrolled_negligible_beside_admitted")
    return flagged


def implausible_fields(
    schema_version: Optional[str], values: ReportedNumbers
) -> dict[str, str]:
    """Return ``{field_id: rule_name}`` for reported values that fail a rule."""
    if not schema_version:
        return {}
    flagged: dict[str, str] = {}
    for name, rule in RULES:
        for field_id in rule(schema_version, values):
            flagged.setdefault(field_id, name)
    return flagged
