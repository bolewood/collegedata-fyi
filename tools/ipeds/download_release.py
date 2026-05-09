#!/usr/bin/env python3
"""Download official NCES/IPEDS metadata and table CSV ZIPs."""

from __future__ import annotations

import argparse
import http.cookiejar
import sys
import urllib.request
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.metadata import DATA_GENERATOR_URL, NCES_IPEDS_ACCESS_PAGE, parse_access_page
from tools.ipeds.mappings import MVP_FACT_MAPPINGS

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection-year", help="Release collection year, e.g. 2024-25. Defaults to latest.")
    parser.add_argument("--data-year", type=int, help="Data year for table downloads, e.g. 2024.")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "scratch" / "ipeds")
    parser.add_argument("--tables", nargs="*", help="Specific table names to download. Defaults to mapped PRD 021 tables.")
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

    metadata_path = out_dir / Path(release.metadata_url).name
    download(opener, release.metadata_url, metadata_path)
    print(f"metadata: {metadata_path}")

    table_names = sorted({name.upper() for name in (args.tables or [m.table_name for m in MVP_FACT_MAPPINGS])})
    # The data generator endpoint returns CSV ZIP bytes. Visiting the page first
    # initializes the same session cookies a browser gets from the NCES app.
    opener.open(f"https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year={data_year}&surveyNumber=1").read()
    for table_name in table_names:
        url = DATA_GENERATOR_URL.format(year=data_year, table_name=table_name)
        path = out_dir / f"{table_name}.zip"
        download(opener, url, path)
        print(f"table: {path}")

    print(f"release: {release.collection_year} {release.release_type}")
    return 0


def build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def download(opener: urllib.request.OpenerDirector, url: str, path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "collegedata-fyi-ipeds-loader/1.0"})
    with opener.open(req) as response, path.open("wb") as f:
        f.write(response.read())


if __name__ == "__main__":
    raise SystemExit(main())

