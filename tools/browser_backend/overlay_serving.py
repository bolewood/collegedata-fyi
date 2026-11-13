"""Which `tier2_template_overlay` values may be served, and how they merge (PRD 038 A2, A3, A12, A13).

Pure Python on purpose: no cv2, no pdfium, no OCR. The projection (`project_browser_data.py`) and the
worker's hold computation import this module; the overlay extractor does not. The web (`web/src/lib/
overlay-serving.ts`) and the SQL view (`supabase/pending/038_overlay_serving.sql`) implement the same
rules and are pinned to this module by the shared fixture `fixtures/overlay_parity.json`.

The rules, in one place:

* The served-class set is configuration (`OVERLAY_SERVE_CLASSES`, comma separated) and is EMPTY by default.
  An unknown class name anywhere in the value means nothing is served (fail closed).
* An overlay artifact is a candidate for a base artifact only when it is `kind='cleaned'`,
  `producer='tier2_template_overlay'`, its notes carry `source_sha256` equal to the base's recorded sha
  (strict, A3; a base with no recorded sha never merges), and its notes say `held` is exactly `false`
  (Decision 3: a held or unmarked overlay is never served).
* The base must be a `tier4_docling` artifact (like the LLM fallback join), and its `schema_version` column and the
  overlay's must both be non-null and equal: the overlay keys its values by its template year's numbering, and Tier 4
  artifacts without a schema version carry 2025-26 ids whatever the template (A13).
* The newest such overlay is the one used.
* A value is served only when its `emission_class` is in the served set, it is not blank, and it has no Lane 2 evidence:
  never `lane` 2 (as 2, 2.0 or "2"), never a 2 in `derived_lanes` (same spellings), whatever the configured set says.
  A blank overlay value (null, "", whitespace) is not merged, so it never overwrites a populated base value.
* `notes.values` must be a JSON object; anything else serves nothing.
* Merge order is `fallback || tier4 base || overlay`: the overlay wins.
"""

from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Optional

OVERLAY_PRODUCER = "tier2_template_overlay"
OVERLAY_BASE_PRODUCER = "tier4_docling"
ENV_SERVE_CLASSES = "OVERLAY_SERVE_CLASSES"
ENV_HOLD_THRESHOLD = "OVERLAY_HOLD_THRESHOLD"   # read by the drain tool at WRITE time only; no selector reads it
DEFAULT_HOLD_THRESHOLD = 0.05          # Decision 3 as written; confirmed or reset from the audit (A6)
HOLD_CANDIDATE_CLASSES = ("numeric", "choice", "checkbox_box")   # the default served-candidate set the hold is computed over

# Every class the producer writes (template_overlay.CLASS_*). `ocr_numeric` is a known class so a typo is
# distinguishable from a deliberate entry, but values with Lane 2 evidence are never served anyway.
KNOWN_CLASSES = frozenset({"numeric", "choice", "checkbox_box", "checkbox_boxless", "free_text", "ocr_numeric"})


def parse_serve_classes(raw: Optional[str]) -> frozenset[str]:
    """Comma-separated class names -> the served set. Empty or missing -> empty. Unknown name -> empty."""
    if raw is None:
        return frozenset()
    names = [part.strip() for part in str(raw).split(",")]
    names = [n for n in names if n]
    if not names or any(n not in KNOWN_CLASSES for n in names):
        return frozenset()
    return frozenset(names)


def served_classes(env: Optional[Mapping[str, str]] = None) -> frozenset[str]:
    return parse_serve_classes((os.environ if env is None else env).get(ENV_SERVE_CLASSES))


def hold_threshold(env: Optional[Mapping[str, str]] = None) -> Optional[float]:
    """The write-time hold threshold: 0..1, default 0.05; `off` (any case) disables the disagreement hold (None)."""
    raw = (os.environ if env is None else env).get(ENV_HOLD_THRESHOLD)
    return parse_hold_threshold(raw)


def parse_hold_threshold(raw: Optional[str]) -> Optional[float]:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_HOLD_THRESHOLD
    if str(raw).strip().lower() == "off":
        return None
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_HOLD_THRESHOLD
    return value if 0 <= value <= 1 else DEFAULT_HOLD_THRESHOLD


def _notes(artifact: Mapping[str, Any]) -> dict[str, Any]:
    notes = artifact.get("notes")
    return notes if isinstance(notes, dict) else {}


def recorded_source_sha(artifact: Mapping[str, Any]) -> Optional[str]:
    """The source sha a canonical artifact records (`notes.source_sha256`, else `notes.source_artifact.sha256`)."""
    notes = _notes(artifact)
    sha = notes.get("source_sha256")
    if not sha and isinstance(notes.get("source_artifact"), dict):
        sha = notes["source_artifact"].get("sha256")
    return str(sha) if sha else None


