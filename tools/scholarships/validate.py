#!/usr/bin/env python3
"""Validate named scholarship program records (PRD 036 M1).

Usage:
    python tools/scholarships/validate.py data/scholarships/programs
    python tools/scholarships/validate.py data/scholarships/programs --base origin/main
    python tools/scholarships/validate.py --print-fields   # regenerate FIELDS.md body

Checks, each with a stable error code:

    E_YAML                      file is not loadable YAML (or has duplicate keys)
    E_SCHEMA                    record does not match program.schema.json
    E_DIR_MISMATCH              file is not at <school_id>/<program_id>.yaml
    E_IDENTITY                  school_id / ipeds_id do not resolve together
    E_OFF_DOMAIN                a source is not on the school or an allowlisted foundation domain
    E_DUPLICATE_ID              duplicate program, version, offer, benefit or source id
    E_EVIDENCE_PATH             field_evidence points at a path that does not exist
    E_EVIDENCE_SOURCE           field_evidence or award_counts names an unknown source id
    E_EXCERPT_LENGTH            short_excerpt is longer than 25 words
    E_NO_EVIDENCE               a publication-grade field has no field_evidence
    E_GUARANTEED_NO_EVIDENCE    automatic_guaranteed without a quoted official promise
    E_SUMMED_TOTAL              a total_program amount the school did not quote
    E_CONFLICT_SHAPE            conflicting evidence needs two or more entries with reported_value
    E_CONFLICT_VALUE            a confident value sits next to conflicting evidence
    E_VERIFIED_INCOMPLETE       verified version lacks reviewer, review date or entry year/label
    E_ENTRY_YEAR_UNKNOWN        dated milestone on a version with no entry_year
    E_MILESTONE_WINDOW          dated milestone outside the version's application cycle
    E_OFFER_PARENT              parent_offer_id missing or cyclic
    E_SUPERSEDES                supersedes names a version that does not exist
    E_RELATION_TARGET           related_programs target does not exist
    E_PUBLISHED_EDITED          a verified version at the base ref changed or vanished
    E_BASE_REF                  --base was given but cannot be resolved

Application cycle for entry_year Y: 1 Jul of Y-1 through 31 Aug of Y. Recurring
milestones (month/day, no year) are exempt.

The identity helpers are imported from tools/finder/identity_guard.py, not copied.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "finder"))
import identity_guard as ig  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "data" / "scholarships" / "schema" / "program.schema.json"
FOUNDATIONS_PATH = REPO_ROOT / "data" / "scholarships" / "foundation_domains.yaml"
DEFAULT_PROGRAMS_DIR = REPO_ROOT / "data" / "scholarships" / "programs"
ARCHIVE_HOSTS = {"web.archive.org"}
MAX_EXCERPT_WORDS = 25
MISSING = object()


@dataclass(frozen=True)
class Issue:
    code: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.code}: {self.message}"


# ---------------------------------------------------------------- YAML loading


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings and rejects duplicate keys."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _construct_mapping(loader: _Loader, node: yaml.MappingNode, deep: bool = False):
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml_text(text: str) -> Any:
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader subclass


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# -------------------------------------------------------------------- context


@dataclass
class Context:
    """Everything the checks need that is not in the record itself."""

    schema: dict[str, Any]
    claims_by_school: dict[str, list[dict[str, Any]]]
    retired_aliases: dict[str, str]
    snapshot: dict[str, dict[str, str]]
    foundations: dict[str, list[str]]
    program_ids: set[str] | None = None  # None: skip relation-target check


def load_context(
    foundations_path: Path = FOUNDATIONS_PATH,
    schema: dict[str, Any] | None = None,
) -> Context:
    claims = ig.load_school_claims()
    by_school: dict[str, list[dict[str, Any]]] = {}
    aliases: dict[str, str] = {}
    for claim in claims:
        by_school.setdefault(claim["school_id"], []).append(claim)
        for alias in claim.get("retired_aliases", []):
            aliases[alias] = claim["school_id"]
    _, snapshot = ig.load_identity_snapshot()
    data = yaml.safe_load(foundations_path.read_text(encoding="utf-8")) or {}
    foundations: dict[str, list[str]] = {}
    for school_id, entries in (data.get("foundations") or {}).items():
        foundations[school_id] = [ig.normalize_domain(e["domain"]) for e in entries]
    return Context(schema or load_schema(), by_school, aliases, snapshot, foundations)


# ------------------------------------------------------------------- helpers


def host_on_domain(url: str, domain: str) -> bool:
    """One-way check: host is the domain or a subdomain of it."""
    host = ig.normalize_domain(url)
    d = ig.normalize_domain(domain)
    return bool(host and d and (host == d or host.endswith("." + d)))


def _deref(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def _schema_child(schema: dict[str, Any], root: dict[str, Any], seg: str):
    """Schema node for one path segment, or None."""
    schema = _deref(schema, root)
    for branch in schema.get("anyOf", []):
        child = _schema_child(branch, root, seg)
        if child is not None:
            return child
    if seg.isdigit() and "items" in schema:
        return schema["items"]
    props = schema.get("properties")
    if props and seg in props:
        return props[seg]
    return None


def resolve_path(version: dict[str, Any], path: str, schema_root: dict[str, Any]):
    """Return (ok, value). ok means the path names a real field of a version.

    A field the schema allows but the record omits resolves with MISSING, so a
    not_published or conflicting entry can point at a field left null.
    """
    node: Any = version
    schema: dict[str, Any] | None = schema_root["$defs"]["version"]
    for seg in path.split("/"):
        if schema is None or not seg:
            return False, None
        child_schema = _schema_child(schema, schema_root, seg)
        if child_schema is None:
            return False, None
        if node is not MISSING and node is not None:
            if isinstance(node, list):
                if not seg.isdigit() or int(seg) >= len(node):
                    return False, None
                node = node[int(seg)]
            elif isinstance(node, dict):
                node = node.get(seg, MISSING)
            else:
                return False, None
        else:
            node = MISSING
        schema = child_schema
    return True, (None if node is MISSING else node)


def _covers(evidence_path: str, field_path: str) -> bool:
    return field_path == evidence_path or field_path.startswith(evidence_path + "/")


def _stated(value: Any) -> bool:
    if value is None or value == "unknown":
        return False
    if isinstance(value, dict) and value.get("qualifier") == "not_published":
        return False
    return True


# -------------------------------------------------------------- record checks


def validate_doc(
    doc: Any,
    ctx: Context,
    where: str = "<record>",
    expected_dir: str | None = None,
    expected_file: str | None = None,
) -> list[Issue]:
    schema_errors = sorted(
        Draft202012Validator(ctx.schema, format_checker=FormatChecker()).iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    if schema_errors:
        return [
            Issue("E_SCHEMA", f"{where}:{'/'.join(map(str, e.absolute_path))}", e.message[:200])
            for e in schema_errors
        ]
    issues: list[Issue] = []
    add = lambda code, loc, msg: issues.append(Issue(code, f"{where}:{loc}", msg))  # noqa: E731

    if expected_dir is not None and doc["school_id"] != expected_dir:
        add("E_DIR_MISMATCH", "school_id", f"school_id {doc['school_id']!r} but directory is {expected_dir!r}")
    if expected_file is not None and doc["program_id"] != expected_file:
        add("E_DIR_MISMATCH", "program_id", f"program_id {doc['program_id']!r} but file is {expected_file!r}.yaml")

    claim = _check_identity(doc, ctx, add)
    allowed_school = set()
    if claim:
        allowed_school.add(claim["claimed_domain"])
        official = ctx.snapshot.get(claim["ipeds_id"], {}).get("official_domain")
        if official:
            allowed_school.add(official)
    foundation = set(ctx.foundations.get(doc["school_id"], []))

    _check_unique(doc, add)
    _check_relations(doc, ctx, add)
    versions_by_id = {v["version_id"]: v for v in doc["versions"]}
    for vi, version in enumerate(doc["versions"]):
        vloc = f"versions/{vi}"
        if claim:  # without a resolved identity the school domain is unknown
            _check_sources(version, vloc, allowed_school, foundation, add)
        _check_offers(version, vloc, add)
        _check_evidence(version, vloc, ctx.schema, add)
        _check_required_evidence(version, vloc, ctx.schema, add)
        _check_verified(version, vloc, add)
        _check_milestones(version, vloc, add)
        sup = version.get("supersedes")
        if sup is not None and (sup not in versions_by_id or sup == version["version_id"]):
            add("E_SUPERSEDES", f"{vloc}/supersedes", f"supersedes {sup!r} is not another version of this program")
    return issues


def _check_identity(doc, ctx, add):
    school_id, ipeds = doc["school_id"], doc["ipeds_id"]
    claims = ctx.claims_by_school.get(school_id)
    if not claims:
        hint = ctx.retired_aliases.get(school_id)
        extra = f"; retired alias, use {hint!r}" if hint else ""
        add("E_IDENTITY", "school_id", f"school_id {school_id!r} is not a known school{extra}")
        return None
    if len(claims) != 1:
        add("E_IDENTITY", "school_id", f"school_id {school_id!r} is ambiguous in schools.yaml")
        return None
    claim = claims[0]
    if ig.normalize_ipeds(ipeds) != claim["ipeds_id"]:
        add("E_IDENTITY", "ipeds_id", f"ipeds_id {ipeds} does not match {school_id!r} (schools.yaml says {claim['ipeds_id']})")
        return None
    if claim["ipeds_id"] not in ctx.snapshot:
        add("E_IDENTITY", "ipeds_id", f"ipeds_id {ipeds} is not in the checked-in IPEDS identity snapshot")
        return None
    return claim


def _check_unique(doc, add):
    def dupes(ids: Iterable[str]) -> set[str]:
        seen, out = set(), set()
        for i in ids:
            (out if i in seen else seen).add(i)
        return out

    for d in dupes(v["version_id"] for v in doc["versions"]):
        add("E_DUPLICATE_ID", "versions", f"duplicate version_id {d!r}")
    for vi, v in enumerate(doc["versions"]):
        for d in dupes(s["source_id"] for s in v["sources"]):
            add("E_DUPLICATE_ID", f"versions/{vi}/sources", f"duplicate source_id {d!r}")
        for d in dupes(o["offer_id"] for o in v["offers"]):
            add("E_DUPLICATE_ID", f"versions/{vi}/offers", f"duplicate offer_id {d!r}")
        for oi, o in enumerate(v["offers"]):
            for d in dupes(b["benefit_id"] for b in o["benefits"]):
                add("E_DUPLICATE_ID", f"versions/{vi}/offers/{oi}/benefits", f"duplicate benefit_id {d!r}")


def _check_relations(doc, ctx, add):
    for i, rel in enumerate(doc.get("related_programs", [])):
        target = rel["program_id"]
        if target == doc["program_id"]:
            add("E_RELATION_TARGET", f"related_programs/{i}", "a program cannot relate to itself")
        elif ctx.program_ids is not None and target not in ctx.program_ids:
            add("E_RELATION_TARGET", f"related_programs/{i}", f"target program {target!r} does not exist")


def _check_sources(version, vloc, allowed_school, foundation, add):
    for si, src in enumerate(version["sources"]):
        loc = f"{vloc}/sources/{si}"
        url = src["url"]
        on_school = any(host_on_domain(url, d) for d in allowed_school)
        on_foundation = any(host_on_domain(url, d) for d in foundation)
        if src["authority"] == "foundation_official":
            if not on_foundation:
                add("E_OFF_DOMAIN", f"{loc}/url", f"{url} is marked foundation_official but is not on an allowlisted foundation domain")
        elif not (on_school or on_foundation):
            add("E_OFF_DOMAIN", f"{loc}/url", f"{url} is not on the school's domain or an allowlisted foundation domain")
        archive = src.get("archive_url")
        if archive and ig.normalize_domain(archive) not in ARCHIVE_HOSTS:
            add("E_OFF_DOMAIN", f"{loc}/archive_url", f"archive_url must be on {sorted(ARCHIVE_HOSTS)}")


def _check_offers(version, vloc, add):
    ids = {o["offer_id"]: o for o in version["offers"]}
    for oi, o in enumerate(version["offers"]):
        seen, cur = {o["offer_id"]}, o.get("parent_offer_id")
        while cur is not None:
            if cur not in ids:
                add("E_OFFER_PARENT", f"{vloc}/offers/{oi}/parent_offer_id", f"parent {cur!r} is not an offer in this version")
                break
            if cur in seen:
                add("E_OFFER_PARENT", f"{vloc}/offers/{oi}/parent_offer_id", "parent_offer_id forms a cycle")
                break
            seen.add(cur)
            cur = ids[cur].get("parent_offer_id")


def _check_evidence(version, vloc, schema_root, add):
    source_ids = {s["source_id"] for s in version["sources"]}
    by_path: dict[str, list[dict[str, Any]]] = {}
    for ei, ev in enumerate(version["field_evidence"]):
        loc = f"{vloc}/field_evidence/{ei}"
        ok, _ = resolve_path(version, ev["field_path"], schema_root)
        if not ok:
            add("E_EVIDENCE_PATH", f"{loc}/field_path", f"{ev['field_path']!r} is not a field of a version")
        if ev["source_ref"] not in source_ids:
            add("E_EVIDENCE_SOURCE", f"{loc}/source_ref", f"unknown source {ev['source_ref']!r}")
        excerpt = ev.get("short_excerpt")
        if excerpt and len(excerpt.split()) > MAX_EXCERPT_WORDS:
            add("E_EXCERPT_LENGTH", f"{loc}/short_excerpt", f"{len(excerpt.split())} words; limit is {MAX_EXCERPT_WORDS}")
        by_path.setdefault(ev["field_path"], []).append(ev)
    for ci, ac in enumerate(version.get("award_counts", [])):
        if ac["source_ref"] not in source_ids:
            add("E_EVIDENCE_SOURCE", f"{vloc}/award_counts/{ci}/source_ref", f"unknown source {ac['source_ref']!r}")
    for path, evs in by_path.items():
        conflicting = [e for e in evs if e["value_status"] == "conflicting"]
        if not conflicting:
            continue
        if len(conflicting) < 2 or any(e.get("reported_value") is None for e in conflicting):
            add("E_CONFLICT_SHAPE", f"{vloc}/field_evidence", f"{path!r}: conflicting needs two or more entries, each with reported_value")
        ok, value = resolve_path(version, path, schema_root)
        if ok and _stated(value):
            add("E_CONFLICT_VALUE", f"{vloc}/{path}", "field has a value although its evidence is conflicting; leave it null")


def _required_evidence_paths(version) -> list[tuple[str, str]]:
    """(path, kind) for every publication-grade field that holds a stated value."""
    out: list[tuple[str, str]] = []
    for oi, o in enumerate(version["offers"]):
        base = f"offers/{oi}"
        if _stated(o["selection_mode"]):
            out.append((f"{base}/selection_mode", "guaranteed" if o["selection_mode"] == "automatic_guaranteed" else "plain"))
        if _stated((o.get("eligibility") or {}).get("national_merit_statuses")):
            out.append((f"{base}/eligibility/national_merit_statuses", "plain"))
        for bi, b in enumerate(o["benefits"]):
            amount = b.get("amount")
            if _stated(amount):
                kind = "total" if amount.get("period") == "total_program" else "plain"
                out.append((f"{base}/benefits/{bi}/amount", kind))
    app = version.get("application")
    if app:
        if _stated(app["separate_application"]):
            out.append(("application/separate_application", "plain"))
        for mi, m in enumerate(app["milestones"]):
            out.append((f"application/milestones/{mi}", "plain"))
    return out


def _check_required_evidence(version, vloc, schema_root, add):
    evidence = version["field_evidence"]
    for path, kind in _required_evidence_paths(version):
        covering = [e for e in evidence if _covers(e["field_path"], path)]
        if kind == "guaranteed":
            ok = any(
                e["value_status"] == "reported" and e.get("short_excerpt") for e in covering
            )
            if not ok:
                add("E_GUARANTEED_NO_EVIDENCE", f"{vloc}/{path}", "automatic_guaranteed needs reported evidence with a short_excerpt of the school's explicit promise")
        elif kind == "total":
            if not any(e["value_status"] == "reported" for e in covering):
                add("E_SUMMED_TOTAL", f"{vloc}/{path}", "a total_program amount must be quoted by the school (reported field_evidence); never add up components")
        elif not covering:
            add("E_NO_EVIDENCE", f"{vloc}/{path}", "publication-grade field has no field_evidence")


def _check_verified(version, vloc, add):
    if version["verification_status"] != "verified":
        return
    if not version.get("last_reviewed_at"):
        add("E_VERIFIED_INCOMPLETE", f"{vloc}/last_reviewed_at", "verified version needs last_reviewed_at")
    if not version.get("reviewed_by"):
        add("E_VERIFIED_INCOMPLETE", f"{vloc}/reviewed_by", "verified version needs reviewed_by")
    if version["entry_year"] is None and not version.get("entry_year_label"):
        add("E_VERIFIED_INCOMPLETE", f"{vloc}/entry_year", "verified version needs entry_year or an explicit entry_year_label")


def _check_milestones(version, vloc, add):
    app = version.get("application")
    if not app:
        return
    year = version["entry_year"]
    for mi, m in enumerate(app["milestones"]):
        if m.get("date") is None:
            continue  # recurring: exempt
        loc = f"{vloc}/application/milestones/{mi}/date"
        try:
            d = dt.date.fromisoformat(m["date"])
        except ValueError:
            add("E_SCHEMA", loc, f"{m['date']!r} is not a calendar date")
            continue
        if year is None:
            add("E_ENTRY_YEAR_UNKNOWN", loc, "dated milestone on a version with no entry_year; use a recurring month/day")
            continue
        lo, hi = dt.date(year - 1, 7, 1), dt.date(year, 8, 31)
        if not lo <= d <= hi:
            add("E_MILESTONE_WINDOW", loc, f"{m['date']} is outside the {year} entry cycle ({lo} to {hi})")


# ------------------------------------------------------------ published check


def compare_published(
    base_docs: dict[str, Any], head_docs: dict[str, Any]
) -> list[Issue]:
    """A verified version at base must be identical at head.

    Docs are keyed by file path for reporting; versions are matched on
    (program_id, version_id), so a moved file is fine but a deleted, renamed or
    edited verified version is not. A correction is a new version with supersedes.
    """
    head_versions: dict[tuple[str, str], Any] = {}
    for doc in head_docs.values():
        if isinstance(doc, dict):
            for v in doc.get("versions") or []:
                if isinstance(v, dict):
                    head_versions[(doc.get("program_id"), v.get("version_id"))] = v
    issues = []
    for path, doc in base_docs.items():
        if not isinstance(doc, dict):
            continue
        for v in doc.get("versions") or []:
            if not (isinstance(v, dict) and v.get("verification_status") == "verified"):
                continue
            key = (doc.get("program_id"), v.get("version_id"))
            now = head_versions.get(key)
            if now is None:
                issues.append(Issue("E_PUBLISHED_EDITED", path, f"verified version {key[1]!r} of {key[0]!r} was removed or renamed; add a new version with supersedes instead"))
            elif json.dumps(now, sort_keys=True) != json.dumps(v, sort_keys=True):
                issues.append(Issue("E_PUBLISHED_EDITED", path, f"verified version {key[1]!r} of {key[0]!r} was edited; add a new version with supersedes instead"))
    return issues


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def load_base_docs(programs_dir: Path, base: str) -> tuple[dict[str, Any], list[Issue]]:
    top = _git(programs_dir if programs_dir.exists() else programs_dir.parent, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return {}, [Issue("E_BASE_REF", str(programs_dir), "not inside a git repository, cannot compare to --base")]
    repo = Path(top.stdout.strip()).resolve()
    rel = programs_dir.resolve().relative_to(repo).as_posix()
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode != 0:
        return {}, [Issue("E_BASE_REF", base, f"base ref {base!r} does not resolve; fetch it (git fetch origin main) or pass a valid ref")]
    listing = _git(repo, "ls-tree", "-r", "--name-only", base, "--", rel)
    docs: dict[str, Any] = {}
    issues: list[Issue] = []
    for name in listing.stdout.splitlines():
        if not name.endswith(".yaml"):
            continue
        show = _git(repo, "show", f"{base}:{name}")
        try:
            docs[name] = load_yaml_text(show.stdout)
        except yaml.YAMLError as exc:
            issues.append(Issue("E_YAML", f"{base}:{name}", f"base file is not loadable: {exc}"))
    return docs, issues


# ------------------------------------------------------------------- the tree


def validate_tree(
    programs_dir: Path, ctx: Context | None = None, base: str | None = None
) -> list[Issue]:
    ctx = ctx or load_context()
    files = sorted(programs_dir.glob("*/*.yaml")) if programs_dir.is_dir() else []
    stray = [p for p in (sorted(programs_dir.rglob("*.yaml")) if programs_dir.is_dir() else []) if p not in files]
    issues = [Issue("E_DIR_MISMATCH", str(p), "program files live at <school_id>/<program_id>.yaml") for p in stray]
    docs: dict[Path, Any] = {}
    for path in files:
        try:
            docs[path] = load_yaml_text(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            issues.append(Issue("E_YAML", str(path), str(exc).replace("\n", " ")))
    ids = [d["program_id"] for d in docs.values() if isinstance(d, dict) and isinstance(d.get("program_id"), str)]
    ctx = copy.copy(ctx)
    ctx.program_ids = set(ids)
    for pid in {i for i in ids if ids.count(i) > 1}:
        issues.append(Issue("E_DUPLICATE_ID", str(programs_dir), f"program_id {pid!r} appears in more than one file"))
    for path, doc in docs.items():
        issues += validate_doc(doc, ctx, str(path), path.parent.name, path.stem)
    if base:
        base_docs, base_issues = load_base_docs(programs_dir, base)
        issues += base_issues
        if not any(i.code == "E_BASE_REF" for i in base_issues):
            top = Path(_git(programs_dir, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
            head = {p.resolve().relative_to(top).as_posix(): d for p, d in docs.items()}
            issues += compare_published(base_docs, head)
    return issues


# ------------------------------------------------------------------ FIELDS.md


def schema_leaf_rows(schema: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(path, type, enum or note) for every field in the schema, in order."""
    rows: list[tuple[str, str, str]] = []

    def type_of(node: dict[str, Any]) -> str:
        node = dict(node)
        if "anyOf" in node:
            parts = [type_of(_deref(b, schema)) if "$ref" not in b else "object" for b in node["anyOf"]]
            return "|".join(dict.fromkeys(parts))
        t = node.get("type")
        if "enum" in node:
            return "enum" + ("|null" if None in node["enum"] else "")
        if isinstance(t, list):
            return "|".join(t)
        return t or "any"

    def walk(node: dict[str, Any], path: str) -> None:
        raw = node
        node = _deref(node, schema)
        branches = [_deref(b, schema) for b in raw.get("anyOf", [])]
        obj_node = node if node.get("type") == "object" else next((b for b in branches if b.get("type") == "object"), None)
        if obj_node is not None:
            if path:
                rows.append((path, "object" + ("|null" if branches else ""), ""))
            for name, child in obj_node["properties"].items():
                walk(child, f"{path}.{name}" if path else name)
            return
        items = node.get("items")
        if node.get("type") == "array" or (isinstance(node.get("type"), list) and "array" in node["type"]):
            inner = _deref(items, schema) if items else {}
            if inner.get("type") == "object":
                rows.append((path + "[]", "array of object" + ("|null" if "null" in str(node.get("type")) else ""), ""))
                for name, child in inner["properties"].items():
                    walk(child, f"{path}[].{name}")
            else:
                note = ""
                if "enum" in inner:
                    note = ", ".join(str(v) for v in inner["enum"] if v is not None)
                rows.append((path + "[]", f"array of {type_of(inner) if inner else 'any'}" + ("|null" if "null" in str(node.get("type")) else ""), note))
            return
        enum = node.get("enum")
        note = ", ".join(str(v) for v in enum if v is not None) if enum else ""
        rows.append((path, type_of(node), note))

    for name, child in schema["properties"].items():
        if name == "versions":
            rows.append(("versions[]", "array of object", ""))
            for vname, vchild in schema["$defs"]["version"]["properties"].items():
                walk(vchild, f"versions[].{vname}")
        else:
            walk(child, name)
    return rows


def render_fields_table(schema: dict[str, Any]) -> str:
    lines = ["| Field path | Type | Allowed values |", "|---|---|---|"]
    for path, typ, note in schema_leaf_rows(schema):
        lines.append(f"| `{path}` | {typ} | {note} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("programs_dir", nargs="?", type=Path, default=DEFAULT_PROGRAMS_DIR)
    ap.add_argument("--base", help="git ref to compare against, e.g. origin/main")
    ap.add_argument("--print-fields", action="store_true", help="print the FIELDS.md table and exit")
    args = ap.parse_args(argv)
    if args.print_fields:
        sys.stdout.write(render_fields_table(load_schema()))
        return 0
    issues = validate_tree(args.programs_dir, base=args.base)
    for issue in issues:
        print(issue, file=sys.stderr)
    n = len(list(args.programs_dir.glob("*/*.yaml"))) if args.programs_dir.is_dir() else 0
    if issues:
        print(f"FAILED: {len(issues)} issue(s) in {n} program file(s)", file=sys.stderr)
        return 1
    print(f"OK: {n} program file(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
