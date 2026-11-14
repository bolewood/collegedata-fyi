# PRD 036: `scholarship_directory` view contract

The contract the web work (PRD 036 M3) builds against. Source of truth for
column names is `supabase/migrations/20261114160000_scholarship_directory.sql`;
`tools/scholarships/test_load.py` fails if this file's column list, the example
row or the attribution string drift from it.

Status: written for the M2 migration, which is **not applied yet**. It is applied
from `main` after merge, then `tools/scholarships/load.py --apply` fills it.
Until then the view does not exist, and after that it holds only the programs
that have been merged under `data/scholarships/programs/`.

## What a row is

- Endpoint: `GET https://api.collegedata.fyi/rest/v1/scholarship_directory` (PostgREST,
  anon key, no account). `Accept: application/vnd.pgrst.object+json` for one row.
- One row per **program per participating school**. A joint program (Robertson at
  Duke and UNC) appears once for each participating school, with the same
  `program_id` and `version_id`; `school_id` is the school this row belongs to
  and `participating_school_ids` lists all of them, lead school first. The
  primary key is `(program_id, school_id)`.
- Per program, the row is the **latest entry year** whose chain-head version is
  `verified`, `conflicting` or `historical_only`. `unverified` versions never
  appear. Within one entry year the head of the `supersedes` chain is served.
- A school with no rows has no documented programs yet. That is "No named
  programs documented yet", not "this school has none".
- `freshness_status` and `current_entry_year` are computed when the row is read.
  Everything else comes from a cache refreshed after each load and after the
  change monitor writes (it is not refreshed by the clock).
- Not exposed: `field_evidence` (locators and short excerpts), `content_sha256`,
  the monitor's `detail`, and the verbatim `record`. Add them if M3 needs them.

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
| `awarding_authority` | text | no | `institution`, `affiliated_foundation`, `cofunded`, `unknown`. For `affiliated_foundation` the sources are the foundation's pages; say so. |
| `program_status` | text | no | Program-level summary: `active`, `paused`, `closed_to_new_entrants`, `merged`, `discontinued`, `unknown`. |
| `applicable_campuses` | text[] | no | Empty means not campus-specific. |
| `related_programs` | jsonb | no | `[{program_id, relation}]`, relation: `component_of`, `includes`, `replaces`, `mutually_exclusive_with`, `successor_to`. The target may have no row yet. |
| `version_id` | text | no | Unique within a program only. |
| `entry_year` | integer | yes | Entering class (fall 2027 is 2027). Null when the school's cycle is unclear; then use `entry_year_label`. |
| `entry_year_label` | text | yes | The school's own wording when `entry_year` is null. |
| `entry_terms` | text[] | no | Elements: `fall`, `spring`, `summer`, `unspecified`. |
| `source_cohort_text` | text | yes | The school's own cohort wording. |
| `verification_status` | text | no | `verified`, `conflicting`, `historical_only`. (`unverified` is never served.) Internal: VOICE.md forbids saying "verified" in product copy. |
| `freshness_status` | text | no | `current_cycle_verified`, `current_cycle_unconfirmed`, `past_cycle`, `conflicting`. Rule below. |
| `current_entry_year` | integer | no | The entry year `freshness_status` was computed against. |
| `last_reviewed_at` | date | yes | |
| `reviewed_by` | text | yes | |
| `owner_spot_checked` | boolean | yes | |
| `program_status_for_entry` | text | yes | Status for this entering class; same values as `program_status`. |
| `coverages` | text[] | no | Distinct `normalized_coverage` across the version's offers. Filter column. |
| `selection_modes` | text[] | no | Distinct offer `selection_mode`: `automatic_guaranteed`, `competitive`, `hybrid`, `unknown`. |
| `residencies` | text[] | no | Distinct offer `residency`: `in_state`, `out_of_state`, `international`, `any`, `unknown`. |
| `national_merit_statuses` | text[] | no | Union over offers: `semifinalist`, `finalist`, `commended`, `nrp_hispanic`, `nrp_african_american`, `nrp_indigenous`. |
| `need_roles` | text[] | no | Distinct offer `need_role`: `required`, `considered`, `not_considered`, `top_up_only`, `unknown`. |
| `separate_application` | text | yes | `required`, `encouraged`, `not_required`, `invitation_only`, `unknown`; null when the version has no `application` block. |
| `deadline_months` | integer[] | no | Months (1 to 12) of required or priority deadlines, dated or recurring. Filter column. |
| `key_deadline` | date | yes | Earliest dated required deadline, else earliest dated priority one. Null if none is dated (recurring deadlines are in `application`). Always label it with `entry_year`. |
| `latest_milestone_date` | date | yes | Latest dated milestone of any kind. Input to `freshness_status`. |
| `source_retrieved_at` | date | yes | Newest `retrieved_at` among the version's sources: "as published on the school's page <date>". |
| `offers` | jsonb | no | Array of offers as in `data/scholarships/schema/FIELDS.md` (`versions[].offers[]`), each with one extra key, `normalized_coverage`. |
| `application` | jsonb | yes | `versions[].application`: `separate_application`, `milestones[]`, `prerequisites[]`, interview fields, `notes`. |
| `renewal_rules` | jsonb | yes | Array; null means not documented, `[]` means documented as none. |
| `stacking_rules` | jsonb | yes | Same null versus `[]` meaning. |
| `award_counts` | jsonb | no | Array; `metric` is the unit, `claim` is `target` or `actual`. Never present these as odds. |
| `sources` | jsonb | no | `[{source_id, url, authority, retrieved_at, archive_url}]`. Link the official source one click away. |
| `last_check_at` | timestamptz | yes | Latest monitor check of this version; null until the monitor (M4) has run. |
| `needs_review` | boolean | yes | Latest check flagged a change for review. Null when never checked. |
| `license` | text | no | Always `CC-BY-SA-4.0`. |
| `attribution` | text | no | The canonical credit string. Clients that copy rows must display it. |

