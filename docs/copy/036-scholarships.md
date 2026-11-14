# PRD 036 M3: Scholarship pages copy deck

Every new user-visible string, grouped by surface, with the state that triggers
it. Owner reads before anything ships. Voice rules applied (VOICE.md, PRD 036
product principles):

- The school's page is the authority. We say "as the school published it" or
  "the school's page". We never say "verified" (internal status only), "full
  ride", "guaranteed" (unless the school's own field says automatic), "best",
  or anything about odds.
- Nothing implies collegedata.fyi checked the school's figures. We say what the
  page said and the date we read it.
- Every date sits next to "confirm on the official page" and the source link.
- Unknown is not no: a blank field is written as "not stated", never as zero,
  "none", or "open to all".
- Tokens: `{school}`, `{program}`, `{date}` are filled from the row. Dates print
  as "Nov 14, 2026"; month-only as "December 2026".

---

## 1. School page card (`ScholarshipProgramsCard`)

Renders only when the school has at least one row. A school with no rows shows
nothing (no empty card). **Departure from the PRD**, decided by the owner: the PRD
had "No named programs documented yet". The index page says the list is partial.

| String | Where / state |
|---|---|
| § Named scholarship programs | Section meta label |
| Programs this school publishes, as it published them. | Card title (serif; "as it published them" italic) |
| School-wide CDS figures above describe {cds year}. The programs below are documented separately, each with its own terms and date, and are not an estimate of any student's award. | Shared line under the title, when the merit card is shown (cds year from the merit profile) |
| The programs below are documented separately from the school's Common Data Set figures, each with its own terms and date. They are not an estimate of any student's award. | Same line when the school has no merit card |
| {n} program / {n} programs | Count chip beside the title |
| Part of a shared program with {other school}. | Joint program (`participating_school_ids` has more than one id). Other school names link to their pages |
| Offered by a foundation tied to the school. The foundation's page is the source. | `awarding_authority` = affiliated_foundation |
| Offered with a state program. | `awarding_authority` = state_program |
| Funded jointly by the school and a partner. | `awarding_authority` = cofunded |
| Part of {program} | `related_programs` relation component_of. Name from the school's own rows when present, else the program id in words |
| Includes {program} | relation includes |
| Replaces {program} | relation replaces |
| Successor to {program} | relation successor_to |
| Cannot be held together with {program} | relation mutually_exclusive_with |

### Program status (shown as a plain chip, not amber)

| String | State |
|---|---|
| Closed to new entrants | `program_status_for_entry` (else `program_status`) = closed_to_new_entrants |
| Paused | paused |
| Merged into another program | merged |
| Discontinued | discontinued |
| Status not stated | unknown or null (no chip is shown when status is active) |
| The school's page lists this program as closed to new entrants. Terms below are kept for reference. | Line under the program name when closed. If the program has no benefit terms the coverage line is replaced by "No award terms listed for new entrants." |

### Per program

| String | State |
|---|---|
| {official name} | Program name (serif) |
| {variant name} | Offer heading when a program has more than one offer (resident, nonresident, a tier) |
| Includes everything in {parent variant}, plus: | A tier offer (`parent_offer_id`) that lists only what it adds |
| § What it covers | Meta label |
| Benefits not documented for this offer. | Offer has no benefit components |
| {Category}: {text} | One line per benefit component. See "Benefit wording" below |
| As the school quotes the total: "{amount}" ({scope}). Not added up by collegedata.fyi. | Offer has `advertised_totals`. The scope text is always shown. We never sum components |
| § How you are considered | Meta label |
| Open to {residency} students | residency in_state / out_of_state / international / any. "any" prints "all residencies"; unknown prints nothing |
| § Deadline | Meta label |
| § Renewal | Meta label |
| § Counts the school published | Meta label, only when `award_counts` exists |
| {value} {metric} ({target or actual}), {cohort year}. These are not odds of receiving it. | One line per award count. Metric words: offers, new recipients, share of the class. "target" prints "the school's target", "actual" prints "as the school reported it" |
| Stacking with other aid: {line} | One line per stacking rule: allowed "Can be combined with {aid type}", not_allowed "Cannot be combined with {aid type}", replaces "Replaces {aid type}", counts_within_package "Counts within the package for {aid type}" |

