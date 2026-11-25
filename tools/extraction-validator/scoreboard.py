"""
Extraction scoreboard: one corpus-level measure of what the site serves.

Read-only. For every live, extracted document of the chosen CDS years it takes
the extraction the browser projection serves (not the newest artifact) and
reports, by CDS year and source format:

  1. Federal match on admissions. C1 applied, admitted and enrolled against
     the IPEDS figures for the same fall: within 2%, blank, or present but
     different.
  2. Coverage. Median and 10th-percentile field count per served extraction.
  3. Internal consistency. The sums the form defines (B1 totals, C1 by sex
     against the total, H1 grant and self-help totals): pass, fail, or not
     checkable.
  4. Fix reach. Served extractions by producer and version, how many the
     current cleaner has read (a re-clean that reads the same values writes
     nothing, so the artifact's version alone does not say), documents a
     worker guard is holding, and documents hidden behind a quality flag.

Where the numbers come from:

  - Years the projection covers (2024-25 on): `cds_fields` and
    `school_browser_rows`, which are what the site reads.
  - Earlier years: the artifact the projection's own ordering
    (`project_browser_data.sort_base_candidates`) would pick, read from
    `cds_artifacts` with only the keys needed. These reads are throttled and
    cached by artifact id under the output directory, so a second run reads
    only what changed. The projection's cross-field sanity rules are applied
    to the values. Applied/admitted/enrolled is the sum of the rows by sex
    when both men and women were read, else the printed total, which is the
    order the projection uses for the 2024-25 form. An LLM gap-fill artifact,
    which the projection would merge in, is not read; the output says how
    many documents that leaves out (none in 2023-24 as of November 2026).
  - Federal figures: `ipeds_facts` for the fall the CDS year starts in.
    Documents filed for one campus or unit of an institution are left out of
    the federal comparison, because IPEDS reports the whole institution.

The year page of a school shows the newest canonical artifact, not the
projection's pick. Section 4 counts the documents where the two differ.

The production database host is small. Artifact reads go one at a time, a few
seconds apart, and stop while the host is short of memory (checked only when
the service-role key is available). Never run two copies at once.

Usage:
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/scoreboard.py

    # print deltas against an earlier run
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/scoreboard.py \\
        --compare scratch/extraction-scoreboard/scoreboard-<earlier>.json

Writes `scoreboard-<UTC timestamp>.json` and `.md` to `--out-dir`
(default `scratch/extraction-scoreboard/`) and prints the Markdown.

PRD 040 (the public Data quality page). The run JSON is `run_format: 3`.
Format 2 added the manifest of every document (year, format, status, flag, removed),
`federal_left_out`, `forms`, the current-year `renewal` block (computed by
`tools/ops/discovery_renewal.py`) and `sum_check_version: 2`, which splits a
failing enrollment or admissions sum into off by under 2% of its printed total
and off by more. `--compare` against an earlier version notes the switch and
shows no deltas for those columns. Format 3 keeps the raw inputs of PRD 040's
"Later" items on every document and changes no table: `ipeds_id` and
`source_sha256` (so a file filed under two federal records can be found),
`federal_values` (our number and the exact IPEDS figure for applied, admitted, enrolled),
`sections` (stored fields per CDS section letter by `value_status`; the counts
add up to `fields`) and `federal_extra` (our B1 total undergraduates and G1
tuition beside IPEDS fall undergraduate enrollment and tuition, unjudged).
`--public` needs a format 3 run (format 2 has no `federal_values`, so it cannot give the size split).

    # public aggregates from one saved run: reads that file only, no database
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/scoreboard.py \\
        --public scratch/extraction-scoreboard/scoreboard-<ts>.json
    # -> web/src/data/data-quality/<YYYY-MM-DD>.json

    # earlier years (staged, not yet run in production): see "Earlier years" in
    # tools/extraction-validator/README.md for the commands, throttle, sizing and resume
    #   --years 2022-23            (first slice; not publishable)
    #   --years 2019-20 ... 2025-26   (publishable: --public needs the three current years too)

    # the near-miss split of a saved run (no database)
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/scoreboard.py \\
        --from-json scratch/extraction-scoreboard/scoreboard-<ts>.json --report-near-miss
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import glob
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, NoReturn, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "browser_backend"))
sys.path.insert(0, str(REPO_ROOT))
import project_browser_data as projection  # noqa: E402
from tools.ops import discovery_renewal  # noqa: E402  (one copy of the renewal mechanism)

DEFAULT_YEARS = ("2023-24", "2024-25", "2025-26")
DEFAULT_OUT_DIR = REPO_ROOT / "scratch" / "extraction-scoreboard"
DEFAULT_SUMMARIES = str(REPO_ROOT / "scratch" / "extraction-drain" / "local" / "*.summary.json")
TIER4 = "tier4_docling"
FEDERAL_TOLERANCE = Decimal("0.02")
FEDERAL_KEYS = {
    "applied": "applicants_total",
    "admitted": "admissions_total",
    "enrolled": "enrolled_total",
}
# Raw federal inputs kept for PRD 040's "Later" items (never classified in the
# run). Every IPEDS figure is stored with the `data_year` it came from.
# Fall enrollment: IPEDS DRVEF EFUG, total undergraduates for the fall that
# opens the CDS year Y-(Y+1), so data_year Y, the same as C1. CDS B1's "Total
# all undergraduates" is B.193 on the 2023-24 and 2024-25 forms, B.176 on 2025-26.
# Tuition: IPEDS COST1_<y> (IC<y>_AY) TUITION2 / TUITION3 are full-time
# undergraduate charges for academic year y-(y+1). CDS G1 asks for the
# FOLLOWING year's costs: the 2023-24 template's G1 says "FULL 2024-2025
# academic year", 2024-25 says 2025-2026, 2025-26 says 2026-2027 (its G.002
# names 2026-2027). So tuition on the CDS year Y-(Y+1) form is held against
# data_year Y+1. For 2025-26 that is 2026, which may not be loaded: `federal`
# is then null. 2024 and 2025 are fetched anyway for the fall figures, so only
# the boundary data year is a new request (tuition keys only).
# Uncertain, stored not decided: whether IPEDS tuition matches the first-year
# or the all-undergraduates column (both kept), and that CDS tuition excludes
# required fees as TUITION2/3 do (fees are separate rows, G.111, on the form).
ENROLLMENT_KEY = "undergraduate_enrollment"
TUITION_KEYS = ("tuition_in_state", "tuition_out_of_state")
# Form years whose G1 ids (G.101 to G.110) were checked against the schema files.
TUITION_FORM_YEARS = ("2023-24", "2024-25", "2025-26")
# name -> (CDS field, IPEDS field_key). A private institution's single tuition
# row is held against in-state tuition (IPEDS reports one figure for both).
TUITION_CANDIDATES = {
    "g1_private_undergraduates": ("G.102", "tuition_in_state"),
    "g1_in_state_undergraduates": ("G.108", "tuition_in_state"),
    "g1_out_of_state_undergraduates": ("G.109", "tuition_out_of_state"),
    "g1_private_first_year": ("G.101", "tuition_in_state"),
    "g1_in_state_first_year": ("G.104", "tuition_in_state"),
    "g1_out_of_state_first_year": ("G.105", "tuition_out_of_state"),
}
# Quality flags. Flagged documents are left out of sections 1 to 3 and counted
# in section 4. `blank_template` hides a document everywhere; the other two
# keep it out of the school browser's figures and the acceptance history.
HIDDEN_FLAGS = ("blank_template", "low_coverage", "wrong_file")
RELEASE_RANK = {"final": 0, "provisional": 1, "preliminary": 2}
PAGE_SIZE = 1000

# PRD 040. The run JSON is versioned so `--public` can refuse a run that lacks
# what it needs. Format 2 adds `manifest`, `federal_left_out`, `forms`,
# `renewal`, and near-miss sum outcomes (`sum_check_version` 2). Format 3 adds,
# per document, `ipeds_id`, `source_sha256`, `federal_values`, `sections` and
# `federal_extra`. `--public` needs 3: public format 2 splits Table B's "differs"
# by size, which needs `federal_values`. A format 2 run is refused, not written as
# public format 1: a snapshot quietly missing the split would look like one that has it.
RUN_FORMAT = 3
PUBLIC_RUN_FORMATS = (3,)
SUM_CHECK_VERSION = 2
# Public format 2 adds `federal.differs_2_to_10pct` and `federal.differs_over_10pct`.
# Public format 3 adds `sections` per year (fields stored and usable answers by CDS section A to J).
PUBLIC_FORMAT = 3
# `value_status` values the projection writes (project_browser_data.parse_field_value). A usable
# answer is a `reported` one: a value a reader can use. `parse_error` is a cell we could not read
# as the kind of value its question takes, `not_applicable` is a school's "N/A" (a real answer,
# but nothing to use) and `missing` an empty cell. A status outside this list stops `--public`.
VALUE_STATUSES = ("reported", "not_applicable", "parse_error", "missing")
USABLE_STATUS = "reported"
DEFAULT_PUBLIC_DIR = REPO_ROOT / "web" / "src" / "data" / "data-quality"
SCHEMA_DIR = REPO_ROOT / "schemas"
# A failing enrollment or admissions sum is a near miss when its gap is under
# this share of its printed total (strictly under: exactly 2% is "off by more").
NEAR_MISS_SHARE = Decimal("0.02")
NEAR_MISS_TABLES = ("B1", "C1")


# ---------------------------------------------------------------------------
# The sums the form defines
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SumCheck:
    """`total` should equal the sum of one group of rows.

    `groups` are alternatives; the first whose `required` rows were all read
    is used, and its other rows count as 0 when blank. With `required` empty,
    at least one row of the group must have been read.
    """
    table: str
    name: str
    total: str
    groups: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]  # ((rows, required), ...)
    tolerance: int = 0


def _c(*ids: int) -> tuple[str, ...]:
    return tuple(f"C.{i}" for i in ids)


def _b(*ids: int) -> tuple[str, ...]:
    return tuple(f"B.{i}" for i in ids)


def _h(*ids: int) -> tuple[str, ...]:
    return tuple(f"H.{i}" for i in ids)


def _h1_checks(first_need: int, first_non_need: int) -> list[SumCheck]:
    """H1 in every year: four grant rows and a total, three self-help rows and
    a total in the need-based column; the non-need column has no Federal
    Work-Study row. Dollar totals may be off by rounding."""
    n, x = first_need, first_non_need
    return [
        SumCheck("H1", "need-based grants", f"H.{n + 4}", ((_h(n, n + 1, n + 2, n + 3), ()),), 5),
        SumCheck("H1", "need-based self-help", f"H.{n + 8}", ((_h(n + 5, n + 6, n + 7), ()),), 5),
        SumCheck("H1", "non-need grants", f"H.{x + 4}", ((_h(x, x + 1, x + 2, x + 3), ()),), 5),
        SumCheck("H1", "non-need self-help", f"H.{x + 7}", ((_h(x + 5, x + 6), ()),), 5),
    ]


def _older_form_checks(with_unknown: bool) -> list[SumCheck]:
    """2023-24 and 2024-25 share one numbering; 2024-25 adds an Unknown
    gender row to each block (the fourth id of every group of four)."""
    def rows(ids: tuple[int, ...], unknown: tuple[int, ...], prefix: Callable[..., tuple[str, ...]]):
        return prefix(*(ids + (unknown if with_unknown else ())))

    return [
        SumCheck("C1", "applied by sex", "C.117", ((rows((101, 102, 103), (104,), _c), _c(101, 102)),)),
        SumCheck("C1", "admitted by sex", "C.118", ((rows((105, 106, 107), (108,), _c), _c(105, 106)),)),
        SumCheck("C1", "enrolled by sex", "C.119",
                 ((rows((109, 110, 111, 112, 113, 114), (115, 116), _c), _c(109, 111)),)),
        SumCheck("B1", "undergraduates by sex", "B.193", ((rows((149, 150, 151), (152,), _b), _b(149, 150)),)),
        SumCheck("B1", "undergraduate + graduate", "B.195", ((_b(193, 194), _b(193)),)),
        *_h1_checks(106, 118),
    ]


SUM_CHECKS: dict[str, list[SumCheck]] = {
    "2023-24": _older_form_checks(with_unknown=False),
    "2024-25": _older_form_checks(with_unknown=True),
    "2025-26": [
        SumCheck("C1", "applied by sex", "C.116", ((_c(101, 102, 103), _c(101, 102)),)),
        SumCheck("C1", "admitted by sex", "C.117", ((_c(104, 105, 106), _c(104, 105)),)),
        SumCheck("C1", "enrolled by sex", "C.118", (
            (_c(107, 108, 109), _c(107, 108)),
            (_c(110, 111, 112, 113, 114, 115), _c(110, 112)),
        )),
        SumCheck("B1", "undergraduates by sex", "B.176", (
            (_b(113, 138, 163), _b(113, 138)),
            (_b(106, 112, 131, 137, 156, 162), _b(106, 131)),
        )),
        SumCheck("B1", "undergraduate + graduate", "B.178", ((_b(176, 177), _b(176)),)),
        *_h1_checks(105, 117),
    ],
}
SUM_TABLES = ("B1", "C1", "H1")


def run_check_detail(check: SumCheck, numbers: dict[str, Decimal]) -> tuple[str, Optional[Decimal]]:
    """('pass' | 'fail' | 'nc', gap share).

    The share is a failing sum's gap as a fraction of its printed total, so
    enrollment and admissions can tell a small cell left out of the rows from
    a real miss. It is None unless the sum fails, and when the printed total
    is not positive (a gap cannot be a share of zero).

    A total of 0 beside rows that add to more is an unfilled auto-sum cell,
    which the projection also ignores: not checkable."""
    total = numbers.get(check.total)
    if total is None:
        return "nc", None
    for rows, required in check.groups:
        read = [numbers[r] for r in rows if r in numbers]
        if not read or any(r not in numbers for r in required):
            continue
        row_sum = sum(read, Decimal(0))
        if total == 0 and row_sum > 0:
            return "nc", None
        gap = abs(row_sum - total)
        if gap <= check.tolerance:
            return "pass", None
        return "fail", (gap / total if total > 0 else None)
    return "nc", None


def run_check(check: SumCheck, numbers: dict[str, Decimal]) -> str:
    """'pass', 'fail' or 'nc' (not checkable)."""
    return run_check_detail(check, numbers)[0]


def is_near_miss(check: SumCheck, share: Optional[Decimal]) -> bool:
    return check.table in NEAR_MISS_TABLES and share is not None and share < NEAR_MISS_SHARE


_OUTCOME_RANK = {"nc": 0, "pass": 1, "near": 2, "fail": 3}


def table_outcomes(schema_version: Optional[str], numbers: dict[str, Decimal],
                   tables: Iterable[str] = SUM_TABLES) -> dict[str, str]:
    """One outcome per table (`sum_check_version` 2).

    'pass': at least one sum could be checked and none missed. 'near'
    (B1 and C1 only): at least one missed, and every miss was under 2% of its
    printed total. 'fail': at least one missed by more (for H1, at all).
    'nc': nothing could be checked.

    `tables` are the tables the document's year has sums for (`forms_for`);
    the others stay 'nc' whatever the numbering says."""
    outcomes = {table: "nc" for table in SUM_TABLES}
    tables = set(tables)
    for check in SUM_CHECKS.get(schema_version or "", []):
        if check.table not in tables:
            continue
        result, share = run_check_detail(check, numbers)
        if result == "fail" and is_near_miss(check, share):
            result = "near"
        if _OUTCOME_RANK[result] > _OUTCOME_RANK[outcomes[check.table]]:
            outcomes[check.table] = result
    return outcomes


def printed_admissions(schema_version: Optional[str], numbers: dict[str, Decimal]) -> dict[str, Optional[int]]:
    """Applied/admitted/enrolled for a year the projection does not publish:
    the rows by sex when men and women were both read, else the printed
    total. This is the projection's order for the 2024-25 form, whose C1
    numbering the earlier forms share."""
    out: dict[str, Optional[int]] = {"applied": None, "admitted": None, "enrolled": None}
    for check in SUM_CHECKS.get(schema_version or "", []):
        if check.table != "C1":
            continue
        metric = check.name.split()[0]
        for rows, required in check.groups:
            if required and all(r in numbers for r in required):
                out[metric] = int(sum((numbers[r] for r in rows if r in numbers), Decimal(0)))
                break
        else:
            total = numbers.get(check.total)
            if total is not None and total > 0:
                out[metric] = int(total)
    return out


def classify_federal(cds: Optional[int], federal: Optional[Decimal]) -> Optional[str]:
    """'match', 'blank', 'different', or None when there is no federal figure."""
    if federal is None or federal <= 0:
        return None
    if cds is None:
        return "blank"
    return "match" if abs(Decimal(cds) - federal) <= FEDERAL_TOLERANCE * federal else "different"


def percentile(values: list[int], pct: float) -> Optional[int]:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * pct // 100))  # ceil
    return ordered[int(rank) - 1]


# ---------------------------------------------------------------------------
# Which artifact the projection serves, with as few reads as possible
# ---------------------------------------------------------------------------

def _true_key(row: dict[str, Any], expected: Optional[str], recency: int) -> tuple:
    return (
        0 if not expected or projection.artifact_schema_version(row) == expected else 1,
        1 if projection.artifact_schema_fallback_used(row) else 0,
        1 if projection.artifact_is_unusable_label_acroform(row) else 0,
        projection.BASE_PRODUCER_RANK.get(str(row.get("producer")), 99),
        recency,
    )


def _best_possible_key(row: dict[str, Any], expected: Optional[str], recency: int) -> tuple:
    column = row.get("schema_version")  # an empty column falls through to notes, as in the projection
    known_mismatch = bool(expected) and bool(column) and str(column) != expected
    return (1 if known_mismatch else 0, 0, 0,
            projection.BASE_PRODUCER_RANK.get(str(row.get("producer")), 99), recency)


def pick_served_artifact(
    candidates: list[dict[str, Any]],
    expected_schema_version: Optional[str],
    load_notes: Callable[[dict[str, Any]], dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """The row `projection.sort_base_candidates` would put first.

    The ordering needs three things stored inside `notes`. `candidates` carry
    only top-level columns; `load_notes(row)` returns the row with `notes`
    filled. Rows are loaded best-possible-first and loading stops once no
    unread row could beat the best one read.
    """
    base = [c for c in candidates if c.get("kind") == "canonical"
            and c.get("producer") in projection.BASE_PRODUCER_RANK]
    if not base:
        return None
    newest_first = sorted(base, key=lambda r: (str(r.get("created_at") or ""), str(r.get("id") or "")), reverse=True)
    recency = {str(r["id"]): i for i, r in enumerate(newest_first)}
    order = sorted(base, key=lambda r: _best_possible_key(r, expected_schema_version, recency[str(r["id"])]))
    best: Optional[tuple[tuple, dict[str, Any]]] = None
    for row in order:
        rid = str(row["id"])
        if best is not None and _best_possible_key(row, expected_schema_version, recency[rid]) >= best[0]:
            break
        loaded = load_notes(row)
        key = _true_key(loaded, expected_schema_version, recency[rid])
        if best is None or key < best[0]:
            best = (key, loaded)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Read-only HTTP
# ---------------------------------------------------------------------------

class Api:
    """GET-only PostgREST client with a pause between requests."""

    def __init__(self, url: str, key: str, min_free_mb: int, log: Callable[[str], None]):
        self.url = url.rstrip("/")
        self.key = key
        self.min_free_mb = min_free_mb
        self.log = log
        self.requests = 0

    def _open(self, request: urllib.request.Request) -> tuple[bytes, dict[str, str]]:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read(), dict(response.headers)
            except urllib.error.HTTPError as exc:
                if exc.code < 500 or attempt == 3:
                    raise
            except (urllib.error.URLError, http.client.HTTPException, OSError):
                if attempt == 3:
                    raise
            time.sleep(5 * (attempt + 1))
        raise RuntimeError("unreachable")

    def get(self, table: str, params: dict[str, str], pause: float = 0.0) -> list[dict[str, Any]]:
        """Every row matching `params`, a page of PAGE_SIZE at a time."""
        rows: list[dict[str, Any]] = []
        while True:
            query = urllib.parse.urlencode(
                {**params, "limit": str(PAGE_SIZE), "offset": str(len(rows))}, safe="(),.*:>-")
            request = urllib.request.Request(
                f"{self.url}/rest/v1/{table}?{query}",
                headers={"apikey": self.key, "Authorization": f"Bearer {self.key}"},
                method="GET",
            )
            body, _ = self._open(request)
            self.requests += 1
            page = json.loads(body)
            rows.extend(page)
            if pause:
                time.sleep(pause)
            if len(page) < PAGE_SIZE:
                return rows

    def check_page_size(self) -> None:
        """Paging stops at the first short page, so the server must really
        return PAGE_SIZE rows when that many exist."""
        query = urllib.parse.urlencode({"select": "field_id", "limit": str(PAGE_SIZE)})
        request = urllib.request.Request(
            f"{self.url}/rest/v1/cds_fields?{query}",
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}"}, method="GET",
        )
        got = len(json.loads(self._open(request)[0]))
        if got != PAGE_SIZE:
            raise SystemExit(f"The API returned {got} rows for a page of {PAGE_SIZE}; lower PAGE_SIZE to its row cap.")

    def free_mb(self) -> Optional[int]:
        """Host memory available, or None when it cannot be read."""
        token = base64.b64encode(f"service_role:{self.key}".encode()).decode()
        request = urllib.request.Request(
            f"{self.url}/customer/v1/privileged/metrics",
            headers={"Authorization": f"Basic {token}"}, method="GET",
        )
        try:
            body, _ = self._open(request)
        except Exception:
            return None
        match = re.search(rb"^node_memory_MemAvailable_bytes(?:\{[^}]*\})?\s+([0-9.e+]+)", body, re.M)
        return int(float(match.group(1)) / 1048576) if match else None

    def wait_for_memory(self) -> None:
        """Hold while the host is short of memory; give up after 15 minutes."""
        for _ in range(15):
            free = self.free_mb()
            if free is None or free >= self.min_free_mb:
                return
            self.log(f"  host has {free} MB free (< {self.min_free_mb}); waiting 60 s")
            time.sleep(60)
        raise SystemExit(
            f"Stopped: the database host stayed under {self.min_free_mb} MB free for 15 minutes. "
            "Artifacts read so far are cached; run again later."
        )


def chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


# ---------------------------------------------------------------------------
# Gathering
# ---------------------------------------------------------------------------

def fetch_documents(api: Api, years: tuple[str, ...]) -> list[dict[str, Any]]:
    return api.get("cds_manifest", {
        "select": "document_id,school_id,school_name,ipeds_id,sub_institutional,canonical_year,"
                  "source_format,extraction_status,data_quality_flag,removed_at,"
                  "source_url,cds_year,detected_year",
        "canonical_year": f"in.({','.join(years)})",
        "order": "document_id",
    })


def fetch_source_hashes(api: Api) -> dict[str, Optional[str]]:
    """`source_sha256` per live document. `cds_manifest` does not expose it,
    so this reads two columns (`id`, `source_sha256`) of every live
    `cds_documents` row (about six pages)."""
    return {
        row["id"]: row.get("source_sha256")
        for row in api.get("cds_documents", {
            "select": "id,source_sha256", "removed_at": "is.null", "order": "id",
        }, pause=0.2)
    }


def fetch_artifact_index(api: Api, document_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Top-level columns of every canonical artifact and LLM gap-fill
    artifact (`notes` is not touched)."""
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks(document_ids, 50):
        for row in api.get("cds_artifacts", {
            "select": "id,document_id,kind,producer,producer_version,schema_version,created_at",
            "or": f"(kind.eq.canonical,producer.eq.{projection.FALLBACK_PRODUCER})",
            "document_id": f"in.({','.join(chunk)})",
            "order": "id",
        }, pause=0.2):
            by_document[row["document_id"]].append(row)
    return by_document


