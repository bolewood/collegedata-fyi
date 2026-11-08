"""Refuse to extract on an environment that doesn't match the lock.

Extraction output depends on the exact Docling, torch, OCR and parser
builds. A venv that silently drifts from the lock writes different field
values for the same PDF (a Python 3.9 venv stuck on Docling 2.69.1 dropped
Sacramento State 2023-24 from 274 to 108 fields). The worker calls
``check_environment`` at startup and exits unless the operator passes
``--allow-dependency-drift``.

Fix a mismatch with:
    python3.12 -m venv .venv && .venv/bin/pip install -r requirements.lock
"""
from __future__ import annotations

import re
import sys
from importlib.metadata import distributions
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parent
LOCK_PATH = WORKER_DIR / "requirements.lock"
PYTHON_VERSION_PATH = WORKER_DIR.parent.parent / ".python-version"

_LOCK_LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in text.splitlines():
        match = _LOCK_LINE_RE.match(line.strip())
        if match:
            pins[_normalize(match.group(1))] = match.group(2)
    return pins


def installed_versions() -> dict[str, str]:
    return {
        _normalize(dist.metadata["Name"]): dist.version
        for dist in distributions()
        if dist.metadata["Name"]
    }


def environment_problems(
    pins: dict[str, str],
    installed: dict[str, str],
    python_version: tuple[int, int],
    expected_python: str | None,
) -> list[str]:
    problems: list[str] = []
    if expected_python:
        have = f"{python_version[0]}.{python_version[1]}"
        if have != expected_python:
            problems.append(f"python {have} (expected {expected_python})")
    # Packages pinned for another platform are simply absent; only a
    # different installed version is drift.
    for name, want in sorted(pins.items()):
        have = installed.get(name)
        if have is not None and have != want:
            problems.append(f"{name} {have} (lock {want})")
    return problems


def check_environment() -> list[str]:
    pins = parse_lock(LOCK_PATH.read_text())
    expected = PYTHON_VERSION_PATH.read_text().strip() if PYTHON_VERSION_PATH.exists() else None
    return environment_problems(pins, installed_versions(), sys.version_info[:2], expected)
