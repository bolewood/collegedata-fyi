#!/usr/bin/env python3
"""Load validated scholarship records into Supabase (PRD 036 M2).

Usage:
    python tools/scholarships/load.py                      # dry run, no network
    python tools/scholarships/load.py --check-db           # dry run, read-only DB compare
    python tools/scholarships/load.py --apply              # write; needs credentials
    python tools/scholarships/load.py path/to/programs     # another programs tree

Validates the whole tree first (the same checks as validate.py, minus the
published-version git compare, which CI runs on the PR). Any issue aborts.

--apply upserts scholarship_programs, scholarship_program_versions and
scholarship_sources, keyed on program_id and (program_id, version_id), then
prunes rows whose program, version or source is no longer in the YAML (so a
removed draft cannot stay public; a run that would remove more than 5 programs
or 10% of them is refused unless --allow-prune), then calls
refresh_scholarship_directory_cache(). It is idempotent: a second run writes
the same rows and prunes nothing. The writes are separate PostgREST requests,
not one transaction; parents go first and prune goes last, so a failed run
leaves a state the next run repairs.

normalized_coverage is not in the YAML. It is derived per offer (model.py) and
stored on the version's `offers` column.

Credentials: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from the environment,
or from the repo's .env. The migration must be applied first (from main).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402
import validate  # noqa: E402

REPO_ROOT = validate.REPO_ROOT
DEFAULT_REPORT = REPO_ROOT / "scratch" / "scholarships" / "load-report.json"
CHUNK = 100

TABLE_KEYS = {
    "scholarship_programs": ("program_id",),
    "scholarship_program_versions": ("program_id", "version_id"),
    "scholarship_sources": ("program_id", "version_id", "source_id"),
}


# ------------------------------------------------------------------ validation


def load_dataset(programs_dir: Path) -> Tuple[Optional[model.Dataset], List[validate.Issue]]:
    """Validate the tree, then build rows. Dataset is None when anything fails."""
    issues = validate.validate_tree(programs_dir)
    if issues:
        return None, issues
    docs: Dict[str, Dict[str, Any]] = {}
    for path in sorted(programs_dir.glob("*/*.yaml")):
        docs[str(path)] = validate.load_yaml_text(path.read_text(encoding="utf-8"))
    return model.build_dataset(docs, root=REPO_ROOT), []


# ----------------------------------------------------------------- prune plan


@dataclass
class Existing:
    programs: Set[Tuple[str, ...]] = field(default_factory=set)
    versions: Set[Tuple[str, ...]] = field(default_factory=set)
    sources: Set[Tuple[str, ...]] = field(default_factory=set)


@dataclass
class Prune:
    programs: List[Tuple[str, ...]] = field(default_factory=list)
    versions: List[Tuple[str, ...]] = field(default_factory=list)
    sources: List[Tuple[str, ...]] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.programs or self.versions or self.sources)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "programs": [list(k) for k in self.programs],
            "versions": [list(k) for k in self.versions],
            "sources": [list(k) for k in self.sources],
        }


def _keys(rows: Iterable[Dict[str, Any]], table: str) -> Set[Tuple[str, ...]]:
    cols = TABLE_KEYS[table]
    return {tuple(r[c] for c in cols) for r in rows}


def compute_prune(ds: model.Dataset, existing: Existing) -> Prune:
    """Database rows with no counterpart in the YAML.

    Versions and sources of a pruned program are not listed separately; the
    foreign keys cascade.
    """
    want_programs = _keys(ds.programs, "scholarship_programs")
    want_versions = _keys(ds.versions, "scholarship_program_versions")
    want_sources = _keys(ds.sources, "scholarship_sources")
    gone_programs = sorted(existing.programs - want_programs)
    gone_ids = {k[0] for k in gone_programs}
    gone_versions = sorted(k for k in existing.versions - want_versions if k[0] not in gone_ids)
    gone_version_keys = {k for k in gone_versions}
    gone_sources = sorted(
        k
        for k in existing.sources - want_sources
        if k[0] not in gone_ids and (k[0], k[1]) not in gone_version_keys
    )
    return Prune(gone_programs, gone_versions, gone_sources)


# ---------------------------------------------------------------------- store


class Store:
    """The database operations the loader needs. SupabaseStore is the real one."""

    def existing(self) -> Existing:  # pragma: no cover - interface
        raise NotImplementedError

    def upsert(self, table: str, rows: List[Dict[str, Any]]) -> None:  # pragma: no cover
        raise NotImplementedError

    def delete(self, table: str, keys: List[Tuple[str, ...]]) -> None:  # pragma: no cover
        raise NotImplementedError

    def refresh(self) -> Optional[int]:  # pragma: no cover
        raise NotImplementedError


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class SupabaseStore(Store):
    def __init__(self, url: str, key: str) -> None:
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("supabase package is required for --apply / --check-db") from exc
        self.client = create_client(url, key)

    @classmethod
    def from_env(cls) -> "SupabaseStore":
        load_env(REPO_ROOT / ".env")
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return cls(url, key)

    def _all(self, table: str, cols: Tuple[str, ...]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        start = 0
        while True:
            query = self.client.table(table).select(",".join(cols))
            for col in cols:  # a total order keeps pages from overlapping
                query = query.order(col)
            page = query.range(start, start + 999).execute().data
            out.extend(page)
            if len(page) < 1000:
                return out
            start += 1000

    def existing(self) -> Existing:
        return Existing(
            programs=_keys(self._all("scholarship_programs", TABLE_KEYS["scholarship_programs"]), "scholarship_programs"),
            versions=_keys(
                self._all("scholarship_program_versions", TABLE_KEYS["scholarship_program_versions"]),
                "scholarship_program_versions",
            ),
            sources=_keys(self._all("scholarship_sources", TABLE_KEYS["scholarship_sources"]), "scholarship_sources"),
        )

    def upsert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        on_conflict = ",".join(TABLE_KEYS[table])
        for i in range(0, len(rows), CHUNK):
            self.client.table(table).upsert(rows[i : i + CHUNK], on_conflict=on_conflict).execute()

    def delete(self, table: str, keys: List[Tuple[str, ...]]) -> None:
        # Delete with a non-empty filter always (the database runs safeupdate).
        cols = TABLE_KEYS[table]
        if len(cols) == 1:
            for i in range(0, len(keys), CHUNK):
                self.client.table(table).delete().in_(cols[0], [k[0] for k in keys[i : i + CHUNK]]).execute()
            return
        grouped: Dict[Tuple[str, ...], List[str]] = {}
        for k in keys:
            grouped.setdefault(k[:-1], []).append(k[-1])
        for prefix, last in grouped.items():
            q = self.client.table(table).delete()
            for col, val in zip(cols[:-1], prefix):
                q = q.eq(col, val)
            q.in_(cols[-1], last).execute()

    def refresh(self) -> Optional[int]:
        res = self.client.rpc("refresh_scholarship_directory_cache").execute()
        return res.data if isinstance(res.data, int) else None


# ---------------------------------------------------------------------- apply


class RefusedError(RuntimeError):
    """The apply would do something the loader will not do without a flag."""


# Removing more than this many programs, or this share of them, in one run looks
# like a bad checkout rather than an edit, and the cascade also deletes their
# check history. One program may always be removed.
MAX_PRUNE_PROGRAMS = 5
MAX_PRUNE_SHARE = 0.10


def check_prune_guard(prune: Prune, existing: Existing, allow_prune: bool) -> None:
    n, total = len(prune.programs), len(existing.programs)
    if allow_prune or n <= 1:
        return
    if n > MAX_PRUNE_PROGRAMS or n / total > MAX_PRUNE_SHARE:
        raise RefusedError(
            f"this run would remove {n} of {total} programs (limit: {MAX_PRUNE_PROGRAMS} programs "
            f"or {int(MAX_PRUNE_SHARE * 100)}%); that looks like a bad checkout, not an edit. "
            "Check the tree, then pass --allow-prune to proceed."
        )


def apply(store: Store, ds: model.Dataset, allow_prune: bool = False) -> Dict[str, Any]:
    """Upsert, prune, refresh. Returns a summary. Raises RefusedError before any write."""
    existing = store.existing()
    prune = compute_prune(ds, existing)
    if not ds.programs and existing.programs and not allow_prune:
        raise RefusedError(
            f"the YAML tree has no programs but the database has {len(existing.programs)}; "
            "this looks like a bad checkout. Pass --allow-prune to remove them all."
        )
    check_prune_guard(prune, existing, allow_prune)
    store.upsert("scholarship_programs", ds.programs)
    store.upsert("scholarship_program_versions", ds.versions)
    store.upsert("scholarship_sources", ds.sources)
    if prune.sources:
        store.delete("scholarship_sources", prune.sources)
    if prune.versions:
        store.delete("scholarship_program_versions", prune.versions)
    if prune.programs:
        store.delete("scholarship_programs", prune.programs)
    refreshed = store.refresh()
    return {"upserted": counts(ds), "pruned": prune.as_dict(), "cache_rows": refreshed}


def counts(ds: model.Dataset) -> Dict[str, int]:
    return {
        "programs": len(ds.programs),
        "versions": len(ds.versions),
        "sources": len(ds.sources),
        "published_programs": len(model.select_published(ds)),
    }


def build_report(ds: model.Dataset, prune: Optional[Prune]) -> Dict[str, Any]:
    published = {r["program_id"]: r["version_id"] for r in model.select_published(ds)}
    return {
        "counts": counts(ds),
        # Every school a program page appears on: the load workflow tells the web app to refresh these.
        "school_ids": sorted({sch["school_id"] for p in ds.programs for sch in model.participants_of(p)}),
        "programs": [
            {
                "program_id": p["program_id"],
                "published_version": published.get(p["program_id"]),
                "versions": [
                    {
                        "version_id": v["version_id"],
                        "entry_year": v["entry_year"],
                        "verification_status": v["verification_status"],
                        "is_chain_head": v["is_chain_head"],
                        "coverage_by_offer": {o["offer_id"]: o["normalized_coverage"] for o in v["offers"]},
                    }
                    for v in ds.versions
                    if v["program_id"] == p["program_id"]
                ],
            }
            for p in ds.programs
        ],
        "would_prune": prune.as_dict() if prune else None,
    }


# ------------------------------------------------------------------------ CLI


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("programs_dir", nargs="?", type=Path, default=validate.DEFAULT_PROGRAMS_DIR)
    ap.add_argument("--apply", action="store_true", help="write to Supabase (default is a dry run)")
    ap.add_argument("--check-db", action="store_true", help="dry run that also reads the database to list what --apply would prune")
    ap.add_argument("--allow-prune", action="store_true", help="allow --apply to remove many programs at once (more than 5 or 10%% of them, or all of them)")
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="where to write the JSON report")
    args = ap.parse_args(argv)

    ds, issues = load_dataset(args.programs_dir)
    if ds is None:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"FAILED: {len(issues)} validation issue(s); nothing loaded", file=sys.stderr)
        return 1

    store: Optional[SupabaseStore] = SupabaseStore.from_env() if (args.apply or args.check_db) else None
    prune = compute_prune(ds, store.existing()) if store and not args.apply else None
    report = build_report(ds, prune)

    if args.apply:
        assert store is not None
        try:
            result = apply(store, ds, allow_prune=args.allow_prune)
        except RefusedError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
        report["applied"] = result
        print(f"APPLIED: {json.dumps(result['upserted'])}; pruned {sum(len(v) for v in result['pruned'].values())} row(s); cache rows {result['cache_rows']}")
    else:
        c = report["counts"]
        print(
            f"DRY RUN: {c['programs']} program(s), {c['versions']} version(s), {c['sources']} source(s); "
            f"{c['published_programs']} would be served by scholarship_directory. Pass --apply to write."
        )
        if prune is not None and not prune.empty():
            print(f"  would prune: {json.dumps(prune.as_dict())}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
