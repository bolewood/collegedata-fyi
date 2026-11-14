/**
 * PRD 036 M3: types and pure text builders for the scholarship pages.
 * Copy lives in docs/copy/036-scholarships.md; keep the two in step.
 *
 * Voice rules (VOICE.md): the school's page is the authority; never "verified",
 * "full ride", "best" or odds; never imply we checked the school's figures; a
 * blank field is "not stated", never zero or "none".
 */

/** The canonical credit string. The one place it is written in web code. A test pins it to data/scholarships/LICENSE. */
export const SCHOLARSHIP_ATTRIBUTION =
  "Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record.";

export const SCHOLARSHIP_LICENSE = "CC-BY-SA-4.0";
export const SCHOLARSHIP_LICENSE_LINE = "Data CC BY-SA 4.0 · collegedata.fyi · how to cite";
export const SCHOLARSHIP_CORRECTION_URL =
  "https://github.com/bolewood/collegedata-fyi/issues/new?template=scholarship-correction.yml";

// ------------------------------------------------------------------ types

export type FreshnessStatus =
  | "current_cycle_verified"
  | "year_not_stated"
  | "current_cycle_unconfirmed"
  | "past_cycle"
  | "conflicting";

export type CycleBasis = "entry_year" | "milestone_dates" | "none";

export type Amount = {
  qualifier: "exact" | "range" | "up_to" | "at_least" | "approximate" | "not_published" | null;
  value: number | null;
  min: number | null;
  max: number | null;
  period: "semester" | "academic_year" | "one_time" | "total_program" | null;
};

export type Benefit = {
  benefit_id?: string;
  category: string;
  instrument: string;
  coverage: "full" | "partial" | "fixed_amount" | "variable" | string;
  amount: Amount | null;
  duration_terms?: string | null;
  conditions_text?: string | null;
  exclusions?: string[] | null;
  scope_text?: string | null;
  advertised_coverage_label?: string | null;
};

export type AdvertisedTotal = { amount: Amount | null; scope_text: string | null };

export type Offer = {
  offer_id: string;
  parent_offer_id: string | null;
  variant_name: string | null;
  residency: string | null;
  selection_mode: string | null;
  consideration_route: string | null;
  need_role: string | null;
  funds_limited: boolean | null;
  eligibility?: { national_merit_statuses?: string[] | null } | null;
  benefits: Benefit[] | null;
  advertised_totals?: AdvertisedTotal[] | null;
  normalized_coverage: string | null;
};

export type Milestone = {
  kind: string;
  requirement: string;
  date: string | null;
  recurring: { month: number; day: number } | null;
  precision?: string | null;
  source_date_text?: string | null;
};

export type Application = {
  separate_application: string | null;
  milestones: Milestone[];
  interview_mode?: string | null;
  notes?: string | null;
} | null;

export type RenewalRule = {
  applies_to?: string[] | null;
  gpa_min: number | null;
  gpa_scale: number | null;
  credit_load_min_per_term?: number | null;
  credit_load_min_per_year?: number | null;
  evaluation_timing?: string | null;
  summer_courses_can_fix_shortfall?: boolean | null;
  max_semesters?: number | null;
  notes?: string | null;
};

export type StackingRule = { other_aid_type: string; relation: string; note?: string | null };

export type AwardCount = {
  metric: string;
  qualifier: string | null;
  value: number | null;
  cohort_year: number | null;
  claim?: string | null;
  denominator?: string | null;
};

export type ScholarshipSource = {
  source_id: string;
  url: string;
  authority: string;
  retrieved_at: string | null;
  archive_url: string | null;
};

export type ScholarshipEvidence = { field_path: string; value_status: string };

