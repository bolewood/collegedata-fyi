# Data license

**Effective date:** 2026-11-23

The structured data that collegedata.fyi authors is licensed under the
[Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
The code in this repository stays under the MIT license in [`LICENSE`](LICENSE).

Copyright © 2026 Anthony S. and Bolewood Group, LLC.

## What this license covers

- The structured Common Data Set extracts we produce, as a compilation: the
  values we read out of each school's document, normalized and keyed to
  canonical field IDs, as served on the site, the API, the MCP server, the CLI,
  spreadsheets and snapshots.
- Field documentation and methodology notes we wrote.
- Definitions of derived metrics we wrote (for example how an acceptance or
  yield rate is computed).

## What it does not cover

- **The schools' Common Data Set documents** (PDF, XLSX, DOCX, HTML), including
  the archived copies. They belong to the schools that published them.
- **CDS Initiative template material**, including the field labels and
  definitions in [`schemas/`](schemas/) that come from the CDS template, and
  [`schemas/templates/`](schemas/templates/).
- **Federal data**: NCES/IPEDS, College Scorecard and FSA figures. Keep the
  source credit each fact carries.
- **School names, trademarks and logos**, and the project's own name and logo.
- **Content that already has its own license**, which is unchanged:
  - [`data/discovery/`](data/discovery/LICENSE) and
    [`data/scholarships/`](data/scholarships/LICENSE): CC BY-SA 4.0.
  - [`web/src/data/community/`](web/src/data/community/README.md) project
    write-ups: CC BY-SA 4.0.
  - Usage statistics at `/usage.json`: CC0 1.0.
  - Code: MIT.

## Facts are not owned

Individual facts, such as a school's number of applicants, are not protected by
U.S. copyright, and nobody needs our permission to state them. This license
applies to our compilation and our writing, not to each fact. We use it so that
people who reuse the dataset know how to credit it, and so research, journalism
and software that build on it can point back to the source. CC BY 4.0 allows
any use, including commercial use, as long as you give credit.

## How to credit

CC BY 4.0 asks for three things: credit, a link to the license, and a note if
you changed the data. Use this line:

  Common Data Set extracts from collegedata.fyi (https://www.collegedata.fyi), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Figures as published in each school's Common Data Set.

If you changed, filtered or recomputed the data, say so (for example "adapted
from…"). Where it's practical, please also link the school's page,
`https://www.collegedata.fyi/schools/<school_id>`. That link is a request, not
a condition, and `nofollow` is fine.

API responses, snapshot manifests and the MCP payloads carry the same line in
a nested `data_license` block (`applies_to`, `license`, `license_url`, `scope`,
`attribution`). The block applies to the CDS extracts in the payload, not to the
federal facts next to them.

CSV downloads send it as an HTTP `Link: <…>; rel="license"` header, so the file
itself stays a clean table.

## Earlier releases

Before the effective date, the derived dataset was published under the MIT
license. Anything you obtained under MIT, including from this repository's git
history, stays usable under MIT. This license applies to data published from
the effective date on.

Dated snapshot URLs (`/snapshots/v1/<date>/…`) currently serve live data, not
frozen copies, so a snapshot's date doesn't show which license a file was
released under. Use the effective date above.
