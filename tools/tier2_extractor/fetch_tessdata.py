#!/usr/bin/env python3
"""Fetch the second OCR model for Lane 2 (PRD 038 A12): tessdata_best eng.traineddata, sha256-verified.

Model binaries are never committed. Usage: python tools/tier2_extractor/fetch_tessdata.py [DEST_DIR]
DEST_DIR defaults to $CDS_TESSDATA_BEST or ~/.cache/cds-tessdata/best. The primary model is the tessdata_fast eng file
that ships with the OS tesseract package (its sha256 is checked by TesseractEngine.check, not downloaded here).
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane2_ocr as L  # noqa: E402

URL = "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata"


def main(argv=None) -> int:
    dest = Path((argv or sys.argv[1:] or [L.best_model_dir()])[0])
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "eng.traineddata"
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == L.MODEL_SHA256["best"]:
        print(f"ok (already present): {target}")
        return 0
    data = urllib.request.urlopen(URL, timeout=120).read()
    sha = hashlib.sha256(data).hexdigest()
    if sha != L.MODEL_SHA256["best"]:
        print(f"REFUSED: sha256 {sha} != expected {L.MODEL_SHA256['best']}", file=sys.stderr)
        return 1
    target.write_bytes(data)
    print(f"fetched and verified: {target} ({sha})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