def fetch_federal(api: Api, data_year: int, keys: tuple[str, ...]) -> dict[str, dict[str, Decimal]]:
    """The IPEDS facts named by `keys` for one `data_year`. For C1 that is the
    class entering in fall `data_year`. `ipeds_facts` keeps every year (the
    unified view keeps only each school's latest); a final release beats a
    provisional one."""
    best: dict[tuple[str, str], tuple[tuple, Decimal]] = {}
    for row in api.get("ipeds_facts", {
        "select": "ipeds_id,field_key,value_numeric,release_type,created_at",
        "field_key": f"in.({','.join(keys)})",
        "data_year": f"eq.{data_year}",
        "public_visible": "is.true",
        "order": "ipeds_id,field_key,release_type,created_at,release_id",
    }, pause=0.2):
        if row.get("value_numeric") is None:
            continue
        rank = (RELEASE_RANK.get(str(row.get("release_type")), 9), _descending(str(row.get("created_at") or "")))
        key = (str(row["ipeds_id"]), row["field_key"])
        if key not in best or rank < best[key][0]:
            best[key] = (rank, Decimal(str(row["value_numeric"])))
    facts: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for (ipeds_id, field_key), (_, value) in best.items():
        facts[ipeds_id][field_key] = value
    return facts


def _descending(text: str) -> tuple:
    """Sort key that puts the later string first."""
    return tuple(-ord(char) for char in text)


