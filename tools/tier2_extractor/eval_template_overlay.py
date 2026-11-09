#!/usr/bin/env python3
"""Reproduce the PRD 038 M1 acceptance numbers from local school PDFs.

School PDFs and the review's inventories are not in the repo, so every input is
a flag with a scratch-style default. Nothing here touches a database.

Subcommands:
  stage1   Stage 1 over the review's scanned set vs the 95-document cohort CSV.
  (lane subcommands are added with the lanes that they measure)

Inputs (all read-only):
  --pdf-dir      directory of <sha256>.pdf files
  --t4-docs      review/t4_docs.txt  (year|school|doc_id|pages|fields|producer|storage_path)
  --docmeta      doc_id|detected_year|cds_year|source_format|pages  (read-only psql dump)
  --scanned      review/ras*_ink225.jsonl files; their 'file' prefixes define the 298 scanned PDFs
  --cohort-csv   docs/prd/assets/038/template-cohort-2026-11-09.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_overlay as to  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def load_eval_set(args) -> list[dict]:
    meta = {}
    for line in Path(args.docmeta).read_text().splitlines():
        parts = line.split("|")
        if len(parts) >= 3:
            meta[parts[0]] = {"detected_year": parts[1] or None, "cds_year": parts[2] or None}
    prefixes = set()
    for f in args.scanned:
        for line in Path(f).read_text().splitlines():
            prefixes.add(json.loads(line)["file"])
    by_sha: dict[str, dict] = {}
    for line in Path(args.t4_docs).read_text().splitlines():
        yr, school, doc_id, pages, nstat, producer, path = (line.split("|") + [""] * 7)[:7]
        if not path:
            continue
        sha, ext = os.path.splitext(os.path.basename(path))
        e_ext = ext
        if sha[:12] not in prefixes:
            continue
        e = by_sha.setdefault(sha, {"sha": sha, "ext": e_ext, "school": school, "years": set(), "docs": [], "producer": producer,
                                    "tier4_fields": int(nstat or 0)})
        e["years"].add(yr)
        m = meta.get(doc_id, {})
        e["docs"].append({"doc_id": doc_id, "detected_year": m.get("detected_year"), "cds_year": m.get("cds_year")})
    out = []
    for e in by_sha.values():
        e["year"] = sorted(e["years"])[0]
        dys = {d["detected_year"] for d in e["docs"]}
        e["detected_year"] = next(iter(dys)) if len(dys) == 1 else None
        out.append(e)
    return sorted(out, key=lambda e: e["sha"])


def _run_one(job):
    pdf_dir, e = job
    t0 = time.time()
    path = Path(pdf_dir) / f"{e['sha']}{e.get('ext', '.pdf')}"
    try:
        data = path.read_bytes()
        if not data.startswith(b"%PDF"):
            return {"sha": e["sha"], "error": "not_a_pdf"}
        real = to.match_template(data, detected_year=e["detected_year"], align=False)
        none = to.match_template(data, detected_year=None, align=False)
    except Exception as exc:  # noqa: BLE001
        return {"sha": e["sha"], "error": repr(exc)}
    return {"sha": e["sha"], "real": real.to_dict(), "none": none.to_dict(), "sec": round(time.time() - t0, 2)}


def cmd_stage1(args) -> int:
    evalset = load_eval_set(args)
    print(f"eval set: {len(evalset)} distinct PDFs")
    cohort = {r["source_sha256_prefix"]: r for r in csv.DictReader(open(args.cohort_csv))}
    print(f"cohort csv: {len(cohort)} rows")
    with Pool(args.jobs) as pool:
        results = pool.map(_run_one, [(args.pdf_dir, e) for e in evalset], chunksize=2)
    by = {r["sha"]: r for r in results}
    errors = [r for r in results if "error" in r]
    print("errors:", len(errors), errors[:3])

    def passed_gate(r):  # >= 30 pages for the best year, whatever the year rule says
        return max(r["pages_matched"].values(), default=0) >= to.GATE_PAGES

    matched, rows = set(), []
    for e in evalset:
        r = by[e["sha"]]
        if "error" in r:
            continue
        real = r["real"]
        if passed_gate(real):
            matched.add(e["sha"][:12])
        rows.append((e, r))
    exp = set(cohort)
    print(f"\nStage 1 gate (>=30 pages, best year): {len(matched)} matched, {len(evalset) - len(errors) - len(matched)} rejected")
    print(f"expected cohort {len(exp)}; matched & expected {len(matched & exp)}; "
          f"false positives {sorted(matched - exp)}; misses {sorted(exp - matched)}")
    nonm = [max(r["real"]["pages_matched"].values(), default=0) for e, r in rows if e["sha"][:12] not in exp]
    mm = [max(r["real"]["pages_matched"].values(), default=0) for e, r in rows if e["sha"][:12] in exp]
    print(f"worst matching doc {min(mm) if mm else None} pages; best non-matching doc {max(nonm) if nonm else None} pages")

    for label, key in (("real detected_year", "real"), ("detected_year=None", "none")):
        c = Counter()
        wrong = []
        for e, r in rows:
            if e["sha"][:12] not in exp:
                continue
            res = r[key]
            if res["status"] == "matched":
                c["matched_correct" if res["year"] == e["year"] else "matched_WRONG"] += 1
                if res["year"] != e["year"]:
                    wrong.append((e["sha"][:12], e["school"], e["year"], res["year"], res["pages_matched"]))
            else:
                c[res["status"] + ":" + (res["reason"] or "")] += 1
        print(f"\nyear selection with {label}: {dict(c)}")
        for w in wrong:
            print("  WRONG", w)

    # lead distribution (final matcher, all three years), per true year
    print("\nyear lead = best minus runner-up pages, 95 cohort docs (best year == true year?):")
    lead_hist = defaultdict(Counter)
    runner = defaultdict(Counter)
    for e, r in rows:
        if e["sha"][:12] not in exp:
            continue
        pm = r["none"]["pages_matched"]
        order = sorted(pm, key=lambda y: (-pm[y], y))
        lead = pm[order[0]] - pm[order[1]]
        lead_hist[e["year"]][lead if lead < 10 else "10+"] += 1
        runner[e["year"]][order[1] + ("(tie)" if lead == 0 else "")] += 1
        if order[0] != e["year"]:
            lead_hist[e["year"]]["best_is_not_true_year"] += 1
    for y in sorted(lead_hist):
        print(f"  true {y}: lead histogram {dict(sorted(lead_hist[y].items(), key=lambda kv: str(kv[0])))}")
        print(f"           runner-up year {dict(runner[y])}")
    under3 = [(e["sha"][:12], e["year"], e["detected_year"], r["none"]["pages_matched"]) for e, r in rows
              if e["sha"][:12] in exp and r["none"]["lead"] is not None and r["none"]["lead"] < 3]
    print(f"  docs with lead < 3: {len(under3)}; with detected_year NULL among them: "
          f"{sum(1 for x in under3 if x[2] is None)}")

    # DP vs the review's greedy counts
    review = {}
    for f in args.scanned:
        for line in Path(f).read_text().splitlines():
            d = json.loads(line)
            review.setdefault(d["file"], {})["2425" if "2425" in f else "2526"] = d.get("matched")
    diffs = []
    for e, r in rows:
        if e["sha"][:12] not in exp:
            continue
        rv = review.get(e["sha"][:12], {})
        rv_n = rv.get("2526" if e["year"] == "2025-26" else "2425")
        mine = r["none"]["pages_matched"][e["year"]]
        if rv_n is not None and rv_n != mine:
            diffs.append((e["sha"][:12], e["school"], e["year"], rv_n, mine))
    print(f"\ncohort docs whose page count differs from the review (true-year template): {len(diffs)}")
    for d in diffs:
        print("  ", d)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(json.dumps({"eval": {k: (sorted(v) if isinstance(v, set) else v) for k, v in e.items()}, **by[e["sha"]]})
                                        for e in evalset) + "\n")
    print(f"\nwrote {args.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("stage1")
    s1.add_argument("--pdf-dir", required=True)
    s1.add_argument("--t4-docs", required=True)
    s1.add_argument("--docmeta", required=True)
    s1.add_argument("--scanned", nargs="+", required=True)
    s1.add_argument("--cohort-csv", default=str(REPO / "docs/prd/assets/038/template-cohort-2026-11-09.csv"))
    s1.add_argument("--jobs", type=int, default=4)
    s1.add_argument("--out", default="scratch/prd038/m1/stage1.jsonl")
    s1.set_defaults(fn=cmd_stage1)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
