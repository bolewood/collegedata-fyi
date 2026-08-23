"""Replay a finder probe log onto schools.yaml without a Brave re-run.

Friday 2026-08-21's probe rewrote seeds on the runner, then lost them when
the seed PR push was rejected. The logs still have every FOUND / not found
line. This reapplies `should_replace_seed` (listings replace PDFs; PDFs
do not replace listings) and records probe_state so the next monthly run
does not burn the budget twice.

Line-based YAML edits on purpose: PyYAML round-trip would strip comments
across the 27k-line manifest.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

from tools.finder.probe_urls import (  # noqa: E402
    host_belongs_to_domain,
    looks_like_article_slug,
    looks_like_news_or_blog,
    looks_like_non_cds_document,
    looks_like_search_junk,
    record_probe,
    should_replace_seed,
)

FOUND_RE = re.compile(
    r"^\[\s*\d+/\d+\]\s+(?P<name>.+) \((?P<domain>[^)]+)\) \.\.\. "
    r"(?:\[(?P<method>\w+)\] )?FOUND: (?P<url>\S+)\s*$"
)
MISS_RE = re.compile(
    r"^\[\s*\d+/\d+\]\s+(?P<name>.+) \((?P<domain>[^)]+)\) \.\.\. not found\s*$"
)
ID_RE = re.compile(r"^- id: (\S+)\s*$")
SEED_RE = re.compile(r"^(  )(?:discovery_seed_url|cds_url_hint)(: )(\S+.*)$")
POLICY_RE = re.compile(r"^(  scrape_policy: )(\S+)\s*$")
PROBED_AT_RE = re.compile(r"^(    last_probed_at: )(.+)$")
LAST_RESULT_RE = re.compile(r"^(    last_result: )(\S+)\s*$")
LAST_METHOD_RE = re.compile(r"^(    last_method: )(\S+)\s*$")


@dataclass(frozen=True)
class ProbeHit:
    name: str
    domain: str | None
    url: str | None
    method: str
    found: bool


def parse_probe_log(text: str) -> list[ProbeHit]:
    hits: list[ProbeHit] = []
    for raw in text.splitlines():
        found = FOUND_RE.match(raw)
        if found:
            domain = found.group("domain")
            hits.append(
                ProbeHit(
                    name=found.group("name"),
                    domain=None if domain in {"None", ""} else domain,
                    url=found.group("url"),
                    method=found.group("method") or "pattern",
                    found=True,
                )
            )
            continue
        miss = MISS_RE.match(raw)
        if miss:
            domain = miss.group("domain")
            hits.append(
                ProbeHit(
                    name=miss.group("name"),
                    domain=None if domain in {"None", ""} else domain,
                    url=None,
                    method="brave",
                    found=False,
                )
            )
    return hits


def index_schools(schools: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for school in schools:
        name = str(school.get("name") or "")
        domain = str(school.get("domain") or "")
        out[(name, domain)] = school
    return out


def resolve_school(hit: ProbeHit, by_key: dict[tuple[str, str], dict]) -> dict | None:
    if hit.domain:
        return by_key.get((hit.name, hit.domain))
    matches = [school for (name, _domain), school in by_key.items() if name == hit.name]
    if len(matches) == 1:
        return matches[0]
    return None


def url_is_usable(url: str, domain: str | None) -> bool:
    if (
        looks_like_search_junk(url)
        or looks_like_article_slug(url)
        or looks_like_news_or_blog(url)
        or looks_like_non_cds_document(url)
    ):
        return False
    if domain and not host_belongs_to_domain(url, domain):
        return False
    return True


def apply_hit(school: dict, hit: ProbeHit, probed_at: str) -> str:
    """Mutate school. Returns action: replaced, found_kept, not_found, skipped_junk."""
    if hit.found:
        url = hit.url or ""
        if not url_is_usable(url, hit.domain or school.get("domain")):
            return "skipped_junk"
        existing = school.get("discovery_seed_url") or school.get("cds_url_hint")
        if should_replace_seed(existing, url):
            school["discovery_seed_url"] = url
            school["scrape_policy"] = "active"
            record_probe(school, "found", hit.method, 0, hit.method != "pattern")
            school["probe_state"]["last_probed_at"] = probed_at
            return "replaced"
        record_probe(school, "found", hit.method, 0, hit.method != "pattern")
        school["probe_state"]["last_probed_at"] = probed_at
        return "found_kept"
    record_probe(school, "not_found", hit.method, 0, True)
    school["probe_state"]["last_probed_at"] = probed_at
    return "not_found"


def write_school_updates(schools_yaml: Path, schools: list[dict], changed_ids: set[str]) -> int:
    """Rewrite seed, scrape_policy, and probe_state lines for changed ids."""
    by_id = {str(school.get("id")): school for school in schools}
    lines = schools_yaml.read_text().splitlines(keepends=True)
    out: list[str] = []
    current_sid: str | None = None
    wrote_seed = False
    applied = 0

    def flush_missing_seed() -> None:
        nonlocal applied
        if current_sid not in changed_ids or wrote_seed:
            return
        school = by_id.get(current_sid or "")
        url = school.get("discovery_seed_url") if school else None
        if not url:
            return
        out.append(f"  discovery_seed_url: {url}\n")
        applied += 1

    for line in lines:
        matched_id = ID_RE.match(line)
        if matched_id:
            flush_missing_seed()
            current_sid = matched_id.group(1)
            wrote_seed = False
            out.append(line)
            continue

        school = by_id.get(current_sid or "")
        if current_sid not in changed_ids or school is None:
            out.append(line)
            continue

        seed_match = SEED_RE.match(line)
        if seed_match:
            url = school.get("discovery_seed_url")
            if url:
                out.append(f"{seed_match.group(1)}discovery_seed_url{seed_match.group(2)}{url}\n")
                wrote_seed = True
                applied += 1
                continue

        policy_match = POLICY_RE.match(line)
        if policy_match and school.get("scrape_policy"):
            out.append(f"{policy_match.group(1)}{school['scrape_policy']}\n")
            continue

        probed_match = PROBED_AT_RE.match(line)
        if probed_match and school.get("probe_state"):
            stamped = school["probe_state"].get("last_probed_at")
            out.append(f"{probed_match.group(1)}'{stamped}'\n")
            continue

        result_match = LAST_RESULT_RE.match(line)
        if result_match and school.get("probe_state"):
            out.append(
                f"{result_match.group(1)}{school['probe_state'].get('last_result')}\n"
            )
            continue

        method_match = LAST_METHOD_RE.match(line)
        if method_match and school.get("probe_state"):
            out.append(
                f"{method_match.group(1)}{school['probe_state'].get('last_method')}\n"
            )
            continue

        out.append(line)

    flush_missing_seed()
    schools_yaml.write_text("".join(out))
    return applied


def apply_logs(
    schools_yaml: Path,
    log_paths: list[Path],
    *,
    probed_at: str,
    dry_run: bool = False,
) -> dict[str, int]:
    data = yaml.safe_load(schools_yaml.read_text())
    schools = data.get("schools") or []
    by_key = index_schools(schools)
    counts = {
        "hits": 0,
        "unmatched": 0,
        "replaced": 0,
        "found_kept": 0,
        "not_found": 0,
        "skipped_junk": 0,
    }
    changed: set[str] = set()
    for log_path in log_paths:
        for hit in parse_probe_log(log_path.read_text()):
            counts["hits"] += 1
            school = resolve_school(hit, by_key)
            if school is None:
                counts["unmatched"] += 1
                print(f"unmatched: {hit.name} ({hit.domain})", file=sys.stderr)
                continue
            action = apply_hit(school, hit, probed_at)
            counts[action] = counts.get(action, 0) + 1
            sid = str(school.get("id") or "")
            if sid and action != "skipped_junk":
                changed.add(sid)
    if not dry_run:
        write_school_updates(schools_yaml, schools, changed)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--schools-yaml", type=Path, default=Path("tools/finder/schools.yaml"))
    ap.add_argument("--log", type=Path, action="append", required=True)
    ap.add_argument(
        "--probed-at",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary-json", type=Path)
    args = ap.parse_args()
    counts = apply_logs(
        args.schools_yaml,
        args.log,
        probed_at=args.probed_at,
        dry_run=args.dry_run,
    )
    print(json.dumps(counts, indent=2, sort_keys=True))
    if args.summary_json:
        args.summary_json.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