def numbers_from_values(values: dict[str, Any], schema_defs: dict[str, Any],
                        schema_version: Optional[str]) -> dict[str, Decimal]:
    """Reported numbers of an artifact's values as the projection would
    publish them: parsed the same way, and without the fields its cross-field
    sanity rules reject."""
    numbers: dict[str, Decimal] = {}
    for field_id, record in values.items():
        parsed = projection.parse_field_value(record, schema_defs.get(field_id))
        if parsed.value_status == "reported" and parsed.value_num is not None:
            numbers[field_id] = parsed.value_num
    for field_id in projection._sanity.implausible_fields(schema_version or "", numbers):
        numbers.pop(field_id, None)
    return numbers


def effective_statuses(values: dict[str, Any], schema_defs: dict[str, Any],
                       schema_version: Optional[str]) -> dict[str, str]:
    """{field id: value_status} of an artifact's values as `cds_fields` would hold them: the projection
    (`project_browser_data`, where it applies the cross-field sanity rules) publishes a value that fails a rule as
    `parse_error` and a loan average of 0 with no borrowers as `not_applicable`. A year that is not projected
    (2023-24) is read from its artifact here, so it must apply the same two downgrades or it would count those
    fields as usable. The runs made before this function (the 2026-11-25 run among them) counted 2023-24 usable
    answers with `parse_field_value` alone: 266 falsely usable fields in 149 2023-24 reports. It changed no
    published median (checked offline against the artifact cache), and the committed snapshot was not rebuilt.
    Not reproduced: the projection passes a metric and the year to `parse_field_value` for some fields."""
    parsed = {field_id: projection.parse_field_value(record, schema_defs.get(field_id))
              for field_id, record in values.items()}
    reported = {field_id: p.value_num for field_id, p in parsed.items()
                if p.value_status == "reported" and p.value_num is not None}
    implausible = projection._sanity.implausible_fields(schema_version or "", reported)
    no_borrowers = set(projection._sanity.averages_without_borrowers(
        schema_version or "", {k: v for k, v in reported.items() if k not in implausible}))
    return {field_id: ("parse_error" if field_id in implausible
                       else "not_applicable" if field_id in no_borrowers else p.value_status)
            for field_id, p in parsed.items()}


def section_counts(statuses: Iterable[tuple[str, str]]) -> dict[str, dict[str, int]]:
    """(field id, value_status) pairs -> {section letter: {status: count}}.
    The section is the id's prefix before the first `.` (`C.116` -> `C`)."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for field_id, status in statuses:
        counts[field_id.split(".", 1)[0]][status] += 1
    return {section: dict(sorted(counts[section].items())) for section in sorted(counts)}


def federal_extra(schema_version: Optional[str], numbers: dict[str, Decimal],
                  fall_facts: dict[str, Decimal], fall_year: int,
                  tuition_facts: dict[str, Decimal], tuition_year: int) -> dict[str, dict[str, Any]]:
    """Our number beside the IPEDS figure for the B1 and G1 checks, unjudged.
    `cds_field` is the field read (null on a form we have no ids for);
    `ours` is a string Decimal (dollars and head counts both), null when that
    field was not reported; `federal_data_year` is the IPEDS year looked up,
    whether or not it had a figure."""
    total = next((c.total for c in SUM_CHECKS.get(schema_version or "", [])
                  if c.table == "B1" and c.name == "undergraduates by sex"), None)
    candidates = {"b1_undergraduates": (total, ENROLLMENT_KEY, fall_facts, fall_year)}
    for name, (field_id, key) in TUITION_CANDIDATES.items():
        candidates[name] = (field_id if schema_version in TUITION_FORM_YEARS else None,
                            key, tuition_facts, tuition_year)
    return {
        name: {
            "cds_field": field_id,
            "ours": str(numbers[field_id]) if field_id in numbers else None,
            "federal_key": key,
            "federal": str(facts[key]) if key in facts else None,
            "federal_data_year": data_year,
        }
        for name, (field_id, key, facts, data_year) in candidates.items()
    }


def run_outcomes(pattern: str) -> Iterable[tuple[str, bool, str, str]]:
    """(run finished at, dry run, document id, action) for every document in
    every local worker run summary."""
    for path in glob.glob(pattern):
        try:
            summary = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(summary, dict):
            continue
        finished, dry_run = str(summary.get("finished_at") or ""), bool(summary.get("dry_run"))
        for record in summary.get("documents") or []:
            yield finished, dry_run, str(record.get("document_id")), str(record.get("action") or "")


def load_holds(pattern: str) -> dict[str, dict[str, str]]:
    """Latest worker outcome per document, kept only when that outcome is a
    guard keeping the previous extraction. Dry runs are left out: they apply
    no guards and write nothing, so they neither hold a document nor release it."""
    latest: dict[str, tuple[str, str]] = {}
    for finished, dry_run, document_id, action in run_outcomes(pattern):
        if not dry_run and (document_id not in latest or finished > latest[document_id][0]):
            latest[document_id] = (finished, action)
    return {
        document_id: {"at": finished, "guard": action.split(" (")[0], "action": action}
        for document_id, (finished, action) in latest.items()
        if "_regression" in action.split(" (")[0]
    }


_UNCHANGED_RE = re.compile(r"tier4_reclean_unchanged \(.*\bcleaner (\S+) ")


def load_unchanged(pattern: str) -> dict[str, dict[str, str]]:
    """Per document, the latest re-clean that read the stored values again and
    so wrote nothing, with the cleaner version that did. A dry run counts: it
    makes the same comparison. Whether the check still stands is the caller's
    question: it does while no artifact has been written since."""
    checked: dict[str, dict[str, str]] = {}
    for finished, _, document_id, action in run_outcomes(pattern):
        match = _UNCHANGED_RE.search(action)
        if match and (document_id not in checked or finished > checked[document_id]["at"]):
            checked[document_id] = {"at": finished, "version": match.group(1)}
    return checked


def current_tier4_version() -> str:
    text = (REPO_ROOT / "tools" / "extraction_worker" / "tier4_extractor.py").read_text()
    match = re.search(r'^PRODUCER_VERSION\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else "unknown"


def forms_for(years: Iterable[str], schema_dir: Path = SCHEMA_DIR) -> dict[str, dict[str, Any]]:
    """Per CDS year: the form its documents are expected to be numbered by,
    whether the full field schema file exists, its field count and the tables
    whose printed sums are checked. Read from the local `schemas/` folder at
    run time.

    A year with a full field schema checks every table in `SUM_TABLES` by the
    numbering each document carries (`SUM_CHECKS[document schema]`), and its
    admissions are compared. A year before 2023-24 has no full schema, only a
    structural one and a core-table overlay; it gets no sum checks and no
    federal comparison (`sum_tables` is empty). The worker reads such a
    document into the 2025-26 ids by row label, and the overlays are not a
    mapping to trust for sums: 2019-20 and 2020-21 map only the men and women
    C1 rows (the forms have no C1 total row), 2021-22 maps one total and maps
    the "total men who applied/admitted" rows onto the men rows, and 2022-23
    leaves the another-gender rows unmapped. A verified per-year C1 mapping,
    with totals and another-gender rows, is what would turn the checks on.

    `field_count` is 0 for such a year: "no question list", not "no questions".
    The structural row and answer-cell counts do not reliably equal the full
    schemas' field counts (2023-24: 1,081 vs 1,053; 2025-26: 1,061 vs 1,105)."""
    forms: dict[str, dict[str, Any]] = {}
    for year in years:
        full = schema_dir / f"cds_schema_{year.replace('-', '_')}.json"
        count = len(json.loads(full.read_text())["fields"]) if full.exists() else 0
        forms[year] = {"expected_form_year": year, "schema_exists": full.exists(), "field_count": count,
                       "sum_tables": list(SUM_TABLES) if full.exists() else []}
    return forms


