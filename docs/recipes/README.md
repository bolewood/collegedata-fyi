# Recipes

Worked examples that show what you can do with the CDS data in this repo. Each recipe pairs a short write-up (Markdown, in this directory) with a reproducible artifact — an interactive HTML visualization, an XLSX template, or a Jupyter notebook, living in [`web/public/recipes/`](../../web/public/recipes/) and served at [collegedata.fyi/recipes](https://collegedata.fyi/recipes). Each recipe is seeded with hand-verified data and designed to be extended with live API results.

## Conventions

- **One topic per recipe.** Each recipe answers a single analytical question.
- **Honest data provenance.** Seed data must be verifiable — either from the hand-audited ground-truth fixtures in [`../../tools/extraction-validator/ground_truth/`](../../tools/extraction-validator/ground_truth/) or from the live API. Sources are cited inline.
- **Extend via the API.** Every recipe ships with copy-pasteable API queries that populate the full dataset, so readers can take the seed and scale it.
- **Coverage caveats in plain sight.** If a recipe relies on a section whose corpus-wide coverage is partial (see [`../extraction-quality.md`](../extraction-quality.md)), the recipe says so.

## Current recipes

- [**Acceptance rate vs yield**](./acceptance-vs-yield.md) — scatter plot showing the gap between how selective a school looks on paper (acceptance rate) and how selective it actually is in practice (yield). Seeded with 18 hand-audited schools across a range of selectivity tiers. Extends to 697 via the API. Artifacts: [`acceptance-vs-yield-demo.html`](../../web/public/recipes/acceptance-vs-yield-demo.html), [`acceptance-vs-yield-starter.xlsx`](../../web/public/recipes/acceptance-vs-yield-starter.xlsx).
- [**Test-optional tracker**](./test-optional-tracker.md) — line chart of SAT submission percentage over time for seven well-documented schools (Yale 2009–2024, Caltech 2002–2020, MIT, Princeton, Stanford, Harvard, Wake Forest). Uses the submission rate as an honest proxy for effective test-optional policy: written disclosures lie, enrollment numbers don't. Artifact: [`test-optional-tracker-demo.html`](../../web/public/recipes/test-optional-tracker-demo.html).

## Ideas for future recipes

- **Net-price-by-income-bracket.** H2A and H4 broken down by income band — the single most-asked and least-answered question in college search.
- **Realistic/reach/safety calibration.** Given a student's stats, which schools in their target list are historically realistic, reach, and safety based on the published C9 and C11 distributions.
- **Recruited athlete × program strength.** Schools that sponsor a given sport (Section F) crossed with strength in a specific academic program (Section J CIP codes).
- **Has this school changed?** Longitudinal view of any school's admissions selectivity, yield, and aid generosity over 5+ years.
- **API starter kit.** The fifteen most useful `curl` queries for developers building on top of the corpus.
- **Audit your own school's extraction.** An IR-staff-facing recipe showing how to pull their own school's current extracted values, compare against their source PDF, and flag errors.

## Contributing a recipe

Recipes are welcome as PRs. Aim for 300-600 words of write-up, a single reproducible artifact, and honest provenance for every number. See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) for general contribution guidelines.
