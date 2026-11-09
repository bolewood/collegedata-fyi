# CollegeData.FYI CLI

Thin command-line wrapper for the public CollegeData.FYI friendly API (`/api/schools/search`, `/api/schools/{id}/facts`, `/api/compare`, `/api/schools/{id}/sources`, `/api/fields`, and the `/snapshots/latest/` files). One Node file, no dependencies, Node 20 or newer.

**Install:** the package (`@collegedata-fyi/cli`, version 0.1.0) is not published to npm. Run it from a clone of this repository:

```bash
git clone https://github.com/bolewood/collegedata-fyi.git
cd collegedata-fyi
node packages/cli/bin/collegedata.js search mit
```

## Commands

| Command | What it does |
|---|---|
| `search <query> [--format json]` | Find canonical `school_id`s by name, alias, city or state. |
| `facts <school_id> [--categories admissions,cost,outcomes] [--format json\|table]` | Source-labeled facts for one school. Categories: `identity`, `admissions`, `enrollment`, `cost`, `aid`, `finance`, `outcomes`, `sources`. |
| `compare <school_id...> [--categories ...] [--fields applied,admitted] [--format json\|csv\|table]` | Side-by-side facts for several schools. |
| `sources <school_id>` | Source documents, archive URLs, federal release metadata and coverage status (always JSON). |
| `fields [--category admissions] [--format json\|table]` | The field dictionary. |
| `export <snapshot> [--format jsonl\|json]` | Prints a public data file from `/snapshots/latest/`: `schools`, `school_facts` and `sources` as `jsonl`; `field_dictionary` as `json`. |

`--format` defaults to `table` in a terminal and `json` when piped. For `export`, `--format` is the file extension, so it defaults to `jsonl`; the `duckdb` extension is not served. `help` prints usage.

```bash
node packages/cli/bin/collegedata.js facts mit --categories admissions,cost
node packages/cli/bin/collegedata.js compare mit yale university-of-chicago --format csv
node packages/cli/bin/collegedata.js export schools > schools.jsonl
```

Set `COLLEGEDATA_API_BASE` (default `https://www.collegedata.fyi`) to point at a preview or local server. Requests carry `cd_client=cli`, the CLI version and the command name so usage can be attributed (see `docs/api-usage-attribution.md`).

## Using the data?

Tell us what you're building, researching, or using in your work.
A link and a sentence are plenty: https://www.collegedata.fyi/feedback.
You can also [open an issue](https://github.com/bolewood/collegedata-fyi/issues)
or [star this repository](https://github.com/bolewood/collegedata-fyi).
No account or response is required to use the data.
