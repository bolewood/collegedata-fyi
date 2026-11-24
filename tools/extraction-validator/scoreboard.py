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
from typing import Any, Callable, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "browser_backend"))
import project_browser_data as projection  # noqa: E402

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
# Quality flags. Flagged documents are left out of sections 1 to 3 and counted
# in section 4. `blank_template` hides a document everywhere; the other two
# keep it out of the school browser's figures and the acceptance history.
HIDDEN_FLAGS = ("blank_template", "low_coverage", "wrong_file")
RELEASE_RANK = {"final": 0, "provisional": 1, "preliminary": 2}
PAGE_SIZE = 1000


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


def run_check(check: SumCheck, numbers: dict[str, Decimal]) -> str:
    """'pass', 'fail' or 'nc' (not checkable).

    A total of 0 beside rows that add to more is an unfilled auto-sum cell,
    which the projection also ignores: not checkable."""
    total = numbers.get(check.total)
    if total is None:
        return "nc"
    for rows, required in check.groups:
        read = [numbers[r] for r in rows if r in numbers]
        if not read or any(r not in numbers for r in required):
            continue
        row_sum = sum(read, Decimal(0))
        if total == 0 and row_sum > 0:
            return "nc"
        return "pass" if abs(row_sum - total) <= check.tolerance else "fail"
    return "nc"


def table_outcomes(schema_version: Optional[str], numbers: dict[str, Decimal]) -> dict[str, str]:
    """One outcome per table: fail if any of its checks fails, pass if at
    least one could be checked and none failed."""
    outcomes = {table: "nc" for table in SUM_TABLES}
    for check in SUM_CHECKS.get(schema_version or "", []):
        result = run_check(check, numbers)
        if result == "fail" or (result == "pass" and outcomes[check.table] == "nc"):
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
                  "source_format,extraction_status,data_quality_flag,removed_at",
        "canonical_year": f"in.({','.join(years)})",
        "order": "document_id",
    })


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


def fetch_federal(api: Api, year_start: int) -> dict[str, dict[str, Decimal]]:
    """IPEDS applicants, admissions and enrolled for the class entering in
    fall `year_start`. `ipeds_facts` keeps every year (the unified view keeps
    only each school's latest); a final release beats a provisional one."""
    best: dict[tuple[str, str], tuple[tuple, Decimal]] = {}
    for row in api.get("ipeds_facts", {
        "select": "ipeds_id,field_key,value_numeric,release_type,created_at",
        "field_key": f"in.({','.join(FEDERAL_KEYS.values())})",
        "data_year": f"eq.{year_start}",
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


def gather(api: Api, years: tuple[str, ...], out_dir: Path, artifact_interval: float,
           field_interval: float, summaries: str, log: Callable[[str], None],
           limit: Optional[int] = None) -> dict[str, Any]:
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
    federal = {
        year: fetch_federal(api, projection.parse_year_start(year) or 0) for year in years
    }
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

    documents: list[dict[str, Any]] = []
    for position, doc in enumerate(sorted(served, key=lambda d: (d["canonical_year"], d["document_id"])), 1):
        document_id, year = doc["document_id"], doc["canonical_year"]
        artifacts = artifact_index.get(document_id, [])
        candidates = [a for a in artifacts if a["kind"] == "canonical"]
        newest = max(candidates, key=lambda r: (str(r.get("created_at") or ""), str(r["id"])), default=None)
        entry: dict[str, Any] = {
            "document_id": document_id, "school_id": doc["school_id"], "year": year,
            "format": doc.get("source_format") or "unknown", "flag": doc.get("data_quality_flag"),
            "sub_institutional": bool(doc.get("sub_institutional")),
            "producer": None, "version": None, "schema_version": None, "fields": 0,
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
                numbers = numbers_from_values(values, definitions.get(schema_version or "") or {}, schema_version)
                entry.update(producer=picked.get("producer"), version=picked.get("producer_version"),
                             schema_version=schema_version, fields=len(values))
                entry["gap_fill_not_read"] = picked.get("producer") == TIER4 and any(
                    a["producer"] == projection.FALLBACK_PRODUCER for a in artifacts)
            entry["admissions"] = printed_admissions(entry["schema_version"], numbers)

        facts = {} if entry["sub_institutional"] else federal[year].get(str(doc.get("ipeds_id") or ""), {})
        entry["federal"] = {
            metric: classify_federal(entry["admissions"][metric], facts.get(key))
            for metric, key in FEDERAL_KEYS.items()
        }
        entry["sums"] = table_outcomes(entry["schema_version"], numbers)
        entry["check_numbers"] = {
            field_id: str(numbers[field_id])
            for check in SUM_CHECKS.get(entry["schema_version"] or "", [])
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
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years": list(years),
        "current_tier4_version": current_tier4_version(),
        "projected_years": list(projected_years),
        "federal_schools": {year: len(facts) for year, facts in federal.items()},
        "hold_summaries_read": len(glob.glob(summaries)),
        "not_served": {f"{year} {status}": count for (year, status), count in sorted(not_served.items())},
        "documents": documents,
    }


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
        shown = [d for d in docs if d["flag"] not in HIDDEN_FLAGS]
        metrics[f"{key}|docs"] = len(shown)
        metrics[f"{key}|flagged"] = len(docs) - len(shown)

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
            for outcome in ("pass", "fail", "nc"):
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


def render(data: dict[str, Any], previous: Optional[dict[str, Any]] = None) -> str:
    metrics = aggregate(data)
    before = aggregate(previous) if previous else {}
    current = data["current_tier4_version"]

    def cell(key: str) -> str:
        value = metrics.get(key)
        if value is None:
            return "–"
        text = f"{value:,}"
        if previous is not None and before.get(key) is not None and before[key] != value:
            text += f" ({value - before[key]:+,})"
        return text

    def triple(key: str, table: str) -> str:
        return " / ".join(cell(f"{key}|{table}_{o}") for o in ("pass", "fail", "nc"))

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
        if not data["federal_schools"].get(year):
            lines.append(f"\n{year}: no federal admissions figures are loaded for that fall yet, so it is not scored.")

    lines += ["", "### 2. Coverage", "", "Fields per served extraction.",
              "", "| Year | Format | Docs | Median | 10th percentile |", "|---|---|---:|---:|---:|"]
    for key in keys:
        year, fmt = key.split("|")
        if metrics[f"{key}|docs"]:
            lines.append(f"| {year} | {fmt} | {cell(key + '|docs')} | {cell(key + '|fields_median')} | "
                         f"{cell(key + '|fields_p10')} |")

    lines += ["", "### 3. Internal consistency",
              "", "Documents whose printed totals agree with their rows: pass / fail / not checkable. "
              "B1: undergraduates by sex, and undergraduate + graduate. C1: applied, admitted and enrolled by sex. "
              "H1: grant and self-help totals, need-based and non-need-based (within $5).",
              "", "| Year | Format | Docs | B1 | C1 | H1 |", "|---|---|---:|---|---|---|"]
    for key in keys:
        year, fmt = key.split("|")
        if metrics[f"{key}|docs"]:
            lines.append(f"| {year} | {fmt} | {cell(key + '|docs')} | {triple(key, 'B1')} | "
                         f"{triple(key, 'C1')} | {triple(key, 'H1')} |")

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
    if data["not_served"]:
        lines.append("\nNot counted above: " + "; ".join(f"{k} {v}" for k, v in data["not_served"].items()) + ".")
    return "\n".join(lines) + "\n"


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
    args = parser.parse_args()

    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

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
