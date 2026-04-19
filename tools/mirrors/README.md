# mirrors

Ingest pipelines for third-party CDS archives. When a school deletes an older CDS from their IR page but a public mirror has preserved it, we can pull the mirrored copy and tag it with structured provenance so consumers know where it came from.

## The pattern

Each mirror gets a subdirectory here. Every mirror follows the same contract:

```
tools/mirrors/<mirror_name>/
  README.md          one-page summary of what the mirror is, what it covers, caveats
  fetch.py           downloads / scrapes the mirror, writes catalog.json
  catalog.json       committed snapshot — what the mirror had at last fetch
  ingest.py          reads catalog.json, cross-refs against cds_documents,
                     posts gaps to archive-process?POST force_urls with
                     source_provenance='mirror_<name>'
```

`catalog.json` is committed so diffs are reviewable: when CT adds a school or year, the ingest PR shows what's new. Ingest is idempotent — it only acts on (school, year) pairs we don't already have.

## Policy: school's own publication always wins

`archive.ts` and `db.ts` encode this policy:

- **Inserts** default to `source_provenance='school_direct'` unless the caller explicitly passes a mirror value.
- **Refreshes** (new sha for an existing row) also default to `school_direct`. This means: if we previously ingested a mirror copy of school X year Y, and later the resolver finds the school's own current file for that year, the refresh branch upgrades the provenance. The school's publication always wins over a mirror.
- **Mirror ingest scripts never call refresh.** They check the DB first; if the row already exists they skip, regardless of whether the bytes match. This avoids flip-flopping provenance between mirrors or re-downloading files we already have from the school directly.

## Re-running a mirror

```bash
# 1. Refresh the catalog (one-time setup: playwright install if needed)
python tools/mirrors/<mirror_name>/fetch.py

# 2. Review the diff
git diff tools/mirrors/<mirror_name>/catalog.json

# 3. Ingest the gaps
python tools/mirrors/<mirror_name>/ingest.py

# 4. Commit the updated catalog
git add tools/mirrors/<mirror_name>/catalog.json
git commit -m "mirrors(<mirror_name>): refresh catalog"
```

## Current mirrors

| Mirror | Schools | Files | Provenance value | Notes |
|---|---:|---:|---|---|
| [`college_transitions/`](college_transitions/) | 333 | 1,983 | `mirror_college_transitions` | Re-hosts CDS PDFs on Google Drive. 2019-20 through 2024-25 window. Spot-check confirmed some files are older revisions than what schools currently publish. |

## Adding a new mirror

1. Create `tools/mirrors/<name>/` following the layout above.
2. Add the provenance value to the CHECK constraint in a new migration:
   ```sql
   alter table public.cds_documents
     drop constraint cds_documents_source_provenance_valid;
   alter table public.cds_documents
     add constraint cds_documents_source_provenance_valid
     check (source_provenance in (
       'school_direct',
       'mirror_college_transitions',
       'mirror_<new_name>',        -- new
       'operator_manual'
     ));
   ```
3. Add the new value to the allowlist in `supabase/functions/archive-process/index.ts:runForceUrls()` (search for `ALLOWED_PROVENANCE`).
4. Write the fetch + ingest scripts.
5. Document in this README's table.
