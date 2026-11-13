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
        real = to.match_template(data, detected_year=e["detected_year"], align=False)   # real metadata path
        oracle = to.match_template(data, detected_year=e["year"], align=False)         # ORACLE: the answer injected
    except Exception as exc:  # noqa: BLE001
        return {"sha": e["sha"], "error": repr(exc)}
    return {"sha": e["sha"], "real": real.to_dict(), "oracle": oracle.to_dict(), "sec": round(time.time() - t0, 2)}


def cmd_stage1(args) -> int:
    evalset = load_eval_set(args)
    print(f"eval set: {len(evalset)} distinct PDFs")
    cohort = {r["source_sha256_prefix"]: r for r in csv.DictReader(open(args.cohort_csv))}
    print(f"cohort csv: {len(cohort)} rows")
    with Pool(args.jobs) as pool:
        results = pool.map(_run_one, [(args.pdf_dir, e) for e in evalset], chunksize=2)
    by = {r["sha"]: r for r in results}
    errors = [r for r in results if "error" in r]
    print("errors:", len(errors), [(r["sha"][:12], r["error"]) for r in errors][:3])
    exp = set(cohort)
    rows = [(e, by[e["sha"]]) for e in evalset if "error" not in by[e["sha"]]]

    def gate(r):
        return max(r["pages_matched"].values(), default=0) >= to.GATE_PAGES

    matched = {e["sha"][:12] for e, r in rows if gate(r["real"])}
    print(f"\nStage 1 gate (>= 30 raster pages, best year): {len(matched)} matched, "
          f"{len(rows) - len(matched)} rejected (+{len(errors)} not a PDF)")
    print(f"expected cohort {len(exp)}; matched & expected {len(matched & exp)}; "
          f"false positives {sorted(matched - exp)}; misses {sorted(exp - matched)}")
    mm = [max(r["real"]["pages_matched"].values(), default=0) for e, r in rows if e["sha"][:12] in exp]
    nm = [max(r["real"]["pages_matched"].values(), default=0) for e, r in rows if e["sha"][:12] not in exp]
    print(f"worst matching doc {min(mm)} pages; best non-matching doc {max(nm)} pages")

    for label, key in (("REAL metadata (detected_year from cds_documents, NULL kept NULL)", "real"),
                       ("ORACLE (coalesced true year injected as detected_year)", "oracle")):
        c = Counter()
        wrong, details = [], []
        for e, r in rows:
            if e["sha"][:12] not in exp:
                continue
            res = r[key]
            if res["status"] == "matched":
                ok = res["year"] == e["year"]
                c["matched_correct_year" if ok else "matched_WRONG_YEAR"] += 1
                if not ok:
                    wrong.append((e["sha"][:12], e["school"], e["year"], res["year"]))
            else:
                c[f"{res['status']}:{res['reason']}"] += 1
                details.append((e["sha"][:12], e["school"], e["year"], e["detected_year"], res["status"], res["reason"],
                                res["pages_matched"], res["header_votes"]))
        print(f"\nyear outcome, {label}: {dict(c)}")
        for w in wrong:
            print("  WRONG", w)
        for d in details:
            print("  NOT MATCHED", d)

    print("\nraster lead (best minus runner-up) and header votes, 95 cohort docs (real run):")
    lead_hist = defaultdict(Counter)
    hv = Counter()
    for e, r in rows:
        if e["sha"][:12] not in exp:
            continue
        pm = r["real"]["pages_matched"]
        order = sorted(pm, key=lambda y: (-pm[y], y))
        lead = pm[order[0]] - pm[order[1]]
        lead_hist[e["year"]][lead if lead < 10 else "10+"] += 1
        votes = r["real"]["header_votes"]
        hv["unanimous_for_true_year" if set(votes) == {e["year"]} else "not_unanimous"] += 1
        if order[0] != e["year"]:
            lead_hist[e["year"]]["best_raster_is_not_true_year"] += 1
    for y in sorted(lead_hist):
        print(f"  true {y}: lead histogram {dict(sorted(lead_hist[y].items(), key=lambda kv: str(kv[0])))}")
    print("  header votes:", dict(hv))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps([{"eval": {k: (sorted(v) if isinstance(v, set) else v) for k, v in e.items()}, **by[e["sha"]]}
                                          for e in evalset]))
    print(f"\nwrote {args.out}")
    return 0


