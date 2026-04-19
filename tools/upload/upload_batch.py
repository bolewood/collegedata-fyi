#!/usr/bin/env python3
"""Batch upload — drop PDFs/XLSX/DOCX into a folder, this tool figures
out the school_id + cds_year from the filename and uploads each one.

Filename parsing rules (applied in order; first match wins):

  Year extraction:
    - YYYY-YYYY      (e.g. 2024-2025)
    - YYYY_YYYY      (e.g. 2024_2025)
    - YYYY-YY        (e.g. 2024-25)
    - YYYY_YY        (e.g. 2024_25)
    - YYYYYY         (e.g. 202425, common in cdsXXXX shapes)
    - YYYY only      → assume that's the start year (warn)
    Output is normalized to YYYY-YY where YY = (YYYY+1) % 100.

  School matching:
    - Folder name immediately above the file matches a schools.yaml id  → use it
    - Filename token sequence matches a schools.yaml name (case-insensitive)
    - Fuzzy match (>=0.85 ratio on the highest-scoring contiguous token run)
    - Fallback: skip and report "unmatched"

The tool produces a planned manifest first. With --yes (or after
confirmation), it calls archive-upload for each file. Anything
unmatched is listed and skipped — never auto-guessed below the
match threshold.

Usage:
    # See what would happen
    python tools/upload/upload_batch.py ~/Downloads/cds/

    # Actually upload
    python tools/upload/upload_batch.py ~/Downloads/cds/ --yes

    # Constrain to one school (folder is treated as authoritative)
    python tools/upload/upload_batch.py ~/Downloads/williams/ --school williams --yes
"""

from __future__ import annotations

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
UPLOAD_PY = Path(__file__).resolve().parent / "upload.py"

SUPPORTED_EXTS = {".pdf", ".xlsx", ".xls", ".docx", ".doc"}

# Year-pair patterns. Order matters — most specific first.
YEAR_PATTERNS = [
    # YYYY-YYYY (CDS_2024_2025, 2024-2025-Common-Data-Set, ...)
    re.compile(r"(?<!\d)(20\d{2})[\-_](20\d{2})(?!\d)"),
    # YYYY-YY (cds-2024-25, CDS_2425 split with separator)
    re.compile(r"(?<!\d)(20\d{2})[\-_](\d{2})(?!\d)"),
    # YYYYYY (cds_202425) — six consecutive digits, must split as 4+2
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(?!\d)"),
    # CDS<YY> — two-digit shorthand like CDS22 (assumes 20xx)
    re.compile(r"(?:^|[^\d])(?:CDS|cds)[_\-]?(\d{2})(?!\d)"),
    # Lone YYYY (last resort, may be ambiguous)
    re.compile(r"(?<!\d)(20\d{2})(?!\d)"),
]


def parse_year(filename: str) -> Optional[str]:
    """Return CDS academic year in 'YYYY-YY' form, or None."""
    name = filename.lower()
    for pat in YEAR_PATTERNS:
        m = pat.search(name)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 2:
            yyyy = int(groups[0])
            second = int(groups[1])
            # Disambiguate YYYY-YY vs YYYY-YYYY
            if second < 100:
                # Two-digit year: should be (yyyy+1) % 100
                if second == (yyyy + 1) % 100:
                    return f"{yyyy}-{second:02d}"
            else:
                # Four-digit year: should be yyyy + 1
                if second == yyyy + 1:
                    return f"{yyyy}-{second % 100:02d}"
        elif len(groups) == 1:
            val = groups[0]
            if len(val) == 2:
                # CDS22 → year 2022 → 2022-23
                yy = int(val)
                yyyy = 2000 + yy
                return f"{yyyy}-{(yyyy + 1) % 100:02d}"
            if len(val) == 4:
                yyyy = int(val)
                return f"{yyyy}-{(yyyy + 1) % 100:02d}"
    return None


