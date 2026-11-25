# Data quality snapshots (PRD 040)

One JSON file per scoreboard run, named `<YYYY-MM-DD>.json`, in the public
shape documented in `docs/prd/040-data-quality-page.md` ("Public JSON shape",
plus the `renewal` block). They are written by `scoreboard.py --public` and
committed in a PR with the `--compare` deltas.

`/data-quality` and the "This year's reports on file" tile on `/coverage` read
the file with the newest `snapshot_of`. The build fails when:

- two files have the same `snapshot_of` date;
- a file's `public_format` is one the page doesn't know;
- a file is not valid JSON or is missing the keys the page reads
  (including `renewal`);
- this directory has no `.json` file **and the launch gate
  (`isDataQualityLaunched()` in `web/src/lib/data-quality.ts`) is open**.

Before launch, an empty directory is allowed: `/data-quality` returns 404 and
the `/coverage` tile is left out. Once the gate opens, an empty directory is
an error, never "no data, ok". Keep old snapshots here: they feed a later
trend line.
