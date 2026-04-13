# ADR 0003: MIT license for the repository

**Date:** 2026-04-11
**Status:** Accepted

## Context

Open-source license choice for a small Python/TypeScript data pipeline project intended to attract community contributors and downstream consumers. Candidates considered: MIT, Apache-2.0, BSD-3-Clause.

## Decision

Use the MIT License.

## Why

MIT is the most permissive mainstream license, is one paragraph long, and is what contributors and downstream users expect for a small open-source data/tooling project. It maximizes compatibility with everything else — any future cleanup tool, research notebook, or commercial product built on top of this data can use it without thinking about license compatibility.

Apache-2.0 was the main alternative. Its advantages (explicit patent grants, NOTICE file requirement, trademark clause) are real but don't matter for this project: there are no novel algorithms that need patent protection, the code is a thin glue pipeline over public data, and the NOTICE discipline adds friction contributors don't need at week one.

## Trade-offs accepted

- No explicit patent retaliation clause. Acceptable because the threat model doesn't include large corporations weaponizing patents against forks of a thin data pipeline.
- No explicit contributor grant beyond what MIT implies. Acceptable for V1; a CLA can be added later if the project scales to a point where it matters.
