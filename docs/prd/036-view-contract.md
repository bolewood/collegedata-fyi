# PRD 036: `scholarship_directory` view contract

The contract the web work (PRD 036 M3) builds against. Source of truth for
column names is the newest `supabase/migrations/*_scholarship_directory*.sql`
(currently `20261118120000_scholarship_directory_other_info.sql`);
`tools/scholarships/test_load.py` fails if this file's column list, the example
row or the attribution string drift from it.

Status: live. The view is applied in production and filled by
`tools/scholarships/load.py --apply`, which the `scholarships-load.yml` workflow
runs on every merge to `main`. It holds only the programs that have been merged
under `data/scholarships/programs/`.

## What a row is

- Endpoint: `GET https://api.collegedata.fyi/rest/v1/scholarship_directory` (PostgREST,
  anon key, no account). `Accept: application/vnd.pgrst.object+json` for one row.
- One row per **program per participating school**. A joint program (Robertson at
  Duke and UNC) appears once for each participating school, with the same
  `program_id` and `version_id`; `school_id` is the school this row belongs to
  and `participating_school_ids` lists all of them, lead school first. The
  primary key is `(program_id, school_id)`.
- Per program, the row is one version: the **latest** among the published ones.
  A version is published when it is the newest member of its `supersedes` chain
  that is not `unverified`, so an unverified correction leaves the verified
  version it corrects in place, and `unverified` versions never appear. "Latest"
  ranks by `entry_year`; a version with no `entry_year` ranks by the entry year of
  the cycle its `cycle_through_date` falls in (else of its `source_retrieved_at`),
  and a version with an `entry_year` wins a tie.
- A school with no rows has no documented programs yet. That is "No named
  programs documented yet", not "this school has none".
- `freshness_status` and `current_entry_year` are computed when the row is read.
  Everything else comes from a cache refreshed after each load and after the
  change monitor writes (it is not refreshed by the clock).
- Exposed with the row: sources (`url`, `authority`, `retrieved_at`) and evidence
  locators (`evidence`: which source and where on it supports which field), and
  `other_info` entries (text, source reference and source URL).
  Never exposed: evidence excerpts (`short_excerpt`), `content_sha256`, the
  monitor's `detail`, and the verbatim `record`.

## Columns

Types are Postgres types; PostgREST returns arrays as JSON arrays, `date` as
`YYYY-MM-DD` strings, `timestamptz` as ISO 8601 strings, `jsonb` as JSON.
"Null" means the key is present with `null`. Unknown is never false: a null or
`unknown` value means the school did not say, not "no".