def renewal_block(rows: list[dict[str, Any]], as_of: dt.date, sql_floor: Optional[str] = None) -> dict[str, Any]:
    """Current-year renewal (PRD 040 amendment), computed by `discovery_renewal`.

    `rows` are every live `cds_manifest` row (school_id, canonical_year,
    removed_at, participation_status). Fails loudly on a small denominator or
    on a freshness floor that disagrees with the database."""
    floor = discovery_renewal.cds_freshness_floor(as_of)
    if sql_floor is not None:
        discovery_renewal.check_floor_agrees(floor, sql_floor)
    year = discovery_renewal.parse_year(floor)
    if year is None:
        raise SystemExit(f"cds_freshness_floor({as_of}) = {floor!r} is not a CDS year")
    by_school = discovery_renewal.school_years(rows)
    # The same numerator as the alarm: a flagged current-year document
    # (wrong file, blank template, low coverage) is not a renewal.
    good = discovery_renewal.school_years(rows, exclude_flagged=True)
    one = discovery_renewal.renewal(by_school, year, good)
    two = discovery_renewal.two_year_renewal(by_school, year, good)
    for label, schools in (("one-year", one.prev_schools), ("two-year", two.prev_schools)):
        if len(schools) < discovery_renewal.MIN_PREV_SCHOOLS:
            raise SystemExit(
                f"only {len(schools)} schools in the {label} renewal denominator for {floor} "
                f"(minimum {discovery_renewal.MIN_PREV_SCHOOLS}); the manifest does not look complete")
    return {
        "as_of": as_of.isoformat(),
        "current_year": floor,
        "previous_year": discovery_renewal.format_year(year - 1),
        "current": sum(1 for years in by_school.values() if year in years),
        "previous": len(one.prev_schools),
        "both": len(one.renewed),
        "two_year_previous": len(two.prev_schools),
        "two_year_both": len(two.renewed),
    }


def gather_renewal(api: "Api", as_of: dt.date) -> dict[str, Any]:
    rows = discovery_renewal.fetch_live_manifest(api.url, api.key)
    sql_floor = discovery_renewal.fetch_sql_floor(api.url, api.key, as_of)
    return renewal_block(rows, as_of, sql_floor)


# ---------------------------------------------------------------------------
# The status classifier (PRD 040)
# ---------------------------------------------------------------------------

STATUSES = ("published", "set_aside", "couldnt_read", "not_read_yet")
SET_ASIDE_REASON = {"blank_template": "blank_form", "low_coverage": "too_little_read", "wrong_file": "wrong_file"}
PENDING_STATUSES = ("extraction_pending", "discovered")


def manifest_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": row["document_id"], "year": row["canonical_year"],
        "source_format": row.get("source_format"), "extraction_status": row["extraction_status"],
        "data_quality_flag": row.get("data_quality_flag"), "removed": bool(row.get("removed_at")),
    }


def classify_document(entry: dict[str, Any], served: Optional[dict[str, Any]]) -> str:
    """Exactly one class per manifest document, in this order of precedence:

    removed, no_file, set_aside (a hidden quality flag, whatever the
    extraction status), couldnt_read, not_read_yet, published.

    `served` is the run's entry for the document (None if it has none). A
    document that is `extracted` but has no served extraction is not read yet.
    A document a worker guard is holding on an earlier extraction is still
    served, so it is published."""
    if entry["removed"]:
        return "removed"
    status = entry["extraction_status"]
    if status == "not_applicable":
        return "no_file"
    if entry.get("data_quality_flag") in HIDDEN_FLAGS:
        return "set_aside"
    if status == "failed":
        return "couldnt_read"
    if status in PENDING_STATUSES:
        return "not_read_yet"
    if status == "extracted":
        return "published" if served is not None and served.get("producer") else "not_read_yet"
    raise ValueError(f"unknown extraction_status {status!r} on document {entry['document_id']}")


def is_published(doc: dict[str, Any]) -> bool:
    """A served document with a read extraction and no hidden quality flag:
    the population of every table."""
    return bool(doc["producer"]) and doc["flag"] not in HIDDEN_FLAGS


def federal_left_out(documents: list[dict[str, Any]], year: str) -> dict[str, int]:
    """Among a year's published reports: those filed for one campus or unit
    (IPEDS reports the whole institution) and those whose school has no IPEDS
    admissions figure to compare, and those we could not compare because we
    have no checked C1 mapping for the form they are numbered by
    (`federal_compared` false; a run without the key compared every report).
    The three, with the reports that have an outcome, add up to the published
    reports (`no_federal_figures` is only "IPEDS has no positive figure")."""
    published = [d for d in documents if d["year"] == year and is_published(d)]
    rest = [d for d in published if not d["sub_institutional"]]
    comparable = [d for d in rest if d.get("federal_compared", True)]
    return {"single_campus": len(published) - len(rest),
            "no_federal_figures": sum(1 for d in comparable if not any(d["federal"].values())),
            "not_compared": len(rest) - len(comparable)}


def gather(api: Api, years: tuple[str, ...], out_dir: Path, artifact_interval: float,
           field_interval: float, summaries: str, log: Callable[[str], None],
           limit: Optional[int] = None) -> dict[str, Any]:
    # Renewal first: a short read or a floor that disagrees with the database
    # fails before the heavy per-document reads. One timestamp serves both
    # `generated_at` and the renewal date, so a run that crosses midnight UTC
    # still agrees with itself.
    bad = [y for y in years if projection.parse_year_start(y) is None]
    if bad:
        raise SystemExit(f"--years takes CDS years like 2022-23; not {', '.join(bad)} (an `unknown` year is not one)")
    if len(set(years)) != len(years):
        raise SystemExit(f"--years lists a year twice: {', '.join(years)}")
    years = tuple(sorted(years))   # the public page lists years oldest first
    now = dt.datetime.now(dt.timezone.utc)
    renewal = gather_renewal(api, now.date())
    log(f"renewal {renewal['current_year']}: {renewal['both']} of {renewal['previous']} schools also have the year")
    definitions = projection.load_schema_definitions()
    api.check_page_size()
    all_documents = fetch_documents(api, years)
    served = [d for d in all_documents if d["extraction_status"] == "extracted" and not d.get("removed_at")]
    log(f"{len(all_documents)} documents in {', '.join(years)}; {len(served)} live and extracted")
    if limit:
        seen: Counter = Counter()
        kept = []
        for doc in served:
            seen[doc["canonical_year"]] += 1
            if seen[doc["canonical_year"]] <= limit:
                kept.append(doc)
        served = kept
        log(f"--limit {limit}: keeping {len(served)} documents; the numbers are a smoke test, not a scoreboard")

    source_hashes = fetch_source_hashes(api)
    artifact_index = fetch_artifact_index(api, [d["document_id"] for d in served])
    log(f"artifact index read ({sum(len(v) for v in artifact_index.values())} artifacts)")

    projected_years = tuple(y for y in years if (projection.parse_year_start(y) or 0) >= projection.MIN_YEAR_START)
    browser_rows = {
        row["document_id"]: row
        for row in (api.get("school_browser_rows", {
            "select": "document_id,producer,producer_version,applied,admitted,enrolled_first_year",
            "canonical_year": f"in.({','.join(projected_years)})",
            "order": "document_id",
        }) if projected_years else [])
    }
    # One read per IPEDS data year. Fall figures (C1, enrollment) come from the
    # CDS year's start year, tuition from the year after (see TUITION_KEYS).
    fall_year = {year: projection.parse_year_start(year) or 0 for year in years}
    wanted: dict[int, set[str]] = defaultdict(set)
    for start in fall_year.values():
        wanted[start].update((*FEDERAL_KEYS.values(), ENROLLMENT_KEY))
        wanted[start + 1].update(TUITION_KEYS)
    facts_by_year = {
        data_year: fetch_federal(api, data_year, tuple(sorted(keys)))
        for data_year, keys in sorted(wanted.items())
    }
    federal = {year: facts_by_year[start] for year, start in fall_year.items()}
    holds = load_holds(summaries)
    unchanged = load_unchanged(summaries)

    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact_reads = 0

    def load_notes(row: dict[str, Any]) -> dict[str, Any]:
        nonlocal artifact_reads
        cached = cache_dir / f"{row['id']}.json"
        if cached.exists():
            return {**json.loads(cached.read_text()), **row}
        if artifact_reads % 10 == 0:
            api.wait_for_memory()
        fetched = api.get("cds_artifacts", {
            "select": "id,notes_schema_version:notes->>schema_version,"
                      "schema_fallback_used:notes->schema_fallback_used,stats:notes->stats,values:notes->values",
            "id": f"eq.{row['id']}",
        })
        artifact_reads += 1
        time.sleep(artifact_interval)
        if not fetched:
            raise SystemExit(f"artifact {row['id']} disappeared while reading; run again")
        got = fetched[0]
        loaded = {**row, "notes": {
            "schema_version": got.get("notes_schema_version"),
            "schema_fallback_used": got.get("schema_fallback_used"),
            "stats": got.get("stats"),
            "values": got.get("values") or {},
        }}
        cached.write_text(json.dumps(loaded))
        return loaded

    forms = forms_for(years)
    documents: list[dict[str, Any]] = []
    for position, doc in enumerate(sorted(served, key=lambda d: (d["canonical_year"], d["document_id"])), 1):
        document_id, year = doc["document_id"], doc["canonical_year"]
        artifacts = artifact_index.get(document_id, [])
        candidates = [a for a in artifacts if a["kind"] == "canonical"]
        newest = max(candidates, key=lambda r: (str(r.get("created_at") or ""), str(r["id"])), default=None)
        entry: dict[str, Any] = {
            "document_id": document_id, "school_id": doc["school_id"], "year": year,
            "ipeds_id": doc.get("ipeds_id"), "source_sha256": source_hashes.get(document_id),
            "format": doc.get("source_format") or "unknown", "flag": doc.get("data_quality_flag"),
            "sub_institutional": bool(doc.get("sub_institutional")),
            "sub_institutional_label": doc.get("sub_institutional"),
            "source_url": doc.get("source_url"), "cds_year": doc.get("cds_year"),
            "detected_year": doc.get("detected_year"),
            "producer": None, "version": None, "schema_version": None, "fields": 0, "sections": {},
            "newest_producer": newest.get("producer") if newest else None,
            "newest_version": newest.get("producer_version") if newest else None,
            "newest_at": newest.get("created_at") if newest else None,
        }
        numbers: dict[str, Decimal] = {}
        if year in projected_years:
            if position % 100 == 0:
                api.wait_for_memory()
            rows = api.get("cds_fields", {
                "select": "field_id,value_num,value_status,schema_version,producer,producer_version",
                "document_id": f"eq.{document_id}",
                "order": "field_id",
            }, pause=field_interval)
            entry["fields"] = len(rows)
            entry["sections"] = section_counts((r["field_id"], r["value_status"]) for r in rows)
            for row in rows:
                if row["value_status"] == "reported" and row.get("value_num") is not None:
                    numbers[row["field_id"]] = Decimal(str(row["value_num"]))
            browser = browser_rows.get(document_id)
            base_rows = [r for r in rows if r["producer"] in projection.BASE_PRODUCER_RANK]
            if base_rows:
                entry["producer"], entry["version"] = Counter(
                    (r["producer"], r["producer_version"]) for r in base_rows).most_common(1)[0][0]
            elif rows and browser:
                entry["producer"], entry["version"] = browser.get("producer"), browser.get("producer_version")
            if rows:
                entry["schema_version"] = rows[0]["schema_version"]
            entry["admissions"] = {
                "applied": browser.get("applied") if browser else None,
                "admitted": browser.get("admitted") if browser else None,
                "enrolled": browser.get("enrolled_first_year") if browser else None,
            }
        else:
            picked = pick_served_artifact(candidates, year, load_notes)
            if picked is not None:
                values = projection._values_dict(picked.get("notes") or {})
                # An artifact that records no schema is read as the default one, as in the projection.
                schema_version = projection.artifact_schema_version(picked) or projection.DEFAULT_SCHEMA_VERSION
                schema_defs = definitions.get(schema_version or "") or {}
                numbers = numbers_from_values(values, schema_defs, schema_version)
                entry.update(producer=picked.get("producer"), version=picked.get("producer_version"),
                             schema_version=schema_version, fields=len(values))
                entry["sections"] = section_counts(effective_statuses(values, schema_defs, schema_version).items())
                entry["gap_fill_not_read"] = picked.get("producer") == TIER4 and any(
                    a["producer"] == projection.FALLBACK_PRODUCER for a in artifacts)
            entry["admissions"] = printed_admissions(entry["schema_version"], numbers)

        facts = {} if entry["sub_institutional"] else federal[year].get(str(doc.get("ipeds_id") or ""), {})
        # Compared only for a year with a full field schema; else
        # "not compared" (None), not "blank", which would say the school left it empty.
        sum_tables = forms[year]["sum_tables"]
        compared = "C1" in sum_tables
        entry["federal_compared"] = compared
        entry["federal"] = {
            metric: classify_federal(entry["admissions"][metric], facts.get(key)) if compared else None
            for metric, key in FEDERAL_KEYS.items()
        }
        # `ours` is an int here (the admissions counts compared) and a string
        # Decimal in `federal_extra` (dollars may carry cents).
        entry["federal_values"] = {
            metric: {"ours": entry["admissions"][metric],
                     "federal": str(facts[key]) if key in facts else None,
                     "federal_data_year": fall_year[year]}
            for metric, key in FEDERAL_KEYS.items()
        }
        tuition_facts = {} if entry["sub_institutional"] else facts_by_year[fall_year[year] + 1].get(
            str(doc.get("ipeds_id") or ""), {})
        # B1 and G1 ids are known only for a year whose form has them (see forms_for).
        entry["federal_extra"] = federal_extra(entry["schema_version"] if forms[year]["schema_exists"] else None,
                                               numbers, facts, fall_year[year], tuition_facts, fall_year[year] + 1)
        entry["sums"] = table_outcomes(entry["schema_version"], numbers, sum_tables)
        entry["check_numbers"] = {
            field_id: str(numbers[field_id])
            for check in SUM_CHECKS.get(entry["schema_version"] or "", []) if check.table in sum_tables
            for field_id in (check.total, *(r for rows, _ in check.groups for r in rows))
            if field_id in numbers
        }
        hold = holds.get(document_id)
        if hold and (entry["newest_at"] or "") < hold["at"]:
            entry["hold"] = hold["guard"]
        # The worker compared against the newest extraction, so the check
        # speaks for the served one only when they are the same.
        check = unchanged.get(document_id)
        newest_is_served = (entry["producer"], entry["version"]) == (entry["newest_producer"], entry["newest_version"])
        if check and newest_is_served and (entry["newest_at"] or "") < check["at"]:
            entry["checked_version"] = check["version"]
        documents.append(entry)
        if position % 100 == 0:
            log(f"  {position}/{len(served)} documents ({artifact_reads} artifact reads, {api.requests} requests)")

    not_served = Counter(
        (d["canonical_year"], "removed" if d.get("removed_at") else d["extraction_status"])
        for d in all_documents if d.get("removed_at") or d["extraction_status"] != "extracted"
    )
    return {
        "run_format": RUN_FORMAT,
        "sum_check_version": SUM_CHECK_VERSION,
        "limit": limit,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years": list(years),
        "manifest": [manifest_entry(d) for d in sorted(all_documents, key=lambda d: d["document_id"])],
        "federal_left_out": {year: federal_left_out(documents, year) for year in years},
        "forms": forms,
        "renewal": renewal,
        "current_tier4_version": current_tier4_version(),
        "projected_years": list(projected_years),
        # Schools with a C1 figure; the extra keys do not widen this count.
        "federal_schools": {
            year: sum(1 for school in facts.values() if any(key in school for key in FEDERAL_KEYS.values()))
            for year, facts in federal.items()
        },
        "hold_summaries_read": len(glob.glob(summaries)),
        "not_served": {f"{year} {status}": count for (year, status), count in sorted(not_served.items())},
        "documents": documents,
        "same_year_duplicates": same_year_duplicates_block(documents),
    }


