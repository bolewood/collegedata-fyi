"""URL/filename academic-year parser shared by Playwright archive ingest.

Canonical form is ``YYYY-YY``. Matches the Deno ``normalizeYear`` contract
in ``supabase/functions/_shared/year.ts``: accept 1990-2035 and require
``y2 == (y1 + 1) % 100`` so Drupal upload months like ``2020-04`` do not
become CDS years. The previous Python copy only matched ``20xx``, so
``cds1997-98.pdf`` archived as ``unknown``.
"""

from __future__ import annotations

import re

_YEAR_SPAN = re.compile(r"(19\d{2}|20\d{2})[-_\u2010-\u2014\u2212](\d{2,4})")


def normalize_academic_year(text: str | None) -> str | None:
    """Return the first valid CDS span in ``text``, or None."""
    if not text:
        return None
    for match in _YEAR_SPAN.finditer(str(text)):
        y1 = int(match.group(1))
        raw_y2 = match.group(2)
        y2 = int(raw_y2) % 100 if len(raw_y2) == 4 else int(raw_y2)
        if (y1 + 1) % 100 != y2:
            continue
        if y1 < 1990 or y1 > 2035:
            continue
        return f"{y1}-{y2:02d}"
    return None