def _cohort_docs(args) -> list[dict]:
    exp = {r["source_sha256_prefix"] for r in csv.DictReader(open(args.cohort_csv))}
    return [e for e in load_eval_set(args) if e["sha"][:12] in exp]


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
    for label, kw in (("centre-in-rect (spec)", {}), ("+-1pt pad (review method)", {"lane1_pad": 1.0}),
                      ("centre-in-rect, value_type check off", {"strict_types": False})):
        ov = to.extract_overlay(flat.read_bytes(), detected_year=args.year, source_name=flat.name, **kw)
        c = compare_with_tier2(ov, t2, maps[args.year].fmap)
        print(f"\n== {args.label}: {label}\n   {c['ok']} / {c['total']}  {c['by_type']}")
        print(f"   lane_counts {ov['notes']['lane_counts']}  rejected {len(ov['notes']['rejected_fields'])}  "
              f"unreadable pages {ov['notes']['unreadable_pages']}  ocr-candidate pages {ov['notes']['pages_needing_ocr']}")
        if args.verbose or not kw:
            why = {w["pdf_tag"]: w["reason"] for w in ov["notes"]["withheld"]}
            why.update({x["pdf_tag"]: x["reason"] for x in ov["notes"]["rejected_fields"]})
            for m in c["misses"]:
                print("   MISS", m, "| rule:", why.get(m["tag"], "no rule: not read / printed differently"))
            print("   withheld by rule:", ov["notes"]["withheld_by_reason"])
            print(f"   emitted where Tier 2 is blank: {len(c['extras'])}")
            for x in c["extras"]:
                print("   EXTRA", x)
        for r in ov["notes"]["rejected_fields"]:
            if not kw:
                print("   REJECT", r)
    return 0


def _extract_job(job):
    pdf_dir, e, mode = job
    data = (Path(pdf_dir) / f"{e['sha']}.pdf").read_bytes()
    t0 = time.time()
    if mode == "real":
        ov = to.extract_overlay(data, detected_year=e["detected_year"], source_name=e["sha"][:12])
    elif mode == "oracle":
        ov = to.extract_overlay(data, detected_year=e["year"], source_name=e["sha"][:12])
    else:  # "force-other": DIAGNOSTIC wrong-year control
        ov = to._diagnostic_extract_forced_year(data, "2024-25" if e["year"] == "2025-26" else "2025-26", source_name=e["sha"][:12])
    n = ov["notes"]
    st = n["stage1"]
    return {"sha": e["sha"], "school": e["school"], "year": e["year"], "detected_year": e["detected_year"],
            "producer": e["producer"], "tier4_fields": e["tier4_fields"], "mode": mode,
            "status": st["status"], "reason": st["reason"], "header_votes": st["header_votes"],
            "values": {qn: [r["pdf_tag"], r["value"], r["lane"]] for qn, r in ov["values"].items() if "pdf_tag" in r},
            "n_values": len(ov["values"]), "lane_counts": n.get("lane_counts", {}),
            "class_counts": n.get("emission_class_counts", {}),
            "rejected": n.get("rejected_fields", []), "withheld": n.get("withheld", []),
            "withheld_by_reason": n.get("withheld_by_reason", {}), "identity_failures": n.get("identity_failures", []),
            "unreadable_pages": n.get("unreadable_pages", []), "invisible_pages": n.get("invisible_text_pages", []),
            "ocr_pages": n.get("pages_needing_ocr", []), "ocr_widgets": len(n.get("ocr_widgets", [])),
            "page_map": n.get("page_map", {}), "rejected_pages": st["rejected_pages"],
            "rejected_template_pages": st["rejected_template_pages"], "band_rejections": st["band_rejections"],
            "alignment": st["alignment"], "sec": round(time.time() - t0, 1)}