def overlay_is_held(overlay: Mapping[str, Any]) -> bool:
    """Held unless `notes.held` is exactly False: an artifact without the mark is not served."""
    return _notes(overlay).get("held") is not False


def overlay_matches_base(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> bool:
    if overlay.get("kind") != "cleaned" or overlay.get("producer") != OVERLAY_PRODUCER:
        return False
    if base.get("producer") != OVERLAY_BASE_PRODUCER:
        return False
    base_schema, overlay_schema = base.get("schema_version"), overlay.get("schema_version")
    if not base_schema or not overlay_schema or str(base_schema) != str(overlay_schema):
        return False
    base_sha = recorded_source_sha(base)
    overlay_sha = _notes(overlay).get("source_sha256")
    if not base_sha or not overlay_sha or str(overlay_sha) != base_sha:
        return False
    return not overlay_is_held(overlay)


def _created_at_key(row: Mapping[str, Any]) -> str:
    return str(row.get("created_at") or "")


def pick_overlay(base: Mapping[str, Any], artifacts: Iterable[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """The newest overlay artifact that may merge onto `base` (ties broken by id, like the other joins)."""
    matching = [a for a in artifacts if overlay_matches_base(base, a)]
    if not matching:
        return None
    return sorted(matching, key=lambda r: (_created_at_key(r), str(r.get("id") or "")), reverse=True)[0]


def _is_two(x: Any) -> bool:
    """2, 2.0 and "2" (also "2.0", surrounding spaces) are the number two; booleans and everything else are not."""
    if isinstance(x, bool):
        return False
    if isinstance(x, (int, float)):
        return x == 2
    if isinstance(x, str) and re.fullmatch(r"\s*[0-9]+(\.[0-9]+)?\s*", x):
        return float(x) == 2
    return False


def has_lane2_evidence(record: Mapping[str, Any]) -> bool:
    derived = record.get("derived_lanes")
    return _is_two(record.get("lane")) or (isinstance(derived, (list, tuple)) and any(_is_two(d) for d in derived))


def serve_overlay_values(values: Any, classes: frozenset[str]) -> dict[str, Any]:
    """The overlay values a consumer may serve. `classes` is REQUIRED (no default): the caller passes the
    configured set explicitly, so the producer's own default set can never leak into serving. Blank values are
    not merged (a blank never overwrites a populated Tier 4 value); a non-object `values` serves nothing."""
    if not classes or not isinstance(values, dict):
        return {}
    out: dict[str, Any] = {}
    for key, record in values.items():
        if not isinstance(record, dict):
            continue
        if record.get("emission_class") not in classes or has_lane2_evidence(record):
            continue
        if _record_text(record) is None:
            continue
        out[key] = record
    return out


def served_overlay_for_base(
    base: Mapping[str, Any],
    artifacts: Iterable[Mapping[str, Any]],
    classes: frozenset[str],
) -> tuple[Optional[Mapping[str, Any]], dict[str, Any]]:
    """(overlay artifact used, its served values). With an empty set: (None, {}) without looking at any artifact."""
    if not classes:
        return None, {}
    overlay = pick_overlay(base, artifacts)
    if overlay is None:
        return None, {}
    served = serve_overlay_values(_notes(overlay).get("values"), classes)
    return (overlay, served) if served else (None, {})


OVERLAY_MARK = "+overlay."


def overlay_version_suffix(
    base_version: Optional[str], overlay_version: Optional[str], classes: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """A4: `<tier4 version>+overlay.<overlay version>/<served classes, sorted, comma-joined>`. The class set is part of the
    identity because changing it changes served values with no version change. With no overlay: the base version alone."""
    if not overlay_version:
        return base_version
    tail = "/" + ",".join(sorted(classes)) if classes else ""
    return f"{base_version or ''}{OVERLAY_MARK}{overlay_version}{tail}"


def overlay_identity_of_version(producer_version: Optional[str]) -> Optional[str]:
    """The single reader of overlay identity from a stored `producer_version` (None when no overlay was merged). If the
    owner later moves the identity to an explicit column, this and `overlay_version_suffix` are the only places to change."""
    text = str(producer_version or "")
    return text.split(OVERLAY_MARK, 1)[1] if OVERLAY_MARK in text else None


# ---- comparing an overlay value with a Tier 4 value (the write-time hold facts and the shadow report) ---------------

_NUMERIC_CLASSES = {"numeric", "ocr_numeric"}
_BOX_CLASSES = {"choice", "checkbox_box", "checkbox_boxless"}


def _record_text(record: Any) -> Optional[str]:
    """The text of a record: `value_decoded` when it is non-blank, else `value`; trimmed; None when both are blank."""
    if isinstance(record, dict):
        candidates = (record.get("value_decoded"), record.get("value"))
    else:
        candidates = (record,)
    for raw in candidates:
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return None


# Tier 4 writes a ticked box as "X" (and a yes/no pair as "Yes"/"No"); the overlay writes the widget's export value
# ("/Y", "/N", "/X"), decoded as "Yes"/"No". Applied to checkbox and choice classes only.
_YES = {"yes", "y", "x", "true", "checked", "on", "\u2713", "\u2714"}
_NO = {"no", "n", "false", "off"}


def normalise_for_compare(record: Any, cls: Optional[str] = None) -> Optional[str]:
    """A comparison key by the OVERLAY value's emission class (`cls`, default: the record's own `emission_class`):

    * numeric classes: numbers by value ($, %, commas and trailing zeros ignored);
    * choice / checkbox classes: yes/no/ticked spellings ("/Y", "Yes", "X", "/N", "No") as one boolean, other text
      lower-cased with collapsed whitespace;
    * free text (and an unknown class): the trimmed text, nothing else.

    None for a missing or blank value. "Required" vs "Required of All" is a known spelling difference that is NOT
    normalised (83 pairs in the cohort)."""
    text = _record_text(record)
    if text is None:
        return None
    if cls is None and isinstance(record, dict):
        cls = record.get("emission_class")
    if cls in _NUMERIC_CLASSES:
        stripped = text.replace(",", "").replace("$", "").replace("%", "").strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", stripped):
            try:
                return "n:" + format(Decimal(stripped).normalize(), "f")
            except InvalidOperation:
                pass
        return "t:" + text
    if cls in _BOX_CLASSES:
        flag = text.lstrip("/").strip().lower()
        if flag in _YES:
            return "b:yes"
        if flag in _NO:
            return "b:no"
        return "t:" + re.sub(r"\s+", " ", text).lower()
    return "t:" + text


def values_agree(overlay_record: Any, other_record: Any, cls: Optional[str] = None) -> bool:
    """Compare under the overlay record's class (both sides normalised the same way)."""
    if cls is None and isinstance(overlay_record, dict):
        cls = overlay_record.get("emission_class")
    return normalise_for_compare(overlay_record, cls) == normalise_for_compare(other_record, cls)


def comparison_facts(
    base_values: Mapping[str, Any], overlay_values: Mapping[str, Any], tier4_only_class_of=None,
) -> dict[str, Any]:
    """The facts the write-time hold (and any later rule) is computed from, so no re-extraction is needed:
    per emission class the fields both populate and the ones that disagree, the disagreeing question ids with class, and
    per class the fields Tier 4 populates that the overlay leaves empty (the hold's blind spot). `tier4_only_class_of`
    maps a question id to a class name for those fields (unknown -> "unclassified")."""
    by_class: dict[str, dict[str, int]] = {}
    disagreeing: list[dict[str, str]] = []
    for key in sorted(overlay_values):
        record = overlay_values[key]
        cls = str(record.get("emission_class")) if isinstance(record, dict) else "unclassified"
        ours = normalise_for_compare(record, cls)
        if ours is None or key not in base_values:
            continue
        theirs = normalise_for_compare(base_values[key], cls)
        if theirs is None:
            continue
        slot = by_class.setdefault(cls, {"both": 0, "disagree": 0})
        slot["both"] += 1
        if ours != theirs:
            slot["disagree"] += 1
            disagreeing.append({"question": key, "class": cls})
    tier4_only: dict[str, int] = {}
    for key in sorted(base_values):
        if _record_text(base_values[key]) is None:
            continue
        ov = overlay_values.get(key)
        if ov is not None and _record_text(ov) is not None:
            continue
        cls = (tier4_only_class_of(key) if tier4_only_class_of else None) or "unclassified"
        tier4_only[cls] = tier4_only.get(cls, 0) + 1
    return {"by_class": by_class, "disagreeing": disagreeing, "tier4_populated_overlay_empty": tier4_only}


def share_over(by_class: Mapping[str, Mapping[str, int]], classes: Iterable[str]) -> tuple[int, int, Optional[float]]:
    both = sum(by_class.get(c, {}).get("both", 0) for c in classes)
    bad = sum(by_class.get(c, {}).get("disagree", 0) for c in classes)
    return both, bad, (bad / both if both else None)


def disagreement_hold(
    by_class: Mapping[str, Mapping[str, int]], classes: Iterable[str] = HOLD_CANDIDATE_CLASSES,
    threshold: Optional[float] = DEFAULT_HOLD_THRESHOLD,
) -> dict[str, Any]:
    """The Decision 3 rule over `classes`: hold when disagree / compared > threshold; threshold None (`off`) never holds."""
    classes = tuple(classes)
    both, bad, share = share_over(by_class, classes)
    held = bool(threshold is not None and share is not None and share > threshold)
    return {"classes": sorted(classes), "threshold": threshold, "compared": both, "disagree": bad,
            "share": None if share is None else round(share, 6), "held": held}