### `normalized_coverage` (inside each `offers[]` element)

Derived by the loader per offer from that offer's own benefits; it is not in the
YAML and a child offer does not inherit from its parent. Null when the offer's
benefits are not documented.

| Value | Meaning |
|---|---|
| `full_tuition` | A full tuition benefit that is a real scholarship. |
| `full_tuition_fees` | Full tuition and full mandatory fees. |
| `tuition_housing_meals` | Full tuition, housing and meals (fees optional). |
| `full_school_coa` | Full tuition, fees, housing, meals and books, plus a stipend. Display copy should still use the school's own label, not "full ride". |
| `partial_or_fixed` | No full tuition, but a partial, fixed-amount or variable benefit. |
| `other` | Anything else, including coverage the school did not state. |

A `tuition_waiver` instrument or a `nonresident_differential` category never
counts toward any value above (a waiver is not a scholarship). There is no
"full ride" value; derive any display label from the components.

### `freshness_status` rule

Entry cycle: a class entering in fall Y becomes the current cycle on 1 July of
Y-1, UTC. `current_entry_year` is `year + 1` from July through December and
`year` from January through June (2027 on 2026-11-14). First match wins:

1. `conflicting`: `verification_status` is `conflicting`, or the latest check's
   result is `conflicting`.
2. `past_cycle`: `verification_status` is `historical_only`; or `entry_year` is
   below `current_entry_year`; or `entry_year` is null and `latest_milestone_date`
   is before today.
3. `current_cycle_unconfirmed`: `entry_year` is null; or the latest check has
   `needs_review` true; or the status is anything other than `verified`.
4. `current_cycle_verified`: everything else (verified, `entry_year` at or after
   `current_entry_year`, nothing flagged).

UI: `past_cycle` and `conflicting` get the amber note; never roll last year's
dates forward.

## Filtering and sorting (PostgREST)

