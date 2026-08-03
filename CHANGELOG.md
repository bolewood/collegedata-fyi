# Changelog

All notable changes to this project will be documented in this file.

This project uses four-part semantic versioning.

## [0.2.1.0] - 2026-08-03

### Changed

- Read the endowment draw-rate recipe in plainer language, with clearer descriptions of coverage, thresholds, school comparisons, and the federal accounting check.

## [0.2.0.0] - 2026-08-03

### Added

- Explore five years of private nonprofit college endowment draw rates at `/recipes/endowment-draw-rate`, including sector distributions, threshold shares, and selection-neutral school histories.
- Rebuild the versioned recipe dataset from public IPEDS Finance Part H facts with a read-only, paginated generator and documented source-release provenance.

### Changed

- Expand the recipes index and methodology documentation to cover reproducible federal-data analyses alongside CDS recipes.

### Fixed

- Calculate percentile and strict threshold statistics from exact values before display rounding, keep documentation tied to the generated dataset version, and display each institution under its latest reported identity.

## [0.1.0.0] - 2026-08-03

### Added

- Load and analyze IPEDS endowment values, gifts, investment returns, spending distributions, and other changes from official Finance releases.
- Request endowment facts from the per-school public API with the `finance` category.

### Changed

- Resolve Finance table names by fiscal year and preserve manifest-declared release provenance throughout downloads, analysis, and loads.
- Make release reruns revision-safe by rejecting downgrades and rollbacks, pruning stale rows and facts, and superseding older public facts.

### Fixed

- Route revised-final Finance data through the official Access database, reject zero-fact endowment runs, and prevent stale sibling artifacts from being loaded.
- Bound and stream Access archive downloads, and reject unsupported Finance comparison filters instead of returning unrelated default columns.
