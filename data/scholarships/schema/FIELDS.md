# Scholarship record fields

Contract for the loader, the web card and the monitor. Source of truth is
[`program.schema.json`](program.schema.json); this table is generated from it
(`python tools/scholarships/validate.py --print-fields`) and a test fails if a
field is missing here. Change a name only with a schema version bump.

One YAML file per program: `data/scholarships/programs/<school_id>/<program_id>.yaml`.

## Conventions

- **Placement.** The file starts with `schema_version: 1`. Program-level fields sit
  at the top. Each entry in `versions[]` is one entering class. `offers[]` (and,
  inside each offer, `eligibility` and `benefits[]`) hold the terms that can differ
  by residency or tier. `application`, `renewal_rules`, `stacking_rules`,
  `award_counts`, `sources` and `field_evidence` sit at version level. A tier nests
  under another offer with `parent_offer_id`.
- **Joint programs.** One file per program, under the first participant's directory.
  `participating_schools` lists every participant, the first equal to `school_id`;
  each is validated against identity and each participant's domain is an allowed
  source domain.
- **Lists that can be unknown.** `benefits`, `exclusions`, `test_rules`,
  `renewal_rules` and `stacking_rules` are `array|null`: null means not documented,
  `[]` means documented as none. An explicitly empty `stacking_rules` needs
  `field_evidence` on the path `stacking_rules`.
- **Renewal.** `renewal_rules[]` each carry `applies_to[]` of `{offer_id, benefit_id}`;
  an empty `applies_to` means the whole version.
- **Status.** Program-level `status` is the current summary. Version-level
  `program_status_for_entry` is the status for that entering class and needs
  evidence when it is not `active` or `unknown`. `verification_status` is
  `verified`, `conflicting`, `historical_only` or `unverified`; the monitor's
  needs-review flag and check dates live in the database, not in these files.
- **Coverage is derived.** There is no `normalized_coverage` in YAML; the loader
  derives it from the typed benefit components. A waiver of the out-of-state
  differential is `category: nonresident_differential`, `instrument: tuition_waiver`,
  and never counts. A full waiver of tuition itself (`category: tuition`,
  `instrument: tuition_waiver`) counts as full tuition.
- **Residency** uses one vocabulary everywhere: `in_state`, `out_of_state`,
  `international`, `any`, `unknown`.
- **Types.** `string|null` means the key may be null; an enum shown without
  `|null` has an explicit `unknown` or `not_published` value where unknown is
  possible. `null` and `unknown` never mean false, zero or unrestricted.
  Booleans that are tri-state are `boolean|null`.
- **Dates** are `YYYY-MM-DD` strings (quote them in YAML). `ipeds_id` is a quoted
  six-digit string. Money is USD.
- **Ids** (`program_id`, `version_id`, `offer_id`, `benefit_id`, `source_id`) are
  lowercase slugs unique in their scope. `supersedes` names another `version_id`
  of the same program.
- **`field_evidence[].field_path`** is a slash path inside one version, for example
  `offers/0/benefits/1/amount` or `application/milestones/0`. A path starting with
  `/` addresses the program: `/awarding_authority`, `/related_programs/0`.
  A stated value needs `reported` evidence on its own path or its direct parent;
  `not_published` evidence never supports a value. `automatic_guaranteed` and
  `total_program` amounts need `reported` evidence on the exact path with a
  `short_excerpt`; the former also needs `reported_value: automatic_guaranteed`.
  A conflict is two or more `conflicting` entries on one path, each with
  `reported_value`; the field itself stays null.
- **`milestones[]`** carry at most one of `date` or `recurring: {month, day}`. Both
  null is allowed only when the milestone has `conflicting` evidence. Dated
  milestones must fall between 1 July of `entry_year - 1` and 31 August of
  `entry_year`; with `entry_year: null` the window is skipped and `entry_year`
  needs `conflicting` or `not_published` evidence. A month-precision date uses the
  first of the month.
- **Advertised totals.** `offers[].advertised_totals[]` is the only place a
  school-quoted package total may live: `{amount, scope_text}`. `amount.period`
  may be null when the school states none. Each entry needs `reported` evidence on
  `offers/N/advertised_totals/M/amount` with a `short_excerpt`. Never sum
  components. A benefit promised as full cost of attendance without components
  uses `category: cost_of_attendance`.
