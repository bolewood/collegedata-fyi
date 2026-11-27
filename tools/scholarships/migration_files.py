"""Find the scholarship directory migrations by what they define, not by file name.

A migration that redefines the view (for example a text rename) need not carry
"scholarship_directory" in its name, so tests that globbed by name silently read
an older definition. Every helper scans supabase/migrations/*.sql in sorted order.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

_VIEW = re.compile(r"create\s+(or\s+replace\s+)?view\s+public\.scholarship_directory\b", re.I)
_CACHE = re.compile(r"create\s+materialized\s+view\s+public\.scholarship_directory_cache\b", re.I)
_OBJECT = re.compile(
    r"(create\s+(or\s+replace\s+)?|alter\s+)(materialized\s+view|view|table|function)\s+public\.scholarship_", re.I
)
_COMMENT = re.compile(r"--[^\n]*")


def _matching(pattern: "re.Pattern[str]", directory: Path = MIGRATIONS_DIR) -> List[Path]:
    # Line comments are stripped first: a comment that quotes a statement does not define anything.
    return [p for p in sorted(directory.glob("*.sql")) if pattern.search(_COMMENT.sub("", p.read_text(encoding="utf-8")))]


def view_migrations(directory: Path = MIGRATIONS_DIR) -> List[Path]:
    """Every migration that creates or replaces public.scholarship_directory, oldest first."""
    return _matching(_VIEW, directory)


def newest_view_migration(directory: Path = MIGRATIONS_DIR) -> Path:
    """The migration whose view body is live: attribution, license and column pins read this."""
    return view_migrations(directory)[-1]


def base_migration(directory: Path = MIGRATIONS_DIR) -> Path:
    """The first migration that defines the view (tables, functions, cache and view)."""
    return view_migrations(directory)[0]


def newest_cache_migration(directory: Path = MIGRATIONS_DIR) -> Path:
    """The last migration that (re)creates the materialized cache."""
    return _matching(_CACHE, directory)[-1]


def all_scholarship_migrations(directory: Path = MIGRATIONS_DIR) -> List[Path]:
    """Every migration that defines a scholarship_* table, function, cache or view, in order."""
    return _matching(_OBJECT, directory)