### Benefit wording (one line per component)

Category labels: Tuition, Mandatory fees, Housing, Meals, Books, Laptop,
Stipend, Study abroad, Enrichment, Health insurance, Cost of attendance,
Nonresident tuition differential, Other.

| Pattern | State |
|---|---|
| {Category}: the school says it covers all of it. | `coverage` = full, no cap, no condition |
| {Category}: covers part of it. | `coverage` = partial, no amount |
| {Category}: {amount}. | fixed_amount or any benefit with an amount |
| {Category}: amount varies. | `coverage` = variable, no amount |
| {Category}: capped. Up to {amount}. | A "full" benefit whose amount qualifier is up_to or approximate, or any up_to amount |
| {Category}: waiver, not a scholarship. {text} | `instrument` = tuition_waiver. A waiver is named as a waiver and never described as tuition covered |
| {line} Condition: {conditions text}. | Any benefit with `conditions_text`. The condition is always shown, in the school's words |
| The school calls it "{label}". | `advertised_coverage_label` present (quoted, never our label) |
| {scope text} | `scope_text`, shown after the line in muted type |
| Amount not published. | amount qualifier not_published |

Amount phrases: "$20,000 a year", "up to $12,000 in total", "at least $89,000
a year", "about $4,000 a semester", "$4,000 to $8,000 a year", "$5,000 one
time". Periods: a semester, a year, one time, in total.

### How you are considered (never blends considered and guaranteed)

| String | State (`selection_mode` + `consideration_route`) |
|---|---|
| Automatic if you meet the listed requirements, as the school says. | automatic_guaranteed (the PRD requires an explicit school promise; this is the only place the idea appears) |
| Competitive. The school selects recipients. | competitive |
| Part automatic, part competitive. | hybrid |
| How recipients are chosen is not stated. | unknown |
| You are considered through your admission application. | route admission_application |
| Separate application required. | route separate_application |
| Considered through the honors application. | honors_application |
| By nomination. | nomination |
| By invitation. | invitation |
| More than one route; see the school's page. | multiple |
| National Merit {semifinalist / finalist / commended}. | `eligibility.national_merit_statuses` |
| Financial need is required. / Financial need is considered. / Financial need is not considered. / Need only tops up the award. / The page does not say whether need matters. | need_role: required / considered / not_considered / top_up_only / unknown |
| Funds are limited. | `funds_limited` = true |
| Separate application: required / encouraged / not required / by invitation only / no form, but other steps are required (a visit or interview) / not stated | `separate_application`: required / encouraged / not_required / invitation_only / no_form_other_steps_required / unknown |
| Interview: in person / virtual / in person or virtual / varies / not stated | `interview_mode` (omitted for "none") |

### Deadline

| String | State |
|---|---|
| {Required deadline / Priority deadline}: {date}, for {entry year} entry. Confirm on the official page. | `key_deadline` present and `entry_year` present |
| {Required deadline / Priority deadline}: {date}. The page does not name the entering class. Confirm on the official page. | `key_deadline` present, no `entry_year` |
| {kind label}: {Month day} each year. The page names no year, so no date is shown. Confirm on the official page. | Only a recurring milestone. Never rolled forward into a dated deadline |
| No deadline stated on the page we read. | No milestone |
| Past. Check the official page for the next cycle. | Appended in amber to a dated deadline that is before today (never rolled forward) |

Milestone kind labels: Application deadline, Admission deadline, Scholarship
application deadline, Notification, Other date. Requirement words: required
deadline, priority deadline, recommended, by invitation.

### Renewal

| String | State |
|---|---|
| Renewal terms not documented. | `renewal_rules` null |
| The school's page lists no renewal conditions. | `renewal_rules` is an empty list |
| Keep a {gpa} GPA{ on a {scale} scale}, {n} credits a term, up to {n} semesters. {Timing}. | Built from the fields present; each phrase is dropped when its field is blank. Blank GPA prints "GPA minimum not stated" |
| Summer courses can make up a shortfall. / Summer courses do not make up a shortfall. | `summer_courses_can_fix_shortfall` true / false (nothing when null) |

