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
import re
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
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


def _cohort_docs(args) -> list[dict]:
    exp = {r["source_sha256_prefix"] for r in csv.DictReader(open(args.cohort_csv))}
    return [e for e in load_eval_set(args) if e["sha"][:12] in exp]


def _lane3_job(job):
    pdf_dir, e, inset = job
    data = (Path(pdf_dir) / f"{e['sha']}.pdf").read_bytes()
    doc = pdfium.PdfDocument(data)
    res = to.match_template(doc, detected_year=e["year"], align=True)
    if res.status != "matched":
        return {"sha": e["sha"], "status": res.status}
    sc = to.button_scores(doc, res, to.load_maps()[res.year].fmap, inset=inset)
    flat = [(tag, i, s) for tag, row in sc.items() for i, s in enumerate(row) if s is not None]
    shifts = {f"{a['dx']},{a['dy']}": 0 for a in res.alignment.values()}
    for a in res.alignment.values():
        shifts[f"{a['dx']},{a['dy']}"] += 1
    return {"sha": e["sha"], "status": "matched", "year": res.year, "scores": flat, "shifts": shifts,
            "rejected_pages": res.rejected_pages}


def cmd_lane3_hist(args) -> int:
    docs = _cohort_docs(args)
    with Pool(args.jobs) as pool:
        out = pool.map(_lane3_job, [(args.pdf_dir, e, args.inset) for e in docs], chunksize=1)
    allv = np.array([s for r in out if "scores" in r for _, _, s in r["scores"]])
    edges = [-1, -0.05, 0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3, 0.5, 1.1]
    hist, _ = np.histogram(allv, bins=edges)
    print(f"{len(out)} docs, {allv.size} Btn widget scores at inset {args.inset}")
    for lo, hi, n in zip(edges[:-1], edges[1:], hist):
        print(f"  [{lo:>6}, {hi:>5}) {n:6d}")
    shifts = Counter()
    rej = Counter()
    for r in out:
        for k, v in r.get("shifts", {}).items():
            shifts[k] += v
        for k, v in r.get("rejected_pages", {}).items():
            rej[v] += 1
    print("alignment shifts (dx,dy)->pages:", dict(shifts), "rejected pages:", dict(rej))
    Path(args.out).write_text(json.dumps(out))
    return 0


# ---- comparison against a document's own Tier 2 (fillable copy) -------------

def _norm_num(s):
    s = str(s).strip().replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def values_match(expected: str, got: str | None) -> bool:
    """The review's comparison, unchanged: exact, whitespace/case-insensitive, or numerically equal."""
    if got is None:
        return False
    e, g = str(expected).strip(), str(got).strip()
    if e == g or re.sub(r"\s+", " ", e).lower() == re.sub(r"\s+", " ", g).lower():
        return True
    a, b = _norm_num(e), _norm_num(g)
    return a is not None and b is not None and abs(a - b) < 1e-6 or e.strip("/ ") == g.strip("/ ")


def tier2_truth(fillable: Path, year: str) -> dict:
    sys.path.insert(0, str(REPO / "tools"))
    sys.path.insert(0, str(REPO / "tools" / "extraction_worker"))
    from tier2_extractor.extract import extract, load_schema  # noqa: WPS433
    import build_field_map as bfm
    return extract(fillable, load_schema(bfm.schema_path_for(year)))


def compare_with_tier2(overlay: dict, t2: dict, fmap: dict) -> dict:
    """Score overlay values against Tier 2 values of the fillable copy of the same document."""
    ov = overlay["values"]
    res = {"Tx": [0, 0], "Ch": [0, 0], "Btn": [0, 0], "derived": [0, 0]}
    miss, extra = [], []
    for qn, rec in t2["values"].items():
        tag = rec.get("pdf_tag")
        ft = (fmap["fields"][tag]["ft"].strip("/") if tag in fmap["fields"] else None) if tag else "derived"
        if ft is None:
            continue
        got = ov.get(qn, {}).get("value")
        ok = values_match(rec["value"], got)
        res[ft][1] += 1
        res[ft][0] += ok
        if not ok:
            miss.append({"qn": qn, "tag": tag, "ft": ft, "expected": str(rec["value"])[:50], "got": None if got is None else str(got)[:50]})
    for qn, rec in ov.items():
        if qn not in t2["values"]:
            extra.append({"qn": qn, "tag": rec.get("pdf_tag"), "lane": rec.get("lane"), "value": str(rec["value"])[:50]})
    ok = sum(v[0] for v in res.values())
    tot = sum(v[1] for v in res.values())
    return {"by_type": res, "ok": ok, "total": tot, "misses": miss, "extras": extra}


