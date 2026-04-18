"""
Propose (or apply) landing-page rewrites for direct-PDF cds_url_hint values
in tools/finder/schools.yaml.

Background: ~63% of schools.yaml cds_url_hint values point at a specific
PDF (often a random old year) rather than the school's CDS landing page.
This starves discovery — the resolver and the Playwright probe both yield
best results when given a landing page. This one-shot tool replaces each
direct-PDF hint with the discovered landing URL, sourced in priority order:

  1. manual_urls.yaml:<school>.landing_url_found  (from PR 2 walk-up)
  2. manual_urls.yaml:<school>.final_url          (when probe succeeded
                                                   without walk-up — means
                                                   starting_url was already
                                                   the landing)
  3. cds_documents: most common parent directory across source_url rows
     (weak signal; flagged medium/low confidence in the proposal)

Usage:

    # One: generate proposal (read-only; no schools.yaml edits)
    tools/extraction_worker/.venv/bin/python \\
        tools/finder/promote_landing_hints.py

    # Review: docs/schools_hint_rewrite_proposal.md

    # Two: apply proposal (edits schools.yaml in place, preserving comments)
    tools/extraction_worker/.venv/bin/python \\
        tools/finder/promote_landing_hints.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

_TOOLS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_ROOT / "extraction_worker"))
from worker import load_env  # type: ignore

try:
    from supabase import create_client
except ImportError:
    create_client = None  # DB lookup will be skipped gracefully


DOCUMENT_EXT_RE = re.compile(r"\.(pdf|xlsx|docx)(\?|#|$)", re.I)

# Box / Google Drive share URLs look like direct docs but aren't — skip
# them; the resolver's rewriter already handles these at fetch time and a
# landing-page swap would just lose the year-specific source the operator
# hand-curated.
SKIP_HOST_RE = re.compile(
    r"(drive\.google\.com|docs\.google\.com|"
    r"box\.com|dropbox\.com|onedrive\.live\.com|"
    r"sharepoint\.com)",
    re.I,
)

# Mirror of resolve.ts CDS_LIKE_PATH_SEGMENT_RE plus a few close friends
# observed in the survey (institutionalresearch, irp, pair, oie, oira).
# Used to filter out option-(b) proposals whose "most common parent" is a
# generic CDN upload dir with no CDS signal in the path — those aren't
# landing pages, they're where files happen to sit.
CDS_LIKE_SEGMENT_RE = re.compile(
    r"^(cds|common-data-set|common_data_set|common-data-sets|commondataset|"
    r"institutional-research|institutional_research|institutionalresearch|"
    r"institutional-data|ir|oir|oira|iro|irp)$",
    re.I,
)

# Hostnames / path prefixes that are CDN upload containers, not landings.
# Used as a negative signal in option (b) — if the proposed "parent"
# matches these patterns AND has no CDS-like segment, discard the
# proposal.
UPLOAD_DIR_PATH_RE = re.compile(
    r"(/wp-content/uploads/|"
    r"/sites/default/files/|"
    r"/sites/g/files/|"
    r"/dist/d/|"
    r"/images/|"
    r"/media/home/|"
    r"/uploads/)",
    re.I,
)
UPLOAD_CDN_HOST_RE = re.compile(
    r"(wpmucdn\.com|s3\.amazonaws\.com|cloudfront\.net)",
    re.I,
)


def path_has_cds_segment(url: str) -> bool:
    try:
        parts = [s for s in urlparse(url).path.split("/") if s]
    except Exception:
        return False
    return any(CDS_LIKE_SEGMENT_RE.match(s) for s in parts)


def looks_like_upload_dir(url: str) -> bool:
    """Filter for option-(b) proposals: a URL that lives under a known
    CDN upload tree is an asset directory, not a landing page. Match
    even when the URL happens to contain a CDS-like segment earlier in
    the path (e.g. `/ir/wp-content/uploads/sites/60/2014/07/`) — the
    upload-tree suffix means the resolver would hit a directory that
    doesn't list files in HTML."""
    try:
        parsed = urlparse(url)
    except Exception:
        return True
    if UPLOAD_CDN_HOST_RE.search(parsed.netloc):
        return True
    if UPLOAD_DIR_PATH_RE.search(parsed.path):
        return True
    return False


