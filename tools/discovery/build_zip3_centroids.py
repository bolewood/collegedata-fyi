#!/usr/bin/env python3
"""Build the 3-digit ZIP prefix centroid artifact (PRD 026 Q5, v1 answer).

Input: the Census ZCTA National Gazetteer (public domain), e.g.
  curl -sL -o scratch/discovery-spike/zcta_gazetteer.zip \\
    https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip
  unzip -o scratch/discovery-spike/zcta_gazetteer.zip -d scratch/discovery-spike

Output: data/discovery/geo/zip3-centroids-v1.json — unweighted mean of ZCTA
internal points per 3-digit prefix, rounded to 3 decimals. Coarse by design
(tens of miles): the UI presents distances as approximate straight-line
miles, and shipping the whole table to the browser keeps the full ZIP on
the student's device.
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAZETTEER = ROOT / "scratch" / "discovery-spike" / "2023_Gaz_zcta_national.txt"
OUT = ROOT / "data" / "discovery" / "geo" / "zip3-centroids-v1.json"


def main() -> int:
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with open(GAZETTEER, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            row = {k.strip(): v.strip() for k, v in row.items()}
            groups[row["GEOID"][:3]].append(
                (float(row["INTPTLAT"]), float(row["INTPTLONG"]))
            )

    centroids = {
        prefix: [
            round(sum(p[0] for p in pts) / len(pts), 3),
            round(sum(p[1] for p in pts) / len(pts), 3),
        ]
        for prefix, pts in sorted(groups.items())
    }
    out = {
        "zip3_centroid_version": "v1",
        "status": "published",
        "created": "2026-07-12",
        "license": "Public domain (U.S. Census Bureau); compilation CC-BY-SA-4.0 with the rest of data/discovery",
        "source": "2023 Census ZCTA National Gazetteer (2023_Gaz_zcta_national.txt), ZCTA internal points averaged per 3-digit ZIP prefix",
        "method": "zip3_centroid_v1: unweighted mean of ZCTA internal points sharing a 3-digit prefix; coordinates rounded to 3 decimals (~110m); accuracy is tens of miles by design — distances rendered as approximate straight-line miles",
        "notes": [
            "Resolves PRD 026 Open Question 5 for v1: the table is small enough to ship to the browser, so the full ZIP never leaves the device — a 3-digit prefix lookup happens client-side.",
            "A ZIP whose prefix is absent here fails resolution; the UI's existing no-ZIP-match failure state applies.",
        ],
        "centroids": centroids,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(centroids)} prefixes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
