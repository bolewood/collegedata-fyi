"""Join FSA OPEIDs to in-scope directory school_id values.

The matcher is shared by the M0 report and the M1 loader. Identity is
stamped on facts at load time; the current view does not rematch.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from tools.fsa.opeid import normalize_opeid8, opeid6_from_opeid8, restore_fsa_opeid
from tools.fsa.parse import FsaRow


@dataclass(frozen=True)
class DirectoryRow:
    ipeds_id: str
    school_id: str
    school_name: str
    in_scope: bool
    main_campus: bool | None
    opeid: str | None
    opeid6: str | None


@dataclass(frozen=True)
class MatchResult:
    opeid: str
    school_id: str | None
    ipeds_id: str | None
    match_kind: str
    reason: str


@dataclass(frozen=True)
class CollapseResult:
    kept: tuple[MatchResult, ...]
    omitted_school_ids: tuple[str, ...]
    collisions_before_collapse: tuple[str, ...]


def directory_from_scorecard(
    *,
    ipeds_id: str,
    school_id: str,
    school_name: str,
    in_scope: bool,
    main_campus: bool | None,
    scorecard_opeid: Any,
) -> DirectoryRow:
    opeid = normalize_opeid8(scorecard_opeid)
    return DirectoryRow(
        ipeds_id=ipeds_id,
        school_id=school_id,
        school_name=school_name,
        in_scope=in_scope,
        main_campus=main_campus,
        opeid=opeid,
        opeid6=opeid6_from_opeid8(opeid),
    )


def index_directory(rows: Iterable[DirectoryRow]) -> tuple[dict[str, list[DirectoryRow]], dict[str, list[DirectoryRow]]]:
    by_opeid8: dict[str, list[DirectoryRow]] = defaultdict(list)
    by_opeid6_main: dict[str, list[DirectoryRow]] = defaultdict(list)
    for row in rows:
        if not row.in_scope:
            continue
        if row.opeid:
            by_opeid8[row.opeid].append(row)
        if row.opeid6 and row.main_campus is True:
            by_opeid6_main[row.opeid6].append(row)
    return by_opeid8, by_opeid6_main


def _unique(rows: list[DirectoryRow]) -> DirectoryRow | None:
    school_ids = {row.school_id for row in rows}
    if len(school_ids) == 1:
        return rows[0]
    return None


def match_fsa_row(
    fsa_opeid: str,
    by_opeid8: Mapping[str, list[DirectoryRow]],
    by_opeid6_main: Mapping[str, list[DirectoryRow]],
) -> MatchResult:
    key = restore_fsa_opeid(fsa_opeid) or fsa_opeid
    if len(key) == 8:
        hits = list(by_opeid8.get(key, ()))
        unique = _unique(hits)
        if unique:
            return MatchResult(key, unique.school_id, unique.ipeds_id, "exact_8", "exact")
        if hits:
            return MatchResult(key, None, None, "unmatched", "ambiguous_opeid8")
        # Fall through to 6-digit main rollup for unmatched 8-digit keys.
        opeid6 = opeid6_from_opeid8(key)
    else:
        opeid6 = key.zfill(6) if len(key) < 6 else key[:6]

    mains = list(by_opeid6_main.get(opeid6 or "", ()))
    unique = _unique(mains)
    if unique:
        return MatchResult(key, unique.school_id, unique.ipeds_id, "rollup_6", "main_opeid6")
    if not mains:
        return MatchResult(key, None, None, "unmatched", "no_in_scope_main")
    return MatchResult(key, None, None, "unmatched", "ambiguous_main")


def match_fsa_rows(
    fsa_rows: Iterable[FsaRow],
    directory_rows: Iterable[DirectoryRow],
) -> list[MatchResult]:
    by_opeid8, by_opeid6_main = index_directory(directory_rows)
    return [
        match_fsa_row(row.opeid, by_opeid8, by_opeid6_main)
        for row in fsa_rows
    ]


def collapse_to_school_id(matches: Iterable[MatchResult]) -> CollapseResult:
    """One row per school_id. Prefer an exact 8-digit match; omit multi-rollup."""
    by_school: dict[str, list[MatchResult]] = defaultdict(list)
    unmatched: list[MatchResult] = []
    for match in matches:
        if match.school_id:
            by_school[match.school_id].append(match)
        else:
            unmatched.append(match)

    collisions = tuple(sorted(sid for sid, rows in by_school.items() if len(rows) > 1))
    kept: list[MatchResult] = list(unmatched)
    omitted: list[str] = []
    for school_id, rows in by_school.items():
        exact = [row for row in rows if row.match_kind == "exact_8"]
        if len(exact) == 1:
            kept.append(exact[0])
            continue
        if len(exact) > 1:
            omitted.append(school_id)
            continue
        if len(rows) == 1:
            kept.append(rows[0])
            continue
        omitted.append(school_id)
    return CollapseResult(
        kept=tuple(kept),
        omitted_school_ids=tuple(sorted(omitted)),
        collisions_before_collapse=collisions,
    )
