# Recipes

Worked examples that show what you can do with the CDS and federal data in this repo. Each recipe pairs a short write-up (Markdown, in this directory) with a reproducible artifact — an interactive route, an XLSX template, or a checked-in generated dataset — served from [collegedata.fyi/recipes](https://collegedata.fyi/recipes). Recipe inputs are reviewable and designed to be reproduced or extended through the public API.

## Conventions

- **One topic per recipe.** Each recipe answers a single analytical question.
- **Honest data provenance.** Seed data must be verifiable — either from the hand-audited ground-truth fixtures in [`../../tools/extraction-validator/ground_truth/`](../../tools/extraction-validator/ground_truth/) or from the live API. Sources are cited inline.
- **Extend via the API.** Every recipe ships with copy-pasteable API queries that populate the full dataset, so readers can take the seed and scale it.
- **Coverage caveats in plain sight.** If a recipe relies on a section whose corpus-wide coverage is partial (see [`../extraction-quality.md`](../extraction-quality.md)), the recipe says so.

## Current recipes

- [**Acceptance rate vs yield**](./acceptance-vs-yield.md) — scatter plot showing the gap between how selective a school looks on paper (acceptance rate) and how selective it actually is in practice (yield). Seeded with 18 schools: three hand-checked anchors plus fifteen public-API rows. Extends through the live `school_browser_rows` / `cds_fields` API substrate. Artifacts: [`acceptance-vs-yield-demo.html`](../../web/public/recipes/acceptance-vs-yield-demo.html), [`acceptance-vs-yield-starter.xlsx`](../../web/public/recipes/acceptance-vs-yield-starter.xlsx).
- [**Test-optional tracker**](./test-optional-tracker.md) — line chart of SAT submission percentage over time for seven well-documented schools (Yale 2009–2024, Caltech 2002–2020, MIT, Princeton, Stanford, Harvard, Wake Forest). Uses the submission rate as an honest proxy for effective test-optional policy: C8 states the rule; C9 counts what enrolled first-years did. Artifact: [`test-optional-tracker-demo.html`](../../web/public/recipes/test-optional-tracker-demo.html).
- [**Wait-list odds**](./waitlist-odds.md) — corpus-wide CDS C2 analysis of wait-list offers, accepted spots, and admitted students, bucketed by C1 selectivity and by federal control, size, and Carnegie class. Inspired by the May 2026 WSJ wait-list story; the numbers are from the filings, not the article.
- [**Endowment draw-rate tracker**](./endowment-draw-rate.md) — FY2020–FY2024 distribution and per-school history for private nonprofit IPEDS Finance Part H reporters. Uses a paginated public-API generator and a versioned checked-in dataset; FY2024 is provisional.
- **Agent/CLI starter.** Use the no-auth friendly API to search schools, fetch facts with citations, compare a short list, and list source documents:
  `curl 'https://www.collegedata.fyi/api/schools/mit/facts?categories=admissions,cost,outcomes'`.

## Ideas for future recipes

- **Net-price-by-income-bracket.** H2A and H4 broken down by income band — the single most-asked and least-answered question in college search.
- **Realistic/reach/safety calibration.** Given a student's stats, which schools in their target list are historically realistic, reach, and safety based on the published C9 and C11 distributions.
- **Recruited athlete × program strength.** Schools that sponsor a given sport (Section F) crossed with strength in a specific academic program (Section J CIP codes).
- **Has this school changed?** Longitudinal view of any school's admissions selectivity, yield, and aid generosity over 5+ years.
- **API starter kit.** The fifteen most useful `curl` queries for developers building on top of the corpus.
- **Audit your school’s numbers.** Pull your school’s values from the public API, compare them against the source PDF, and flag discrepancies.

## Contributing a recipe

Recipes are welcome as PRs. Aim for 300-600 words of write-up, a single reproducible artifact, and honest provenance for every number. See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) for general contribution guidelines.