def cmd_cohort(args) -> int:
    docs = _cohort_docs(args)
    mode = "oracle" if args.oracle else "real"
    with Pool(args.jobs) as pool:
        out = pool.map(_extract_job, [(args.pdf_dir, e, mode) for e in docs], chunksize=1)
    Path(args.out).write_text(json.dumps(out))
    label = ("ORACLE run: the coalesced true year was injected as detected_year; not an operational yield"
             if args.oracle else "REAL metadata path: detected_year as stored (NULL stays NULL); holds count as zero values")
    print(f"cohort run, {label}")
    print(f"{'school':36s} {'yr':7s} {'t4':>4s} {'text':>5s} {'chk':>4s} {'wh':>4s} {'rej':>4s} {'pgrej':>5s}  outcome")
    tot = Counter()
    wh_reason, rej_reason, pg_reason = Counter(), Counter(), Counter()
    for r in sorted(out, key=lambda r: (r["year"], r["school"])):
        lc = r["lane_counts"]
        tot["docs"] += 1
        tot["values"] += r["n_values"]
        tot["text"] += lc.get("text", 0)
        tot["checkbox"] += lc.get("checkbox", 0)
        tot["withheld"] += len(r["withheld"])
        tot["rejected"] += len(r["rejected"])
        outcome = "matched" if r["status"] == "matched" else f"HELD {r['reason']}" if r["status"] != "template_year_unsupported" else "UNSUPPORTED"
        tot[f"outcome:{outcome}"] += 1
        for w in r["withheld"]:
            wh_reason[w["reason"]] += 1
        for x in r["rejected"]:
            rej_reason[x["reason"]] += 1
        for v in r["rejected_pages"].values():
            pg_reason[v] += 1
        for v in r["rejected_template_pages"].values():
            pg_reason["template:" + v] += 1
        print(f"{r['school'][:36]:36s} {r['year']:7s} {r['tier4_fields']:4d} {lc.get('text', 0):5d} {lc.get('checkbox', 0):4d} "
              f"{len(r['withheld']):4d} {len(r['rejected']):4d} {len(r['rejected_pages']):5d}  {outcome}")
    print("\nTOTALS", dict(tot))
    cls_tot = Counter()
    for r in out:
        cls_tot.update({k: v for k, v in r.get("class_counts", {}).items() if k})
    served = set(to.SERVE_CLASSES_DEFAULT)
    matched = [r for r in out if r["status"] == "matched"]
    med = lambda xs: float(np.median(xs)) if xs else 0.0
    print("emitted by emission class:", dict(cls_tot.most_common()))
    print(f"medians over the {len(matched)} matched documents: served classes {med([sum(v for k, v in r.get('class_counts', {}).items() if k in served) for r in matched]):.1f}, "
          f"all classes {med([r['n_values'] for r in matched]):.1f}, Tier 4 {med([r['tier4_fields'] for r in matched]):.1f}")
    for yr in sorted({r["year"] for r in matched}):
        ms = [r for r in matched if r["year"] == yr]
        print(f"  {yr} ({len(ms)} docs): served {med([sum(v for k, v in r.get('class_counts', {}).items() if k in served) for r in ms]):.1f}, "
              f"all {med([r['n_values'] for r in ms]):.1f}, Tier 4 {med([r['tier4_fields'] for r in ms]):.1f}")
    print("withheld (abstained) by rule:", dict(wh_reason.most_common()))
    print("rejected_fields by reason:", dict(rej_reason.most_common()))
    print("pages rejected by rule:", dict(pg_reason.most_common()))
    return 0