- **Conditions.** A benefit with `conditions_text` (it depends on something else)
  needs evidence on `offers/N/benefits/M/conditions_text`. `citizenship_text` is
  the school's own wording, at most 40 words. `separate_application:
  no_form_other_steps_required` means other steps (visit, interview,
  recommendations) but no scholarship form; it is treated like `not_required` in
  the `consideration_route` cross-check.
- **Other info.** `versions[].other_info` is null (nothing recorded) or at most 6
  entries `{text, source_ref}` for a sourced fact with no typed field. `text` is one
  plain sentence of at most 40 words in the school's terms; `source_ref` names a
  source of the same version. Each entry needs `reported` evidence on the exact path
  `other_info/N` with a `short_excerpt`. Display only: it never feeds a label,
  filter, count or freshness status.
- **Amounts.** `exact`, `up_to`, `at_least`, `approximate` need `value`; `range`
  needs `min < max`; `not_published` has no numbers.
- **Supersedes.** Only within the same `entry_year`, acyclic, with at most one
  unsuperseded version per `entry_year`. A new cycle is a new version.
- **Award counts.** `metric` is the unit; `claim` is `target` or `actual`;
  `share_of_class` needs a `denominator`.
- **No "full ride".** Coverage is `coverage` plus `normalized_coverage`; the page
  derives any display label.
- **Published versions are immutable.** Every version that existed at the base
  ref, except `unverified`, must be unchanged. A key absent at base and null at
  head is ignored so optional fields can be added later; anything else is an
  edit. A correction is a new version with `supersedes`.

## Fields

Paths use `[]` for list items.

| Field path | Type | Allowed values |
|---|---|---|
| `schema_version` | integer |  |
| `program_id` | string |  |
| `school_id` | string |  |
| `ipeds_id` | string |  |
| `participating_schools[]` | array of object |  |
| `participating_schools[].school_id` | string |  |
| `participating_schools[].ipeds_id` | string |  |
| `applicable_campuses[]` | array of string |  |
| `official_name` | string |  |
| `aliases[]` | array of string |  |
| `program_family` | enum | stamps, national_merit, presidential, honors, other |
| `awarding_authority` | enum | institution, affiliated_foundation, cofunded, state_program, unknown |
| `related_programs[]` | array of object |  |
| `related_programs[].program_id` | string |  |
| `related_programs[].relation` | enum | component_of, includes, replaces, mutually_exclusive_with, successor_to |
| `status` | enum | active, paused, closed_to_new_entrants, merged, discontinued, unknown |
| `versions[]` | array of object |  |
| `versions[].version_id` | string |  |
| `versions[].supersedes` | string|null |  |
| `versions[].entry_year` | integer|null |  |
| `versions[].entry_year_label` | string|null |  |
| `versions[].entry_terms[]` | array of enum | fall, spring, summer, unspecified |
| `versions[].source_cohort_text` | string|null |  |
| `versions[].verification_status` | enum | verified, conflicting, historical_only, unverified |
| `versions[].last_reviewed_at` | string|null |  |
| `versions[].reviewed_by` | string|null |  |
| `versions[].owner_spot_checked` | boolean|null |  |
| `versions[].program_status_for_entry` | enum|null | active, paused, closed_to_new_entrants, merged, discontinued, unknown |
| `versions[].offers[]` | array of object |  |
| `versions[].offers[].offer_id` | string |  |
| `versions[].offers[].parent_offer_id` | string|null |  |
| `versions[].offers[].variant_name` | string|null |  |
| `versions[].offers[].residency` | enum | in_state, out_of_state, international, any, unknown |
| `versions[].offers[].selection_mode` | enum | automatic_guaranteed, competitive, hybrid, unknown |
| `versions[].offers[].consideration_route` | enum | admission_application, separate_application, honors_application, nomination, invitation, multiple, unknown |
| `versions[].offers[].aid_basis` | enum | merit_only, merit_and_need, unclear |
| `versions[].offers[].need_role` | enum | required, considered, not_considered, top_up_only, unknown |
| `versions[].offers[].funds_limited` | boolean|null |  |
| `versions[].offers[].advertised_totals[]` | array of object |  |
| `versions[].offers[].advertised_totals[].amount` | object |  |
| `versions[].offers[].advertised_totals[].amount.qualifier` | enum | exact, range, up_to, at_least, approximate, not_published |
| `versions[].offers[].advertised_totals[].amount.value` | number|null |  |
| `versions[].offers[].advertised_totals[].amount.min` | number|null |  |
| `versions[].offers[].advertised_totals[].amount.max` | number|null |  |
| `versions[].offers[].advertised_totals[].amount.period` | enum|null | semester, academic_year, one_time, total_program |
| `versions[].offers[].advertised_totals[].scope_text` | string |  |
| `versions[].offers[].eligibility` | object |  |
| `versions[].offers[].eligibility.national_merit_statuses[]` | array of enum|null | semifinalist, finalist, commended, nrp_hispanic, nrp_african_american, nrp_indigenous |
| `versions[].offers[].eligibility.status_required_for_award` | enum|null | semifinalist, finalist, commended, nrp_hispanic, nrp_african_american, nrp_indigenous, scholar |
| `versions[].offers[].eligibility.citizenship_text` | string|null |  |
| `versions[].offers[].eligibility.first_choice_required` | boolean|null |  |
| `versions[].offers[].eligibility.gpa` | object|null |  |
| `versions[].offers[].eligibility.gpa.min` | number|null |  |
| `versions[].offers[].eligibility.gpa.scale` | number|null |  |
| `versions[].offers[].eligibility.gpa.basis` | enum | weighted, unweighted, recalculated_by_school, unknown |
| `versions[].offers[].eligibility.test_rules[]` | array of object|null |  |
| `versions[].offers[].eligibility.test_rules[].exam` | string |  |
| `versions[].offers[].eligibility.test_rules[].min` | number|null |  |
| `versions[].offers[].eligibility.test_rules[].scoring` | enum | single_sitting, superscore, unknown |
| `versions[].offers[].eligibility.test_rules[].official_required` | boolean|null |  |
| `versions[].offers[].eligibility.tests_policy_for_scholarship` | enum | required, optional, not_considered, unknown |
| `versions[].offers[].eligibility.citizenship_eligible[]` | array of enum|null | us_citizen, permanent_resident, international, any |
| `versions[].offers[].eligibility.majors_allowed[]` | array of string|null |  |
| `versions[].offers[].eligibility.major_change_restrictions` | string|null |  |
| `versions[].offers[].eligibility.honors_requirement` | boolean|null |  |
| `versions[].offers[].eligibility.first_generation_rule` | enum | required, considered, not_considered, unknown |
| `versions[].offers[].eligibility.eligibility_notes` | string|null |  |
| `versions[].offers[].benefits[]` | array of object|null |  |
| `versions[].offers[].benefits[].benefit_id` | string |  |
| `versions[].offers[].benefits[].category` | enum | tuition, mandatory_fees, housing, meals, books, laptop, stipend, study_abroad, enrichment, health_insurance, nonresident_differential, cost_of_attendance, other |
| `versions[].offers[].benefits[].instrument` | enum | scholarship, tuition_waiver, cash_stipend, restricted_fund, earned_compensation, unknown |
| `versions[].offers[].benefits[].coverage` | enum | full, partial, fixed_amount, variable, unknown |
| `versions[].offers[].benefits[].amount` | object|null |  |
| `versions[].offers[].benefits[].amount.qualifier` | enum | exact, range, up_to, at_least, approximate, not_published |
| `versions[].offers[].benefits[].amount.value` | number|null |  |
| `versions[].offers[].benefits[].amount.min` | number|null |  |
| `versions[].offers[].benefits[].amount.max` | number|null |  |
| `versions[].offers[].benefits[].amount.period` | enum|null | semester, academic_year, one_time, total_program |
| `versions[].offers[].benefits[].duration_terms` | string|null |  |
| `versions[].offers[].benefits[].conditions_text` | string|null |  |
| `versions[].offers[].benefits[].exclusions[]` | array of string|null |  |
| `versions[].offers[].benefits[].scope_text` | string|null |  |
| `versions[].offers[].benefits[].advertised_coverage_label` | string|null |  |
| `versions[].application` | object|null |  |
| `versions[].application.separate_application` | enum | required, encouraged, not_required, invitation_only, no_form_other_steps_required, unknown |
| `versions[].application.milestones[]` | array of object |  |
| `versions[].application.milestones[].kind` | enum | application_open, admission_deadline, application_deadline, nomination_deadline, supporting_materials_deadline, test_score_deadline, interview, finalist_event, notification, acceptance_deadline, other |
| `versions[].application.milestones[].requirement` | enum | required, priority, recommended, invitation_only |
| `versions[].application.milestones[].date` | string|null |  |
| `versions[].application.milestones[].recurring` | object|null |  |
| `versions[].application.milestones[].recurring.month` | integer |  |
| `versions[].application.milestones[].recurring.day` | integer |  |
| `versions[].application.milestones[].precision` | enum | day, month, season, approximate |
| `versions[].application.milestones[].source_date_text` | string|null |  |
| `versions[].application.admission_plan_requirement` | string|null |  |
| `versions[].application.prerequisites[]` | array of object |  |
| `versions[].application.prerequisites[].kind` | enum | portal_credentials, admission_application, test_scores, recommendation, other |
| `versions[].application.prerequisites[].minimum_lead_days` | integer|null |  |
| `versions[].application.prerequisites[].maximum_lead_days` | integer|null |  |
| `versions[].application.prerequisites[].notes` | string|null |  |
| `versions[].application.interview_mode` | enum | none, in_person, virtual, either, mixed, unknown |
| `versions[].application.finalist_event_required` | boolean|null |  |
| `versions[].application.notes` | string|null |  |
| `versions[].renewal_rules[]` | array of object|null |  |
| `versions[].renewal_rules[].applies_to[]` | array of object |  |
| `versions[].renewal_rules[].applies_to[].offer_id` | string|null |  |
| `versions[].renewal_rules[].applies_to[].benefit_id` | string|null |  |
| `versions[].renewal_rules[].gpa_min` | number|null |  |
| `versions[].renewal_rules[].gpa_scale` | number|null |  |
| `versions[].renewal_rules[].credit_load_min_per_term` | number|null |  |
| `versions[].renewal_rules[].credit_load_min_per_year` | number|null |  |
| `versions[].renewal_rules[].evaluation_timing` | string|null |  |
| `versions[].renewal_rules[].summer_courses_can_fix_shortfall` | boolean|null |  |
| `versions[].renewal_rules[].max_semesters` | integer|null |  |
| `versions[].renewal_rules[].notes` | string|null |  |
| `versions[].stacking_rules[]` | array of object|null |  |
| `versions[].stacking_rules[].other_aid_type` | enum | institutional_merit, institutional_need, federal_or_state_need, state_merit, outside_scholarship, athletic, tuition_waiver, other |
| `versions[].stacking_rules[].relation` | enum | allowed, not_allowed, replaces, counts_within_package |
| `versions[].stacking_rules[].note` | string|null |  |
| `versions[].award_counts[]` | array of object |  |
| `versions[].award_counts[].metric` | enum | offers, new_recipients, share_of_class |
| `versions[].award_counts[].qualifier` | enum | exact, up_to, at_least, approximate, not_published |
| `versions[].award_counts[].value` | number|null |  |
| `versions[].award_counts[].cohort_year` | integer|null |  |
| `versions[].award_counts[].source_ref` | string |  |
| `versions[].award_counts[].claim` | enum | target, actual |
| `versions[].award_counts[].denominator` | string|null |  |
| `versions[].sources[]` | array of object |  |
| `versions[].sources[].source_id` | string |  |
| `versions[].sources[].url` | string |  |
| `versions[].sources[].authority` | enum | official_program, official_aid_policy, official_admissions, official_news, archived_official, foundation_official |
| `versions[].sources[].retrieved_at` | string |  |
| `versions[].sources[].content_sha256` | string|null |  |
| `versions[].sources[].archive_url` | string|null |  |
| `versions[].other_info[]` | array of object|null |  |
| `versions[].other_info[].text` | string |  |
| `versions[].other_info[].source_ref` | string |  |
| `versions[].field_evidence[]` | array of object |  |
| `versions[].field_evidence[].field_path` | string |  |
| `versions[].field_evidence[].source_ref` | string |  |
| `versions[].field_evidence[].locator` | string |  |
| `versions[].field_evidence[].short_excerpt` | string|null |  |
| `versions[].field_evidence[].value_status` | enum | reported, not_published, conflicting |
| `versions[].field_evidence[].reported_value` | string|number|boolean|null |  |
