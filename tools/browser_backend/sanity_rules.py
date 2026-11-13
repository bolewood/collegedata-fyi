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


Rule = Callable[[str, ReportedNumbers], tuple[str, ...]]

RULES: tuple[tuple[str, Rule], ...] = (
    ("ed_admitted_exceeds_applicants", _ed_admitted_exceeds_applicants),
    ("graduating_class_is_not_a_count", _graduating_class_is_not_a_count),
    (
        "first_year_aid_count_exceeds_all_undergraduates",
        _first_year_aid_count_exceeds_all_undergraduates,
    ),
    ("per_student_average_is_a_total", _per_student_average_is_a_total),
)


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