def load_schools() -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (by_id, by_lowername)."""
    with open(SCHOOLS_YAML) as f:
        corpus = yaml.safe_load(f)
    schools = corpus.get("schools", [])
    by_id = {s["id"]: s for s in schools}
    by_name = {s["name"].lower(): s for s in schools}
    return by_id, by_name


def parse_school(
    filename: str,
    folder_name: str,
    by_id: dict[str, dict],
    by_name: dict[str, dict],
    forced_school: Optional[str],
) -> tuple[Optional[str], float, str]:
    """Return (school_id, score, source-of-match-reason)."""
    if forced_school:
        if forced_school in by_id:
            return forced_school, 1.0, "operator-forced via --school"
        return None, 0.0, f"--school {forced_school} not in schools.yaml"

    # 1. Folder name == school_id
    if folder_name in by_id:
        return folder_name, 1.0, "folder name matches schools.yaml id"

    # 2. Folder name fuzzy-matches a school name
    folder_low = folder_name.lower().replace("-", " ").replace("_", " ")
    if folder_low in by_name:
        return by_name[folder_low]["id"], 1.0, "folder name matches school name"

    # Strip common CDS-related noise from the filename for matching
    stem = Path(filename).stem.lower()
    cleaned = re.sub(r"\b(cds|common[\s\-_]*data[\s\-_]*set)\b", " ", stem)
    cleaned = re.sub(r"\b(20\d{2})[\-_]?(20\d{2}|\d{2})?\b", " ", cleaned)
    cleaned = re.sub(r"\b(final|v\d+|version|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|fall|spring|updated|revised)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"[\-_]+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None, 0.0, "filename has no school tokens after stripping CDS noise"

    # 3. cleaned tokens form a school name (substring search in schools.yaml names)
    for name_low, s in by_name.items():
        if cleaned == name_low:
            return s["id"], 1.0, f"filename matches school name '{s['name']}'"

    # 4. Fuzzy match the cleaned string against school names — accept >=0.85
    best, best_score = None, 0.0
    for name_low, s in by_name.items():
        r = SequenceMatcher(None, cleaned, name_low).ratio()
        if r > best_score:
            best, best_score = s, r
    if best and best_score >= 0.85:
        return best["id"], best_score, f"fuzzy match to '{best['name']}'"

    # 5. Substring of school name → school. Iterate by_id (not by_name)
    # because the corpus has duplicate entries — e.g., id='williams' AND
    # id='williams-college' both named "Williams College". by_name collapses
    # them; we want to consider all of them.
    # Ambiguity-resolution rules, in order:
    #   a. If filename contains a school_id exactly, that wins.
    #   b. Otherwise, prefer the shortest slug (assumes the canonical entry
    #      is the simpler ID; e.g., 'yale' beats 'yale-college-school-of-...';
    #      'williams' beats 'williams-college').
    STOPWORDS = {
        "college", "university", "the", "of", "and", "at", "in", "saint",
        "state", "international", "city",
    }
    cleaned_tokens = set(cleaned.split())
    candidate_matches: list[dict] = []
    seen_ids: set[str] = set()
    for sid, s in by_id.items():
        if sid in seen_ids:
            continue
        primary = s["name"].split()[0].lower()
        if primary in STOPWORDS:
            continue
        if primary in cleaned_tokens:
            candidate_matches.append(s)
            seen_ids.add(sid)
    if candidate_matches:
        # Rule (a): if filename contains an exact school_id, prefer it
        cleaned_dashed = cleaned.replace(" ", "-")
        exact_id_matches = [s for s in candidate_matches if s["id"] in cleaned_dashed]
        if len(exact_id_matches) == 1:
            s = exact_id_matches[0]
            return s["id"], 0.95, f"filename contains exact slug '{s['id']}'"
        # Rule (b): shortest slug wins
        candidate_matches.sort(key=lambda s: len(s["id"]))
        winner = candidate_matches[0]
        if len(candidate_matches) > 1:
            others = [s["id"] for s in candidate_matches[1:5]]
            reason = f"primary token match '{winner['name']}' (preferred over {others} by slug length)"
        else:
            reason = f"primary token '{winner['name'].split()[0]}' appears in filename"
        return winner["id"], 0.9, reason

    return None, best_score, f"no confident match (best fuzzy: '{best['name'] if best else None}' @ {best_score:.2f})"


def run_upload(file_path: Path, school_id: str, year: str, source_url: Optional[str]) -> tuple[bool, str]:
    """Shell out to upload.py. Returns (success, last_line_of_output)."""
    import subprocess
    venv_python = REPO_ROOT / "tools" / "extraction_worker" / ".venv" / "bin" / "python"
    py = str(venv_python) if venv_python.exists() else sys.executable
    cmd = [py, str(UPLOAD_PY), str(file_path), school_id, year]
    if source_url:
        cmd += ["--source-url", source_url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return False, "timeout after 300s"
    output = (result.stdout + result.stderr).strip().splitlines()
    last_meaningful = next(
        (l for l in reversed(output) if l.strip() and not l.startswith("  ")),
        output[-1] if output else "",
    )
    return result.returncode == 0, last_meaningful


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch upload CDS files from a folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("folder", help="Folder containing the files to upload")
    parser.add_argument("--school",
                        help="Force all files to a specific school_id (folder name "
                             "matching is otherwise used as a hint)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Don't prompt for confirmation; upload everything that "
                             "parses cleanly")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Walk subdirectories")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"ERROR: not a directory: {folder}", file=sys.stderr)
        return 1

    by_id, by_name = load_schools()

    # Find candidate files
    pattern = "**/*" if args.recursive else "*"
    files = sorted(
        f for f in folder.glob(pattern)
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS
    )
    if not files:
        print(f"No PDF/XLSX/DOCX files found in {folder}")
        return 0

    # Build the plan
    plan = []
    for f in files:
        folder_name = f.parent.name
        year = parse_year(f.name)
        school_id, score, reason = parse_school(
            f.name, folder_name, by_id, by_name, args.school,
        )
        plan.append({
            "file": f,
            "year": year,
            "school_id": school_id,
            "match_score": score,
            "reason": reason,
        })

    # Sort: ready first, then issues
    ready = [p for p in plan if p["school_id"] and p["year"]]
    missing_year = [p for p in plan if p["school_id"] and not p["year"]]
    missing_school = [p for p in plan if not p["school_id"]]

    print(f"Folder: {folder}")
    print(f"Files found: {len(files)}")
    print(f"  Ready to upload:  {len(ready)}")
    print(f"  Missing year:     {len(missing_year)}")
    print(f"  Missing school:   {len(missing_school)}")

    if ready:
        print("\nReady to upload:")
        for p in ready:
            print(f"  ✓ {p['file'].name}")
            print(f"      → {p['school_id']} {p['year']}  ({p['reason']}, score={p['match_score']:.2f})")

    if missing_year:
        print("\nSkipped — could not parse year:")
        for p in missing_year:
            print(f"  ? {p['file'].name}  (school={p['school_id']})")

    if missing_school:
        print("\nSkipped — could not match school:")
        for p in missing_school:
            print(f"  ? {p['file'].name}  ({p['reason']})")

    if not ready:
        print("\nNothing to upload.")
        return 0

    if not args.yes:
        try:
            answer = input(f"\nUpload {len(ready)} file(s)? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 1
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    print(f"\nUploading {len(ready)} files...")
    ok = 0
    failed = 0
    for p in ready:
        success, last = run_upload(p["file"], p["school_id"], p["year"], None)
        marker = "✓" if success else "✗"
        print(f"  {marker} {p['file'].name} → {p['school_id']} {p['year']}: {last}")
        if success:
            ok += 1
        else:
            failed += 1

    print(f"\n=== Summary ===")
    print(f"  uploaded: {ok}")
    print(f"  failed:   {failed}")
    print(f"  skipped:  {len(missing_year) + len(missing_school)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