| Column | Type | Null | Notes |
|---|---|---|---|
| `program_id` | text | no | Stable slug. |
| `school_id` | text | no | `schools.yaml` slug of this row's school. |
| `ipeds_id` | text | no | Six-digit IPEDS UNITID of this row's school. |
| `participating_school_ids` | text[] | no | All participating schools, lead first. One element for a single-school program. |
| `official_name` | text | no | |
| `aliases` | text[] | no | May be empty. |
| `program_family` | text | no | `stamps`, `national_merit`, `presidential`, `honors`, `other` |
| `awarding_authority` | text | no | `institution`, `affiliated_foundation`, `cofunded`, `state_program`, `unknown`. For `affiliated_foundation` the sources are the foundation's pages; say so. |
| `program_status` | text | no | Program-level summary: `active`, `paused`, `closed_to_new_entrants`, `merged`, `discontinued`, `unknown`. |
| `applicable_campuses` | text[] | no | Empty means not campus-specific. |
| `related_programs` | jsonb | no | `[{program_id, relation}]`, relation: `component_of`, `includes`, `replaces`, `mutually_exclusive_with`, `successor_to`. The target may have no row yet. |
| `version_id` | text | no | Unique within a program only. |
| `entry_year` | integer | yes | Entering class (fall 2027 is 2027). Null when the school's cycle is unclear; then use `entry_year_label`. |
| `entry_year_label` | text | yes | The school's own wording when `entry_year` is null. |
| `entry_terms` | text[] | no | Elements: `fall`, `spring`, `summer`, `unspecified`. |
| `source_cohort_text` | text | yes | The school's own cohort wording. |
| `verification_status` | text | no | `verified`, `conflicting`, `historical_only`. (`unverified` is never served.) Internal: VOICE.md forbids saying "verified" in product copy. |
| `freshness_status` | text | no | `current_cycle_verified`, `year_not_stated`, `current_cycle_unconfirmed`, `past_cycle`, `conflicting`. Rule below. |
| `cycle_basis` | text | no | What the cycle rests on: `entry_year` (the version states its class), `milestone_dates` (no `entry_year`, but dated milestones), `none` (neither). Most official pages give deadlines only, so expect `milestone_dates`. |
| `cycle_through_date` | date | yes | The latest dated milestone of any kind; the date the cycle is known to run through. Null if no milestone is dated. |
| `current_entry_year` | integer | no | The entry year `freshness_status` was computed against. |
| `last_reviewed_at` | date | yes | |
| `reviewed_by` | text | yes | |
| `owner_spot_checked` | boolean | yes | |
| `program_status_for_entry` | text | yes | Status for this entering class; same values as `program_status`. |
| `coverages` | text[] | no | Distinct `normalized_coverage` across the version's offers. Filter column. |
| `selection_modes` | text[] | no | Distinct offer `selection_mode`: `automatic_guaranteed`, `competitive`, `hybrid`, `unknown`. |
| `residencies` | text[] | no | Distinct offer `residency`: `in_state`, `out_of_state`, `international`, `any`, `unknown`. |
| `national_merit_statuses` | text[] | no | Union over offers: `semifinalist`, `finalist`, `commended`, `nrp_hispanic`, `nrp_african_american`, `nrp_indigenous`. |
| `statuses_required` | text[] | no | Union over offers of `status_required_for_award`: the same values plus `scholar`. |
| `need_roles` | text[] | no | Distinct offer `need_role`: `required`, `considered`, `not_considered`, `top_up_only`, `unknown`. |
| `separate_application` | text | yes | `required`, `encouraged`, `not_required`, `invitation_only`, `no_form_other_steps_required` (other steps such as a visit or interview, but no scholarship form), `unknown`; null when the version has no `application` block. |
| `deadline_months` | integer[] | no | Months (1 to 12) of required or priority deadlines, dated or recurring. Filter column. |
| `key_deadline` | date | yes | Earliest dated required deadline, else earliest dated priority one. Null if none is dated (recurring deadlines are in `application`). Always label it with `entry_year`. |
| `source_retrieved_at` | date | yes | Newest `retrieved_at` among the version's sources: "as published on the school's page <date>". |
| `offers` | jsonb | no | Array of offers as in `data/scholarships/schema/FIELDS.md` (`versions[].offers[]`), each with one extra key, `normalized_coverage`. `advertised_totals` (the school's own quoted package totals, with scope) is passed through; it never feeds `normalized_coverage`. A benefit with `conditions_text` depends on something else; show the condition. |
| `application` | jsonb | yes | `versions[].application`: `separate_application`, `milestones[]`, `prerequisites[]`, `interview_mode` (`none`, `in_person`, `virtual`, `either`, `mixed`, `unknown`), `notes`. |
| `renewal_rules` | jsonb | yes | Array; null means not documented, `[]` means documented as none. |
| `stacking_rules` | jsonb | yes | Same null versus `[]` meaning. |
| `award_counts` | jsonb | no | Array; `metric` is the unit, `claim` is `target` or `actual`. Never present these as odds. |
| `sources` | jsonb | no | `[{source_id, url, authority, retrieved_at, archive_url}]`. Link the official source one click away. |
| `evidence` | jsonb | no | `[{field_path, source_ref, locator, value_status}]`: where on which source (`source_ref` is a `sources[].source_id`) each field comes from. `field_path` is relative to the version (`offers/0/benefits/1/amount`); a leading `/` addresses the program. No excerpts. |
| `other_info` | jsonb | no | `[{text, source_ref, source_url}]`: sourced facts the typed fields cannot hold, each one plain sentence in the school's terms (40 words or fewer), with the source's URL so no join is needed. `[]` when none are recorded. Display only: it never feeds `coverages`, `freshness_status`, a filter or a count, and it is never a substitute for a typed field. The quoted excerpt behind each entry is not exposed. |
| `last_check_at` | timestamptz | yes | Latest monitor check of this version; null until the monitor (M4) has run. |
| `last_check_result` | text | yes | Result of that check: `unchanged`, `changed`, `stale_signal`, `unreachable`, `conflicting`. |
| `needs_review` | boolean | yes | Latest check flagged a change for review. Null when never checked. |
| `license` | text | no | Always `CC-BY-SA-4.0`. |
| `attribution` | text | no | The canonical credit string. Clients that copy rows must display it. |

### `normalized_coverage` (inside each `offers[]` element)

Derived by the loader per offer; it is not in the YAML. Null when the offer's
own `benefits` are not documented. An offer is derived from its own benefits
plus those of all its ancestors (`parent_offer_id`), because a tier lists only
what it adds.

A benefit counts toward a `full_*` value only when it has `coverage: full`, an
instrument of `scholarship` or `restricted_fund`, no `conditions_text`, and an
amount that is absent, `exact` or `not_published` (a capped or approximate
"full" does not count).

| Value | Meaning |
|---|---|
| `full_tuition` | Full tuition. |
| `full_tuition_fees` | Full tuition and full mandatory fees. |
| `tuition_housing_meals` | Full tuition, housing and meals (fees optional). |
| `full_school_coa` | A full `cost_of_attendance` scholarship benefit; or full tuition, fees, housing, meals and books plus a stipend of stated size. Display copy should still use the school's own label, not "full ride". |
| `partial_or_fixed` | No `full_*` value, but a partial, fixed-amount or variable benefit, or a `full` benefit that is capped, conditional or short of a bracket. |
| `other` | Anything else, including coverage the school did not state. |

A waiver of tuition itself (`category: tuition`, `instrument: tuition_waiver`)
counts like a scholarship: full, unconditional and uncapped it fills the tuition
slot, and otherwise it counts as a partial benefit. A `tuition_waiver` on any
other category, and a `nonresident_differential` benefit under any instrument,
never counts toward any value above. There is no
"full ride" value; derive any display label from the components.

### `freshness_status` rule

Entry cycle: a class entering in fall Y becomes the current cycle on 1 July of
Y-1, UTC. `current_entry_year` is `year + 1` from July through December and
`year` from January through June (2027 on 2026-11-14). `cycle_basis` says what
the cycle rests on. First match wins:

1. `conflicting`: `verification_status` is `conflicting`, or the latest check's
   result is `conflicting`.
2. `past_cycle`: `verification_status` is `historical_only`; or `cycle_basis` is
   `entry_year` and `entry_year` is below `current_entry_year`; or `cycle_basis`
   is `milestone_dates` and `cycle_through_date` is before today.
3. `past_cycle` (aging): `verification_status` is `verified`, the latest check
   has no `needs_review`, `cycle_basis` is `none`, and the first 1 July after
   `last_reviewed_at` has passed (on or before today).
4. `current_cycle_unconfirmed`: the latest check has `needs_review` true, or the
   status is anything other than `verified`.
5. `year_not_stated`: verified, no `needs_review`, `cycle_basis` is `none` (no
   `entry_year` and no dated milestone), and not yet aged out by rule 3. The
   terms are checked; the school just names no class or date. A recurring
   month/day milestone never dates a cycle.
6. `current_cycle_verified`: everything else: verified, nothing flagged, and
   either `entry_year` at or after `current_entry_year`, or (no `entry_year`)
   `cycle_through_date` today or later.

An explicit `entry_year` is never overridden by milestone dates. UI:
`past_cycle` and `conflicting` get the amber note; never roll last year's dates
forward. With `cycle_basis` `milestone_dates` do not print an entry year; say
"deadlines through <cycle_through_date>". For `year_not_stated` say the school
does not state a year and show `last_reviewed_at`; do not print a class.

## Filtering and sorting (PostgREST)

```
/rest/v1/scholarship_directory?school_id=eq.tulsa
/rest/v1/scholarship_directory?coverages=cs.{full_tuition}
/rest/v1/scholarship_directory?national_merit_statuses=cs.{finalist}&residencies=ov.{any,out_of_state}
/rest/v1/scholarship_directory?statuses_required=cs.{scholar}&awarding_authority=eq.state_program
/rest/v1/scholarship_directory?separate_application=eq.no_form_other_steps_required&application->>interview_mode=eq.mixed
/rest/v1/scholarship_directory?deadline_months=ov.{11,12}&order=key_deadline.asc.nullslast
/rest/v1/scholarship_directory?select=program_id,official_name,entry_year,freshness_status&freshness_status=eq.current_cycle_verified
```

Sort by deadline, school or coverage, never "best".

## Attribution

Every row carries `license` and `attribution`. The API docs page shows the
string and asks API users to display it; the card footer links to the
methodology page.

> Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record.

## Example row

An invented fixture program (`tools/scholarships/fixtures/valid/uva/`), not real
program data. It shows a full cost-of-attendance offer with an advertised total, a nested tier whose own benefit is a conditional waiver (it takes its parent's coverage), a recurring notification milestone, and the new enum values. Freshness is as of 2026-11-14. `test_load.py` checks it against the loader's output.

```json
{
  "program_id": "fixture-foundation-program",
  "school_id": "uva",
  "ipeds_id": "234076",
  "participating_school_ids": [
    "uva"
  ],
  "official_name": "Fixture Foundation Scholars",
  "aliases": [
    "FFS"
  ],
  "program_family": "other",
  "awarding_authority": "state_program",
  "program_status": "active",
  "applicable_campuses": [],
  "related_programs": [
    {
      "program_id": "fixture-parent-program",
      "relation": "component_of"
    }
  ],
  "version_id": "fixture-foundation-program-2027",
  "entry_year": 2027,
  "entry_year_label": null,
  "entry_terms": [
    "fall"
  ],
  "source_cohort_text": "Terms for the class entering in fall 2027",
  "verification_status": "verified",
  "freshness_status": "current_cycle_verified",
  "cycle_basis": "entry_year",
  "cycle_through_date": "2026-12-01",
  "current_entry_year": 2027,
  "last_reviewed_at": "2026-11-08",
  "reviewed_by": "fixture-agent-run-1",
  "owner_spot_checked": true,
  "program_status_for_entry": "active",
  "coverages": [
    "full_school_coa"
  ],
  "selection_modes": [
    "automatic_guaranteed",
    "competitive"
  ],
  "residencies": [
    "any",
    "out_of_state"
  ],
  "national_merit_statuses": [
    "finalist"
  ],
  "statuses_required": [
    "scholar"
  ],
  "need_roles": [
    "considered",
    "not_considered"
  ],
  "separate_application": "required",
  "deadline_months": [
    12
  ],
  "key_deadline": "2026-12-01",
  "source_retrieved_at": "2026-11-08",
  "offers": [
    {
      "offer_id": "o-main",
      "parent_offer_id": null,
      "variant_name": "Main package",
      "residency": "any",
      "selection_mode": "competitive",
      "consideration_route": "nomination",
      "aid_basis": "merit_and_need",
      "need_role": "considered",
      "funds_limited": null,
      "eligibility": {
        "national_merit_statuses": null,
        "first_choice_required": null,
        "gpa": null,
        "test_rules": [],
        "tests_policy_for_scholarship": "unknown",
        "citizenship_eligible": null,
        "majors_allowed": null,
        "major_change_restrictions": null,
        "honors_requirement": null,
        "first_generation_rule": "unknown",
        "eligibility_notes": null,
        "status_required_for_award": null
      },
      "benefits": [
        {
          "benefit_id": "b-tuition",
          "category": "tuition",
          "instrument": "scholarship",
          "coverage": "full",
          "amount": {
            "qualifier": "not_published",
            "value": null,
            "min": null,
            "max": null,
            "period": null
          },
          "duration_terms": "Eight semesters",
          "exclusions": [],
          "scope_text": null,
          "advertised_coverage_label": "full tuition"
        },
        {
          "benefit_id": "b-stipend",
          "category": "stipend",
          "instrument": "cash_stipend",
          "coverage": "fixed_amount",
          "amount": {
            "qualifier": "exact",
            "value": 5000,
            "min": null,
            "max": null,
            "period": "academic_year"
          },
          "duration_terms": null,
          "exclusions": [],
          "scope_text": null,
          "advertised_coverage_label": null
        },
        {
          "benefit_id": "b-summers",
          "category": "enrichment",
          "instrument": "restricted_fund",
          "coverage": "fixed_amount",
          "amount": {
            "qualifier": "up_to",
            "value": 12000,
            "min": null,
            "max": null,
            "period": "total_program"
          },
          "duration_terms": null,
          "exclusions": [],
          "scope_text": "Funded summer experiences, quoted by the foundation as one total",
          "advertised_coverage_label": null
        },
        {
          "benefit_id": "b-coa",
          "category": "cost_of_attendance",
          "instrument": "scholarship",
          "coverage": "full",
          "amount": {
            "qualifier": "not_published",
            "value": null,
            "min": null,
            "max": null,
            "period": null
          },
          "duration_terms": null,
          "conditions_text": null,
          "exclusions": null,
          "scope_text": "Promised as full cost of attendance; components not listed",
          "advertised_coverage_label": null
        }
      ],
      "advertised_totals": [
        {
          "amount": {
            "qualifier": "at_least",
            "value": 89000,
            "min": null,
            "max": null,
            "period": null
          },
          "scope_text": "Total value of the package per year as the foundation advertises it"
        }
      ],
      "normalized_coverage": "full_school_coa"
    },
    {
      "offer_id": "o-tier",
      "parent_offer_id": "o-main",
      "variant_name": "National Merit tier",
      "residency": "out_of_state",
      "selection_mode": "automatic_guaranteed",
      "consideration_route": "multiple",
      "aid_basis": "merit_only",
      "need_role": "not_considered",
      "funds_limited": false,
      "eligibility": {
        "national_merit_statuses": [
          "finalist"
        ],
        "first_choice_required": true,
        "gpa": null,
        "test_rules": [],
        "tests_policy_for_scholarship": "unknown",
        "citizenship_eligible": [
          "us_citizen",
          "permanent_resident"
        ],
        "majors_allowed": null,
        "major_change_restrictions": null,
        "honors_requirement": null,
        "first_generation_rule": "unknown",
        "eligibility_notes": null,
        "status_required_for_award": "scholar",
        "citizenship_text": "U.S. citizens and permanent residents"
      },
      "benefits": [
        {
          "benefit_id": "b-differential",
          "category": "nonresident_differential",
          "instrument": "tuition_waiver",
          "coverage": "full",
          "amount": {
            "qualifier": "not_published",
            "value": null,
            "min": null,
            "max": null,
            "period": null
          },
          "duration_terms": null,
          "exclusions": null,
          "scope_text": "Waives the out-of-state tuition differential only",
          "advertised_coverage_label": null,
          "conditions_text": "Requires at least $4,000 a year in other competitive scholarships"
        }
      ],
      "normalized_coverage": "full_school_coa"
    }
  ],
  "application": {
    "separate_application": "required",
    "milestones": [
      {
        "kind": "admission_deadline",
        "requirement": "recommended",
        "date": "2026-11-01",
        "recurring": null,
        "precision": "day",
        "source_date_text": "November 1"
      },
      {
        "kind": "application_deadline",
        "requirement": "required",
        "date": "2026-12-01",
        "recurring": null,
        "precision": "day",
        "source_date_text": "December 1"
      },
      {
        "kind": "notification",
        "requirement": "recommended",
        "date": null,
        "recurring": {
          "month": 3,
          "day": 15
        },
        "precision": "approximate",
        "source_date_text": "mid-March each year"
      }
    ],
    "interview_mode": "mixed",
    "finalist_event_required": true,
    "admission_plan_requirement": "Early Action application by November 1",
    "prerequisites": [
      {
        "kind": "portal_credentials",
        "minimum_lead_days": 5,
        "notes": "Allow about five days for portal credentials.",
        "maximum_lead_days": 5
      }
    ],
    "notes": null
  },
  "renewal_rules": [
    {
      "applies_to": [],
      "gpa_min": null,
      "gpa_scale": 4.0,
      "credit_load_min_per_term": 12,
      "evaluation_timing": "End of each spring term",
      "summer_courses_can_fix_shortfall": null,
      "max_semesters": 8,
      "notes": "The page lists two minimum GPAs; see field_evidence.",
      "credit_load_min_per_year": 24
    }
  ],
  "stacking_rules": [
    {
      "other_aid_type": "institutional_merit",
      "relation": "not_allowed",
      "note": null
    }
  ],
  "award_counts": [
    {
      "metric": "offers",
      "qualifier": "approximate",
      "value": 12,
      "cohort_year": 2027,
      "source_ref": "s-foundation",
      "claim": "target",
      "denominator": null
    },
    {
      "metric": "share_of_class",
      "qualifier": "approximate",
      "value": 1,
      "cohort_year": 2027,
      "source_ref": "s-foundation",
      "claim": "actual",
      "denominator": "entering first-year class (percent)"
    }
  ],
  "sources": [
    {
      "source_id": "s-foundation",
      "url": "https://www.jeffersonscholars.org/scholarships/fixture-faq",
      "authority": "foundation_official",
      "retrieved_at": "2026-11-08",
      "archive_url": null
    },
    {
      "source_id": "s-school",
      "url": "https://admission.virginia.edu/affordability/fixture-page",
      "authority": "official_aid_policy",
      "retrieved_at": "2026-11-08",
      "archive_url": "https://web.archive.org/web/2026id_/https://admission.virginia.edu/affordability/fixture-page"
    }
  ],
  "evidence": [
    {
      "field_path": "offers/0/selection_mode",
      "source_ref": "s-foundation",
      "locator": "FAQ, 'How are scholars chosen'",
      "value_status": "reported"
    },
    {
      "field_path": "offers/0/benefits/0/amount",
      "source_ref": "s-foundation",
      "locator": "Benefits table, tuition row",
      "value_status": "not_published"
    },
    {
      "field_path": "offers/0/benefits/1/amount",
      "source_ref": "s-foundation",
      "locator": "Benefits table, stipend row",
      "value_status": "reported"
    },
    {
      "field_path": "offers/0/benefits/2/amount",
      "source_ref": "s-foundation",
      "locator": "Benefits table, summers row",
      "value_status": "reported"
    },
    {
      "field_path": "offers/1/selection_mode",
      "source_ref": "s-school",
      "locator": "National Merit section, first paragraph",
      "value_status": "reported"
    },
    {
      "field_path": "offers/1/eligibility/national_merit_statuses",
      "source_ref": "s-school",
      "locator": "National Merit section, first paragraph",
      "value_status": "reported"
    },
    {
      "field_path": "application/separate_application",
      "source_ref": "s-foundation",
      "locator": "Apply page, heading",
      "value_status": "reported"
    },
    {
      "field_path": "application/milestones/1",
      "source_ref": "s-foundation",
      "locator": "Apply page, deadlines list, first row",
      "value_status": "reported"
    },
    {
      "field_path": "application/milestones/2",
      "source_ref": "s-foundation",
      "locator": "Apply page, timeline paragraph",
      "value_status": "reported"
    },
    {
      "field_path": "renewal_rules/0/gpa_min",
      "source_ref": "s-school",
      "locator": "Renewal section, bullet 1",
      "value_status": "conflicting"
    },
    {
      "field_path": "renewal_rules/0/gpa_min",
      "source_ref": "s-school",
      "locator": "Renewal section, bullet 4",
      "value_status": "conflicting"
    },
    {
      "field_path": "application/milestones/0",
      "source_ref": "s-school",
      "locator": "Apply page, admission box",
      "value_status": "reported"
    },
    {
      "field_path": "/awarding_authority",
      "source_ref": "s-foundation",
      "locator": "About page, first paragraph",
      "value_status": "reported"
    },
    {
      "field_path": "offers/0/advertised_totals/0/amount",
      "source_ref": "s-foundation",
      "locator": "Benefits page, headline",
      "value_status": "reported"
    },
    {
      "field_path": "offers/1/benefits/0/conditions_text",
      "source_ref": "s-school",
      "locator": "Waiver footnote",
      "value_status": "reported"
    }
  ],
  "other_info": [],
  "last_check_at": null,
  "last_check_result": null,
  "needs_review": null,
  "license": "CC-BY-SA-4.0",
  "attribution": "Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record."
}
```