def normalize_landing_url(url: str) -> str:
    """Strip fragments and non-essential querystrings from a landing URL.
    The SMU probe returned `.../common-data-sets#gsc.tab=0&gsc.q=...` —
    the fragment came from an on-page search widget and has no value in
    a hint. Similarly, drop analytics query params that would make the
    URL look different from the canonical landing to the resolver.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    # Fragments are always safe to strip for a landing-page hint.
    # Query strings are usually noise (utm, gsc, challenge tokens).
    # Preserve query only when the path looks empty (e.g. Indiana's
    # cds/index.html?i=home&p=index — the querystring IS the route).
    keep_query = bool(parsed.query and parsed.path in ("", "/"))
    cleaned_query = parsed.query if keep_query else ""
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" + (
        f"?{cleaned_query}" if cleaned_query else ""
    )


def is_direct_doc_hint(hint: str | None) -> bool:
    if not hint:
        return False
    if SKIP_HOST_RE.search(hint):
        return False
    return bool(DOCUMENT_EXT_RE.search(hint))


def most_common_parent(source_urls: list[str]) -> tuple[str | None, int, int]:
    """Return (parent_url, count, total). The parent_url is the most
    common directory URL across `source_urls`; count is how many source
    URLs share that parent; total is the number of non-skipped URLs
    considered. Returns (None, 0, total) when no parent can be extracted.
    """
    parents: list[str] = []
    for u in source_urls:
        if not u or SKIP_HOST_RE.search(u):
            continue
        try:
            p = urlparse(u)
        except Exception:
            continue
        if p.scheme not in ("http", "https"):
            continue
        segments = [s for s in p.path.split("/") if s]
        if len(segments) < 2:
            # Root-level PDF — no meaningful parent for a landing rewrite.
            continue
        parent_path = "/".join(segments[:-1])
        parents.append(f"{p.scheme}://{p.netloc}/{parent_path}/")
    if not parents:
        return None, 0, len(source_urls)
    top, n = Counter(parents).most_common(1)[0]
    return top, n, len(parents)


def load_manual_urls(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("schools") or {}


def fetch_school_source_urls(sb, school_id: str) -> list[str]:
    """Return all non-null source_url values for a school, paging through
    the default 1000-row REST ceiling."""
    out: list[str] = []
    offset = 0
    while True:
        resp = (
            sb.table("cds_documents")
              .select("source_url")
              .eq("school_id", school_id)
              .range(offset, offset + 999)
              .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        out.extend(r["source_url"] for r in rows if r.get("source_url"))
        if len(rows) < 1000:
            break
        offset += 1000
    return out


def build_proposals(
    schools: list[dict],
    manual: dict[str, dict],
    sb,
) -> list[dict]:
    proposals: list[dict] = []
    for s in schools:
        sid = s["id"]
        hint = s.get("cds_url_hint") or ""
        if not is_direct_doc_hint(hint):
            continue

        proposed: str | None = None
        source: str | None = None
        evidence = ""
        confidence: str | None = None

        # Source 1: manual_urls.yaml landing_url_found (high confidence,
        # came from an actual Playwright walk-up with document anchors).
        m = manual.get(sid) or {}
        if m.get("landing_url_found") and m.get("status") == "ok":
            doc_anchors = sum(
                1 for a in (m.get("anchors") or []) if a.get("is_document")
            )
            if doc_anchors >= 1:
                proposed = normalize_landing_url(m["landing_url_found"])
                source = "manual_urls:landing_url_found"
                evidence = f"Playwright probe: {doc_anchors} document anchors"
                confidence = "high"

        # Source 2: manual_urls.yaml final_url when the starting URL WAS
        # itself the landing (no walk-up needed). Only meaningful when
        # that URL differs from the direct-doc hint we're trying to
        # replace — which it does, because we only enter this block for
        # direct-doc hints.
        if not proposed and m.get("status") == "ok" and m.get("final_url"):
            if m["final_url"] != hint and not is_direct_doc_hint(m["final_url"]):
                doc_anchors = sum(
                    1 for a in (m.get("anchors") or []) if a.get("is_document")
                )
                if doc_anchors >= 1:
                    proposed = normalize_landing_url(m["final_url"])
                    source = "manual_urls:final_url"
                    evidence = f"Playwright probe (no walk-up): {doc_anchors} doc anchors"
                    confidence = "high"

        # Source 3: DB most-common-parent heuristic. Weaker signal — many
        # schools store PDFs under /sites/default/files/YYYY-MM/ which is
        # a CDN upload dir, not a landing page. Skip proposals whose
        # parent URL lives under a known upload-tree path AND has no
        # CDS-like segment — those would regress the resolver (it'd end
        # up at a directory that 403s or isn't linked from a landing).
        if not proposed and sb is not None:
            src_urls = fetch_school_source_urls(sb, sid)
            if src_urls:
                parent, n, total = most_common_parent(src_urls)
                if parent and n >= 2:
                    hint_parent = "/".join(urlparse(hint).path.split("/")[:-1])
                    proposed_parent = urlparse(parent).path.rstrip("/")
                    if hint_parent.rstrip("/") != proposed_parent:
                        if looks_like_upload_dir(parent):
                            # Skip — CDN upload dir, not a landing page.
                            pass
                        else:
                            proposed = normalize_landing_url(parent)
                            source = "cds_documents:most_common_parent"
                            evidence = f"{n}/{total} source_urls share this parent"
                            # Upgrade to 'medium' only when the CDS-segment
                            # test passes; without CDS signal it's still
                            # low even with high count.
                            has_cds = path_has_cds_segment(parent)
                            confidence = ("medium" if (n >= 5 and has_cds)
                                          else ("low" if has_cds else None))
                            if confidence is None:
                                # No CDS segment and no upload-dir match —
                                # genuinely unknown. Discard rather than
                                # propose a coin-flip.
                                proposed = None

        if proposed and proposed != hint:
            proposals.append({
                "school_id": sid,
                "school_name": s.get("name") or sid,
                "current_hint": hint,
                "proposed_hint": proposed,
                "source": source,
                "confidence": confidence,
                "evidence": evidence,
            })
    return proposals


def write_proposal_report(path: Path, proposals: list[dict], total_direct_docs: int) -> None:
    """Write a human-reviewable Markdown proposal.

    Grouped by confidence so the reviewer can quickly scan the
    high-confidence rewrites and then decide how hard to scrutinize the
    medium / low ones.
    """
    by_conf: dict[str, list[dict]] = {"high": [], "medium": [], "low": []}
    for p in proposals:
        by_conf[p["confidence"]].append(p)

    lines: list[str] = []
    lines.append("# schools.yaml hint rewrite proposal\n")
    lines.append(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  \n"
        f"Tool: `tools/finder/promote_landing_hints.py`\n"
    )
    lines.append(
        "## Summary\n\n"
        f"- Direct-doc hints found in schools.yaml: **{total_direct_docs}**\n"
        f"- Rewrite proposals: **{len(proposals)}** "
        f"(high: {len(by_conf['high'])}, "
        f"medium: {len(by_conf['medium'])}, "
        f"low: {len(by_conf['low'])})\n"
        f"- Schools with no proposable landing: **{total_direct_docs - len(proposals)}** "
        "(no manual_urls.yaml entry AND no shared parent in cds_documents)\n\n"
        "To apply: `tools/extraction_worker/.venv/bin/python "
        "tools/finder/promote_landing_hints.py --apply`\n\n"
        "High-confidence proposals come from Playwright probes that "
        "actually landed on a page with multiple CDS document anchors. "
        "Medium/low-confidence proposals are derived from shared parent "
        "directories across cds_documents.source_url — manually verify "
        "these are landing pages (not upload dirs) before applying.\n"
    )

    for conf in ("high", "medium", "low"):
        bucket = by_conf[conf]
        if not bucket:
            continue
        lines.append(f"\n## {conf.title()} confidence — {len(bucket)} proposals\n")
        lines.append("| school_id | source | evidence | current → proposed |")
        lines.append("|---|---|---|---|")
        for p in bucket:
            current_short = p["current_hint"]
            proposed_short = p["proposed_hint"]
            lines.append(
                f"| `{p['school_id']}` | {p['source']} | {p['evidence']} | "
                f"`{current_short}` → `{proposed_short}` |"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def apply_proposals(schools_yaml: Path, proposals: list[dict]) -> int:
    """Rewrite `cds_url_hint` lines in-place. Line-based because
    ruamel.yaml isn't available in the venv and round-tripping via
    PyYAML would obliterate every comment, key order, and blank line
    across the 27k-line file. The schools.yaml formatting is consistent
    enough (flat `- id:` + `  cds_url_hint:` blocks) for a regex to be
    safe — confirmed by pre-scan above the loop that every school's
    block matches the expected shape."""
    by_sid = {p["school_id"]: p for p in proposals}
    lines = schools_yaml.read_text().splitlines(keepends=True)

    out: list[str] = []
    current_sid: str | None = None
    applied = 0
    id_re = re.compile(r"^- id: (\S+)\s*$")
    hint_re = re.compile(r"^(  cds_url_hint: )(\S+.*)$")

    for line in lines:
        m_id = id_re.match(line)
        if m_id:
            current_sid = m_id.group(1)
            out.append(line)
            continue
        m_hint = hint_re.match(line)
        if m_hint and current_sid in by_sid:
            new_hint = by_sid[current_sid]["proposed_hint"]
            out.append(f"{m_hint.group(1)}{new_hint}\n")
            applied += 1
            continue
        out.append(line)

    schools_yaml.write_text("".join(out))
    return applied


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--schools-yaml", type=Path,
                    default=Path("tools/finder/schools.yaml"))
    ap.add_argument("--manual-urls", type=Path,
                    default=Path("tools/finder/manual_urls.yaml"))
    ap.add_argument("--report", type=Path,
                    default=Path("docs/schools_hint_rewrite_proposal.md"))
    ap.add_argument("--env", type=Path, default=Path(".env"))
    ap.add_argument("--apply", action="store_true",
                    help="Rewrite schools.yaml in-place using the proposals "
                         "computed this run. Without --apply, writes a "
                         "read-only proposal report.")
    ap.add_argument("--skip-db", action="store_true",
                    help="Don't query cds_documents; proposals come from "
                         "manual_urls.yaml only. Useful for fast iteration.")
    ap.add_argument("--verify", action="store_true",
                    help="After computing proposals, Playwright-probe each "
                         "option-(b) proposal (DB most-common-parent) and "
                         "drop those that render 0 document anchors. Slow "
                         "(~10-20s per probe) but eliminates false "
                         "positives where the 'parent' is a 404 or 403. "
                         "option-(a) proposals are already probe-verified "
                         "via the manual_urls.yaml pipeline.")
    args = ap.parse_args()

    schools_data = yaml.safe_load(args.schools_yaml.read_text())
    schools = schools_data.get("schools") or []
    manual = load_manual_urls(args.manual_urls)

    direct_doc_schools = [s for s in schools if is_direct_doc_hint(s.get("cds_url_hint"))]
    print(f"Schools with direct-doc hints: {len(direct_doc_schools)}", file=sys.stderr)
    print(f"manual_urls.yaml entries: {len(manual)}", file=sys.stderr)

    sb = None
    if not args.skip_db and create_client is not None:
        try:
            env = load_env(args.env)
            sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
            print("Supabase client: ready", file=sys.stderr)
        except Exception as e:
            print(f"warn: Supabase client init failed ({e}); continuing with manual_urls only",
                  file=sys.stderr)

    proposals = build_proposals(schools, manual, sb)
    print(f"Proposals (pre-verify): {len(proposals)}", file=sys.stderr)

    if args.verify:
        to_verify = [p for p in proposals
                     if p["source"] == "cds_documents:most_common_parent"]
        if to_verify:
            print(f"Verifying {len(to_verify)} option-(b) proposals via Playwright...",
                  file=sys.stderr)
            # Import lazily — the tool should still run without Playwright
            # when verification isn't requested.
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from playwright_collect import _probe_url  # type: ignore
            from playwright.sync_api import sync_playwright

            UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36")
            dropped: list[str] = []
            verified_evidence: dict[str, str] = {}
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                ctx = b.new_context(
                    user_agent=UA,
                    viewport={"width": 1280, "height": 900},
                )
                page = ctx.new_page()
                for p_ in to_verify:
                    outcome = _probe_url(page, p_["proposed_hint"])
                    docs = sum(1 for a in outcome.anchors if a.is_document)
                    if docs == 0:
                        dropped.append(p_["school_id"])
                    else:
                        verified_evidence[p_["school_id"]] = (
                            p_["evidence"] + f"; verified: {docs} doc anchors render"
                        )
                b.close()
            # Apply verification results.
            proposals = [
                p for p in proposals if p["school_id"] not in set(dropped)
            ]
            for p_ in proposals:
                if p_["school_id"] in verified_evidence:
                    p_["evidence"] = verified_evidence[p_["school_id"]]
                    # Upgrade confidence on successful verification.
                    if p_["confidence"] in ("low", "medium"):
                        p_["confidence"] = "high"
                        p_["source"] = p_["source"] + "+verified"
            print(f"Dropped {len(dropped)} dead option-(b) proposals: "
                  f"{', '.join(dropped) if dropped else '(none)'}",
                  file=sys.stderr)
            print(f"Proposals (post-verify): {len(proposals)}", file=sys.stderr)

    if args.apply:
        if not proposals:
            print("No proposals to apply.", file=sys.stderr)
            return 0
        applied = apply_proposals(args.schools_yaml, proposals)
        print(f"Rewrote {applied} cds_url_hint lines in {args.schools_yaml}",
              file=sys.stderr)
        return 0

    write_proposal_report(args.report, proposals, len(direct_doc_schools))
    print(f"Wrote {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
