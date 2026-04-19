# upload

Operator CLI for uploading a CDS file directly to the archive when the resolver can't fetch it.

Use this when a school's file is behind a WAF (Cloudflare / Akamai), an auth wall (Microsoft SSO / intranet), a JS-dropdown XLSX download, a private Drive link, or any other obstacle that blocks automated fetch. You download the file in your browser, point this tool at the file, and the archive picks it up with `source_provenance='operator_manual'`.

## What's in the directory

| File | Purpose |
|---|---|
| `upload.py` | The CLI. Wraps the `archive-upload` edge function. |

## Usage

```bash
# Simplest — archive a PDF you downloaded to ~/Downloads/
python tools/upload/upload.py ~/Downloads/williams_cds_2023-2024.pdf williams 2023-24

# Record where you got it (for provenance + human audit later)
python tools/upload/upload.py ./ucla_cds_2024-25.pdf ucla 2024-25 \
    --source-url https://apb.ucla.edu/file/9f8e7d6c-abcd

# Override provenance (e.g., you downloaded from a mirror and want to tag it that way)
python tools/upload/upload.py ./grab.pdf some-school 2022-23 \
    --source-provenance mirror_college_transitions
```

Reads `.env` for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. No new deps beyond what the other `tools/` scripts already use (`requests`, `python-dotenv`).

## Semantics

- **Idempotent.** Upload the same file twice: second call returns `unchanged_verified`.
- **Refresh-on-new-bytes.** Upload a different file for an existing (school, year): the new file becomes the canonical source and gets marked `extraction_pending`. The old artifact row stays in `cds_artifacts` for audit.
- **Magic-byte validated.** PDF, XLSX, or DOCX only. If the bytes don't match one of those three, the server rejects with HTTP 400 — no silent half-upload.
- **Year-format checked locally.** `YYYY-YY` where `YY = YYYY+1`. Rejected client-side before the HTTP call.
- **Provenance.** Default `operator_manual`. Override with `--source-provenance` if the file genuinely came from somewhere else (e.g., you grabbed it off the College Transitions mirror).

## When to use this vs. force_urls

| Situation | Use |
|---|---|
| You have a URL and it works with `curl` | `archive-process?POST force_urls` |
| You have a URL but Cloudflare / auth blocks automated fetch | `tools/finder/headless_download.py` (Playwright-based) |
| You have the **file** but not a working URL | **this tool** |
| You have the file AND a URL to record for provenance | this tool with `--source-url` |

## See also

- [`supabase/functions/archive-upload/index.ts`](../../supabase/functions/archive-upload/index.ts) — the edge function this tool calls
- [`tools/finder/headless_download.py`](../finder/headless_download.py) — Playwright-driven fetcher for WAF-blocked direct URLs
- [`docs/backlog.md`](../../docs/backlog.md) "Public CDS upload form" — the future public pathway this is a precursor to
