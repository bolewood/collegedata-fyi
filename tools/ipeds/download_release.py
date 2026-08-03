#!/usr/bin/env python3
"""Download official NCES/IPEDS metadata and table CSV ZIPs."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.metadata import (
    DATA_GENERATOR_URL,
    NCES_IPEDS_ACCESS_PAGE,
    ReleaseLink,
    normalize_release_date_text,
    parse_access_page,
    parse_tablesdoc,
)
from tools.ipeds.mappings import fact_mappings_for_data_year, resolve_fact_mappings_for_columns

REPO_ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_TIMEOUT_SECONDS = 120
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024 * 1024
MAX_ACCESS_DB_BYTES = 8 * 1024 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection-year", help="Release collection year, e.g. 2024-25. Defaults to latest.")
    parser.add_argument(
        "--release-type",
        choices=["preliminary", "provisional", "final"],
        help=(
            "Expected official release type. Final releases route directly to the "
            "Access database so revised values cannot be mislabeled."
        ),
    )
    parser.add_argument("--data-year", type=int, help="Data year for table downloads, e.g. 2024.")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "scratch" / "ipeds")
    parser.add_argument("--tables", nargs="*", help="Specific table names to download. Defaults to mapped PRD 021 tables.")
    parser.add_argument("--access-fallback", action="store_true", help="Export missing mapped tables from the official Access ZIP with mdb-export.")
    args = parser.parse_args()

    opener = build_opener()
    html = opener.open(NCES_IPEDS_ACCESS_PAGE).read().decode("utf-8", errors="replace")
    releases = parse_access_page(html)
    if not releases:
        raise SystemExit("No IPEDS releases found on NCES Access database page")

    release = select_release(releases, args.collection_year, args.release_type)
    data_year = args.data_year or release.data_year
    if data_year != release.data_year:
        raise SystemExit(
            f"Data year {data_year} does not match collection year {release.collection_year} "
            f"(expected {release.data_year})"
        )
    out_dir = args.out_dir / f"{release.collection_year}-{release.release_type}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "release.json"
    manifest_path.unlink(missing_ok=True)
    release_date, release_date_precision = normalize_release_date_text(release.release_date)

    metadata_path = out_dir / Path(release.metadata_url).name
    download(opener, release.metadata_url, metadata_path)
    print(f"metadata: {metadata_path}")

    tablesdoc = parse_tablesdoc(metadata_path)
    default_tables = [m.table_name for m in resolve_fact_mappings_for_columns(fact_mappings_for_data_year(data_year), tablesdoc.columns)]
    available_tables = {table.table_name.upper() for table in tablesdoc.tables}
    requested_tables = sorted({name.upper() for name in (args.tables or default_tables)})
    table_names = [name for name in requested_tables if name in available_tables]
    missing_tables = sorted(set(requested_tables) - available_tables)
    for table_name in missing_tables:
        print(f"warning: {table_name} is not listed in {metadata_path.name}; skipping", file=sys.stderr)
    missing_finance_tables = [table_name for table_name in missing_tables if is_f2_finance_table(table_name)]
    if missing_finance_tables:
        raise SystemExit(
            "Expected Finance table(s) are absent from the official Tablesdoc: "
            + ", ".join(missing_finance_tables)
        )
    downloaded_tables: list[str] = []
    missing_downloads: list[str] = []
    access_exported_tables: list[str] = []
    if release_uses_access_source(release):
        print("source: revised final release; routing requested tables to the official Access database")
        access_exported_tables = export_access_tables(opener, release.access_url, out_dir, table_names)
        unresolved = sorted(set(table_names) - set(access_exported_tables))
        if unresolved:
            raise SystemExit(
                "Revised-final Access source could not provide expected table(s): "
                + ", ".join(unresolved)
            )
    else:
        # The data generator endpoint returns CSV ZIP bytes. Visiting the page
        # first initializes the same session cookies a browser gets from the
        # NCES app.
        opener.open(f"https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year={data_year}&surveyNumber=1").read()
        for table_name in table_names:
            url = DATA_GENERATOR_URL.format(year=data_year, table_name=table_name)
            path = out_dir / f"{table_name}.zip"
            try:
                download(opener, url, path)
                (out_dir / f"{table_name}.csv").unlink(missing_ok=True)
                downloaded_tables.append(table_name)
                print(f"table: {path}")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                print(f"warning: {table_name} data-generator ZIP returned 404; skipping", file=sys.stderr)
                missing_downloads.append(table_name)

    if not release_uses_access_source(release) and args.access_fallback and missing_downloads:
        access_exported_tables = export_access_tables(opener, release.access_url, out_dir, missing_downloads)
        unresolved = sorted(set(missing_downloads) - set(access_exported_tables))
        if unresolved:
            raise SystemExit(
                "Access fallback could not provide expected table(s): " + ", ".join(unresolved)
            )

    unresolved_tables = sorted(
        set(missing_tables)
        | (set(missing_downloads) - set(access_exported_tables))
    )
    manifest = {
        "collection_year": release.collection_year,
        "data_year": data_year,
        "release_type": release.release_type,
        "requested_release_type": args.release_type,
        "release_date": release_date,
        "release_date_text": release.release_date,
        "release_date_precision": release_date_precision,
        "source_page_url": NCES_IPEDS_ACCESS_PAGE,
        "metadata_url": release.metadata_url,
        "access_url": release.access_url,
        "requested_tables": requested_tables,
        "tablesdoc_missing_tables": missing_tables,
        "downloaded_tables": downloaded_tables,
        "access_exported_tables": access_exported_tables,
        "source_mode": source_mode(downloaded_tables, access_exported_tables),
        "unresolved_tables": unresolved_tables,
    }
    manifest_tmp_path = manifest_path.with_suffix(".json.tmp")
    manifest_tmp_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_tmp_path.replace(manifest_path)
    print(f"manifest: {manifest_path}")
    print(f"release: {release.collection_year} {release.release_type}")
    if release.release_date:
        print(f"release date: {release.release_date}")
    unresolved_finance_tables = [
        table_name for table_name in unresolved_tables if is_f2_finance_table(table_name)
    ]
    if unresolved_finance_tables:
        print(
            "error: expected Finance table(s) remain unresolved: "
            + ", ".join(unresolved_finance_tables)
            + "; rerun with --access-fallback when the data-generator ZIP is unavailable",
            file=sys.stderr,
        )
        return 2
    return 0


def select_release(
    releases: list[ReleaseLink],
    collection_year: str | None,
    release_type: str | None = None,
) -> ReleaseLink:
    """Select the requested release without silently substituting another year."""
    if collection_year is None and release_type is None:
        return releases[0]
    release = next(
        (
            item
            for item in releases
            if (collection_year is None or item.collection_year == collection_year)
            and (release_type is None or item.release_type == release_type)
        ),
        None,
    )
    if release is None:
        requested = " ".join(value for value in (collection_year, release_type) if value)
        available = ", ".join(
            f"{item.collection_year} {item.release_type}" for item in releases
        )
        raise SystemExit(
            f"No IPEDS release matched {requested}. Available: {available}"
        )
    return release


def is_f2_finance_table(table_name: str) -> bool:
    return re.fullmatch(r"F\d{4}_F2", table_name.upper()) is not None


def release_uses_access_source(release: ReleaseLink) -> bool:
    """Final releases must use revised values from Access, never HasRV=0 CSVs."""
    return release.release_type == "final"


def source_mode(downloaded_tables: list[str], access_exported_tables: list[str]) -> str:
    if downloaded_tables and access_exported_tables:
        return "mixed"
    if access_exported_tables:
        return "access"
    return "data_generator"


def build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def download(opener: urllib.request.OpenerDirector, url: str, path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "collegedata-fyi-ipeds-loader/1.0"})
    try:
        with opener.open(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, path.open("wb") as f:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError(
                        f"Download from {url} exceeded {MAX_DOWNLOAD_BYTES} bytes"
                    )
                f.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def export_access_tables(
    opener: urllib.request.OpenerDirector,
    access_url: str | None,
    out_dir: Path,
    table_names: list[str],
) -> list[str]:
    if not access_url:
        print("warning: no Access ZIP URL is available; cannot export fallback tables", file=sys.stderr)
        return []
    mdb_export = shutil.which("mdb-export")
    if not mdb_export:
        print("warning: mdb-export is not installed; cannot export Access fallback tables", file=sys.stderr)
        return []

    exported: list[str] = []
    with tempfile.TemporaryDirectory(prefix="access-", dir=out_dir) as tmp:
        tmp_dir = Path(tmp)
        access_zip = tmp_dir / Path(access_url).name
        download(opener, access_url, access_zip)
        with zipfile.ZipFile(access_zip) as zf:
            accdb_info = next(
                (info for info in zf.infolist() if info.filename.lower().endswith(".accdb")),
                None,
            )
            if accdb_info is None:
                print(f"warning: {access_zip.name} has no .accdb file; cannot export fallback tables", file=sys.stderr)
                return []
            if accdb_info.file_size > MAX_ACCESS_DB_BYTES:
                raise ValueError(
                    f"Access database member exceeds {MAX_ACCESS_DB_BYTES} bytes: "
                    f"{accdb_info.filename}"
                )
            accdb_path = tmp_dir / Path(accdb_info.filename).name
            with zf.open(accdb_info) as source, accdb_path.open("wb") as destination:
                copied = 0
                while chunk := source.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > MAX_ACCESS_DB_BYTES:
                        raise ValueError(
                            f"Access database member exceeds {MAX_ACCESS_DB_BYTES} bytes: "
                            f"{accdb_info.filename}"
                        )
                    destination.write(chunk)

        for table_name in table_names:
            path = out_dir / f"{table_name}.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                result = subprocess_run([mdb_export, str(accdb_path), table_name], stdout=f)
            if result != 0:
                path.unlink(missing_ok=True)
                print(f"warning: mdb-export could not export {table_name}; skipping", file=sys.stderr)
                continue
            exported.append(table_name)
            (out_dir / f"{table_name}.zip").unlink(missing_ok=True)
            print(f"table: {path}")
    return exported


def subprocess_run(args: list[str], *, stdout: object) -> int:
    import subprocess

    return subprocess.run(args, stdout=stdout, stderr=subprocess.PIPE, text=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())
