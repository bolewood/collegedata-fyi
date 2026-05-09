"""Curated IPEDS fact mapping for the PRD 021 federal baseline."""

from __future__ import annotations

from dataclasses import dataclass


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