def cmd_compare(args) -> int:
    import hashlib  # noqa: F401
    flat = Path(args.pdf_dir) / args.flat
    fill = Path(args.pdf_dir) / args.fillable
    t2 = tier2_truth(fill, args.year)
    maps = to.load_maps()
    for label, kw in (("centre-in-rect (spec)", {}), ("review method: +-1pt pad, paren strip", {"lane1_pad": 1.0, "strip_parens": True}),
                      ("centre-in-rect + paren strip", {"strip_parens": True}),
                      ("centre-in-rect, value_type check off", {"strict_types": False})):
        ov = to.extract_overlay(flat.read_bytes(), detected_year=args.year, source_name=flat.name, **kw)
        c = compare_with_tier2(ov, t2, maps[args.year].fmap)
        print(f"\n== {args.label}: {label}\n   {c['ok']} / {c['total']}  {c['by_type']}")
        print(f"   lane_counts {ov['notes']['lane_counts']}  rejected {len(ov['notes']['rejected_fields'])}  "
              f"unreadable pages {ov['notes']['unreadable_pages']}  ocr-candidate pages {ov['notes']['pages_needing_ocr']}")
        if args.verbose or not kw:
            for m in c["misses"]:
                print("   MISS", m)
            print(f"   emitted where Tier 2 is blank: {len(c['extras'])}")
            for x in c["extras"]:
                print("   EXTRA", x)
        for r in ov["notes"]["rejected_fields"]:
            if not kw:
                print("   REJECT", r)
    return 0


def _extract_job(job):
    pdf_dir, e, force_year = job
    data = (Path(pdf_dir) / f"{e['sha']}.pdf").read_bytes()
    t0 = time.time()
    ov = to.extract_overlay(data, detected_year=e["year"], source_name=e["sha"][:12], force_year=force_year)
    n = ov["notes"]
    return {"sha": e["sha"], "school": e["school"], "year": e["year"], "producer": e["producer"],
            "tier4_fields": e["tier4_fields"], "status": n["stage1"]["status"],
            "values": {qn: [r["pdf_tag"], r["value"], r["lane"]] for qn, r in ov["values"].items() if "pdf_tag" in r},
            "n_values": len(ov["values"]), "lane_counts": n.get("lane_counts", {}),
            "rejected": n.get("rejected_fields", []), "identity_failures": n.get("identity_failures", []),
            "unreadable_pages": n.get("unreadable_pages", []), "ocr_pages": n.get("pages_needing_ocr", []),
            "ambiguous_radios": len(n.get("ambiguous_radios", [])), "skipped_null_qn": n.get("skipped_null_question_number"),
            "pages_matched": n["stage1"]["pages_matched"], "rejected_pages": n["stage1"]["rejected_pages"],
            "sec": round(time.time() - t0, 1)}


def cmd_cohort(args) -> int:
    docs = _cohort_docs(args)
    with Pool(args.jobs) as pool:
        out = pool.map(_extract_job, [(args.pdf_dir, e, None) for e in docs], chunksize=1)
    Path(args.out).write_text(json.dumps(out))
    print(f"{'school':38s} {'yr':7s} {'producer':28s} {'t4':>4s} {'text':>5s} {'chk':>4s} {'rej':>3s} {'idf':>3s} {'unrd':>4s} {'ocrp':>4s}  type")
    kinds = Counter()
    for r in sorted(out, key=lambda r: (r["year"], r["school"])):
        lc = r["lane_counts"]
        kind = "text-layer" if lc.get("text", 0) >= 50 else "needs-OCR"
        kinds[(r["year"], kind)] += 1
        print(f"{r['school'][:38]:38s} {r['year']:7s} {r['producer'][:28]:28s} {r['tier4_fields']:4d} {lc.get('text', 0):5d} "
              f"{lc.get('checkbox', 0):4d} {len(r['rejected']):3d} {len(r['identity_failures']):3d} {len(r['unreadable_pages']):4d} "
              f"{len(r['ocr_pages']):4d}  {kind}{'' if r['status'] == 'matched' else ' ' + r['status']}")
    print(dict(kinds))
    return 0


