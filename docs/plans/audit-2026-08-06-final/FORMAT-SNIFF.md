# Source corpus format-sniff execution

Every one of 4,071 current source objects was attempted with `Range: bytes=0-4095`. Fifteen produced explicit HTTP errors after retries; they remain listed exclusions. Among 4,056 successful probes, the observed first-byte families were 3,610 PDF, 389 ZIP, 56 HTML within the worker's first 512 bytes, and one other.

The measured exposure to the two questioned heuristics is zero in the accessible corpus: 0/4,056 PDFs have `%PDF` after byte zero, and 0/4,056 HTML objects first become recognizable after byte 512 but within byte 4,096. This replaces the unsupported “<1%” assertion; it does not prove risk is impossible outside the observed corpus.

All 389 ZIP sources were downloaded with the archive worker's 50 MiB cap and passed through `sniff_zip_inner_format`: 370 XLSX and 19 DOCX, zero probe error, zero artifact-SHA mismatch. Twenty-eight document labels were stale (20 PDF→XLSX, eight XLSX→DOCX), but the current byte-sniff router corrects those labels before dispatch. That is metadata drift, not demonstrated silent data loss.

The same run selected the deterministic B1 cohort only from sources whose 4 KiB probe actually contained `%PDF`, then fully downloaded all 100. Artifact bytes matched artifact SHA; byte-detected year matched `detected_year` whenever both existed. The detector found no year in 16, and two document-level `source_sha256` values differ from bytes even though the selected artifact SHA matches—provenance drift worth review, not evidence of corrupt stored bytes.

Machine-readable exclusions and counts: `evidence/source-corpus-summary.json`. Runnable implementation: `tools/data_quality/probe_source_corpus.py`.