export type ScholarshipDirectoryRow = {
  program_id: string;
  school_id: string;
  participating_school_ids: string[];
  official_name: string;
  program_family: string;
  awarding_authority: string;
  program_status: string;
  related_programs: { program_id: string; relation: string }[];
  entry_year: number | null;
  entry_year_label: string | null;
  entry_terms: string[];
  verification_status: string;
  freshness_status: FreshnessStatus;
  cycle_basis: CycleBasis;
  cycle_through_date: string | null;
  last_reviewed_at: string | null;
  program_status_for_entry: string | null;
  coverages: string[];
  selection_modes: string[];
  residencies: string[];
  national_merit_statuses: string[];
  separate_application: string | null;
  deadline_months: number[];
  key_deadline: string | null;
  source_retrieved_at: string | null;
  offers: Offer[];
  application: Application;
  renewal_rules: RenewalRule[] | null;
  stacking_rules: StackingRule[] | null;
  award_counts: AwardCount[];
  sources: ScholarshipSource[];
  evidence: ScholarshipEvidence[];
  license: string;
  attribution: string;
};

/** Columns the pages read. Everything else in the view is left out of the request. */
export const SCHOLARSHIP_SELECT = [
  "program_id", "school_id", "participating_school_ids", "official_name", "program_family",
  "awarding_authority", "program_status", "related_programs", "entry_year", "entry_year_label",
  "entry_terms", "verification_status", "freshness_status", "cycle_basis", "cycle_through_date",
  "last_reviewed_at", "program_status_for_entry", "coverages", "selection_modes", "residencies",
  "national_merit_statuses", "separate_application", "deadline_months", "key_deadline",
  "source_retrieved_at", "offers", "application", "renewal_rules", "stacking_rules",
  "award_counts", "sources", "evidence", "license", "attribution",
].join(",");

/** Make a row from the API safe to read: every list is a list, so a partial row cannot crash a page. */
export function normalizeScholarshipRow(raw: unknown): ScholarshipDirectoryRow | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.program_id !== "string" || typeof r.school_id !== "string") return null;
  const list = (v: unknown) => (Array.isArray(v) ? v : []);
  return {
    ...(r as unknown as ScholarshipDirectoryRow),
    participating_school_ids: list(r.participating_school_ids).length
      ? (list(r.participating_school_ids) as string[])
      : [r.school_id],
    official_name: typeof r.official_name === "string" ? r.official_name : r.program_id,
    related_programs: list(r.related_programs),
    entry_terms: list(r.entry_terms),
    coverages: list(r.coverages),
    selection_modes: list(r.selection_modes),
    residencies: list(r.residencies),
    national_merit_statuses: list(r.national_merit_statuses),
    deadline_months: list(r.deadline_months),
    offers: list(r.offers),
    award_counts: list(r.award_counts),
    sources: list(r.sources),
    evidence: list(r.evidence),
    renewal_rules: Array.isArray(r.renewal_rules) ? r.renewal_rules : null,
    stacking_rules: Array.isArray(r.stacking_rules) ? r.stacking_rules : null,
    application:
      r.application && typeof r.application === "object"
        ? { ...(r.application as object), milestones: list((r.application as { milestones?: unknown }).milestones) }
        : null,
  } as ScholarshipDirectoryRow;
}

// ------------------------------------------------------------- formatting

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function parseDay(iso: string | null | undefined): { y: number; m: number; d: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  if (!match) return null;
  return { y: Number(match[1]), m: Number(match[2]), d: Number(match[3]) };
}

/** "Nov 14, 2026". Empty string when the value is not a date. */
export function formatDay(iso: string | null | undefined): string {
  const p = parseDay(iso);
  return p ? `${MONTHS_SHORT[p.m - 1]} ${p.d}, ${p.y}` : "";
}

/** "December 2026". */
export function formatMonthYear(iso: string | null | undefined): string {
  const p = parseDay(iso);
  return p ? `${MONTHS[p.m - 1]} ${p.y}` : "";
}

const PERIOD: Record<string, string> = {
  semester: "a semester",
  academic_year: "a year",
  one_time: "one time",
  total_program: "in total",
};