def cmd_wrong_year(args) -> int:
    docs = _cohort_docs(args)
    right = {r["sha"]: r for r in json.loads(Path(args.cohort_json).read_text())}
    picks = []
    for yr in ("2024-25", "2025-26"):
        pool_ = [e for e in docs if e["year"] == yr and right[e["sha"]]["lane_counts"].get("text", 0) >= 200]
        picks += pool_[: args.n // 2 + (args.n % 2 if yr == "2025-26" else 0)]
    with Pool(args.jobs) as pool:
        wrong = pool.map(_extract_job, [(args.pdf_dir, e, "2024-25" if e["year"] == "2025-26" else "2025-26") for e in picks], chunksize=1)
    for e, w in zip(picks, wrong):
        r = right[e["sha"]]
        rv = {v[0]: v[1] for v in r["values"].values()}
        wv = {v[0]: v[1] for v in w["values"].values()}
        shared = set(rv) & set(wv)
        same = sum(1 for t in shared if str(rv[t]).strip("/ ") == str(wv[t]).strip("/ "))
        print(f"\n{e['school']} true {e['year']}, forced {'2024-25' if e['year'] == '2025-26' else '2025-26'}: "
              f"stage1 {w['status']} pages {w['pages_matched']}")
        print(f"  right-year: {r['n_values']} values (rejected {len(r['rejected'])}, identity failures {len(r['identity_failures'])})")
        print(f"  wrong-year: {w['n_values']} values pass validation (rejected {len(w['rejected'])}, "
              f"identity failures {len(w['identity_failures'])}); of {len(shared)} tags in both, "
              f"{same} identical, {len(shared) - same} DIFFERENT; {len(set(wv) - set(rv))} only in wrong-year, {len(set(rv) - set(wv))} only in right-year")
        diffs = [(t, rv[t], wv[t]) for t in sorted(shared) if str(rv[t]).strip("/ ") != str(wv[t]).strip("/ ")][:4]
        print("  sample differences (tag, right, wrong):", diffs)
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
    for name, fn in (("cohort", cmd_cohort), ("wrong-year", cmd_wrong_year)):
        sp = sub.add_parser(name)
        for a in ("--pdf-dir", "--t4-docs", "--docmeta"):
            sp.add_argument(a, required=True)
        sp.add_argument("--scanned", nargs="+", required=True)
        sp.add_argument("--cohort-csv", default=str(REPO / "docs/prd/assets/038/template-cohort-2026-11-09.csv"))
        sp.add_argument("--jobs", type=int, default=4)
        sp.add_argument("--out", default="scratch/prd038/m1/cohort.json")
        if name == "wrong-year":
            sp.add_argument("--cohort-json", default="scratch/prd038/m1/cohort.json")
            sp.add_argument("--n", type=int, default=5)
        sp.set_defaults(fn=fn)
    cp = sub.add_parser("compare")
    cp.add_argument("--pdf-dir", required=True)
    cp.add_argument("--flat", required=True, help="flattened PDF filename in --pdf-dir")
    cp.add_argument("--fillable", required=True, help="fillable copy of the same document")
    cp.add_argument("--year", required=True)
    cp.add_argument("--label", default="")
    cp.add_argument("--verbose", action="store_true")
    cp.set_defaults(fn=cmd_compare)
    l3 = sub.add_parser("lane3-hist")
    for a in ("--pdf-dir", "--t4-docs", "--docmeta"):
        l3.add_argument(a, required=True)
    l3.add_argument("--scanned", nargs="+", required=True)
    l3.add_argument("--cohort-csv", default=str(REPO / "docs/prd/assets/038/template-cohort-2026-11-09.csv"))
    l3.add_argument("--jobs", type=int, default=4)
    l3.add_argument("--inset", type=float, default=to.LANE3_INSET)
    l3.add_argument("--out", default="scratch/prd038/m1/lane3_hist.json")
    l3.set_defaults(fn=cmd_lane3_hist)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