### Freshness line (one per `freshness_status` and `cycle_basis`)

The freshness line leads the program's footer. Every state is followed by the
source link and "Confirm on the official page."

| String | State |
|---|---|
| Terms for fall 2027 entry, as published on the school's page Nov 14, 2026. | `current_cycle_verified`, `cycle_basis` entry_year. Entry word is "fall {year}" when `entry_terms` is only fall, else "{year}" |
| The dates on the school's page run through December 2026. The page does not name the entering class. Read Nov 8, 2026. | `current_cycle_verified`, `cycle_basis` milestone_dates. No entry year is printed |
| The school's page does not name a year. We read it Nov 8, 2026. | `year_not_stated` (`cycle_basis` none). Uses `last_reviewed_at`; no class is printed |
| Amber: These terms may be out of date. The page we read described fall 2026 entry, which has passed. Read Nov 8, 2026. | `past_cycle`, `cycle_basis` entry_year |
| Amber: These terms may be out of date. The dates on the page ran through October 2026, which have passed. Read Nov 8, 2026. | `past_cycle`, `cycle_basis` milestone_dates |
| Amber: These terms may be out of date. The page we read on Nov 8, 2026 named no year, and a newer cycle has begun. | `past_cycle`, `cycle_basis` none (aged out) |
| Amber: Kept for reference. The school lists this as an earlier cycle. Read Nov 8, 2026. | `past_cycle` from `verification_status` historical_only |
| Amber: The school's pages disagree on {the renewal GPA, a date}. Both are on the official page; read it before relying on either. Read Nov 8, 2026. | `conflicting`, naming what disagrees (from the conflicting evidence fields) |
| Amber: The school's pages disagree with each other. Read the official page before relying on any figure here. Read Nov 8, 2026. | `conflicting` with no field named |
| These terms have not been re-read for this cycle. Last read Nov 8, 2026. | `current_cycle_unconfirmed` |
| Confirm on the official page | Plain text beside the source link on every freshness line; also ends every printed date |
| Official page ↗ | Source link. One per source; the label for a foundation source is "Foundation's page ↗"; for an archived copy "Archived copy ↗" |
| Report an update | Link to the GitHub issue template |

Fields we name when pages conflict: the renewal GPA, the renewal credit load, a
deadline, a benefit amount, how recipients are chosen, who is eligible, the
application requirement. Anything else prints "a figure".

### Footer

| String | State |
|---|---|
| Data CC BY-SA 4.0 · collegedata.fyi · how to cite | Card footer, "how to cite" links to /methodology/scholarships#reuse |
| § SOURCE: THE SCHOOL'S OWN PAGES | Card footer meta line |
| METHOD → | Links to /methodology/scholarships |
| All scholarship programs → | Links to /scholarships |

---

## 2. `/scholarships` index