function dollars(n: number): string {
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

/** The school's amount in words: "up to $12,000 in total". Null when it gives none. */
export function amountText(amount: Amount | null | undefined): string | null {
  if (!amount || amount.qualifier === "not_published" || amount.qualifier == null) return null;
  const period = amount.period ? ` ${PERIOD[amount.period] ?? ""}`.trimEnd() : "";
  const tail = period ? ` ${period.trim()}` : "";
  if (amount.qualifier === "range" && amount.min != null && amount.max != null) {
    return `${dollars(amount.min)} to ${dollars(amount.max)}${tail}`;
  }
  if (amount.value == null) return null;
  const lead =
    amount.qualifier === "up_to" ? "up to " :
    amount.qualifier === "at_least" ? "at least " :
    amount.qualifier === "approximate" ? "about " : "";
  return `${lead}${dollars(amount.value)}${tail}`;
}

// -------------------------------------------------------- freshness line

export type FreshnessLine = {
  /** amber for past_cycle and conflicting; plain otherwise. */
  tone: "plain" | "amber";
  text: string;
};

const CONFLICT_WORDS: Array<[RegExp, string]> = [
  [/renewal_rules\/\d+\/gpa/, "the renewal GPA"],
  [/renewal_rules\/\d+\/credit/, "the renewal credit load"],
  [/renewal_rules/, "renewal terms"],
  [/milestones\/\d+\/(date|recurring)/, "a date"],
  [/milestones/, "a date"],
  [/separate_application/, "whether a separate application is needed"],
  [/benefits\/\d+\/(amount|coverage)/, "a benefit amount"],
  [/benefits/, "what it covers"],
  [/selection_mode/, "how recipients are chosen"],
  [/eligibility/, "who is eligible"],
];

/** What the school's pages disagree on, in words, from the conflicting evidence locators. */
export function conflictTopics(evidence: ScholarshipEvidence[]): string[] {
  const out: string[] = [];
  for (const e of evidence) {
    if (e.value_status !== "conflicting") continue;
    const hit = CONFLICT_WORDS.find(([re]) => re.test(e.field_path));
    const word = hit ? hit[1] : "a figure";
    if (!out.includes(word)) out.push(word);
  }
  return out;
}

function joinWords(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

/** "fall 2027", or just "2027" when the school's page lists more than fall. */
function entryWord(row: Pick<ScholarshipDirectoryRow, "entry_year" | "entry_terms">): string {
  const terms = row.entry_terms.filter((t) => t !== "unspecified");
  return terms.length === 1 && terms[0] === "fall" ? `fall ${row.entry_year}` : `${row.entry_year}`;
}

type FreshnessInput = Pick<
  ScholarshipDirectoryRow,
  | "freshness_status" | "cycle_basis" | "entry_year" | "entry_terms" | "cycle_through_date"
  | "last_reviewed_at" | "source_retrieved_at" | "verification_status" | "evidence"
>;

/**
 * One line per freshness_status and cycle_basis. Never prints a class we were
 * not given: milestone_dates and none say so, and past dates are never rolled
 * forward. "Verified" never appears.
 */
export function freshnessLine(row: FreshnessInput): FreshnessLine {
  const read = formatDay(row.last_reviewed_at ?? row.source_retrieved_at);
  const published = formatDay(row.source_retrieved_at ?? row.last_reviewed_at);
  const readSentence = read ? ` Read ${read}.` : "";

  switch (row.freshness_status) {
    case "conflicting": {
      const topics = conflictTopics(row.evidence);
      const what = topics.length
        ? `The school's pages disagree on ${joinWords(topics)}. Both are on the official page; read it before relying on either.`
        : "The school's pages disagree with each other. Read the official page before relying on any figure here.";
      return { tone: "amber", text: `${what}${readSentence}` };
    }
    case "past_cycle": {
      if (row.verification_status === "historical_only") {
        return { tone: "amber", text: `Kept for reference. The school lists this as an earlier cycle.${readSentence}` };
      }
      const lead = "These terms may be out of date.";
      if (row.cycle_basis === "entry_year" && row.entry_year != null) {
        return {
          tone: "amber",
          text: `${lead} The page we read described ${entryWord(row)} entry, which has passed.${readSentence}`,
        };
      }
      if (row.cycle_basis === "milestone_dates" && row.cycle_through_date) {
        return {
          tone: "amber",
          text: `${lead} The dates on the page ran through ${formatMonthYear(row.cycle_through_date)}, which have passed.${readSentence}`,
        };
      }
      return {
        tone: "amber",
        text: read
          ? `${lead} The page we read on ${read} named no year, and a newer cycle has begun.`
          : `${lead} The page we read named no year, and a newer cycle has begun.`,
      };
    }
    case "current_cycle_unconfirmed":
      return {
        tone: "plain",
        text: read
          ? `These terms have not been re-read for this cycle. Last read ${read}.`
          : "These terms have not been re-read for this cycle.",
      };
    case "year_not_stated":
      return {
        tone: "plain",
        text: read
          ? `The school's page does not name a year. We read it ${read}.`
          : "The school's page does not name a year.",
      };
    case "current_cycle_verified":
    default: {
      if (row.cycle_basis === "entry_year" && row.entry_year != null) {
        return {
          tone: "plain",
          text: published
            ? `Terms for ${entryWord(row)} entry, as published on the school's page ${published}.`
            : `Terms for ${entryWord(row)} entry, as published on the school's page.`,
        };
      }
      if (row.cycle_basis === "milestone_dates" && row.cycle_through_date) {
        return {
          tone: "plain",
          text: `The dates on the school's page run through ${formatMonthYear(row.cycle_through_date)}. The page does not name the entering class.${readSentence}`,
        };
      }
      return {
        tone: "plain",
        text: read
          ? `The school's page does not name a year. We read it ${read}.`
          : "The school's page does not name a year.",
      };
    }
  }
}

/** Short form for the index table's last column. */
export function freshnessShort(row: FreshnessInput): { tone: "plain" | "amber"; text: string } {
  switch (row.freshness_status) {
    case "conflicting": return { tone: "amber", text: "Pages disagree" };
    case "past_cycle": return { tone: "amber", text: "Past cycle" };
    case "current_cycle_unconfirmed": return { tone: "plain", text: "Not re-read" };
    case "year_not_stated": return { tone: "plain", text: "No year stated" };
    default:
      if (row.cycle_basis === "entry_year" && row.entry_year != null) {
        return { tone: "plain", text: `Entry ${row.entry_year}` };
      }
      if (row.cycle_basis === "milestone_dates" && row.cycle_through_date) {
        return { tone: "plain", text: `Dates through ${formatMonthYear(row.cycle_through_date)}` };
      }
      return { tone: "plain", text: "No year stated" };
  }
}

// ------------------------------------------------------ coverage summary

const CATEGORY_LABEL: Record<string, string> = {
  tuition: "Tuition",
  mandatory_fees: "Mandatory fees",
  housing: "Housing",
  meals: "Meals",
  books: "Books",
  laptop: "Laptop",
  stipend: "Stipend",
  study_abroad: "Study abroad",
  enrichment: "Enrichment",
  health_insurance: "Health insurance",
  cost_of_attendance: "Cost of attendance",
  nonresident_differential: "Nonresident tuition differential",
  other: "Other",
};

export type BenefitLine = {
  label: string;
  text: string;
  /** How the line is flagged in the card. */
  flags: { waiver: boolean; capped: boolean; conditional: boolean };
  scope: string | null;
  quotedLabel: string | null;
};

/** One benefit component in words. Waivers, caps and conditions are always named. */
export function benefitLine(b: Benefit): BenefitLine {
  const label = CATEGORY_LABEL[b.category] ?? "Other";
  const amount = amountText(b.amount);
  const waiver = b.instrument === "tuition_waiver";
  const capped =
    b.amount?.qualifier === "up_to" ||
    (b.coverage === "full" && b.amount?.qualifier === "approximate");
  const conditional = Boolean(b.conditions_text);

  let text: string;
  if (waiver) {
    text = `waiver, not a scholarship${amount ? `. ${capFirst(amount)}` : ""}.`;
  } else if (capped && amount) {
    text = `capped. ${capFirst(amount)}.`;
  } else if (amount) {
    text = `${amount}.`;
  } else if (b.coverage === "full") {
    text = "the school says it covers all of it.";
  } else if (b.coverage === "partial") {
    text = "covers part of it.";
  } else if (b.coverage === "variable") {
    text = "amount varies.";
  } else {
    text = "amount not published.";
  }
  if (conditional) text += ` Condition: ${trimStop(b.conditions_text as string)}.`;
  return {
    label,
    text,
    flags: { waiver, capped: capped && !waiver, conditional },
    scope: b.scope_text?.trim() || null,
    quotedLabel: b.advertised_coverage_label?.trim() || null,
  };
}

function capFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
function trimStop(s: string): string {
  return s.trim().replace(/[.\s]+$/, "");
}

export type OfferSummary = {
  offerId: string;
  variantName: string | null;
  parentName: string | null;
  benefits: BenefitLine[];
  /** The school's own quoted totals, with scope. Never a sum we made. */
  quotedTotals: { quote: string; scope: string | null }[];
  documented: boolean;
};

/** The coverage summary for one offer. A tier lists only what it adds, so it names its parent. */
export function coverageSummary(offer: Offer, all: Offer[]): OfferSummary {
  const parent = offer.parent_offer_id ? all.find((o) => o.offer_id === offer.parent_offer_id) : undefined;
  const benefits = (offer.benefits ?? []).map(benefitLine);
  const quotedTotals: OfferSummary["quotedTotals"] = [];
  for (const t of offer.advertised_totals ?? []) {
    const quote = amountText(t.amount);
    if (quote) quotedTotals.push({ quote, scope: t.scope_text?.trim() || null });
  }
  return {
    offerId: offer.offer_id,
    variantName: offer.variant_name?.trim() || null,
    parentName: parent ? parent.variant_name?.trim() || "the main package" : null,
    benefits,
    quotedTotals,
    documented: benefits.length > 0 || quotedTotals.length > 0,
  };
}

// ----------------------------------------------------- considered / need

const NM_LABEL: Record<string, string> = {
  semifinalist: "semifinalist",
  finalist: "finalist",
  commended: "commended",
};

/** How you are considered. "Considered" and "automatic" are different sentences on purpose. */
export function consideredLines(offer: Offer): string[] {
  const lines: string[] = [];
  switch (offer.selection_mode) {
    case "automatic_guaranteed":
      lines.push("Automatic if you meet the listed requirements, as the school says.");
      break;
    case "competitive":
      lines.push("Competitive. The school selects recipients.");
      break;
    case "hybrid":
      lines.push("Part automatic, part competitive.");
      break;
    default:
      lines.push("How recipients are chosen is not stated.");
  }
  const route: Record<string, string> = {
    admission_application: "You are considered through your admission application.",
    separate_application: "Separate application required.",
    honors_application: "Considered through the honors application.",
    nomination: "By nomination.",
    invitation: "By invitation.",
    multiple: "More than one route; see the school's page.",
  };
  if (offer.consideration_route && route[offer.consideration_route]) lines.push(route[offer.consideration_route]);
  const nm = (offer.eligibility?.national_merit_statuses ?? []).map((s) => NM_LABEL[s]).filter(Boolean);
  if (nm.length) lines.push(`National Merit ${nm.join(" or ")}.`);
  const need: Record<string, string> = {
    required: "Financial need is required.",
    considered: "Financial need is considered.",
    not_considered: "Financial need is not considered.",
    top_up_only: "Need only tops up the award.",
    unknown: "The page does not say whether need matters.",
  };
  if (offer.need_role && need[offer.need_role]) lines.push(need[offer.need_role]);
  if (offer.funds_limited === true) lines.push("Funds are limited.");
  return lines;
}

const RESIDENCY: Record<string, string> = {
  in_state: "in-state students",
  out_of_state: "out-of-state students",
  international: "international students",
  any: "all residencies",
};

export function residencyLine(offer: Offer): string | null {
  const w = offer.residency ? RESIDENCY[offer.residency] : null;
  return w ? `Open to ${w}.` : null;
}

const SEPARATE_APP: Record<string, string> = {
  required: "Separate application: required.",
  encouraged: "Separate application: encouraged.",
  not_required: "Separate application: not required.",
  invitation_only: "Separate application: by invitation only.",
  no_form_other_steps_required: "No separate form, but other steps are required (a visit or interview).",
  unknown: "Separate application: not stated.",
};

export function applicationLines(app: Application): string[] {
  if (!app) return [];
  const lines: string[] = [];
  if (app.separate_application && SEPARATE_APP[app.separate_application]) {
    lines.push(SEPARATE_APP[app.separate_application]);
  }
  const mode: Record<string, string> = {
    in_person: "Interview: in person.",
    virtual: "Interview: virtual.",
    either: "Interview: in person or virtual.",
    mixed: "Interview: varies.",
    unknown: "Interview: not stated.",
  };
  if (app.interview_mode && mode[app.interview_mode]) lines.push(mode[app.interview_mode]);
  return lines;
}

// -------------------------------------------------------------- deadlines

const KIND_LABEL: Record<string, string> = {
  application_deadline: "Application deadline",
  admission_deadline: "Admission deadline",
  supporting_materials_deadline: "Supporting materials deadline",
  test_score_deadline: "Test score deadline",
  acceptance_deadline: "Acceptance deadline",
  notification: "Notification",
};

const REQ_WORD: Record<string, string> = {
  required: "Required deadline",
  priority: "Priority deadline",
};

export type DeadlineLine = { text: string; past: boolean };

/**
 * The key deadline, never rolled forward. A dated deadline prints with its
 * entry year only when the page states one; a recurring month/day prints as
 * recurring with no year.
 */
export function deadlineLine(
  row: Pick<ScholarshipDirectoryRow, "key_deadline" | "entry_year" | "entry_terms" | "application">,
  today: string,
): DeadlineLine {
  if (row.key_deadline) {
    const ms = (row.application?.milestones ?? []).find((m) => m.date === row.key_deadline);
    const label = (ms && REQ_WORD[ms.requirement]) ?? "Deadline";
    const entry = row.entry_year != null ? `, for ${entryWord(row)} entry` : "";
    const named = row.entry_year != null ? "" : " The page does not name the entering class.";
    const past = row.key_deadline < today;
    return {
      text: `${label}: ${formatDay(row.key_deadline)}${entry}.${named} Confirm on the official page.`,
      past,
    };
  }
  const recurring = (row.application?.milestones ?? []).find(
    (m) => m.recurring && (m.requirement === "required" || m.requirement === "priority"),
  );
  if (recurring?.recurring) {
    const label = KIND_LABEL[recurring.kind] ?? "Date";
    return {
      text: `${label}: ${MONTHS[recurring.recurring.month - 1]} ${recurring.recurring.day} each year. The page names no year, so no date is shown. Confirm on the official page.`,
      past: false,
    };
  }
  return { text: "No deadline stated on the page we read.", past: false };
}

/** Deadline cell for the index table: a date, "Each November", or "Not stated". */
export function deadlineCell(
  row: Pick<ScholarshipDirectoryRow, "key_deadline" | "application">,
): string {
  if (row.key_deadline) return formatDay(row.key_deadline);
  const recurring = (row.application?.milestones ?? []).find(
    (m) => m.recurring && (m.requirement === "required" || m.requirement === "priority"),
  );
  if (recurring?.recurring) return `Each ${MONTHS[recurring.recurring.month - 1]}`;
  return "Not stated";
}

// ---------------------------------------------------------------- renewal

export function renewalSummary(rules: RenewalRule[] | null): string[] {
  if (rules === null) return ["Renewal terms not documented."];
  if (rules.length === 0) return ["The school's page lists no renewal conditions."];
  return rules.map((r) => {
    const parts: string[] = [];
    if (r.gpa_min != null) {
      parts.push(`Keep a ${r.gpa_min.toFixed(2).replace(/0$/, "")} GPA${r.gpa_scale ? ` on a ${r.gpa_scale} scale` : ""}`);
    } else {
      parts.push("GPA minimum not stated");
    }
    if (r.credit_load_min_per_term != null) parts.push(`${r.credit_load_min_per_term} credits a term`);
    else if (r.credit_load_min_per_year != null) parts.push(`${r.credit_load_min_per_year} credits a year`);
    if (r.max_semesters != null) parts.push(`up to ${r.max_semesters} semesters`);
    let text = `${parts.join(", ")}.`;
    if (r.evaluation_timing) text += ` ${capFirst(trimStop(r.evaluation_timing))}.`;
    if (r.summer_courses_can_fix_shortfall === true) text += " Summer courses can make up a shortfall.";
    if (r.summer_courses_can_fix_shortfall === false) text += " Summer courses do not make up a shortfall.";
    return text;
  });
}

// ----------------------------------------------------- stacking and counts

const AID_TYPE: Record<string, string> = {
  tuition_waiver: "a tuition waiver",
  outside_scholarship: "outside scholarships",
  institutional_merit: "other institutional merit awards",
  federal_or_state_need: "federal or state need-based aid",
  other: "other aid",
};

export function stackingLines(rules: StackingRule[] | null): string[] {
  const lines = (rules ?? []).map((r) => {
    const what = AID_TYPE[r.other_aid_type] ?? "other aid";
    switch (r.relation) {
      case "allowed": return `Can be combined with ${what}.`;
      case "not_allowed": return `Cannot be combined with ${what}.`;
      case "replaces": return `Replaces ${what}.`;
      case "counts_within_package": return `Counts within the package for ${what}.`;
      default: return `Stacking with ${what}: see the school's page.`;
    }
  });
  return Array.from(new Set(lines)); // a record may list the same rule per source; say it once
}

export function awardCountLines(counts: AwardCount[]): string[] {
  return counts
    .filter((c) => c.value != null)
    .map((c) => {
      const metric =
        c.metric === "new_recipients" ? "new recipients" :
        c.metric === "share_of_class" ? "of the class" : "offers";
      const q = c.qualifier === "approximate" ? "about " : c.qualifier === "up_to" ? "up to " : c.qualifier === "at_least" ? "at least " : "";
      const claim = c.claim === "target" ? "the school's target" : c.claim === "actual" ? "as the school reported it" : null;
      const year = c.cohort_year != null ? `, ${c.cohort_year}` : "";
      const unit = c.metric === "share_of_class" ? `${q}${c.value}% ${metric}` : `${q}${c.value} ${metric}`;
      return `${capFirst(unit)}${claim ? ` (${claim})` : ""}${year}. This is not the odds of receiving it.`;
    });
}

// ------------------------------------------------ program-level wording

export function statusChip(row: Pick<ScholarshipDirectoryRow, "program_status" | "program_status_for_entry">): string | null {
  const s = row.program_status_for_entry ?? row.program_status;
  switch (s) {
    case "closed_to_new_entrants": return "Closed to new entrants";
    case "paused": return "Paused";
    case "merged": return "Merged into another program";
    case "discontinued": return "Discontinued";
    case "unknown": return "Status not stated";
    default: return null;
  }
}

export function authorityLine(authority: string): string | null {
  switch (authority) {
    case "affiliated_foundation": return "Offered by a foundation tied to the school. The foundation's page is the source.";
    case "state_program": return "Offered with a state program.";
    case "cofunded": return "Funded jointly by the school and a partner.";
    default: return null;
  }
}

const RELATION: Record<string, string> = {
  component_of: "Part of",
  includes: "Includes",
  replaces: "Replaces",
  successor_to: "Successor to",
  mutually_exclusive_with: "Cannot be held together with",
};

export function humanizeId(id: string): string {
  return id
    .split("-")
    .map((w) => (w.length ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

export function relatedLines(
  row: Pick<ScholarshipDirectoryRow, "related_programs">,
  namesById: Record<string, string>,
): string[] {
  return row.related_programs
    .filter((r) => RELATION[r.relation])
    .map((r) => `${RELATION[r.relation]} ${namesById[r.program_id] ?? humanizeId(r.program_id)}`);
}

export function sourceLabel(authority: string): string {
  if (authority === "foundation_official") return "Foundation's page ↗";
  if (authority === "archived_official") return "Archived copy ↗";
  return "Official page ↗";
}

// ---------------------------------------------------------------- filters

export const COVERAGE_LABEL: Record<string, string> = {
  full_tuition: "Full tuition",
  full_tuition_fees: "Full tuition and fees",
  tuition_housing_meals: "Tuition, housing and meals",
  full_school_coa: "Full cost of attendance",
  partial_or_fixed: "Partial or fixed amount",
  other: "Other or not stated",
};

export const SELECTION_LABEL: Record<string, string> = {
  competitive: "Competitive",
  automatic_guaranteed: "Automatic if you qualify",
  hybrid: "Part automatic and competitive",
};

export const SEPARATE_APP_LABEL: Record<string, string> = {
  required: "Required",
  encouraged: "Encouraged",
  not_required: "Not required",
  invitation_only: "By invitation only",
  no_form_other_steps_required: "No form but other steps",
};

export const RESIDENCY_LABEL: Record<string, string> = {
  in_state: "In-state",
  out_of_state: "Out-of-state",
  international: "International",
  any: "Any residency",
};

export type ScholarshipFilters = {
  coverage: string;
  selection: string;
  nationalMerit: string;
  separateApplication: string;
  deadlineMonth: string;
  residency: string;
  school: string;
};

export const EMPTY_FILTERS: ScholarshipFilters = {
  coverage: "", selection: "", nationalMerit: "", separateApplication: "",
  deadlineMonth: "", residency: "", school: "",
};

export type ScholarshipSort = "school" | "deadline" | "coverage";

export type IndexRow = ScholarshipDirectoryRow & { school_name: string };

export function filterRows(rows: IndexRow[], f: ScholarshipFilters): IndexRow[] {
  const q = f.school.trim().toLowerCase();
  return rows.filter((r) => {
    if (f.coverage && !r.coverages.includes(f.coverage)) return false;
    if (f.selection && !r.selection_modes.includes(f.selection)) return false;
    if (f.nationalMerit && !r.national_merit_statuses.includes(f.nationalMerit)) return false;
    if (f.separateApplication && r.separate_application !== f.separateApplication) return false;
    if (f.deadlineMonth && !r.deadline_months.includes(Number(f.deadlineMonth))) return false;
    if (f.residency && !r.residencies.includes(f.residency)) return false;
    if (q && !r.school_name.toLowerCase().includes(q)) return false;
    return true;
  });
}

/** Sort by a factual field. Never by "best" or by generosity. Ties fall back to school then program name. */
export function sortRows(rows: IndexRow[], by: ScholarshipSort): IndexRow[] {
  const tie = (a: IndexRow, b: IndexRow) =>
    a.school_name.localeCompare(b.school_name) || a.official_name.localeCompare(b.official_name);
  const out = [...rows];
  if (by === "deadline") {
    out.sort((a, b) => {
      if (a.key_deadline && b.key_deadline) return a.key_deadline.localeCompare(b.key_deadline) || tie(a, b);
      if (a.key_deadline) return -1;
      if (b.key_deadline) return 1;
      return tie(a, b);
    });
  } else if (by === "coverage") {
    // Grouped by coverage label, alphabetically. A grouping, not a ranking.
    const key = (r: IndexRow) => [...r.coverages].map((c) => COVERAGE_LABEL[c] ?? c).sort()[0] ?? "~";
    out.sort((a, b) => key(a).localeCompare(key(b)) || tie(a, b));
  } else {
    out.sort(tie);
  }
  return out;
}

// ------------------------------------------------------ type counts

export type SchoolControl = "public" | "private_nonprofit" | "private_for_profit" | "unknown";

export const CONTROL_LABEL: Record<SchoolControl, string> = {
  public: "Public",
  private_nonprofit: "Private nonprofit",
  private_for_profit: "Private for-profit",
  unknown: "Not classified",
};

/**
 * Programs by school type. Each program counts once, by its lead school
 * (first of participating_school_ids), so a shared program is not counted twice.
 */
export function countProgramsByControl(
  rows: Pick<ScholarshipDirectoryRow, "program_id" | "participating_school_ids" | "school_id">[],
  controlOf: (schoolId: string) => SchoolControl,
): Record<SchoolControl, number> {
  const counts: Record<SchoolControl, number> = { public: 0, private_nonprofit: 0, private_for_profit: 0, unknown: 0 };
  const seen = new Set<string>();
  for (const r of rows) {
    if (seen.has(r.program_id)) continue;
    seen.add(r.program_id);
    counts[controlOf(r.participating_school_ids[0] ?? r.school_id)] += 1;
  }
  return counts;
}
