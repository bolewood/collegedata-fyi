# brand-colors: bootstrap a college brand-color scouting queue

A single Python script (`build_crosswalk.py`, no dependencies beyond the
standard library) that joins three public sources to answer one question
cheaply, at scale: **for a given US college, is there an official page that
states its brand color as a hex code, and where?**

That question is normally the slow part of populating a "brand colors"
field for a college directory — searching each school's site one at a time
for `/brand`, `/identity`, or an athletics style guide, most of which are
dead links, PDFs, or don't exist. This tool instead cross-references:

1. **Wikipedia's [`Module:College_color/data`](https://en.wikipedia.org/wiki/Module:College_color/data)**
   — a Lua data module maintained by Wikipedia's college-sports editors,
   mapping ~1,550 NCAA team nicknames ("Iowa Hawkeyes") to 1–3 brand hex
   colors plus a citation (usually the school's own brand/athletics PDF).
2. **Wikipedia's "List of NCAA Division I/II/III institutions"** — three
   tables mapping nickname → official school name + state, needed because
   the color module above is keyed by *nickname*, not school name.
3. **Your own institution directory** — a CSV of `school_id` / `ipeds_id` /
   `school_name` / `state` (and whatever "do we already have this" flag your
   schema uses), so schools are joined by IPEDS UNITID rather than fragile
   name matching, and only schools that actually need colors show up.

The output is a JSONL queue: one row per matched school, with a candidate
hex list, the citation URL, and a citation-quality tier. **It's a hint
list, not a source of truth** — every row still needs a human or agent to
open the cited URL and confirm the hex is genuinely stated there. What this
buys you is skipping the slowest part of manual scouting (finding out
*whether* an official page exists, and where) for a large fraction of
NCAA-affiliated schools.

## Why this exists

Built for [collegedata.fyi](https://collegedata.fyi), an open-source
archive of US college Common Data Set documents, while populating an
`institution_directory.brand_colors` field. Manually scouting one school at
a time (open site, search for a brand page, read a PDF, confirm a hex) ran
at roughly 5–10 minutes per school. Running ~800 schools through this
crosswalk first, then verifying each candidate against its cited source,
cut that down substantially — the crosswalk collapses "does an official
source exist" into a one-time batch join instead of ~800 individual
searches, and the sourcing bar for what actually goes in the database
(a hex explicitly stated on the school's own domain, never eyedropped from
a logo) didn't change at all.

If you're bootstrapping something similar (a directory, a design-system
seed, a data-viz palette by institution) for US colleges, this join is
reusable as-is — swap in your own `institution_directory` export.

## Usage

Fetch the three Wikipedia sources:

```bash
curl -sL "https://en.wikipedia.org/w/index.php?title=Module:College_color/data&action=raw" \
  -o college_color_data.lua

for div in Division_I Division_II Division_III; do
  curl -sL "https://en.wikipedia.org/w/index.php?title=List_of_NCAA_${div}_institutions&action=raw" \
    -o "ncaa_${div}.wikitext"
done
```

Export your institution directory (adjust the query to your own schema —
the script only requires `school_id`, `ipeds_id`, `school_name`, `state`
columns; `needs_colors` and `brand_colors_confidence` are optional and used
only to filter/annotate the output):

```bash
psql "$DATABASE_URL" -c "
  select school_id, ipeds_id, school_name, state,
         (brand_colors is null) as needs_colors,
         brand_colors_confidence
  from institution_directory
  where in_scope = true
" --csv -A -F',' > institution_directory_scope.csv
```

Run it:

```bash
python3 build_crosswalk.py \
  --lua college_color_data.lua \
  --d1 ncaa_Division_I.wikitext --d2 ncaa_Division_II.wikitext --d3 ncaa_Division_III.wikitext \
  --directory institution_directory_scope.csv \
  --out-dir .
```

(All flags default to the same filenames in the current directory, so if
you fetched everything into one folder you can just run
`python3 build_crosswalk.py` from there.)

This writes `candidate_queue.jsonl` (every matched school) and
`candidate_queue_usable.jsonl` (filtered to schools needing colors, with a
citable — not `trucolor.net` or uncited — source).

## Output shape

```json
{
  "school_id": "umich",
  "ipeds_id": "170976",
  "school_name": "University of Michigan-Ann Arbor",
  "state": "MI",
  "needs_colors": true,
  "current_confidence": null,
  "ncaa_division": "I",
  "wikipedia_nickname_key": "Michigan Wolverines",
  "wikipedia_hexes": ["#00274C", "#FFCB05"],
  "wikipedia_cite_tier": "edu",
  "wikipedia_cite_url": "https://example.edu/brand/colors",
  "wikipedia_cite_raw": "{{cite web |title=... |url=... }}",
  "match_score": 1.0
}
```

`wikipedia_cite_tier` is `edu` (cites a `.edu` domain directly), `other`
(cites a non-`trucolor.net` source — often an official athletics-hosted PDF
on S3/CDN, still usually legitimate but worth a closer look), `trucolor`
(cites trucolor.net, an unofficial hobbyist color-archive site — excluded
from `_usable`), or `none` (uncited — excluded from `_usable`).

`match_score` reflects how cleanly the school name matched during the join,
not brand-color confidence — ignore it once a row is independently
verified.

## What to do with the output — verification is not optional

For each candidate: open `wikipedia_cite_url`, confirm the hex(es) are
**explicitly printed as text** on that page (or in that PDF — use
`pdftotext`, and if a page renders swatches as an image with no extractable
text, render it and read the pixels' printed labels, don't eyedrop the
fill color). Wikipedia's transcription can be stale, slightly wrong, or
occasionally pulled from the wrong section of a multi-school PDF. In
practice, verifying ~800 candidates from this queue caught real citation
errors on the order of a third to half the time — dead links needing a
fresh search, hexes that turned out to belong to a *different* school
sharing the same PDF (a conference style guide, a shared CMS template), or
"secondary/accent" colors that Wikipedia had mislabeled as primary. Treat
every row as a lead, not an answer.

## Known limitations

- **NCAA-athletics-only.** Coverage skews to D1/D2/D3 schools; two-year and
  non-athletic colleges never appear in Wikipedia's color module and need
  scouting from scratch.
- **Multi-campus university systems are deliberately left unmatched**
  rather than guessed. If an official name ties equally between several
  IPEDS branch-campus rows with no unique "-Main Campus" designation to
  break the tie, the matcher refuses rather than picking one. See
  `match_official_to_directory()`'s docstring for the exact tie-break rule.
- The matcher was iteratively hardened against real false positives found
  while running it across ~800 schools — see the docstrings in
  `build_crosswalk.py` for the specific cases (Cincinnati main-vs-branch
  campus, Arizona vs. Arizona State, Central Michigan vs. Michigan, Siena
  vs. NYU, Columbia University vs. Columbia-Greene Community College, Penn
  State main vs. branch campuses). It's not guaranteed bug-free for cases
  not yet seen — spot-check a sample of any new run before trusting it
  wholesale, the same way you'd spot-check the Wikipedia citations
  themselves.

## License note

Wikipedia content is CC BY-SA 4.0. This script only reads and transforms
that content locally to build a work queue; it doesn't redistribute the
source data. If you publish the *output* candidate queue (not just use it
internally), attribute Wikipedia per CC BY-SA.