def cmd_wrong_year(args) -> int:
    docs = _cohort_docs(args)
    right = {r["sha"]: r for r in json.loads(Path(args.cohort_json).read_text())}
    picks = []
    for yr in ("2024-25", "2025-26"):
        pool_ = [e for e in docs if e["year"] == yr and right[e["sha"]]["lane_counts"].get("text", 0) >= 200]
        picks += pool_[: args.n // 2]
    with Pool(args.jobs) as pool:
        wrong = pool.map(_extract_job, [(args.pdf_dir, e, "force-other") for e in picks], chunksize=1)
    print("DIAGNOSTIC wrong-year control (forced map of the other year; unreachable from extract_overlay)")
    for e, w in zip(picks, wrong):
        r = right[e["sha"]]
        rv = {v[0]: v[1] for v in r["values"].values()}
        wv = {v[0]: v[1] for v in w["values"].values()}
        shared = set(rv) & set(wv)
        same = sum(1 for t in shared if str(rv[t]).strip("/ ") == str(wv[t]).strip("/ "))
        print(f"{e['school']} true {e['year']}: right-year path emitted {r['n_values']} ({r['status']}); forced wrong map emits "
              f"{w['n_values']}, of {len(shared)} shared tags {len(shared) - same} differ")
    return 0


def _old_vs_new(args) -> int:
    """Previously emitted values (M1 v0.1) vs this run: which are now withheld, by which rule."""
    old = {r["sha"]: r for r in json.loads(Path(args.old).read_text())}
    new = {r["sha"]: r for r in json.loads(Path(args.out).read_text())}
    tot = Counter()
    by_reason = Counter()
    rows = []
    for sha, o in old.items():
        n = new.get(sha)
        if n is None:
            continue
        wh = {(w["pdf_tag"]): w["reason"] for w in n["withheld"]}
        rj = {x["pdf_tag"]: x["reason"] for x in n["rejected"]}
        nv = {v[0]: v[1] for v in n["values"].values()}
        for qn, (tag, val, lane) in o["values"].items():
            tot["old_emitted"] += 1
            if n["status"] != "matched":
                tot["doc_held"] += 1
                by_reason["doc_held:" + str(n["reason"])] += 1
            elif tag in nv and str(nv[tag]).strip("/ ") == str(val).strip("/ "):
                tot["still_emitted"] += 1
            elif tag in nv:
                tot["value_changed"] += 1
            else:
                why = wh.get(tag) or rj.get(tag) or ("page_or_group_not_read")
                by_reason[why] += 1
                tot["withheld_or_rejected"] += 1
                rows.append((sha, o["school"], o["year"], qn, tag, val, lane, why))
    print(dict(tot))
    print("previously emitted values now not emitted, by rule:", dict(by_reason.most_common()))
    Path(args.diff_out).write_text(json.dumps(rows))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp, out_default):
        for a in ("--pdf-dir", "--t4-docs", "--docmeta"):
            sp.add_argument(a, required=True)
        sp.add_argument("--scanned", nargs="+", required=True)
        sp.add_argument("--cohort-csv", default=str(REPO / "docs/prd/assets/038/template-cohort-2026-11-09.csv"))
        sp.add_argument("--jobs", type=int, default=4)
        sp.add_argument("--out", default=out_default)

    s1 = sub.add_parser("stage1")
    common(s1, "scratch/prd038/m1/stage1.json")
    s1.set_defaults(fn=cmd_stage1)
    co = sub.add_parser("cohort")
    common(co, "scratch/prd038/m1/cohort_v2.json")
    co.add_argument("--oracle", action="store_true", help="inject the true year as detected_year (labelled oracle run)")
    co.set_defaults(fn=cmd_cohort)
    wy = sub.add_parser("wrong-year")
    common(wy, "scratch/prd038/m1/wrongyear.json")
    wy.add_argument("--cohort-json", default="scratch/prd038/m1/cohort_v2.json")
    wy.add_argument("--n", type=int, default=6)
    wy.set_defaults(fn=cmd_wrong_year)
    ov = sub.add_parser("old-vs-new")
    ov.add_argument("--old", default="scratch/prd038/m1/cohort_v0.1.json")
    ov.add_argument("--out", default="scratch/prd038/m1/cohort_v2.json")
    ov.add_argument("--diff-out", default="scratch/prd038/m1/old_vs_new.json")
    ov.set_defaults(fn=_old_vs_new)
    cp = sub.add_parser("compare")
    cp.add_argument("--pdf-dir", required=True)
    cp.add_argument("--flat", required=True, help="flattened PDF filename in --pdf-dir")
    cp.add_argument("--fillable", required=True, help="fillable copy of the same document")
    cp.add_argument("--year", required=True)
    cp.add_argument("--label", default="")
    cp.add_argument("--verbose", action="store_true")
    cp.set_defaults(fn=cmd_compare)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