| String | Where / state |
|---|---|
| Scholarship programs · collegedata.fyi | Page title (`<title>` is "Scholarship programs") |
| Named merit scholarships, as the schools published them. | Meta description (first clause); full: "A partial, hand-built list of named merit scholarships at U.S. colleges, each linked to the school's own page and dated. Not a ranking and not an estimate of your award." |
| § Scholarships | Meta label |
| Named scholarships, *as the schools published them.* | H1 (italic on the second clause) |
| This is a partial, hand-built list. A school that is not here has not been documented yet, which is different from having no named scholarships. Every program links to the school's own page. | Lede and the plain statement of partiality |
| {n} programs at {m} schools | Count line. A program shared by two schools counts once in the program count |
| By school type | Heading of the type table |
| Public · Private nonprofit · Private for-profit · Not classified | Row labels |
| Counted once per program, by its lead school. This list leans toward selective schools; it is not a sample of all colleges. | Note under the type table |
| Filters · Sort | Group labels |
| Coverage | Filter label. Options: Any, Full tuition, Full tuition and fees, Tuition, housing and meals, Full cost of attendance, Partial or fixed amount, Other or not stated. (These are the contract's `normalized_coverage` values in words. "Full cost of attendance" is the school-stated component, not our label for "full ride".) |
| How recipients are chosen | Filter label. Options: Any, Competitive, Automatic if you qualify, Part automatic and competitive |
| National Merit | Filter label. Options: Any, Semifinalist, Finalist |
| Separate application | Filter label. Options: Any, Required, Encouraged, Not required, By invitation only, No form but other steps |
| Deadline month | Filter label. Options: Any, January to December |
| Residency | Filter label. Options: Any, In-state, Out-of-state, International, Any residency |
| School | Filter label, a text box. Placeholder: "School name" |
| Sort by | Sort label. Options: School name, Deadline (soonest first), Coverage (grouped alphabetically by coverage label; a grouping, never a ranking) |
| Clear filters | Button, shown when a filter is set |
| Showing {n} of {total} listings. A program shared by two schools is listed once for each. | Result count |
| No programs match these filters. The list is partial, so try fewer filters. | Empty filtered state |
| No programs are documented yet. The list is partial and is being added to. | Empty state when the view has no rows or could not be read. The page still renders |
| Columns: School · Program · What it covers · Chosen how · Deadline · Terms as of | Table header |
| Dates are the schools' own and may have passed. Confirm on the official page. | Note under the table |
| Not a ranking. Rows are sorted by the field you choose, never by how generous a program is. | Note under the table |
| {coverage chip}, one or more per row | Chips use the coverage words above |
| {freshness short}: Entry {year} · Dates through {Month year} · No year stated · Past cycle · Pages disagree · Not re-read | Last column. Amber text for the last three states |
| Deadline cell: "{date}" or "Each {Month}" (recurring) or "Not stated" | Table cell, plus the source link on the program name |
| The data is open. Download or query it; credit is requested. | Footer line; links to the methodology reuse section and /api |
| Data CC BY-SA 4.0 · collegedata.fyi · how to cite | Page footer, same as the card |

---

## 3. `/methodology/scholarships`

| String | Where / state |
|---|---|
| Scholarship programs methodology | Page title |
| § Methodology | Meta label |
| Scholarship *programs.* | H1 |
| How named scholarship programs are recorded: what we read, what each field means, and what you should not infer from any of it. | Lede |
| Sourcing rules | H2. Body: Every fact comes from the school's own pages, or from the page of a foundation the school is tied to (named as such). Third-party scholarship lists are used only to find programs, never as a source of terms. We read the page, record what it says with a locator, and note the date we read it. We do not copy the school's text; we paraphrase it and quote at most 25 words. |
| Field definitions | H2. Definitions for: program, entering class, offer, benefit, coverage words, how you are considered, separate application, deadlines, renewal, stacking, counts |
| Considered is not guaranteed. | Definition lead. Body: "Considered" means the program looks at your application. "Automatic" appears only when the school's page promises the award to everyone who meets the stated requirements. |
| A waiver is not a scholarship. | Definition lead. Body: A tuition waiver (for example, a nonresident differential) is named as a waiver and is never counted as tuition covered. |
| We do not add up totals. | Definition lead. Body: We never sum components, multiply a yearly amount, or turn "up to" into a promise. If the school quotes a total, we show it as a quote with the scope the school gave. |
| What the freshness lines mean | H2, with the five states below |
| Terms for a stated entering class | State 1. The page names the class; we print it and the date we read the page. |
| Dates, but no stated class | State 2. The page gives dated deadlines but does not name the entering class. We print the date the dates run through and do not guess the class. |
| The page names no year | State 3. The page gives neither a class nor a dated deadline. We print the date we read it. After the next July 1 we show it as a past cycle. |
| Past cycle | State 4, amber. The dates or class on the page have passed, or the school marks it as an earlier cycle. We never carry last year's dates forward. |
| Pages disagree | State 5, amber. The school's own pages give different figures. We say what differs and send you to the official page. |
| Not re-read for this cycle | Also shown, plain. A flagged change has not been reviewed yet. |
| What not to infer | H2. List below |
| A missing field is not a no. Not stated means the page did not say. | Bullet |
| This is not a list of the best scholarships, and sorting is never by generosity. | Bullet |
| Award counts are not odds. A program that "offers up to 44" does not tell you the chance you receive one. | Bullet |
| A named award does not explain the CDS merit figures. The two are documented separately, with their own years. | Bullet |
| The list is partial and leans toward selective schools. A school not listed has not been documented yet. | Bullet |
| Nothing here is a personalized estimate of cost or award. | Bullet |
| Report a correction | H2. Body: Found a figure that does not match the school's page? Open a correction. We ask for the official page URL and what differs. We do not ask for your name, email, or any information about a student. |
| Open a correction ↗ | Link to the GitHub issue template |
| Reuse and credit | H2 (anchor `#reuse`) |
| Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record. | The canonical attribution string, imported from one constant and pinned to `data/scholarships/LICENSE` by a test |
| The data is free to read, query and download. If you use it, credit it with the line above. CC BY-SA 4.0 also asks that anything you build from our descriptions and record format be shared under the same license. | Reuse body |
| What the license does not cover: the schools' own pages, their trademarks, and short quoted excerpts. Those stay with the schools. | Reuse body |
| Cite this dataset | H3, then an APA and a BibTeX block. APA: "collegedata.fyi. (2026). *Scholarship program data* [Data set]. https://collegedata.fyi/scholarships. CC BY-SA 4.0." The BibTeX key is `collegedatafyi2026scholarships` |
| Sources and API | H2. Body: the public view is `scholarship_directory`. Links to /api. Example curl |

---

## 4. GitHub issue template (`scholarship-correction.yml`)

| String | Field |
|---|---|
| Scholarship correction | Template name |
| Something on a scholarship page does not match the school's page. | Description |
| scholarship, data-error | Labels |
| Official page URL | Input label. Required. Description: "The school's (or foundation's) own page that shows the correct term." |
| Program and school | Input label. Required. Placeholder: "Program name, school" |
| What does our page say, and what does the official page say? | Textarea label. Required |
| Which fields: amount, deadline, eligibility, renewal, how recipients are chosen, other | Dropdown label "What kind of figure?" |
| Please do not include names, emails, or any detail about a student. | Markdown note at the top |

---

## 5. `/api` docs entry

| String | Where |
|---|---|
| scholarship_directory | Table entry name |
| One row per named merit scholarship program per participating school: the latest published terms, a dated freshness status, and links to the school's own page. Not a ranking; no odds. A blank field means the page did not say. | Table description |
| Fetch the scholarship programs documented for one school | curl heading 1 |
| Find National Merit packages and what they cover | curl heading 2 |
| Every row carries license and attribution columns. If you display or republish these rows, show the attribution string. | Attribution request under the entry |
| Programs are documented by hand and partially. An empty result means the school has not been documented yet. | Partiality note |

---

## 6. Navigation, sitemap, llms.txt

| String | Where |
|---|---|
| Scholarship programs | Methodology index card title. Body: "Named merit scholarships at selected schools, with the date and page each term comes from. Not a ranking, not an estimate." |
| Scholarships | Footer link; command-menu entry ("Named scholarship programs", sub: "A partial, hand-built list with dated terms and source links", call number § /SCHOLARSHIPS) |
| [Scholarship programs](.../scholarships): A partial, hand-built list of named merit scholarships, each dated and linked to the school's page | llms.txt line |
| [Scholarship methodology](.../methodology/scholarships): Sourcing rules, field definitions, freshness states, how to credit | llms.txt line |

Not added to the primary nav (Match / Schools / API) or the More menu: that menu
is a short list of destinations (Compare, Coverage, Recipes, About) and the
VOICE.md chrome rules say to hold it there. The index page is reachable from the
school card, methodology, footer, command menu, sitemap and llms.txt.

---

## 7. Notes for the owner

- The card also renders on the directory-only school page (a school with no Common Data Set on file), because named programs do not depend on a CDS. Tulsa and Tuskegee are in that state today.
- A retired program with no offers (Vanderbilt Chancellor's) shows "Closed to new entrants" and "No award terms listed for new entrants." It never shows an empty coverage line.
- Accent for the amber note is the palette's `--ochre`; no new color is added.
