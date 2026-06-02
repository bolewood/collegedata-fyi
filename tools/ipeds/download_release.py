#!/usr/bin/env python3
"""Download official NCES/IPEDS metadata and table CSV ZIPs."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.metadata import DATA_GENERATOR_URL, NCES_IPEDS_ACCESS_PAGE, normalize_release_date_text, parse_access_page, parse_tablesdoc
from tools.ipeds.mappings import fact_mappings_for_data_year, resolve_fact_mappings_for_columns

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection-year", help="Release collection year, e.g. 2024-25. Defaults to latest.")
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

    release = next((item for item in releases if item.collection_year == args.collection_year), releases[0])
    data_year = args.data_year or release.data_year
    out_dir = args.out_dir / f"{release.collection_year}-{release.release_type}"
    out_dir.mkdir(parents=True, exist_ok=True)
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
    # The data generator endpoint returns CSV ZIP bytes. Visiting the page first
    # initializes the same session cookies a browser gets from the NCES app.
    opener.open(f"https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year={data_year}&surveyNumber=1").read()
    missing_downloads: list[str] = []
    for table_name in table_names:
        url = DATA_GENERATOR_URL.format(year=data_year, table_name=table_name)
        path = out_dir / f"{table_name}.zip"
        try:
            download(opener, url, path)
            print(f"table: {path}")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            print(f"warning: {table_name} data-generator ZIP returned 404; skipping", file=sys.stderr)
            missing_downloads.append(table_name)

    if args.access_fallback and missing_downloads:
        export_access_tables(opener, release.access_url, out_dir, missing_downloads)

    manifest = {
        "collection_year": release.collection_year,
        "data_year": data_year,
        "release_type": release.release_type,
        "release_date": release_date,
        "release_date_text": release.release_date,
        "release_date_precision": release_date_precision,
        "source_page_url": NCES_IPEDS_ACCESS_PAGE,
        "metadata_url": release.metadata_url,
        "access_url": release.access_url,
    }
    manifest_path = out_dir / "release.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"manifest: {manifest_path}")
    print(f"release: {release.collection_year} {release.release_type}")
    if release.release_date:
        print(f"release date: {release.release_date}")
    return 0


def build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def download(opener: urllib.request.OpenerDirector, url: str, path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "collegedata-fyi-ipeds-loader/1.0"})
    with opener.open(req) as response, path.open("wb") as f:
        f.write(response.read())


def export_access_tables(
    opener: urllib.request.OpenerDirector,
    access_url: str | None,
    out_dir: Path,
    table_names: list[str],
) -> None:
    if not access_url:
        print("warning: no Access ZIP URL is available; cannot export fallback tables", file=sys.stderr)
        return
    mdb_export = shutil.which("mdb-export")
    if not mdb_export:
        print("warning: mdb-export is not installed; cannot export Access fallback tables", file=sys.stderr)
        return

    with tempfile.TemporaryDirectory(prefix="access-", dir=out_dir) as tmp:
        tmp_dir = Path(tmp)
        access_zip = tmp_dir / Path(access_url).name
        download(opener, access_url, access_zip)
        with zipfile.ZipFile(access_zip) as zf:
            accdb_name = next((name for name in zf.namelist() if name.lower().endswith(".accdb")), None)
            if accdb_name is None:
                print(f"warning: {access_zip.name} has no .accdb file; cannot export fallback tables", file=sys.stderr)
                return
            zf.extract(accdb_name, tmp_dir)
        accdb_path = tmp_dir / accdb_name

        for table_name in table_names:
            path = out_dir / f"{table_name}.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                result = subprocess_run([mdb_export, str(accdb_path), table_name], stdout=f)
            if result != 0:
                path.unlink(missing_ok=True)
                print(f"warning: mdb-export could not export {table_name}; skipping", file=sys.stderr)
                continue
            print(f"table: {path}")


def subprocess_run(args: list[str], *, stdout: object) -> int:
    import subprocess

    return subprocess.run(args, stdout=stdout, stderr=subprocess.PIPE, text=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())
