#!/usr/bin/env python3
"""Apply the dedup audit's recommendations.

Reads the audit JSON produced by dedup_audit.py. For each pair where
the recommendation is 'delete-other':
  1. Migrate cds_documents / archive_queue / school_hosting_observations
     rows from the wrong slug to the canonical slug. Conflict policy:
     canonical wins (drop the duplicate row from the wrong slug if the
     canonical already has the same (school_id, cds_year)).
  2. Delete the wrong slug's entry from schools.yaml (line-based rewrite
     to preserve formatting + comments).

Lincoln University (the 'manual-review-both-match' case) is handled by
a separate flag: --rename-lincoln renames both slugs to add state
suffixes ('lincoln-university-mo', 'lincoln-university-pa') and updates
the display name accordingly.

Usage:
    # Show what would happen — no DB writes, no yaml edits
    tools/extraction_worker/.venv/bin/python tools/finder/dedup_migrate.py --dry-run

    # Apply
    tools/extraction_worker/.venv/bin/python tools/finder/dedup_migrate.py --apply

    # Also handle the Lincoln University split
    tools/extraction_worker/.venv/bin/python tools/finder/dedup_migrate.py --apply --rename-lincoln
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
DEFAULT_AUDIT = REPO_ROOT / "tools" / "finder" / "dedup-audit-20260419.json"

# Tables to migrate. Each tuple: (table, column).
# storage_path in cds_artifacts is intentionally NOT updated — the path
# is just a string in the DB; consumers query via storage_path so the
# actual bytes don't need to move. A future cosmetic-cleanup pass can
# rename storage if desired.
TABLES_TO_MIGRATE = [
    "cds_documents",
    "archive_queue",
    "school_hosting_observations",
]


def load_audit(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def migrate_one_pair(sb, wrong_slug: str, canonical_slug: str, dry_run: bool) -> dict:
    """Move all rows from wrong_slug to canonical_slug. Returns counts."""
    counts = {"moved": 0, "dropped_conflicts": 0}

    # cds_documents — the conflict-sensitive case (UNIQUE constraint on
    # (school_id, sub_institutional, cds_year)). For each wrong-slug row,
    # check if a canonical row already exists for same (cds_year). If so,
    # delete the wrong-slug row (canonical wins). Otherwise, UPDATE the
    # school_id to canonical.
    wrong_docs = sb.table("cds_documents").select("id, cds_year, sub_institutional").eq(
        "school_id", wrong_slug
    ).execute().data or []
    canonical_years = set()
    if wrong_docs:
        canon_rows = sb.table("cds_documents").select("cds_year, sub_institutional").eq(
            "school_id", canonical_slug
        ).execute().data or []
        canonical_years = {(r["cds_year"], r.get("sub_institutional")) for r in canon_rows}

    for doc in wrong_docs:
        key = (doc["cds_year"], doc.get("sub_institutional"))
        if key in canonical_years:
            print(f"    cds_documents conflict: {wrong_slug} {key} already in {canonical_slug} → drop wrong")
            if not dry_run:
                # Delete the artifact rows first (FK)
                sb.table("cds_artifacts").delete().eq("document_id", doc["id"]).execute()
                sb.table("cds_documents").delete().eq("id", doc["id"]).execute()
            counts["dropped_conflicts"] += 1
        else:
            print(f"    cds_documents: move {wrong_slug} {doc['cds_year']} → {canonical_slug}")
            if not dry_run:
                sb.table("cds_documents").update(
                    {"school_id": canonical_slug, "school_name": None}
                ).eq("id", doc["id"]).execute()
                # Note: school_name update would need the canonical school's
                # name. We leave it null and let the next bumpVerified bump it.
                # Actually - school_name is NOT NULL. Let me handle this.
                # Look up canonical name from schools.yaml
                # For simplicity, fetch a row that already has it
                sample = sb.table("cds_documents").select("school_name").eq(
                    "school_id", canonical_slug
                ).limit(1).execute().data
                if sample:
                    sb.table("cds_documents").update(
                        {"school_name": sample[0]["school_name"]}
                    ).eq("id", doc["id"]).execute()
            counts["moved"] += 1

    # archive_queue — has UNIQUE(enqueued_run_id, school_id). Both slugs
    # have a row in the same monthly run, so a bulk UPDATE collides.
    # Strategy: for each wrong-slug row, check if the canonical slug
    # already has a row with the same enqueued_run_id. If so, the
    # canonical's row is the one to keep (it's seen real probe activity);
    # delete the wrong-slug row. Otherwise, UPDATE the wrong row to point
    # at the canonical slug.
    wrong_aq = sb.table("archive_queue").select("id, enqueued_run_id").eq(
        "school_id", wrong_slug
    ).execute().data or []
    canonical_run_ids = set()
    if wrong_aq:
        canon_aq = sb.table("archive_queue").select("enqueued_run_id").eq(
            "school_id", canonical_slug
        ).execute().data or []
        canonical_run_ids = {r["enqueued_run_id"] for r in canon_aq}
    for aq in wrong_aq:
        if aq["enqueued_run_id"] in canonical_run_ids:
            print(f"    archive_queue: drop {wrong_slug} run={aq['enqueued_run_id'][:8]} (canonical already has)")
            if not dry_run:
                sb.table("archive_queue").delete().eq("id", aq["id"]).execute()
        else:
            print(f"    archive_queue: move {wrong_slug} run={aq['enqueued_run_id'][:8]} → {canonical_slug}")
            if not dry_run:
                sb.table("archive_queue").update({"school_id": canonical_slug}).eq(
                    "id", aq["id"]
                ).execute()

    # school_hosting_observations — append-only; just rebrand school_id
    sho_count = len(sb.table("school_hosting_observations").select("id").eq(
        "school_id", wrong_slug
    ).execute().data or [])
    if sho_count > 0:
        print(f"    school_hosting_observations: move {sho_count} rows from {wrong_slug} → {canonical_slug}")
        if not dry_run:
            sb.table("school_hosting_observations").update({"school_id": canonical_slug}).eq(
                "school_id", wrong_slug
            ).execute()

    return counts


def remove_school_from_yaml(
    slug_to_delete: str,
    dry_run: bool,
    ipeds_to_delete: str | None = None,
) -> bool:
    """Line-based removal of a `- id: <slug>` block from schools.yaml.

    When two entries share the same slug (the colorado-college / lincoln-university
    case where two yaml rows have the same id but different IPEDS IDs), pass
    ipeds_to_delete to remove only the matching entry. Without it, ALL entries
    with that slug would be removed — wrong for the same-slug case.

    Returns True if at least one entry was removed (or would be in dry-run).
    """
    text = SCHOOLS_YAML.read_text()
    lines = text.splitlines(keepends=True)
    out = []
    found = False
    id_re = re.compile(r"^- id: (\S+)\s*$")
    ipeds_re = re.compile(r"^  ipeds_id: ['\"]?(\d+)['\"]?\s*$")

    # Two-pass approach: first find the line ranges of all entries with the
    # target slug, then check each entry's ipeds_id and decide whether to drop.
    # Each entry runs from a `- id:` line up to (but not including) the next
    # `- id:` line.
    entries: list[tuple[int, int, str]] = []  # (start, end_exclusive, ipeds_id)
    cur_start = None
    cur_id = None
    cur_ipeds = ""
    for i, line in enumerate(lines):
        m_id = id_re.match(line)
        if m_id:
            # Close out the previous entry
            if cur_start is not None and cur_id == slug_to_delete:
                entries.append((cur_start, i, cur_ipeds))
            cur_start = i
            cur_id = m_id.group(1)
            cur_ipeds = ""
            continue
        if cur_id == slug_to_delete:
            m_ipeds = ipeds_re.match(line)
            if m_ipeds:
                cur_ipeds = m_ipeds.group(1)
    # Final entry
    if cur_start is not None and cur_id == slug_to_delete:
        entries.append((cur_start, len(lines), cur_ipeds))

    # Decide which entries to drop
    drop_ranges: list[tuple[int, int]] = []
    for start, end, ipeds in entries:
        if ipeds_to_delete is None:
            drop_ranges.append((start, end))
            found = True
        elif ipeds == ipeds_to_delete:
            drop_ranges.append((start, end))
            found = True

    if not found:
        return False

    # Build the new file by skipping drop_ranges
    drop_indices = set()
    for start, end in drop_ranges:
        for i in range(start, end):
            drop_indices.add(i)
    out = [line for i, line in enumerate(lines) if i not in drop_indices]

    if not dry_run:
        SCHOOLS_YAML.write_text("".join(out))
    return found


def rename_school_in_yaml_by_ipeds(
    old_slug: str, ipeds_id: str, new_slug: str, new_name: str | None,
) -> bool:
    """Rename the entry matching (old_slug AND ipeds_id) — used for the
    same-slug-different-IPEDS case (Lincoln University). Mutates schools.yaml."""
    lines = SCHOOLS_YAML.read_text().splitlines(keepends=True)
    out = []
    id_re = re.compile(r"^- id: (\S+)\s*$")
    name_re = re.compile(r"^(  name: )(.+)$")
    ipeds_re = re.compile(r"^(  ipeds_id: )['\"]?(\d+)['\"]?\s*$")

    # Identify the line range of each entry with old_slug, then mutate the
    # matching one in place.
    entries: list[tuple[int, int, str]] = []  # (start, end_exclusive, ipeds)
    cur_start = None
    cur_id = None
    cur_ipeds = ""
    for i, line in enumerate(lines):
        m = id_re.match(line)
        if m:
            if cur_start is not None and cur_id == old_slug:
                entries.append((cur_start, i, cur_ipeds))
            cur_start = i
            cur_id = m.group(1)
            cur_ipeds = ""
        elif cur_id == old_slug:
            mi = ipeds_re.match(line)
            if mi:
                cur_ipeds = mi.group(2)
    if cur_start is not None and cur_id == old_slug:
        entries.append((cur_start, len(lines), cur_ipeds))

    target = next((e for e in entries if e[2] == ipeds_id), None)
    if not target:
        return False
    start, end, _ = target

    # Mutate in-place: replace `- id:` line; also rewrite name if present
    new_lines = list(lines)
    new_lines[start] = f"- id: {new_slug}\n"
    if new_name:
        for i in range(start + 1, end):
            mn = name_re.match(new_lines[i])
            if mn:
                new_lines[i] = f"{mn.group(1)}{new_name}\n"
                break
    SCHOOLS_YAML.write_text("".join(new_lines))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply schools.yaml dedup migration")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--env", default=".env")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen; no DB writes, no yaml edits")
    parser.add_argument("--apply", action="store_true",
                        help="Actually perform the migration")
    parser.add_argument("--rename-lincoln", action="store_true",
                        help="Also handle the Lincoln University split (rename to "
                             "lincoln-university-mo / lincoln-university-pa)")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("ERROR: must specify --dry-run or --apply", file=sys.stderr)
        return 1

    audit = load_audit(Path(args.audit))
    print(f"Loaded audit: {len(audit)} duplicate-name groups\n")

    load_dotenv(args.env)
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    total_moved = 0
    total_conflicts = 0
    total_yaml_removed = 0
    total_yaml_renamed = 0

    for group in audit:
        rec = group.get("recommendation")
        name = group.get("yaml_name")
        if rec == "delete-other":
            canonical_slug = group["recommended_canonical"]
            # Identify the canonical candidate object so we can match its
            # IPEDS id (handles the same-slug, different-IPEDS case where
            # the slug alone doesn't disambiguate which yaml row to keep).
            canonical_cand = next(
                (c for c in group["candidates"]
                 if c["slug"] == canonical_slug and c["name_match"].startswith("EXACT")),
                None,
            )
            canonical_ipeds = canonical_cand["yaml_ipeds_id"] if canonical_cand else None
            wrongs = [c for c in group["candidates"]
                      if not (c["slug"] == canonical_slug and c["yaml_ipeds_id"] == canonical_ipeds)]
            wrong_summary = [
                f"{c['slug']} (ipeds={c['yaml_ipeds_id']})" for c in wrongs
            ]
            print(f"━━━ {name}: keep {canonical_slug!r} (ipeds={canonical_ipeds}), delete {wrong_summary}")
            for wrong in wrongs:
                wrong_slug = wrong["slug"]
                wrong_ipeds = wrong["yaml_ipeds_id"]
                # Migrate DB rows only when the wrong entry has a *different*
                # slug than canonical. Same-slug case has no DB rows to move
                # (the slug is shared, so all rows already live under the
                # canonical slug).
                if wrong_slug != canonical_slug:
                    counts = migrate_one_pair(sb, wrong_slug, canonical_slug, args.dry_run)
                    total_moved += counts["moved"]
                    total_conflicts += counts["dropped_conflicts"]
                # Remove the wrong yaml entry by slug+ipeds (handles
                # both cross-slug and same-slug cases correctly).
                removed = remove_school_from_yaml(
                    wrong_slug, args.dry_run, ipeds_to_delete=wrong_ipeds,
                )
                if removed:
                    print(f"    schools.yaml: remove entry slug={wrong_slug!r} ipeds={wrong_ipeds}")
                    total_yaml_removed += 1
        elif rec == "manual-review-both-match":
            if name == "lincoln university" and args.rename_lincoln:
                print(f"━━━ {name}: split into state-suffixed slugs")
                # Build (state, slug, ipeds_id) plan + URL-based DB row assignment
                # Lincoln University in MO uses lincolnu.edu (IPEDS 177940).
                # Lincoln University in PA uses lincoln.edu (IPEDS 213598).
                # Migrate existing 'lincoln-university' DB rows to the right
                # new slug by inspecting source_url.
                URL_TO_NEW_SLUG = {
                    "lincolnu.edu": "lincoln-university-mo",   # Missouri
                    "lincoln.edu":  "lincoln-university-pa",   # Pennsylvania
                }
                old_slug = "lincoln-university"
                # Migrate cds_documents
                docs = sb.table("cds_documents").select("id, source_url").eq(
                    "school_id", old_slug
                ).execute().data or []
                for d in docs:
                    src = (d.get("source_url") or "").lower()
                    target = None
                    for host, new_slug in URL_TO_NEW_SLUG.items():
                        if host in src:
                            target = new_slug
                            break
                    if target:
                        print(f"    cds_documents.id={d['id'][:8]} → {target} (url contains {[h for h in URL_TO_NEW_SLUG if h in src][0]})")
                        if not args.dry_run:
                            sb.table("cds_documents").update(
                                {"school_id": target, "school_name": f"Lincoln University ({target.split('-')[-1].upper()})"}
                            ).eq("id", d["id"]).execute()
                        total_moved += 1
                    else:
                        print(f"    cds_documents.id={d['id'][:8]} url={src[:60]} — UNKNOWN host, skipping")
                # Migrate archive_queue + hosting_observations by school_id only
                # (these are non-uniqueness-constrained; we put everything under
                # the MO slug as a placeholder; operator can re-run if needed)
                aq_count = len(sb.table("archive_queue").select("id").eq("school_id", old_slug).execute().data or [])
                if aq_count > 0:
                    print(f"    archive_queue: {aq_count} rows — moving all to lincoln-university-mo (operator may need to split)")
                    if not args.dry_run:
                        sb.table("archive_queue").update({"school_id": "lincoln-university-mo"}).eq(
                            "school_id", old_slug,
                        ).execute()
                # YAML: rename each lincoln-university entry by its IPEDS id
                for c in group["candidates"]:
                    state = c.get("ipeds_state", "").lower()
                    new_slug = f"lincoln-university-{state}"
                    new_name = f"Lincoln University ({c['ipeds_state']})"
                    print(f"    yaml: rename slug='{c['slug']}' ipeds={c['yaml_ipeds_id']} → {new_slug} ({new_name})")
                    if not args.dry_run:
                        rename_school_in_yaml_by_ipeds(
                            c["slug"], c["yaml_ipeds_id"], new_slug, new_name,
                        )
                    total_yaml_renamed += 1
            else:
                print(f"━━━ {name}: manual review (use --rename-lincoln to handle Lincoln Univ split)")
        else:
            print(f"━━━ {name}: skip ({rec})")

    print("\n=== Summary ===")
    print(f"  cds_documents rows moved:     {total_moved}")
    print(f"  cds_documents rows dropped:   {total_conflicts}  (canonical already had data)")
    print(f"  schools.yaml entries removed: {total_yaml_removed}")
    print(f"  schools.yaml entries renamed: {total_yaml_renamed}")
    if args.dry_run:
        print("\n(dry-run; no changes made)")
    else:
        print("\nApplied. Re-run dedup_audit.py to confirm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
