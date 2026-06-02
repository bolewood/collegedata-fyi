"""Curated IPEDS fact mapping for the PRD 021 federal baseline."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Any


@dataclass(frozen=True)
class FactMapping:
    field_key: str
    field_label: str
    table_name: str
    var_name: str
    value_kind: str
    display_group: str
    definition_alignment: str
    unit: str | None = None
    cohort: str | None = None
    population: str | None = None
    definition_note: str | None = None
    public_visible: bool = True


MVP_FACT_MAPPINGS: tuple[FactMapping, ...] = (
    FactMapping("institution_name", "Institution name", "HD2024", "INSTNM", "text", "Identity", "direct"),
    FactMapping("city", "City", "HD2024", "CITY", "text", "Identity", "direct"),
    FactMapping("state", "State", "HD2024", "STABBR", "text", "Identity", "direct"),
    FactMapping("sector", "IPEDS sector", "HD2024", "SECTOR", "label", "Identity", "context_only"),
    FactMapping("control", "Control", "HD2024", "CONTROL", "label", "Identity", "context_only"),
    FactMapping("institution_level", "Institution level", "HD2024", "ICLEVEL", "label", "Identity", "context_only"),
    FactMapping("highest_offering", "Highest level of offering", "HD2024", "HLOFFER", "label", "Identity", "context_only"),
    FactMapping("degree_granting_status", "Degree-granting status", "HD2024", "DEGGRANT", "label", "Identity", "context_only"),
    FactMapping("locale", "Locale", "HD2024", "LOCALE", "label", "Identity", "context_only"),
    FactMapping("institution_size", "Institution size category", "HD2024", "INSTSIZE", "label", "Identity", "context_only"),
    FactMapping("open_admissions_policy", "Open admissions policy", "IC2024", "OPENADMP", "label", "Admissions", "context_only"),
    FactMapping("applicants_total", "Applicants total", "ADM2024", "APPLCN", "number", "Admissions", "near", population="first-time degree/certificate-seeking undergraduates"),
    FactMapping("admissions_total", "Admissions total", "ADM2024", "ADMSSN", "number", "Admissions", "near", population="first-time degree/certificate-seeking undergraduates"),
    FactMapping("enrolled_total", "Enrolled total", "ADM2024", "ENRLT", "number", "Admissions", "near", population="first-time degree/certificate-seeking undergraduates"),
    FactMapping("enrolled_full_time", "Enrolled full time", "ADM2024", "ENRLFT", "number", "Admissions", "near", population="first-time degree/certificate-seeking undergraduates"),
    FactMapping("admit_rate_total", "Admit rate", "DRVADM2024", "DVADM01", "number", "Admissions", "near", unit="percent"),
    FactMapping("yield_rate_total", "Yield rate", "DRVADM2024", "DVADM04", "number", "Admissions", "near", unit="percent"),
    FactMapping("sat_submit_rate", "SAT submit rate", "ADM2024", "SATPCT", "number", "Admissions testing", "near", unit="percent"),
    FactMapping("act_submit_rate", "ACT submit rate", "ADM2024", "ACTPCT", "number", "Admissions testing", "near", unit="percent"),
    FactMapping("sat_ebrw_p25", "SAT EBRW 25th percentile", "ADM2024", "SATVR25", "number", "Admissions testing", "near"),
    FactMapping("sat_ebrw_p50", "SAT EBRW 50th percentile", "ADM2024", "SATVR50", "number", "Admissions testing", "near"),
    FactMapping("sat_ebrw_p75", "SAT EBRW 75th percentile", "ADM2024", "SATVR75", "number", "Admissions testing", "near"),
    FactMapping("sat_math_p25", "SAT math 25th percentile", "ADM2024", "SATMT25", "number", "Admissions testing", "near"),
    FactMapping("sat_math_p50", "SAT math 50th percentile", "ADM2024", "SATMT50", "number", "Admissions testing", "near"),
    FactMapping("sat_math_p75", "SAT math 75th percentile", "ADM2024", "SATMT75", "number", "Admissions testing", "near"),
    FactMapping("act_composite_p25", "ACT composite 25th percentile", "ADM2024", "ACTCM25", "number", "Admissions testing", "near"),
    FactMapping("act_composite_p50", "ACT composite 50th percentile", "ADM2024", "ACTCM50", "number", "Admissions testing", "near"),
    FactMapping("act_composite_p75", "ACT composite 75th percentile", "ADM2024", "ACTCM75", "number", "Admissions testing", "near"),
    FactMapping("undergraduate_enrollment", "Undergraduate enrollment", "DRVEF2024", "EFUG", "number", "Enrollment", "near"),
    FactMapping("graduate_enrollment", "Graduate enrollment", "DRVEF2024", "EFGRAD", "number", "Enrollment", "near"),
    FactMapping("total_enrollment", "Total enrollment", "DRVEF2024", "ENRTOT", "number", "Enrollment", "near"),
    FactMapping("full_time_undergraduate_enrollment", "Full-time undergraduate enrollment", "DRVEF2024", "EFUGFT", "number", "Enrollment", "near"),
    FactMapping("part_time_undergraduate_enrollment", "Part-time undergraduate enrollment", "DRVEF2024", "EFUGPT", "number", "Enrollment", "near"),
    FactMapping("retention_rate_full_time", "Full-time retention rate", "EF2024D", "RET_PCF", "number", "Outcomes", "near", unit="percent", cohort="first-time full-time students"),
    FactMapping("retention_rate_part_time", "Part-time retention rate", "EF2024D", "RET_PCP", "number", "Outcomes", "near", unit="percent", cohort="first-time part-time students"),
    FactMapping("student_faculty_ratio", "Student-faculty ratio", "EF2024D", "STUFACR", "number", "Academics", "context_only"),
    FactMapping("graduation_rate_total_150pct", "Graduation rate, 150% time", "DRVGR2024", "GRRTTOT", "number", "Outcomes", "near", unit="percent"),
    FactMapping("transfer_out_rate_total", "Transfer-out rate", "DRVGR2024", "TRRTTOT", "number", "Outcomes", "near", unit="percent"),
    FactMapping("bachelor_4yr_grad_rate", "Bachelor graduation rate, 4 years", "DRVGR2024", "GBA4RTT", "number", "Outcomes", "near", unit="percent"),
    FactMapping("bachelor_5yr_grad_rate", "Bachelor graduation rate, 5 years", "DRVGR2024", "GBA5RTT", "number", "Outcomes", "near", unit="percent"),
    FactMapping("bachelor_6yr_grad_rate", "Bachelor graduation rate, 6 years", "DRVGR2024", "GBA6RTT", "number", "Outcomes", "near", unit="percent"),
    FactMapping("tuition_in_state", "In-state tuition", "COST1_2024", "TUITION2", "number", "Costs", "context_only", unit="usd"),
    FactMapping("tuition_out_of_state", "Out-of-state tuition", "COST1_2024", "TUITION3", "number", "Costs", "context_only", unit="usd"),
    FactMapping("fees_in_state", "In-state required fees", "COST1_2024", "FEE2", "number", "Costs", "context_only", unit="usd"),
    FactMapping("fees_out_of_state", "Out-of-state required fees", "COST1_2024", "FEE3", "number", "Costs", "context_only", unit="usd"),
    FactMapping("room_and_board_on_campus", "On-campus room and board", "COST1_2024", "RMBRDAMT", "number", "Costs", "context_only", unit="usd"),
    FactMapping("total_price_in_state_on_campus", "Total price, in-state on campus", "DRVCOST2024", "CINSON", "number", "Costs", "context_only", unit="usd"),
    FactMapping("total_price_out_of_state_on_campus", "Total price, out-of-state on campus", "DRVCOST2024", "COTSON", "number", "Costs", "context_only", unit="usd"),
    FactMapping("any_aid_rate", "Any aid rate", "SFA2324", "ANYAIDP", "number", "Financial aid", "context_only", unit="percent"),
    FactMapping("federal_grant_rate", "Federal grant aid rate", "SFA2324", "FGRNT_P", "number", "Financial aid", "context_only", unit="percent"),
    FactMapping("federal_grant_average", "Average federal grant aid", "SFA2324", "FGRNT_A", "number", "Financial aid", "context_only", unit="usd"),
    FactMapping("pell_grant_rate", "Pell grant rate", "SFA2324", "PGRNT_P", "number", "Financial aid", "context_only", unit="percent"),
    FactMapping("pell_grant_average", "Average Pell grant", "SFA2324", "PGRNT_A", "number", "Financial aid", "context_only", unit="usd"),
    FactMapping("federal_loan_rate", "Federal loan rate", "SFA2324", "LOAN_P", "number", "Financial aid", "context_only", unit="percent"),
    FactMapping("federal_loan_average", "Average federal loan", "SFA2324", "LOAN_A", "number", "Financial aid", "context_only", unit="usd"),
    FactMapping("bachelor_degrees_awarded", "Bachelor's degrees awarded", "DRVC2024", "BASDEG", "number", "Completions", "context_only"),
    FactMapping("master_degrees_awarded", "Master's degrees awarded", "DRVC2024", "MASDEG", "number", "Completions", "context_only"),
    FactMapping("doctor_degrees_awarded", "Doctor's degrees awarded", "DRVC2024", "DOCDEGRS", "number", "Completions", "context_only"),
)


def fact_mappings_for_data_year(data_year: int) -> tuple[FactMapping, ...]:
    """Return the curated fact mappings with IPEDS table names for a data year."""
    return tuple(replace(mapping, table_name=table_name_for_data_year(mapping.table_name, data_year)) for mapping in MVP_FACT_MAPPINGS)


def resolve_fact_mappings_for_columns(
    mappings: tuple[FactMapping, ...],
    columns: list[Any],
) -> tuple[FactMapping, ...]:
    """Resolve mapped variables to the table names present in a release.

    IPEDS occasionally moves stable variables into year-specific table splits,
    especially student financial aid tables such as SFA1819_P1 or SFA2223_P2.
    """
    available = {(column.table_name.upper(), column.var_name.upper()) for column in columns}
    tables_by_var: dict[str, list[str]] = {}
    for column in columns:
        table_name = column.table_name.upper()
        var_name = column.var_name.upper()
        tables_by_var.setdefault(var_name, [])
        if table_name not in tables_by_var[var_name]:
            tables_by_var[var_name].append(table_name)

    resolved: list[FactMapping] = []
    for mapping in mappings:
        table_name = mapping.table_name.upper()
        var_name = mapping.var_name.upper()
        if (table_name, var_name) in available:
            resolved.append(mapping)
            continue

        candidate = _best_table_candidate(table_name, var_name, tables_by_var.get(var_name, []))
        resolved.append(replace(mapping, table_name=candidate) if candidate else mapping)
    return tuple(resolved)


def table_name_for_data_year(table_name: str, data_year: int) -> str:
    """Translate the 2024 baseline table names into another IPEDS data year.

    Most IPEDS table names use the data year as a suffix. Student financial aid
    tables use the aid-year pair instead, so 2024 maps to SFA2324.
    """
    upper = table_name.upper()
    if upper.startswith("SFA"):
        return f"SFA{(data_year - 1) % 100:02d}{data_year % 100:02d}"
    if upper.startswith("COST1_"):
        return f"COST1_{data_year}"
    if upper.startswith("EF") and upper.endswith("D"):
        return f"EF{data_year}D"

    for prefix in ("DRVCOST", "DRVADM", "DRVEF", "DRVGR", "DRVC", "ADM", "HD", "IC"):
        if upper.startswith(prefix):
            return f"{prefix}{data_year}"
    return upper


def _best_table_candidate(table_name: str, var_name: str, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    if table_name.startswith("SFA"):
        if table_name == "SFA2223" and "SFA2223_P2" in candidates:
            return "SFA2223_P1"
        sfa_candidates = [candidate for candidate in candidates if candidate.startswith(table_name)]
        if sfa_candidates:
            return sorted(sfa_candidates)[0]
    if table_name.startswith("COST1_"):
        year = table_name.rsplit("_", 1)[-1]
        preferred = f"IC{year}_AY" if var_name in {"TUITION2", "TUITION3", "FEE2", "FEE3"} else f"IC{year}"
        if preferred in candidates:
            return preferred
    if table_name.startswith("DRVCOST"):
        year = table_name.removeprefix("DRVCOST")
        preferred = f"DRVIC{year}"
        if preferred in candidates:
            return preferred
    prefix = "".join(char for char in table_name if not char.isdigit()).rstrip("_")
    prefix_candidates = [candidate for candidate in candidates if candidate.startswith(prefix)]
    if len(prefix_candidates) == 1:
        return prefix_candidates[0]
    return None
