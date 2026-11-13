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
* A value is served only when its `emission_class` is in the served set and it has no Lane 2 evidence:
  never `lane == 2`, never `2` in `derived_lanes`, whatever the configured set says.
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
ENV_HOLD_THRESHOLD = "OVERLAY_HOLD_THRESHOLD"
DEFAULT_HOLD_THRESHOLD = 0.05          # Decision 3; confirmed or reset from the shadow distribution (A6)

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


def hold_threshold(env: Optional[Mapping[str, str]] = None) -> float:
    raw = (os.environ if env is None else env).get(ENV_HOLD_THRESHOLD)
    try:
        value = float(raw) if raw not in (None, "") else DEFAULT_HOLD_THRESHOLD
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


def has_lane2_evidence(record: Mapping[str, Any]) -> bool:
    return record.get("lane") == 2 or 2 in (record.get("derived_lanes") or ())


def serve_overlay_values(values: Mapping[str, Any], classes: frozenset[str]) -> dict[str, Any]:
    """The overlay values a consumer may serve. `classes` is REQUIRED (no default): the caller passes the
    configured set explicitly, so the producer's own default set can never leak into serving."""
    if not classes:
        return {}
    out: dict[str, Any] = {}
    for key, record in values.items():
        if not isinstance(record, dict):
            continue
        if record.get("emission_class") not in classes or has_lane2_evidence(record):
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
    values = _notes(overlay).get("values")
    served = serve_overlay_values(values if isinstance(values, dict) else {}, classes)
    return (overlay, served) if served else (None, {})


def overlay_version_suffix(base_version: Optional[str], overlay_version: Optional[str]) -> Optional[str]:
    """A4: `<tier4 version>+overlay.<overlay version>` (the base version alone when there is no overlay)."""
    if not overlay_version:
        return base_version
    return f"{base_version or ''}+overlay.{overlay_version}"


# ---- comparing an overlay value with a Tier 4 value (the Decision 3 hold and the shadow report) --------

_NON_NUMERIC = re.compile(r"[^0-9.\-]")


def _record_text(record: Any) -> Optional[str]:
    if isinstance(record, dict):
        raw = record.get("value_decoded")
        if raw is None:
            raw = record.get("value")
    else:
        raw = record
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


# Representation differences between the two producers, not disagreements: Tier 4 writes a ticked box as "X" (and a
# yes/no pair as "Yes"/"No"); the overlay writes the widget's export value ("/Y", "/N", "/X"), decoded as "Yes"/"No".
_YES = {"yes", "y", "x", "true", "checked", "on", "\u2713", "\u2714"}
_NO = {"no", "n", "false", "off"}


def normalise_for_compare(record: Any) -> Optional[str]:
    """A comparison key: numbers by value ($, %, commas and trailing zeros ignored); yes/no/ticked in their
    spellings ("/Y", "Yes", "X", "/N", "No") as one boolean; other text lower-cased with collapsed whitespace.
    None for a missing or blank value. This documents what is treated as the same value; it was written after
    reading the cohort's disagreeing pairs and is not tuned to a share."""
    text = _record_text(record)
    if text is None:
        return None
    flag = text.lstrip("/").strip().lower()
    if flag in _YES:
        return "b:yes"
    if flag in _NO:
        return "b:no"
    stripped = text.replace(",", "").replace("$", "").replace("%", "").strip()
    if stripped and re.fullmatch(r"-?\d+(\.\d+)?", stripped):
        try:
            return "n:" + format(Decimal(stripped).normalize(), "f")
        except InvalidOperation:
            pass
    return "t:" + re.sub(r"\s+", " ", text).lower()


def values_agree(a: Any, b: Any) -> bool:
    return normalise_for_compare(a) == normalise_for_compare(b)


def disagreement_summary(base_values: Mapping[str, Any], overlay_values: Mapping[str, Any]) -> dict[str, Any]:
    """Fields both populate and the share that disagree (all overlay classes: this is shadow data)."""
    both = []
    disagree = []
    for key, record in overlay_values.items():
        if key not in base_values:
            continue
        ours, theirs = normalise_for_compare(record), normalise_for_compare(base_values[key])
        if ours is None or theirs is None:
            continue
        both.append(key)
        if ours != theirs:
            disagree.append(key)
    share = (len(disagree) / len(both)) if both else 0.0
    return {"both_populated": len(both), "disagreeing": len(disagree), "share": round(share, 6),
            "disagreeing_fields": sorted(disagree)}
