# Data quality snapshots (PRD 040)

One JSON file per scoreboard run, named `<YYYY-MM-DD>.json`, in the public
shape documented in `docs/prd/040-data-quality-page.md` ("Public JSON shape",
plus the `renewal` block). They are written by `scoreboard.py --public` and
committed in a PR with the `--compare` deltas.

`/data-quality` and the "{year} reports on file" tile on `/coverage` read
the file with the newest `snapshot_of`, and the "Over time" section of
`/data-quality` reads every file here, each against its own `public_format`.
Never commit a snapshot that is not from a real run. The build fails when:

- two files have the same `snapshot_of` date;
- a file's `public_format` is one the page doesn't know;
- a file is not valid JSON or is missing the keys the page reads
  (including `renewal`);
- this directory has no `.json` file, with the launch gate open or closed.

An empty directory is an error, never "no data, ok": `/coverage` reads the
newest snapshot for its renewal tile whether or not the gate is open. Keep old
snapshots here: they feed a later trend line.

## `reports/<date>.json`

Written with each snapshot by the same `scoreboard.py --public` run: one row per
report that a count in the snapshot counts (document id, school, format, status,
and the outcome in each table; no values), so a count on `/data-quality` can list
the reports behind it. It lives in a subdirectory so the snapshot loader, which
reads only `*.json` files here, never mistakes it for a snapshot. `--public`
refuses to write it unless every count in the snapshot equals the rows it lists,
and the build checks the same thing (`loadReportsFor`). The page fetches it on the
first click, from `/data-quality/reports/<date>`; it is not part of the page's
bundle. School names come from `tools/finder/schools.yaml`, not from the
database. A row carries `nopage: true` when its school has no page for that year
(only a blank template that year), and a row whose school the run did not record
has `school: null`; the page lists both without a link. A snapshot written before this has no file and its counts are not
buttons.

Only the newest snapshot's reports file is ever read or served, so **keep one:
when you add a snapshot with its reports file, delete the older reports files**
in the same PR (a test fails if more than one is left). The aggregate snapshots
stay for the trend, and git history keeps the old reports files. This is also
why `next.config.ts` traces `reports/` only for `/data-quality` and its reports
route, and not for `/coverage`.
