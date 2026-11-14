#!/usr/bin/env python3
"""Build the versioned scholarship downloads (PRD 036 M2).

Usage:
    python tools/scholarships/build_downloads.py
    python tools/scholarships/build_downloads.py path/to/programs --out-dir web/public/data
    python tools/scholarships/build_downloads.py --dataset-version 2 --generated-at 2026-11-14

Writes, for dataset version N:
    scholarships-vN.json      {"meta": {...}, "programs": [...]}
    scholarships-vN.csv.zip   scholarships-vN.csv (first line is a # attribution
                              comment), LICENSE.txt, ATTRIBUTION.txt

The records are the ones scholarship_directory serves: per program, the latest
non-unverified chain-head version. The downloads leave out freshness_status
because it depends on the day it is read; every record carries
verification_status and last_reviewed_at instead.

Output is deterministic: the same records give byte-identical files. N comes
from --dataset-version (default model.DATASET_VERSION); generated_at defaults to
the newest last_reviewed_at in the data, and meta.dataset_id is the version plus
a digest of the records, so a changed record is a new dataset_id.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import load  # noqa: E402
import model  # noqa: E402
import validate  # noqa: E402

REPO_ROOT = validate.REPO_ROOT
DEFAULT_OUT_DIR = REPO_ROOT / "web" / "public" / "data"
LICENSE_PATH = REPO_ROOT / "data" / "scholarships" / "LICENSE"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

CSV_COLUMNS = [
    "program_id",
    "school_id",
    "ipeds_id",
    "participating_school_ids",
    "official_name",
    "program_family",
    "awarding_authority",
    "program_status",
    "version_id",
    "entry_year",
    "entry_year_label",
    "verification_status",
    "last_reviewed_at",
    "coverages",
    "selection_modes",
    "residencies",
    "national_merit_statuses",
    "need_roles",
    "separate_application",
    "deadline_months",
    "key_deadline",
    "source_retrieved_at",
    "source_urls",
    "offers_json",
    "license",
    "attribution",
]


def public_records(ds: model.Dataset) -> List[Dict[str, Any]]:
    """One record per program, ordered by school_id then program_id."""
    out = []
    for version in model.select_published(ds):
        program = ds.program(version["program_id"])
        rec = model.public_record(program, version, model.participants_of(program)[0])
        out.append(rec)
    out.sort(key=lambda r: (r["school_id"], r["program_id"]))
    return out


def csv_rows(ds: model.Dataset) -> List[Dict[str, Any]]:
    """One row per program per participating school, like the view."""
    rows = []
    for version in model.select_published(ds):
        program = ds.program(version["program_id"])
        for school in model.participants_of(program):
            rec = model.public_record(program, version, school)
            rows.append(rec)
    rows.sort(key=lambda r: (r["school_id"], r["program_id"]))
    return rows


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return str(value)


def render_csv(rows: List[Dict[str, Any]]) -> str:
    buf = io.StringIO(newline="")
    buf.write(f"# {model.ATTRIBUTION}\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for r in rows:
        flat = dict(r)
        flat["source_urls"] = [s["url"] for s in r["sources"]]
        flat["offers_json"] = json.dumps(r["offers"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        flat["license"] = model.LICENSE_ID
        flat["attribution"] = model.ATTRIBUTION
        writer.writerow([_cell(flat.get(c)) for c in CSV_COLUMNS])
    return buf.getvalue()


def attribution_text() -> str:
    return (
        f"{model.ATTRIBUTION}\n\n"
        f"License: {model.LICENSE_ID} ({model.LICENSE_URL})\n"
        f"Source repository: {model.SOURCE_REPOSITORY}\n"
        "If you change the data, say so and release your version under CC BY-SA 4.0.\n"
    )


def dataset_id(version: int, records: List[Dict[str, Any]]) -> str:
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"collegedata-scholarships-v{version}-{digest[:12]}"


def default_generated_at(records: List[Dict[str, Any]]) -> str:
    dates = [r["last_reviewed_at"] for r in records if r["last_reviewed_at"]]
    return max(dates) if dates else dt.datetime.now(dt.timezone.utc).date().isoformat()


def build_json(records: List[Dict[str, Any]], version: int, generated_at: str) -> str:
    doc = {
        "meta": {
            "dataset_id": dataset_id(version, records),
            "version": version,
            "license": model.LICENSE_ID,
            "license_url": model.LICENSE_URL,
            "attribution": model.ATTRIBUTION,
            "generated_at": generated_at,
            "source_repository": model.SOURCE_REPOSITORY,
            "record_count": len(records),
        },
        "programs": records,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def build_zip(csv_text: str, version: int, license_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in (
            (f"scholarships-v{version}.csv", csv_text),
            ("LICENSE.txt", license_text),
            ("ATTRIBUTION.txt", attribution_text()),
        ):
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


def build(
    ds: model.Dataset,
    out_dir: Path,
    version: int = model.DATASET_VERSION,
    generated_at: Optional[str] = None,
    license_path: Path = LICENSE_PATH,
) -> List[Path]:
    records = public_records(ds)
    generated_at = generated_at or default_generated_at(records)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"scholarships-v{version}.json"
    zip_path = out_dir / f"scholarships-v{version}.csv.zip"
    json_path.write_text(build_json(records, version, generated_at), encoding="utf-8")
    zip_path.write_bytes(
        build_zip(render_csv(csv_rows(ds)), version, license_path.read_text(encoding="utf-8"))
    )
    return [json_path, zip_path]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("programs_dir", nargs="?", type=Path, default=validate.DEFAULT_PROGRAMS_DIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--dataset-version", type=int, default=model.DATASET_VERSION)
    ap.add_argument("--generated-at", help="YYYY-MM-DD; default is the newest last_reviewed_at in the data")
    args = ap.parse_args(argv)
    ds, issues = load.load_dataset(args.programs_dir)
    if ds is None:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"FAILED: {len(issues)} validation issue(s); nothing built", file=sys.stderr)
        return 1
    paths = build(ds, args.out_dir, args.dataset_version, args.generated_at)
    n = len(public_records(ds))
    print(f"built {n} record(s): " + ", ".join(str(p) for p in paths))
    if n == 0:
        print("note: no published records yet; the files hold only the meta block and headers", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
