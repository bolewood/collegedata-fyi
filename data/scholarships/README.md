# Named scholarship directory (PRD 036)

Hand-reviewed records of named, institution-tied merit scholarship programs,
one YAML file per program, with one version per entering class
([PRD 036](../../docs/prd/036-named-scholarship-directory.md)). Every
important fact traces to an official page of the school or of a foundation
the school ties to the program.

This directory holds the record format, the validator inputs and, later, the
records. The M1 milestone ships the format only; `programs/` is empty until
the first batch is reviewed.

## Licensing: read before contributing

**This directory is CC BY-SA 4.0, not MIT.** See [`LICENSE`](LICENSE). The
code that reads these files stays MIT like the rest of the repo. The content
here is authored compilation and writing, so it carries its own license:
reuse needs attribution and share-alike. The LICENSE lists what it does not
cover (the schools' own pages, trademarks, quoted excerpts, source PDFs).

**Contribution gate:** outside contributions to this directory are not
accepted without a signed contribution agreement. This is the same gate as
[`data/discovery/`](../discovery/README.md) and keeps the maintainer able to
relicense the content later. Code contributions elsewhere in the repo are
unaffected. To report a wrong term without contributing, open an issue with
the official URL.

## How to credit this data

Use this string, unchanged, wherever the data or a summary of it appears:

> Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record.

Examples:

- App or website: put the string in the footer of the page that shows the data, with the link live.
- Article: add it as a source line under the table or chart.
- Spreadsheet: put the string in the first row of the sheet and keep the source link column.

If you change the data, say so ("adapted from ..."), and release your
version under CC BY-SA 4.0.

## Layout

- `programs/<school_id>/<program_id>.yaml`: one file per program. `school_id`
  is the canonical slug from `tools/finder/schools.yaml`. The directory name
  and file name must match the record.
- `schema/program.schema.json`: the JSON Schema (draft 2020-12).
- `schema/FIELDS.md`: every field path, type and allowed value. Treat the
  names as a contract; loaders and the site read them.
- `foundation_domains.yaml`: foundation domains allowed as official sources,
  per school.

Validate with:

```
python tools/scholarships/validate.py data/scholarships/programs --base origin/main
```

## Sourcing rules

1. The school's own page is the authority. Third-party directories are leads
   and are never copied.
2. A program run by a foundation the school ties to it (Jefferson Scholars at
   UVA, Morehead-Cain at UNC, Robertson at Duke and UNC) uses the
   foundation's official page. Set `awarding_authority: affiliated_foundation`
   and mark the source `foundation_official`. The domain must be listed in
   `foundation_domains.yaml`, and a school page naming the foundation should
   back the listing.
3. Every source URL must be on the school's domain (from `schools.yaml` or
   the IPEDS identity snapshot) or an allowlisted foundation domain.
4. Every version names its entering class. If the class is unclear, set
   `entry_year: null` with an `entry_year_label` that says so, and use
   recurring month/day milestones, never a guessed year.
5. Unknown is not no. Leave a field `null` or `unknown` rather than guessing.
   If the school says nothing, record `value_status: not_published`. If the
   school contradicts itself, record two `conflicting` evidence entries with
   `reported_value` and leave the field itself `null`.
6. Being considered is not winning. Use `selection_mode: automatic_guaranteed`
   only when the school makes an explicit promise, and quote it in
   `short_excerpt`.
7. No made-up totals. Never add components or multiply an annual amount. A
   `period: total_program` amount must be quoted by the school.
8. A waiver is not a scholarship. Use `instrument: tuition_waiver`, and do not
   count it as tuition coverage.
9. There is no "full ride" value. Describe coverage with typed components and
   `normalized_coverage`; keep the school's own words in
   `advertised_coverage_label`.
10. Excerpts are 25 words or fewer.
11. Published versions are immutable. Once a version is `verified` and merged,
    it cannot change. A correction is a new version with `supersedes`.

## Field guide

The structure is a program with a list of `versions`. Each version holds
`offers` (resident, nonresident or tier variants; a tier nests under another
with `parent_offer_id`), each offer holds `eligibility` and `benefits`, and
the version holds `application`, `renewal_rules`, `stacking_rules`,
`award_counts`, `sources` and `field_evidence`. See
[`schema/FIELDS.md`](schema/FIELDS.md) for every field.

Fields that need `field_evidence` before they can carry a value: an offer's
`selection_mode`, `eligibility.national_merit_statuses`, each benefit's
`amount`, `application.separate_application` and each milestone.
`field_path` is a slash path inside the version, such as
`offers/0/benefits/1/amount`; evidence on a parent path covers its children.

Application cycle: for entry year Y, dated milestones must fall between
1 July of Y-1 and 31 August of Y. Recurring milestones have no year and are
exempt.

Review state: `verification_status` is an internal status and does not appear
in product copy. A `verified` version needs `last_reviewed_at`, `reviewed_by`
and an `entry_year` or an explicit label.
