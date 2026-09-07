"""Derive CDS B1 All unit_load gender totals from FT + PT components.

2023-24 / 2024-25 (and 2025-26) schemas leave All undergrad/grad gender
fields without AcroForm pdf_tags, so Tier 2 never reads them. Schools also
often leave the All XLSX cells blank while FT/PT are filled. CDS defines
All = FT + PT per gender, so deriving missing All cells is safe.
"""

from __future__ import annotations

from typing import Any


def _as_int(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("value")
    if raw is None:
        return None
    try:
        return int(float(str(raw).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _set_derived(values: dict[str, Any], qn: str, total: int) -> None:
    existing = values.get(qn)
    if isinstance(existing, dict):
        values[qn] = {
            **existing,
            "value": str(total),
            "derived_from": "b1_ft_pt_sum",
        }
    else:
        values[qn] = {
            "value": str(total),
            "source": "b1_derive_totals",
            "derived_from": "b1_ft_pt_sum",
        }


def _index_total_fields(schema_fields: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """Map (student_group, unit_load, gender) → question_number for Total/All rows."""
    out: dict[tuple[str, str, str], str] = {}
    for field in schema_fields:
        qn = str(field.get("question_number") or "")
        if not qn.startswith("B."):
            continue
        try:
            n = int(qn.split(".", 1)[1])
        except ValueError:
            continue
        if not (101 <= n <= 195):
            continue
        if field.get("category") not in (None, "All"):
            # Still allow category All only for enrollment totals.
            if field.get("category") != "All":
                continue
        cohort = str(field.get("cohort") or "")
        if not cohort.startswith("Total"):
            continue
        student_group = str(field.get("student_group") or "")
        unit_load = str(field.get("unit_load") or "")
        gender = str(field.get("gender") or "")
        if student_group not in {"Undergraduates", "Graduates", "All Students"}:
            continue
        if unit_load not in {"FT", "PT", "All"}:
            continue
        if gender in {"", "All"}:
            continue
        out[(student_group, unit_load, gender)] = qn
    return out


def apply_b1_derived_all_totals(
    values: dict[str, Any],
    schema_fields: list[dict[str, Any]] | None = None,
) -> int:
    """Fill missing All gender totals in ``values``. Returns count added.

    Never overwrites an existing All value. When ``schema_fields`` is omitted,
    uses the 2023-24/2024-25 interleaved question numbers.
    """
    added = 0
    if schema_fields:
        index = _index_total_fields(schema_fields)
        genders = sorted({g for (_sg, _ul, g) in index})
        for student_group in ("Undergraduates", "Graduates"):
            for gender in genders:
                all_qn = index.get((student_group, "All", gender))
                if not all_qn or _as_int(values.get(all_qn)) is not None:
                    continue
                ft_n = _as_int(values.get(index.get((student_group, "FT", gender), "")))
                pt_n = _as_int(values.get(index.get((student_group, "PT", gender), "")))
                if ft_n is None or pt_n is None:
                    continue
                _set_derived(values, all_qn, ft_n + pt_n)
                added += 1

        for gender in genders:
            all_qn = index.get(("All Students", "All", gender))
            if not all_qn or _as_int(values.get(all_qn)) is not None:
                continue
            ug_n = _as_int(values.get(index.get(("Undergraduates", "All", gender), "")))
            gr_n = _as_int(values.get(index.get(("Graduates", "All", gender), "")))
            if ug_n is None or gr_n is None:
                continue
            _set_derived(values, all_qn, ug_n + gr_n)
            added += 1
        return added

    # Fallback pairs for 2023-24 / 2024-25 interleaved schemas.
    pairs = [
        # undergrad All = FT + PT
        ("B.149", "B.121", "B.145"),
        ("B.150", "B.122", "B.146"),
        ("B.151", "B.123", "B.147"),
        ("B.152", "B.124", "B.148"),
        # graduate All = FT + PT
        ("B.185", "B.165", "B.181"),
        ("B.186", "B.166", "B.182"),
        ("B.187", "B.167", "B.183"),
        ("B.188", "B.168", "B.184"),
    ]
    for all_qn, ft_qn, pt_qn in pairs:
        if _as_int(values.get(all_qn)) is not None:
            continue
        ft_n = _as_int(values.get(ft_qn))
        pt_n = _as_int(values.get(pt_qn))
        if ft_n is None or pt_n is None:
            continue
        _set_derived(values, all_qn, ft_n + pt_n)
        added += 1

    all_student_pairs = [
        ("B.189", "B.149", "B.185"),
        ("B.190", "B.150", "B.186"),
        ("B.191", "B.151", "B.187"),
        ("B.192", "B.152", "B.188"),
    ]
    for all_qn, ug_qn, gr_qn in all_student_pairs:
        if _as_int(values.get(all_qn)) is not None:
            continue
        ug_n = _as_int(values.get(ug_qn))
        gr_n = _as_int(values.get(gr_qn))
        if ug_n is None or gr_n is None:
            continue
        _set_derived(values, all_qn, ug_n + gr_n)
        added += 1
    return added
