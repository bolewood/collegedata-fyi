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
python tools/scholarships/validate.py data/scholarships/programs --merge-base origin/main
```

## What belongs here: the size floor

The directory lists large awards only. A program qualifies when the school's
own page shows that its top tier meets one of these:

1. At least $10,000 per academic year, or an advertised program total of at
   least $40,000 over four years.
2. Full tuition or more, whatever the dollar value.
3. A waiver of the nonresident tuition differential attached to the award
   (out-of-state tier only). Record it as a waiver, per sourcing rule 8.

Rule 2 is read broadly: a program the school calls full tuition, a full ride
or total cost of attendance qualifies even when the wording is hedged ("valued
up to"), the value is stated for a group of scholarships, or a component is
capped or unpublished. Keep the school's exact wording, and leave coverage
`partial` or `unknown` where the page does not promise the charge in full.

Test the top tier only, then record every tier of a qualifying program. Never
add components or multiply an amount to reach the floor. Do not submit a
program whose value the school does not publish. Reviewers check the floor;
the validator does not.

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
11. Published versions are immutable. Once a version other than `unverified`
    is merged, it cannot change. A correction is a new version with
    `supersedes`. A key that is absent in the published version and null in the
    new one is not counted as a change, so optional fields can be added later.

## Field guide

Every file starts with `schema_version: 1`. The structure is a program with a
list of `versions`. Each version holds `offers` (resident, out-of-state or tier
variants; a tier nests under another with `parent_offer_id`), each offer holds
`eligibility` and `benefits`, and the version holds `application`,
`renewal_rules`, `stacking_rules`, `award_counts`, `sources` and
`field_evidence`. See [`schema/FIELDS.md`](schema/FIELDS.md) for every field.

- **Joint programs** (Robertson at Duke and UNC) are one file under the first
  participant's directory, with `participating_schools` listing every school.
  Each participant's domain is an allowed source domain.
- **Not documented vs none.** `benefits`, `exclusions`, `test_rules`,
  `renewal_rules` and `stacking_rules` are null when you did not find the
  terms, and `[]` only when the school says there are none. An empty
  `stacking_rules` needs evidence.
- **Renewal** is a list of rules; each `applies_to` names offers or benefits,
  and an empty `applies_to` covers the whole version.
- **Status.** `status` is the program's current summary.
  `program_status_for_entry` is the status for that entering class and needs
  evidence unless it is `active` or `unknown`. Evidence for program-level
  fields uses a leading slash: `/awarding_authority`, `/related_programs/0`.
- **No coverage label in YAML.** The loader derives `full tuition` and similar
  labels from the typed benefits. A waiver of the out-of-state differential is
  `category: nonresident_differential`, `instrument: tuition_waiver`.
- **Check dates and the monitor's needs-review flag are not in these files.**
  They live in the database. `last_reviewed_at`, `reviewed_by` and
  `owner_spot_checked` stay.
- **Application.** Use milestone kind `admission_deadline` for the admission
  plan date and `application_deadline` for the scholarship's own. Record lead
  times in `application.prerequisites` (`minimum_lead_days`), the required
  admission plan in `admission_plan_requirement`, and anything else in `notes`.
- **Amounts.** `exact`, `up_to`, `at_least` and `approximate` carry `value`;
  `range` carries `min` and `max` with `min < max`; `not_published` carries
  no numbers.
- **Quoted totals.** A package total the school itself advertises (for example
  "more than $89,000 per year") goes in the offer's `advertised_totals` with its
  `scope_text`; `period` may be null. It needs `reported` evidence on the exact
  path with an excerpt. This is the only place a total may live. A promise of
  full cost of attendance with no components is a benefit with
  `category: cost_of_attendance`.
- **Conditions and wording.** `conditions_text` on a benefit records what it
  depends on (it needs evidence on that path). `citizenship_text` keeps the
  school's own citizenship wording, 40 words or fewer. Use
  `separate_application: no_form_other_steps_required` when a school asks for a
  visit, interview or recommendations but has no scholarship form.
  `awarding_authority: state_program` is for a state program run through the
  school. `interview_mode: mixed` covers a virtual first round with in-person
  finals. `status_required_for_award: scholar` is a Finalist who receives a
  National Merit award. Renewal rules take `credit_load_min_per_year` and
  prerequisites take `maximum_lead_days`.
- **Counts.** `award_counts[].metric` is the unit (`offers`, `new_recipients`,
  `share_of_class`), `claim` says `target` or `actual`, and a share needs a
  `denominator`.
- **Recognition.** `national_merit_statuses` also takes `commended` and the
  `nrp_*` recognition programs; `status_required_for_award` records the status
  a student must hold to receive the award when it differs from the one that
  lets them apply.

Evidence rules. `field_path` is a slash path inside the version, such as
`offers/0/benefits/1/amount`. A stated value (an offer's `selection_mode`,
`eligibility.national_merit_statuses`, a benefit `amount`,
`application.separate_application`, a milestone) needs `reported` evidence on
its own path or its direct parent. `not_published` evidence never supports a
value. `automatic_guaranteed` and `total_program` amounts need `reported`
evidence on the exact path with a `short_excerpt` of the school's words (and
`reported_value: automatic_guaranteed` for the former). When a school
contradicts itself, leave the field null and add two or more `conflicting`
entries with `reported_value`.

Dates. For entry year Y, dated milestones fall between 1 July of Y-1 and
31 August of Y. Recurring milestones have no year and are exempt. If the entry
year is genuinely unclear, set `entry_year: null` with an `entry_year_label`
and `conflicting` or `not_published` evidence on `entry_year`; dated
milestones are then kept as published and the window is skipped. A milestone
whose date is in conflict may have both `date` and `recurring` null if it has
`conflicting` evidence.

Corrections. A correction is a new version in the same `entry_year` with
`supersedes` pointing at the version it replaces. A new cycle is a new version
with no `supersedes`. `supersedes` never crosses entry years, and each year has
one unsuperseded version.

Review state. `verification_status` is `verified`, `conflicting`,
`historical_only` or `unverified`, and does not appear in product copy. A
`verified` version needs `last_reviewed_at`, `reviewed_by` and an `entry_year`
or an explicit label.
