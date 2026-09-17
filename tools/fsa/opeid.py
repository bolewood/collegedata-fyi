"""Title IV OPEID helpers.

Scorecard ``OPEID`` is an 8-digit campus key. FSA's institutional nonpayment
workbook identifies the main branch with a 6-digit OPEID. Excel may store
either as a number, dropping leading zeros. Digit length after ``int()`` is
not grain.
"""

from __future__ import annotations

from typing import Any

_SUPPRESSION = {"", "NULL", "PrivacySuppressed", "NA", "N/A", "None", "-2", "-9"}


def _digits(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value <= 0:
            return None
        return str(value)
    if isinstance(value, float):
        if value <= 0 or value != int(value):
            return None
        return str(int(value))
    text = str(value).strip()
    if text in _SUPPRESSION:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if not text.isdigit():
        return None
    if int(text) <= 0:
        return None
    return text.lstrip("0") or "0"


def normalize_opeid8(value: Any) -> str | None:
    """Pad a Title IV OPEID to 8-character text.

    Do not call ``normalize_opeid6`` on this value: that helper pads the
    whole integer to 6 and would turn ``00100201`` into ``100201``.
    """
    digits = _digits(value)
    if digits is None or digits == "0":
        return None
    if len(digits) > 8:
        return None
    return digits.zfill(8)


def restore_fsa_opeid(value: Any) -> str | None:
    """Restore leading zeros Excel dropped without promoting 6-digit keys to 8.

    FSA's school-level sheet is a 6-digit main-campus OPE ID. Numeric cells
    such as ``100201`` stay ``100201``. An 8-digit campus key stays 8-wide.
    """
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text in _SUPPRESSION:
            return None
        if text.isdigit():
            if len(text) >= 7:
                return normalize_opeid8(text)
            digits = _digits(text)
            if digits is None or digits == "0":
                return None
            return digits.zfill(6)
    digits = _digits(value)
    if digits is None or digits == "0":
        return None
    if len(digits) >= 7:
        return digits.zfill(8)
    return digits.zfill(6)


def opeid6_from_opeid8(opeid8: str | None) -> str | None:
    if not opeid8:
        return None
    if len(opeid8) < 6:
        return opeid8.zfill(6)
    return opeid8[:6]