```
/rest/v1/scholarship_directory?school_id=eq.tulsa
/rest/v1/scholarship_directory?coverages=cs.{full_tuition}
/rest/v1/scholarship_directory?national_merit_statuses=cs.{finalist}&residencies=ov.{any,out_of_state}
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
program data. It shows a nested offer whose only benefit is a nonresident
tuition waiver, which derives `other`, and a recurring notification milestone.
The row is the real output of the loader and the view against a local database.

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
  "awarding_authority": "affiliated_foundation",
  "program_status": "active",
  "applicable_campuses": [],
  "related_programs": [
    {
      "relation": "component_of",
      "program_id": "fixture-parent-program"
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
  "current_entry_year": 2027,
  "last_reviewed_at": "2026-11-08",
  "reviewed_by": "fixture-agent-run-1",
  "owner_spot_checked": true,
  "program_status_for_entry": "active",
  "coverages": [
    "full_tuition",
    "other"
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
  "need_roles": [
    "considered",
    "not_considered"
  ],
  "separate_application": "required",
  "deadline_months": [
    12
  ],
  "key_deadline": "2026-12-01",
  "latest_milestone_date": "2026-12-01",
  "source_retrieved_at": "2026-11-08",
  "offers": [
    {
      "benefits": [
        {
          "amount": {
            "max": null,
            "min": null,
            "value": null,
            "period": null,
            "qualifier": "not_published"
          },
          "category": "tuition",
          "coverage": "full",
          "benefit_id": "b-tuition",
          "exclusions": [],
          "instrument": "scholarship",
          "scope_text": null,
          "duration_terms": "Eight semesters",
          "advertised_coverage_label": "full tuition"
        },
        {
          "amount": {
            "max": null,
            "min": null,
            "value": 5000,
            "period": "academic_year",
            "qualifier": "exact"
          },
          "category": "stipend",
          "coverage": "fixed_amount",
          "benefit_id": "b-stipend",
          "exclusions": [],
          "instrument": "cash_stipend",
          "scope_text": null,
          "duration_terms": null,
          "advertised_coverage_label": null
        },
        {
          "amount": {
            "max": null,
            "min": null,
            "value": 12000,
            "period": "total_program",
            "qualifier": "up_to"
          },
          "category": "enrichment",
          "coverage": "fixed_amount",
          "benefit_id": "b-summers",
          "exclusions": [],
          "instrument": "restricted_fund",
          "scope_text": "Funded summer experiences, quoted by the foundation as one total",
          "duration_terms": null,
          "advertised_coverage_label": null
        }
      ],
      "offer_id": "o-main",
      "aid_basis": "merit_and_need",
      "need_role": "considered",
      "residency": "any",
      "eligibility": {
        "gpa": null,
        "test_rules": [],
        "majors_allowed": null,
        "eligibility_notes": null,
        "honors_requirement": null,
        "citizenship_eligible": null,
        "first_choice_required": null,
        "first_generation_rule": "unknown",
        "national_merit_statuses": null,
        "major_change_restrictions": null,
        "status_required_for_award": null,
        "tests_policy_for_scholarship": "unknown"
      },
      "variant_name": "Main package",
      "funds_limited": null,
      "selection_mode": "competitive",
      "parent_offer_id": null,
      "consideration_route": "nomination",
      "normalized_coverage": "full_tuition"
    },
    {
      "benefits": [
        {
          "amount": {
            "max": null,
            "min": null,
            "value": null,
            "period": null,
            "qualifier": "not_published"
          },
          "category": "nonresident_differential",
          "coverage": "full",
          "benefit_id": "b-differential",
          "exclusions": null,
          "instrument": "tuition_waiver",
          "scope_text": "Waives the out-of-state tuition differential only",
          "duration_terms": null,
          "advertised_coverage_label": null
        }
      ],
      "offer_id": "o-tier",
      "aid_basis": "merit_only",
      "need_role": "not_considered",
      "residency": "out_of_state",
      "eligibility": {
        "gpa": null,
        "test_rules": [],
        "majors_allowed": null,
        "eligibility_notes": null,
        "honors_requirement": null,
        "citizenship_eligible": null,
        "first_choice_required": true,
        "first_generation_rule": "unknown",
        "national_merit_statuses": [
          "finalist"
        ],
        "major_change_restrictions": null,
        "status_required_for_award": null,
        "tests_policy_for_scholarship": "unknown"
      },
      "variant_name": "National Merit tier",
      "funds_limited": false,
      "selection_mode": "automatic_guaranteed",
      "parent_offer_id": "o-main",
      "consideration_route": "multiple",
      "normalized_coverage": "other"
    }
  ],
  "application": {
    "notes": null,
    "milestones": [
      {
        "date": "2026-11-01",
        "kind": "admission_deadline",
        "precision": "day",
        "recurring": null,
        "requirement": "recommended",
        "source_date_text": "November 1"
      },
      {
        "date": "2026-12-01",
        "kind": "application_deadline",
        "precision": "day",
        "recurring": null,
        "requirement": "required",
        "source_date_text": "December 1"
      },
      {
        "date": null,
        "kind": "notification",
        "precision": "approximate",
        "recurring": {
          "day": 15,
          "month": 3
        },
        "requirement": "recommended",
        "source_date_text": "mid-March each year"
      }
    ],
    "prerequisites": [
      {
        "kind": "portal_credentials",
        "notes": "Allow about five days for portal credentials.",
        "minimum_lead_days": 5
      }
    ],
    "interview_mode": "in_person",
    "separate_application": "required",
    "finalist_event_required": true,
    "admission_plan_requirement": "Early Action application by November 1"
  },
  "renewal_rules": [
    {
      "notes": "The page lists two minimum GPAs; see field_evidence.",
      "gpa_min": null,
      "gpa_scale": 4.0,
      "applies_to": [],
      "max_semesters": 8,
      "evaluation_timing": "End of each spring term",
      "credit_load_min_per_term": 12,
      "summer_courses_can_fix_shortfall": null
    }
  ],
  "stacking_rules": [
    {
      "note": null,
      "relation": "not_allowed",
      "other_aid_type": "institutional_merit"
    }
  ],
  "award_counts": [
    {
      "claim": "target",
      "value": 12,
      "metric": "offers",
      "qualifier": "approximate",
      "source_ref": "s-foundation",
      "cohort_year": 2027,
      "denominator": null
    },
    {
      "claim": "actual",
      "value": 1,
      "metric": "share_of_class",
      "qualifier": "approximate",
      "source_ref": "s-foundation",
      "cohort_year": 2027,
      "denominator": "entering first-year class (percent)"
    }
  ],
  "sources": [
    {
      "url": "https://www.jeffersonscholars.org/scholarships/fixture-faq",
      "authority": "foundation_official",
      "source_id": "s-foundation",
      "archive_url": null,
      "retrieved_at": "2026-11-08"
    },
    {
      "url": "https://admission.virginia.edu/affordability/fixture-page",
      "authority": "official_aid_policy",
      "source_id": "s-school",
      "archive_url": "https://web.archive.org/web/2026id_/https://admission.virginia.edu/affordability/fixture-page",
      "retrieved_at": "2026-11-08"
    }
  ],
  "last_check_at": null,
  "needs_review": null,
  "license": "CC-BY-SA-4.0",
  "attribution": "Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record."
}
```