def same_year_duplicates_block(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """School-years with two or more served documents, by the same classifier
    the discovery renewal job uses (tools/ops/same_year_duplicates.py).

    Only the served, extracted documents of the scoreboard's years are here,
    so this is a subset of what the pipeline page counts. The run records
    `source_sha256` per document (format 3), but this block does not pass it
    on yet, so a same-file pair still shows as a duplicate.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.ops.same_year_duplicates import find_groups

    rows = []
    for d in documents:
        # `year` is the filed (canonical) year. A saved run from before the
        # URL and year columns were kept has neither: file it under `year`.
        has_years = "cds_year" in d
        rows.append({
            "id": d["document_id"], "school_id": d["school_id"],
            # The raw label, so two distinct programs of one school are not one group.
            # A saved run from before the label was kept has only the boolean.
            "sub_institutional": d.get("sub_institutional_label")
            or ("sub-institutional" if d.get("sub_institutional") else None),
            "cds_year": d["cds_year"] if has_years else d["year"],
            "detected_year": d.get("detected_year") if has_years else d["year"],
            "source_url": d.get("source_url"), "source_sha256": None,
        })
    return find_groups(rows).as_dict()


# ---------------------------------------------------------------------------
# Aggregation and rendering
# ---------------------------------------------------------------------------

def _version_key(version: Optional[str]) -> tuple:
    return tuple(int(part) if part.isdigit() else 0 for part in str(version or "0").split("."))


def aggregate(data: dict[str, Any]) -> dict[str, Any]:
    """Flat `metric -> number` map (for deltas) plus the rows to print."""
    current = data["current_tier4_version"]
    metrics: dict[str, Any] = {}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for doc in data["documents"]:
        groups[(doc["year"], "all")].append(doc)
        groups[(doc["year"], doc["format"])].append(doc)

    for (year, fmt), docs in sorted(groups.items()):
        key = f"{year}|{fmt}"
        # Sections 1 to 3 cover published reports: not flagged, and with an
        # extraction (a document with none counts under `no_extraction`).
        shown = [d for d in docs if is_published(d)]
        metrics[f"{key}|docs"] = len(shown)
        metrics[f"{key}|flagged"] = sum(1 for d in docs if d["flag"] in HIDDEN_FLAGS)

        federal = Counter()
        with_federal = 0
        for doc in shown:
            outcomes = [o for o in doc["federal"].values() if o]
            with_federal += 1 if outcomes else 0
            federal.update(outcomes)
        metrics[f"{key}|federal_docs"] = with_federal
        for outcome in ("match", "blank", "different"):
            metrics[f"{key}|federal_{outcome}"] = federal[outcome]

        counts = [d["fields"] for d in shown]
        metrics[f"{key}|fields_median"] = percentile(counts, 50)
        metrics[f"{key}|fields_p10"] = percentile(counts, 10)

        for table in SUM_TABLES:
            tally = Counter(d["sums"][table] for d in shown)
            for outcome in ("pass", "near", "fail", "nc"):
                if outcome != "near" or table in NEAR_MISS_TABLES:
                    metrics[f"{key}|{table}_{outcome}"] = tally[outcome]

        if fmt != "all":
            continue
        tier4 = [d for d in docs if d["producer"] == TIER4]
        metrics[f"{key}|tier4"] = len(tier4)
        metrics[f"{key}|tier4_current"] = sum(1 for d in tier4 if d["version"] == current)
        # Read by the current cleaner: it wrote the served extraction, or it
        # re-cleaned the document and read the same values (nothing written).
        metrics[f"{key}|tier4_checked"] = sum(
            1 for d in tier4 if current in (d["version"], d.get("checked_version")))
        metrics[f"{key}|no_extraction"] = sum(1 for d in docs if not d["producer"])
        metrics[f"{key}|held"] = sum(1 for d in docs if d.get("hold"))
        metrics[f"{key}|other_schema"] = sum(1 for d in docs if d["producer"] and d["schema_version"] != year)
        metrics[f"{key}|newest_not_served"] = sum(
            1 for d in docs
            if d["producer"] and d["newest_producer"]
            and (d["producer"], d["version"]) != (d["newest_producer"], d["newest_version"])
        )
    return metrics


def sum_check_version(data: dict[str, Any]) -> int:
    """Runs saved before near misses existed have no version: they are 1."""
    return int(data.get("sum_check_version") or 1)


def render(data: dict[str, Any], previous: Optional[dict[str, Any]] = None) -> str:
    metrics = aggregate(data)
    before = aggregate(previous) if previous else {}
    current = data["current_tier4_version"]
    version = sum_check_version(data)
    switched = previous is not None and sum_check_version(previous) != version
    if switched:
        # The B1 and C1 outcomes mean something different now, so a change in
        # them is not a change in quality: show no deltas for them.
        before = {k: v for k, v in before.items() if not re.search(r"\|(B1|C1)_(pass|near|fail|nc)$", k)}

    def cell(key: str) -> str:
        value = metrics.get(key)
        if value is None:
            return "–"
        text = f"{value:,}"
        if previous is not None and before.get(key) is not None and before[key] != value:
            text += f" ({value - before[key]:+,})"
        return text

    def triple(key: str, table: str) -> str:
        outcomes = ("pass", "near", "fail", "nc") if version >= 2 and table in NEAR_MISS_TABLES else ("pass", "fail", "nc")
        return " / ".join(cell(f"{key}|{table}_{o}") for o in outcomes)

    keys = sorted({k.rsplit("|", 1)[0] for k in metrics},
                  key=lambda k: (k.split("|")[0], k.split("|")[1] != "all", k.split("|")[1]))
    docs = data["documents"]
    lines = [
        f"## Extraction scoreboard, {data['generated_at'].replace('T', ' ').replace('Z', ' UTC')}",
        "",
        f"What the site serves for {', '.join(data['years'])}: {len(docs):,} live, extracted documents. "
        f"Tier 4 cleaner on this checkout: {current}. "
        "Sections 1 to 3 leave out documents that carry a quality flag; section 4 counts them.",
    ]
    if previous is not None:
        lines.append(f"Changes in brackets are against the run of {previous['generated_at']}.")
    if data.get("renewal"):
        r = data["renewal"]
        lines.append(f"\nCurrent-year renewal: of {r['previous']:,} schools with a live {r['previous_year']} report, "
                     f"{r['both']:,} also have a {r['current_year']} report ({r['current']:,} schools have a "
                     f"{r['current_year']} report in all).")

    lines += ["", "### 1. Federal match on admissions",
              "", "C1 applied, admitted and enrolled as published, against IPEDS for the same fall. Three values "
              "per document: within 2%, blank, or present but different. Documents filed for one campus or unit "
              "are left out.",
              "", "| Year | Format | Docs with federal figures | Values | Match | Blank | Different | Match rate |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for key in keys:
        year, fmt = key.split("|")
        if not metrics[f"{key}|federal_docs"]:
            continue
        total = sum(metrics[f"{key}|federal_{o}"] for o in ("match", "blank", "different"))
        rate = f"{100 * metrics[f'{key}|federal_match'] / total:.1f}%" if total else "–"
        lines.append(f"| {year} | {fmt} | {cell(key + '|federal_docs')} | {total:,} | {cell(key + '|federal_match')} | "
                     f"{cell(key + '|federal_blank')} | {cell(key + '|federal_different')} | {rate} |")
    for year in data["years"]:
        if "C1" not in data.get("forms", {}).get(year, {}).get("sum_tables", SUM_TABLES):
            lines.append(f"\n{year}: we have no checked field mapping for admissions on this form, so they are not "
                         "compared with IPEDS.")
        if not data["federal_schools"].get(year):
            lines.append(f"\n{year}: no federal admissions figures are loaded for that fall yet, so it is not scored.")

    lines += ["", "### 2. Coverage", "", "Fields per served extraction.",
              "", "| Year | Format | Docs | Median | 10th percentile |", "|---|---|---:|---:|---:|"]
    for key in keys:
        year, fmt = key.split("|")
        if metrics[f"{key}|docs"]:
            lines.append(f"| {year} | {fmt} | {cell(key + '|docs')} | {cell(key + '|fields_median')} | "
                         f"{cell(key + '|fields_p10')} |")

    if switched:
        lines.append(
            f"Sum checks changed from version {sum_check_version(previous)} to {version}: B1 and C1 now split "
            "failing sums into off by under 2% and off by more, so their changes are not shown. "
            "This is a change in how the sums are scored, not in quality.")
    near = (" B1 and C1 read pass / off by under 2% (every miss under 2% of its printed total) / off by more / "
            "not checkable; H1 reads pass / fail / not checkable." if version >= 2 else "")
    lines += ["", "### 3. Internal consistency",
              "", "Documents whose printed totals agree with their rows: pass / fail / not checkable. "
              "B1: undergraduates by sex, and undergraduate + graduate. C1: applied, admitted and enrolled by sex. "
              "H1: grant and self-help totals, need-based and non-need-based (within $5)." + near,
              "", "| Year | Format | Docs | B1 | C1 | H1 |", "|---|---|---:|---|---|---|"]
    for key in keys:
        year, fmt = key.split("|")
        if metrics[f"{key}|docs"]:
            lines.append(f"| {year} | {fmt} | {cell(key + '|docs')} | {triple(key, 'B1')} | "
                         f"{triple(key, 'C1')} | {triple(key, 'H1')} |")

    for year in data["years"]:
        tables = data.get("forms", {}).get(year, {}).get("sum_tables", SUM_TABLES)
        missing = [t for t in SUM_TABLES if t not in tables]
        if missing:
            lines.append(f"\n{year}: we have no checked field mapping for {', '.join(missing)} on this form, "
                         "so those sums aren't checked and read not checkable for every document.")

    lines += ["", "### 4. Fix reach",
              "", f"| Year | Served | Tier 4 | Read by {current} | Of those, written by it | Tier 4, not yet read by it | "
              "Other extractors | No extraction | "
              "Numbered by another year's form | Flagged | Held by a guard | Newest is not the served one |",
              "|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|"]
    for year in data["years"]:
        key = f"{year}|all"
        if f"{key}|docs" not in metrics:
            continue
        year_docs = [d for d in docs if d["year"] == year]
        older = Counter(d["version"] for d in year_docs if d["producer"] == TIER4
                        and current not in (d["version"], d.get("checked_version")))
        older_text = ", ".join(f"{v}: {n}" for v, n in sorted(older.items(), key=lambda i: _version_key(i[0]), reverse=True))
        others = Counter(f"{d['producer']} {d['version']}" for d in year_docs if d["producer"] and d["producer"] != TIER4)
        others_text = ", ".join(f"{name}: {n}" for name, n in sorted(others.items()))
        lines.append(
            f"| {year} | {len(year_docs):,} | {cell(key + '|tier4')} | {cell(key + '|tier4_checked')} | "
            f"{cell(key + '|tier4_current')} | "
            f"{older_text or '–'} | {others_text or '–'} | {cell(key + '|no_extraction')} | "
            f"{cell(key + '|other_schema')} | {cell(key + '|flagged')} | {cell(key + '|held')} | {cell(key + '|newest_not_served')} |")

    lines.append(
        f"\nRead by {current}: the current cleaner wrote the served extraction, or re-cleaned the document and "
        "read the same values, which writes nothing. The second kind is known from local worker run summaries.")
    flags = Counter((d["year"], d["flag"]) for d in docs if d["flag"] in HIDDEN_FLAGS)
    if flags:
        lines.append("\nFlagged: " + "; ".join(
            f"{year} {flag.replace('_', ' ')} {n}" for (year, flag), n in sorted(flags.items())) + ".")
    held = [d for d in docs if d.get("hold")]
    if held:
        lines.append("\nHeld by a guard (the previous extraction is still served): " + "; ".join(
            f"{d['school_id']} {d['year']} ({d['hold']})" for d in sorted(held, key=lambda d: (d["year"], d["school_id"]))) + ".")
    elif not data["hold_summaries_read"]:
        lines.append("\nGuard holds are read from local worker run summaries; none were found on this machine.")
    lines.append("\n\"Numbered by another year's form\": the served extraction's field numbers follow a different "
                 "year's form than the document's own, so the same number can mean a different question.")
    lines.append("\n\"Newest is not the served one\": the school's year page shows the newest extraction, "
                 "the browser shows the projection's pick, and for these documents the two differ.")
    unread = sum(1 for d in docs if d.get("gap_fill_not_read"))
    if unread:
        lines.append(f"\n{unread} documents before the projected years have an LLM gap-fill artifact that this "
                     "script does not merge; their field counts are of the base extraction only.")
    lines.append(render_same_year_duplicates(data))
    if data["not_served"]:
        lines.append("\nNot counted above: " + "; ".join(f"{k} {v}" for k, v in data["not_served"].items()) + ".")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Near-miss measurement (no database)
# ---------------------------------------------------------------------------

def near_miss_counts(data: dict[str, Any], published_only: bool = True) -> dict[str, dict[str, int]]:
    """From a saved run's `check_numbers`: how many failing B1 and C1 sums
    (and failing tables) are off by under 2% of their printed total.

    Keys are `<year>|<table>`. `sums_*` count individual sums, `tables_*`
    count documents' table outcomes."""
    out: dict[str, Counter] = defaultdict(Counter)
    for doc in data["documents"]:
        if published_only and not is_published(doc):
            continue
        numbers = {k: Decimal(v) for k, v in (doc.get("check_numbers") or {}).items()}
        worst: dict[str, str] = {}
        for check in SUM_CHECKS.get(doc["schema_version"] or "", []):
            if check.table not in NEAR_MISS_TABLES:
                continue
            result, share = run_check_detail(check, numbers)
            bucket = out[f"{doc['year']}|{check.table}"]
            bucket["sums_checked"] += result != "nc"
            if result == "fail":
                bucket["sums_failing"] += 1
                if share is None:
                    bucket["sums_no_share"] += 1
                bucket["sums_near" if is_near_miss(check, share) else "sums_over"] += 1
                level = "near" if is_near_miss(check, share) else "fail"
                if _OUTCOME_RANK[level] > _OUTCOME_RANK.get(worst.get(check.table, "nc"), 0):
                    worst[check.table] = level
        for table, level in worst.items():
            out[f"{doc['year']}|{table}"][f"tables_{level}"] += 1
    return {key: dict(counter) for key, counter in sorted(out.items())}


def render_near_miss(data: dict[str, Any]) -> str:
    lines = [f"## Near-miss split, run of {data['generated_at']}", "",
             "Failing B1 (enrollment) and C1 (admissions) sums, split at 2% of the printed total "
             "(strictly under 2% is a near miss). Built from the run's `check_numbers`; no database reads.", ""]
    for label, published_only in (("Published reports (not flagged, with an extraction)", True),
                                  ("All served documents, flags included", False)):
        counts = near_miss_counts(data, published_only)
        lines += [f"### {label}", "",
                  "| Year | Table | Sums checked | Sums failing | Under 2% | 2% or more | Tables near | Tables off by more |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        pooled: Counter = Counter()
        pooled_tables: Counter = Counter()
        for key, c in counts.items():
            year, table = key.split("|")
            lines.append(f"| {year} | {table} | {c.get('sums_checked', 0)} | {c.get('sums_failing', 0)} | "
                         f"{c.get('sums_near', 0)} | {c.get('sums_over', 0)} | {c.get('tables_near', 0)} | "
                         f"{c.get('tables_fail', 0)} |")
            pooled.update({"failing": c.get("sums_failing", 0), "near": c.get("sums_near", 0)})
            pooled_tables.update({"near": c.get("tables_near", 0), "fail": c.get("tables_fail", 0)})
        share = f"{100 * pooled['near'] / pooled['failing']:.1f}%" if pooled["failing"] else "n/a"
        t_total = pooled_tables["near"] + pooled_tables["fail"]
        t_share = f"{100 * pooled_tables['near'] / t_total:.1f}%" if t_total else "n/a"
        lines += ["", f"All years, B1 and C1: {pooled['near']} of {pooled['failing']} failing sums are under 2% ({share}); "
                      f"{pooled_tables['near']} of {t_total} tables that miss are near misses only ({t_share}).", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# --public: aggregates only, from one run JSON
# ---------------------------------------------------------------------------

FORMAT_LABELS = {
    "pdf_flat": "standard PDF", "pdf_fillable": "fillable PDF", "pdf_scanned": "scanned PDF",
    "xlsx": "spreadsheet", "docx": "Word", "html": "web page", "other": "other or unknown format",
}
FORMAT_ORDER = tuple(FORMAT_LABELS)
SUM_OUTCOME_KEY = {"pass": "adds_up", "near": "under_2pct", "fail": "off_more", "nc": "cant_check"}
AID_OUTCOME_KEY = {"pass": "adds_up", "fail": "doesnt", "nc": "cant_check"}

# A "different" value is split by its gap as a share of the federal figure:
# above 2% (the match tolerance) up to and including 10%, or over 10%.
FEDERAL_LARGE_SHARE = Decimal("0.10")


def federal_difference_band(cds: Optional[int], federal: Optional[Decimal]) -> Optional[str]:
    """'2_to_10' or 'over_10' for a value `classify_federal` calls 'different'
    (gap over 2% of the federal figure; exactly 10% is still '2_to_10'), else None."""
    if classify_federal(cds, federal) != "different":
        return None
    return "2_to_10" if abs(Decimal(cds) - federal) <= FEDERAL_LARGE_SHARE * federal else "over_10"


_COUNT, _TEXT, _FLAG = "count", "text", "flag"


@dataclass(frozen=True)
class _Optional:
    """A key `check_public_shape` allows but does not require."""
    spec: Any


_STATUS_SPEC = {k: _COUNT for k in STATUSES}
_ROW_SPEC = {
    "status": _STATUS_SPEC,
    "fields_stored": {"median": _COUNT, "p10": _COUNT},
    "federal": {k: _COUNT for k in ("reports", "values", "matches", "no_value", "differs",
                                    "differs_2_to_10pct", "differs_over_10pct")},
    "totals": {
        "reports": _COUNT,
        "B1": {k: _COUNT for k in SUM_OUTCOME_KEY.values()},
        "C1": {k: _COUNT for k in SUM_OUTCOME_KEY.values()},
        "H1": {k: _COUNT for k in AID_OUTCOME_KEY.values()},
    },
}
PUBLIC_SPEC = {
    "public_format": _COUNT, "snapshot_of": _TEXT, "scoreboard_run": _TEXT,
    "renewal": {"as_of": _TEXT, "current_year": _TEXT, "previous_year": _TEXT, "current": _COUNT,
                "previous": _COUNT, "both": _COUNT, "two_year_previous": _COUNT, "two_year_both": _COUNT},
    "years": [{
        "cds_year": _TEXT,
        "form": {"form_year": _TEXT, "full_field_schema": _FLAG, "questions": _COUNT},
        # Present only for a year whose form has no sums to check for some table
        # (an older form): those tables' "can't check" counts are not a result.
        "sum_checks_unavailable": _Optional([_TEXT]),
        "federal_fall_loaded": _FLAG, "other_form_numbering": _COUNT, "removed": _COUNT, "no_file": _COUNT,
        "set_aside_reasons": {k: _COUNT for k in SET_ASIDE_REASON.values()},
        # not_compared is omitted when 0, so years without it are unchanged
        "federal_left_out": {"single_campus": _COUNT, "no_federal_figures": _COUNT, "not_compared": _Optional(_COUNT)},
        "rows": [{"format": _TEXT, "label": _TEXT, **_ROW_SPEC}],
        "total": _ROW_SPEC,
        # Empty `rows` for a year whose form has no full field schema.
        "sections": {"reports": _COUNT,
                     "rows": [{"section": _TEXT, "questions": _COUNT, "stored_median": _COUNT, "usable_median": _COUNT}]},
    }],
}


def check_public_shape(value: Any, spec: Any = PUBLIC_SPEC, where: str = "public") -> None:
    """Raise unless `value` has exactly the keys of the allow-list `spec`, with
    counts as non-negative integers. Nothing outside the list is ever written."""
    if isinstance(spec, dict):
        required = {k for k, sub in spec.items() if not isinstance(sub, _Optional)}
        if not isinstance(value, dict) or not required <= set(value) <= set(spec):
            extra = sorted(set(value) - set(spec)) if isinstance(value, dict) else "not an object"
            missing = sorted(required - set(value)) if isinstance(value, dict) else ""
            raise ValueError(f"{where}: keys outside the allow-list {extra}, missing {missing}")
        for key, sub in spec.items():
            if key in value:
                check_public_shape(value[key], sub.spec if isinstance(sub, _Optional) else sub, f"{where}.{key}")
    elif isinstance(spec, list):
        if not isinstance(value, list):
            raise ValueError(f"{where}: not a list")
        if where.endswith(".years"):
            names = [y.get("cds_year") if isinstance(y, dict) else None for y in value]
            if len(set(names)) != len(names):
                raise ValueError(f"{where}: a cds_year is listed twice")
        if where.endswith(".sum_checks_unavailable") and (not value or not set(value) <= set(SUM_TABLES)):
            raise ValueError(f"{where}: {value!r} must be a non-empty list of {', '.join(SUM_TABLES)}")
        for i, item in enumerate(value):
            check_public_shape(item, spec[0], f"{where}[{i}]")
    elif spec == _COUNT:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{where}: {value!r} is not a non-negative integer")
    elif spec == _FLAG:
        if not isinstance(value, bool):
            raise ValueError(f"{where}: {value!r} is not a boolean")
    elif not isinstance(value, str):
        raise ValueError(f"{where}: {value!r} is not text")


def public_format_key(source_format: Optional[str]) -> str:
    return source_format if source_format in FORMAT_LABELS else "other"


def section_questions(year: str, schema_dir: Path = SCHEMA_DIR) -> dict[str, int]:
    """{section letter: questions on the year's form}, from its full field schema ({} when it has none).
    The letter is the question number's prefix before the first `.` (`C.116` -> `C`)."""
    full = schema_dir / f"cds_schema_{year.replace('-', '_')}.json"
    if not full.exists():
        return {}
    counts = Counter(f["question_number"].split(".", 1)[0] for f in json.loads(full.read_text())["fields"])
    return dict(sorted(counts.items()))


def section_block(year: str, published: list[dict[str, Any]], questions: dict[str, int]) -> dict[str, Any]:
    """Per CDS section: the form's questions and the median fields stored and usable answers per report.
    Over published reports numbered by the year's own form (the rest are counted in
    `other_form_numbering`: their ids come from another form, so a section's count can't be set against
    this form's question count). Medians of per-report counts, zero for a report with none."""
    if not questions:
        return {"reports": 0, "rows": []}   # no full field schema for the year: no section table
    own = [d for d in published if d["schema_version"] == year]
    rows = []
    for d in own:
        if "sections" not in d:
            raise SystemExit(f"--public: {d['document_id']} has no `sections`; run the scoreboard again")
    for letter, total in questions.items():
        stored, usable = [], []
        for d in own:
            statuses = d["sections"].get(letter, {})
            if set(statuses) - set(VALUE_STATUSES):
                raise SystemExit(f"--public: {d['document_id']}: unknown value_status {sorted(set(statuses) - set(VALUE_STATUSES))}")
            stored.append(sum(statuses.values()))
            usable.append(statuses.get(USABLE_STATUS, 0))
            if stored[-1] > total:
                raise SystemExit(f"--public: {d['document_id']}: {stored[-1]} fields stored in section {letter}, "
                                 f"but the {year} form has {total} questions there")
        rows.append({"section": letter, "questions": total,
                     "stored_median": percentile(stored, 50) or 0, "usable_median": percentile(usable, 50) or 0})
    for d in own:
        if set(d["sections"]) - set(questions):
            raise SystemExit(f"--public: {d['document_id']}: fields stored in sections {sorted(set(d['sections']) - set(questions))} "
                             f"that the {year} form does not have")
    return {"reports": len(own), "rows": rows}


def check_public_sections(public: dict[str, Any]) -> None:
    """The arithmetic of every year's `sections` block (`check_public_shape` only checks its keys and types):
    all of A to J, in order and not repeated (every CDS form has the ten sections), questions add up to the form's, reports = published minus those numbered by
    another year's form, rows exactly when the form has a full field schema, 0 <= usable <= stored <= questions,
    and zero medians when there are no reports."""
    letters = "ABCDEFGHIJ"
    for year in public["years"]:
        where, block = f"--public: {year['cds_year']}: sections", year["sections"]
        rows = block["rows"]
        if rows and [r["section"] for r in rows] != list(letters):
            raise SystemExit(f"{where}: sections {[r['section'] for r in rows]} are not all of A to J, in order")
        if bool(rows) != year["form"]["full_field_schema"]:
            raise SystemExit(f"{where}: rows are present exactly when the form has a full field schema")
        expected = year["total"]["status"]["published"] - year["other_form_numbering"] if rows else 0
        if block["reports"] != expected:
            raise SystemExit(f"{where}: reports is {block['reports']}, not published minus other_form_numbering ({expected})")
        if rows and sum(r["questions"] for r in rows) != year["form"]["questions"]:
            raise SystemExit(f"{where}: the sections' questions do not add up to the form's {year['form']['questions']}")
        for r in rows:
            if r["questions"] <= 0:
                raise SystemExit(f"{where}: section {r['section']} has no questions")
            if not 0 <= r["usable_median"] <= r["stored_median"] <= r["questions"]:
                raise SystemExit(f"{where}: section {r['section']} breaks 0 <= usable <= stored <= questions")
            if block["reports"] == 0 and (r["stored_median"] or r["usable_median"]):
                raise SystemExit(f"{where}: section {r['section']} has a median but no reports")


def _row_counts(classes: Counter, published: list[dict[str, Any]], federal_loaded: bool) -> dict[str, Any]:
    counts = [d["fields"] for d in published]
    # Reports filed for one campus or unit are left out of the federal comparison
    # (they are counted in federal_left_out.single_campus instead).
    outcomes = [[o for o in d["federal"].values() if o]
                for d in published if not d["sub_institutional"]] if federal_loaded else []
    federal_values = Counter(o for each in outcomes for o in each)
    bands = Counter()
    if federal_loaded:
        for d in published:
            if d["sub_institutional"]:
                continue
            for metric, outcome in d["federal"].items():
                if not outcome:
                    continue
                v = d.get("federal_values", {}).get(metric)
                if v is None:
                    raise SystemExit(f"--public: {d['document_id']} has a {metric} outcome but no federal_values for it; "
                                     "run the scoreboard again")
                federal = Decimal(v["federal"]) if v["federal"] is not None else None
                if classify_federal(v["ours"], federal) != outcome:
                    raise SystemExit(f"--public: {d['document_id']} {metric}: federal_values say "
                                     f"{classify_federal(v['ours'], federal)!r}, the run's outcome is {outcome!r}")
                bands[federal_difference_band(v["ours"], federal)] += 1
    if bands["2_to_10"] + bands["over_10"] != federal_values["different"]:
        raise SystemExit("--public: the two size bands do not add up to the differing values")
    totals: dict[str, Any] = {"reports": len(published)}
    for table in SUM_TABLES:
        keys = SUM_OUTCOME_KEY if table in NEAR_MISS_TABLES else AID_OUTCOME_KEY
        tally = Counter(d["sums"][table] for d in published)
        if set(tally) - set(keys):
            raise SystemExit(f"{table} outcome {sorted(set(tally) - set(keys))} is not valid at sum_check_version 2")
        totals[table] = {name: tally[outcome] for outcome, name in keys.items()}
    return {
        "status": {name: classes[name] for name in STATUSES},
        "fields_stored": {"median": percentile(counts, 50) or 0, "p10": percentile(counts, 10) or 0},
        "federal": {
            "reports": sum(1 for each in outcomes if each),
            "values": sum(federal_values.values()),
            "matches": federal_values["match"], "no_value": federal_values["blank"],
            "differs": federal_values["different"],
            "differs_2_to_10pct": bands["2_to_10"], "differs_over_10pct": bands["over_10"],
        },
        "totals": totals,
    }


def require_public_run(run: Any) -> None:
    """Refuse a run that lacks what `--public` needs, instead of inventing zeros."""
    if not isinstance(run, dict) or run.get("run_format") not in PUBLIC_RUN_FORMATS:
        found = run.get("run_format") if isinstance(run, dict) else None
        raise SystemExit(f"--public needs a run with run_format 3 (this one has {found!r}); "
                         "run the scoreboard again.")
    missing = [k for k in ("generated_at", "years", "manifest", "documents", "federal_left_out", "forms",
                           "renewal", "federal_schools", "sum_check_version") if k not in run]
    if missing:
        raise SystemExit(f"--public: the run is missing {', '.join(missing)}")
    if run["sum_check_version"] != SUM_CHECK_VERSION:
        raise SystemExit(f"--public needs sum_check_version {SUM_CHECK_VERSION}, got {run['sum_check_version']!r}")
    if "limit" not in run or run["limit"] is not None:
        raise SystemExit("--public: the run must record limit: null; a --limit run covers only part of each year")
    years = run["years"]
    if not years or not run["manifest"]:
        raise SystemExit("--public: the run has no years or an empty manifest")
    if len(set(years)) != len(years):
        raise SystemExit(f"--public: the run lists a year twice: {years}")
    if not set(DEFAULT_YEARS) <= set(years):
        raise SystemExit(f"--public: the run must cover {', '.join(DEFAULT_YEARS)}; it has {', '.join(years)}")
    for year in years:
        if year not in run["forms"] or year not in run["federal_left_out"]:
            raise SystemExit(f"--public: the run has no forms or federal_left_out entry for {year}")
    require_public_renewal(run["renewal"], run["generated_at"])


def require_public_renewal(renewal: Any, generated_at: str) -> None:
    """The renewal block must be internally consistent and match the run date, offline."""
    def bad(why: str) -> NoReturn:
        raise SystemExit(f"--public: renewal block: {why}")

    keys = ("as_of", "current_year", "previous_year", "current", "previous", "both",
            "two_year_previous", "two_year_both")
    if not isinstance(renewal, dict):
        bad("not an object")
    for key in keys:
        if key not in renewal:
            bad(f"{key} is missing")
    for key in keys[3:]:
        if not isinstance(renewal[key], int) or isinstance(renewal[key], bool) or renewal[key] < 0:
            bad(f"{key} is not a non-negative integer")
    try:
        snapshot_day = dt.date.fromisoformat(str(generated_at)[:10])
        as_of = dt.date.fromisoformat(str(renewal["as_of"]))
    except ValueError:
        bad("as_of or the run's generated_at is not an ISO date")
    if as_of != snapshot_day:
        bad(f"as_of {as_of} is not the snapshot date {snapshot_day}")
    floor = discovery_renewal.cds_freshness_floor(snapshot_day)
    if renewal["current_year"] != floor:
        bad(f"current_year {renewal['current_year']!r} is not the freshness floor {floor} for {snapshot_day}")
    start = discovery_renewal.parse_year(floor)
    if renewal["previous_year"] != discovery_renewal.format_year(start - 1):
        bad(f"previous_year {renewal['previous_year']!r} is not the year before {floor}")
    minimum = discovery_renewal.MIN_PREV_SCHOOLS
    if renewal["previous"] < minimum or renewal["two_year_previous"] < minimum:
        bad(f"a denominator is under {minimum} schools")
    if renewal["both"] > renewal["previous"] or renewal["both"] > renewal["current"]:
        bad("both exceeds previous or current")
    if renewal["two_year_both"] > renewal["two_year_previous"] or renewal["two_year_both"] > renewal["current"]:
        bad("two_year_both exceeds two_year_previous or current")
    if renewal["two_year_previous"] < renewal["previous"] or renewal["two_year_both"] < renewal["both"]:
        bad("the two-year figures are smaller than the one-year figures")


def sum_tables_of(year: str, form: dict[str, Any]) -> list[str]:
    """The tables with sums for a year's form. A run made before earlier years
    existed has no `sum_tables`; every year it covered had a full field schema,
    and such a year has all three (as `forms_for` says now)."""
    if "sum_tables" in form:
        return form["sum_tables"]
    if not form.get("schema_exists"):
        raise SystemExit(f"--public: the run's forms entry for {year} has no sum_tables; run the scoreboard again")
    return list(SUM_TABLES)


def build_public(run: dict[str, Any], run_name: str) -> dict[str, Any]:
    """The public snapshot (PRD 040 "Public JSON shape"): aggregates and
    labels only, from one run. No database, no per-document rows."""
    require_public_run(run)
    served = {d["document_id"]: d for d in run["documents"]}
    manifest_ids = {m["document_id"] for m in run["manifest"]}
    if len(manifest_ids) != len(run["manifest"]):
        raise SystemExit("--public: the manifest lists a document twice")
    if set(served) - manifest_ids:
        raise SystemExit("--public: the run serves documents that are not in its manifest")
    years_out = []
    for year in run["years"]:
        entries = [m for m in run["manifest"] if m["year"] == year]
        by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            by_class[classify_document(entry, served.get(entry["document_id"]))].append(entry)
        published_docs = [d for d in run["documents"] if d["year"] == year and is_published(d)]
        if len(by_class["published"]) != len(published_docs):
            raise SystemExit(f"--public: {year}: the manifest classifies {len(by_class['published'])} reports as "
                             f"published, the run's documents say {len(published_docs)}")
        left_out = federal_left_out(run["documents"], year)
        if left_out != {"not_compared": 0, **run["federal_left_out"][year]}:
            raise SystemExit(f"--public: {year}: federal_left_out in the run disagrees with its documents")
        loaded = run["federal_schools"].get(year, 0) > 0
        if not loaded:
            left_out = {**left_out, "no_federal_figures": 0}
        if not left_out["not_compared"]:
            del left_out["not_compared"]
        form = run["forms"][year]
        unavailable = [t for t in SUM_TABLES if t not in sum_tables_of(year, form)]
        rows = []
        for fmt in FORMAT_ORDER:
            classes = Counter()
            for cls, members in by_class.items():
                classes[cls] = sum(1 for m in members if public_format_key(m["source_format"]) == fmt)
            if not any(classes[s] for s in STATUSES):
                continue
            docs = [d for d in published_docs if public_format_key(d["format"]) == fmt]
            rows.append({"format": fmt, "label": FORMAT_LABELS[fmt], **_row_counts(classes, docs, loaded)})
        classes = Counter({cls: len(members) for cls, members in by_class.items()})
        reasons = Counter(SET_ASIDE_REASON[m["data_quality_flag"]] for m in by_class["set_aside"])
        years_out.append({
            "cds_year": year,
            "form": {"form_year": form["expected_form_year"], "full_field_schema": form["schema_exists"],
                     "questions": form["field_count"]},
            **({"sum_checks_unavailable": unavailable} if unavailable else {}),
            "federal_fall_loaded": loaded,
            "other_form_numbering": sum(1 for d in published_docs if d["schema_version"] != year),
            "removed": classes["removed"], "no_file": classes["no_file"],
            "set_aside_reasons": {name: reasons[name] for name in SET_ASIDE_REASON.values()},
            "federal_left_out": left_out,
            "rows": rows,
            "total": _row_counts(classes, published_docs, loaded),
            "sections": section_block(year, published_docs, section_questions(year)),
        })
    renewal = run["renewal"]
    public = {
        "public_format": PUBLIC_FORMAT,
        "snapshot_of": run["generated_at"],
        "scoreboard_run": run_name,
        "renewal": {k: renewal[k] for k in PUBLIC_SPEC["renewal"]},
        "years": years_out,
    }
    check_public_shape(public)
    check_public_sections(public)
    return public


def write_public(run_path: Path, out_dir: Path) -> Path:
    run = json.loads(run_path.read_text())
    public = build_public(run, run_path.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{public['snapshot_of'][:10]}.json"
    target.write_text(json.dumps(public, indent=1) + "\n")
    return target


def render_same_year_duplicates(data: dict[str, Any]) -> str:
    block = data.get("same_year_duplicates")
    if block is None:
        return "\n## Two documents in one year\n\nThis saved run has no duplicate check; run the scoreboard again."
    lines = [
        "\n## Two documents in one year\n",
        f"{block['same_year_duplicates']} school-years among these served documents have two or more "
        "(" + ", ".join(f"{n} {c}" for c, n in block["same_year_duplicates_by_class"].items())
        + f"; {block['undated_duplicates']} undated). The pipeline page counts every live document, "
        "so its number is larger. Hashes are not read here, so same-file pairs show as duplicates.",
    ]
    if block["groups"]:
        lines += ["", "| School | Year | Class | Evidence |", "|---|---|---|---|"]
        for g in block["groups"]:
            lines.append(f"| {g['school_id']} | {g['year']} | {g['class']} | {g['evidence'].replace('|', '/')} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--years", nargs="+", default=list(DEFAULT_YEARS))
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--compare", type=Path, help="An earlier scoreboard JSON to print deltas against.")
    parser.add_argument("--artifact-interval", type=float, default=4.0,
                        help="Seconds between cds_artifacts reads (default 4).")
    parser.add_argument("--field-interval", type=float, default=0.25,
                        help="Seconds between per-document cds_fields reads (default 0.25).")
    parser.add_argument("--min-free-mb", type=int, default=300,
                        help="Wait while the database host has less memory free than this (default 300).")
    parser.add_argument("--worker-summaries", default=DEFAULT_SUMMARIES,
                        help="Glob of local worker --summary-json files, for guard holds.")
    parser.add_argument("--limit", type=int, help="Smoke test: only this many documents per year.")
    parser.add_argument("--from-json", type=Path, help="Render a saved scoreboard JSON instead of reading the database.")
    parser.add_argument("--public", type=Path, metavar="RUN_JSON",
                        help="Write the public aggregates (PRD 040) from one saved run JSON. Reads nothing else: "
                             "no database, no network. Needs a run_format 3 run.")
    parser.add_argument("--public-out-dir", type=Path, default=DEFAULT_PUBLIC_DIR,
                        help="Where --public writes <YYYY-MM-DD>.json (default web/src/data/data-quality).")
    parser.add_argument("--report-near-miss", action="store_true",
                        help="With --from-json: print the enrollment and admissions near-miss split from the run.")
    args = parser.parse_args()

    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    if args.public:
        target = write_public(args.public, args.public_out_dir)
        log(f"wrote {target}")
        return 0
    if args.report_near_miss:
        if not args.from_json:
            raise SystemExit("--report-near-miss needs --from-json")
        print(render_near_miss(json.loads(args.from_json.read_text())))
        return 0

    if args.from_json:
        data = json.loads(args.from_json.read_text())
    else:
        env = {**(projection.load_env(args.env) if args.env.exists() else {}), **dict(__import__("os").environ)}
        url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required (in --env or the environment)")
        api = Api(url, key, args.min_free_mb, log)
        data = gather(api, tuple(args.years), args.out_dir, args.artifact_interval,
                      args.field_interval, args.worker_summaries, log, args.limit)
        stamp = data["generated_at"].replace(":", "").replace("-", "")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / f"scoreboard-{stamp}.json").write_text(json.dumps(data, indent=1, default=str))
        log(f"wrote {args.out_dir / f'scoreboard-{stamp}.json'}")

    previous = json.loads(args.compare.read_text()) if args.compare else None
    markdown = render(data, previous)
    if not args.from_json:
        (args.out_dir / f"scoreboard-{stamp}.md").write_text(markdown)
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
