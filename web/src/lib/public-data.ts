import { supabase, STORAGE_BASE_URL } from "./supabase";
import {
  fetchInstitutionCoverage,
  fetchSchoolDocuments,
  fetchSchoolFederalFacts,
  fetchScorecardByIpedsId,
} from "./queries";
import type { InstitutionCoverage, ManifestRow, SchoolFactUnifiedRow } from "./types";

const SITE_URL = "https://www.collegedata.fyi";

type UntypedSupabase = {
  from: (table: string) => any;
  rpc: (fn: string, args?: Record<string, unknown>) => any;
};

export type PublicFactCategory =
  | "identity"
  | "admissions"
  | "enrollment"
  | "cost"
  | "aid"
  | "outcomes"
  | "sources";

export type PublicSourceLayer = "cds" | "ipeds" | "scorecard" | "derived" | "directory";

export type PublicFactQualityFlag =
  | "reported"
  | "derived"
  | "imputed"
  | "provisional"
  | "definition_mismatch"
  | "not_reported"
  | "not_available"
  | "low_confidence_extract";

export type PublicFact = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  display_value: string;
  unit: string | null;
  category: PublicFactCategory;
  source: {
    layer: PublicSourceLayer;
    name?: string;
    url?: string | null;
    archive_url?: string | null;
    data_year?: number | null;
    canonical_year?: string | null;
    release_type?: string | null;
    source_table?: string | null;
    source_variable?: string | null;
    field_ids?: string[];
    derivation?: string | null;
    imputation_label?: string | null;
    definition_alignment?: string | null;
  } | null;
  quality: {
    flag: PublicFactQualityFlag;
    note: string | null;
  };
};

export type PublicFieldDefinition = {
  key: string;
  label: string;
  category: PublicFactCategory;
  source_layer: PublicSourceLayer | "mixed";
  unit: string | null;
  value_type: "string" | "number" | "boolean" | "percent" | "money";
  definition: string;
  source_fields?: string[];
  derivation_note?: string | null;
  caveat?: string | null;
};

type FactDefinitionInput = PublicFieldDefinition & {
  path?: string;
};

export const FRIENDLY_FACT_FIELDS: FactDefinitionInput[] = [
  {
    key: "city",
    label: "City",
    category: "identity",
    source_layer: "directory",
    unit: null,
    value_type: "string",
    definition: "Institution city from the public institution directory.",
    path: "coverage.city",
  },
  {
    key: "state",
    label: "State",
    category: "identity",
    source_layer: "directory",
    unit: null,
    value_type: "string",
    definition: "Institution state abbreviation from the public institution directory.",
    path: "coverage.state",
  },
  {
    key: "coverage_status",
    label: "CDS coverage status",
    category: "identity",
    source_layer: "directory",
    unit: null,
    value_type: "string",
    definition: "CollegeData.FYI public coverage status for the school's Common Data Set availability.",
    path: "coverage.coverage_status",
  },
  {
    key: "undergraduate_enrollment",
    label: "Undergraduate enrollment",
    category: "enrollment",
    source_layer: "directory",
    unit: "students",
    value_type: "number",
    definition: "Directory-level undergraduate enrollment used for coverage and search pages.",
    path: "coverage.undergraduate_enrollment",
  },
  {
    key: "applied",
    label: "Applicants",
    category: "admissions",
    source_layer: "cds",
    unit: "applicants",
    value_type: "number",
    definition: "Total first-time, first-year applicants reported in the Common Data Set.",
    source_fields: ["C.116"],
    path: "browser.applied",
  },
  {
    key: "admitted",
    label: "Admitted",
    category: "admissions",
    source_layer: "cds",
    unit: "students",
    value_type: "number",
    definition: "Total first-time, first-year admitted students reported in the Common Data Set.",
    source_fields: ["C.117"],
    path: "browser.admitted",
  },
  {
    key: "enrolled_first_year",
    label: "Enrolled first-year students",
    category: "admissions",
    source_layer: "cds",
    unit: "students",
    value_type: "number",
    definition: "Total enrolled first-time, first-year students reported in the Common Data Set.",
    source_fields: ["C.120"],
    path: "browser.enrolled_first_year",
  },
  {
    key: "acceptance_rate",
    label: "Acceptance rate",
    category: "admissions",
    source_layer: "derived",
    unit: "percent",
    value_type: "percent",
    definition: "Admitted students divided by applicants.",
    source_fields: ["C.116", "C.117"],
    derivation_note: "Derived from the CDS applicants and admitted counts.",
    path: "browser.acceptance_rate",
  },
  {
    key: "yield_rate",
    label: "Yield rate",
    category: "admissions",
    source_layer: "derived",
    unit: "percent",
    value_type: "percent",
    definition: "Enrolled first-year students divided by admitted students.",
    source_fields: ["C.117", "C.120"],
    derivation_note: "Derived from the CDS admitted and enrolled counts.",
    path: "browser.yield_rate",
  },
  {
    key: "sat_composite_p50",
    label: "SAT composite midpoint",
    category: "admissions",
    source_layer: "cds",
    unit: "score",
    value_type: "number",
    definition: "Midpoint SAT composite score from the CDS testing section.",
    source_fields: ["C.905", "C.908"],
    path: "browser.sat_composite_p50",
  },
  {
    key: "act_composite_p50",
    label: "ACT composite midpoint",
    category: "admissions",
    source_layer: "cds",
    unit: "score",
    value_type: "number",
    definition: "Midpoint ACT composite score from the CDS testing section.",
    source_fields: ["C.930"],
    path: "browser.act_composite_p50",
  },
  {
    key: "sat_submit_rate",
    label: "SAT submit rate",
    category: "admissions",
    source_layer: "cds",
    unit: "percent",
    value_type: "percent",
    definition: "Share of enrolled first-year students submitting SAT scores.",
    source_fields: ["C.907"],
    path: "browser.sat_submit_rate",
  },
  {
    key: "act_submit_rate",
    label: "ACT submit rate",
    category: "admissions",
    source_layer: "cds",
    unit: "percent",
    value_type: "percent",
    definition: "Share of enrolled first-year students submitting ACT scores.",
    source_fields: ["C.930"],
    path: "browser.act_submit_rate",
  },
  {
    key: "ed_offered",
    label: "Early Decision offered",
    category: "admissions",
    source_layer: "cds",
    unit: null,
    value_type: "boolean",
    definition: "Whether the CDS reports an Early Decision plan.",
    source_fields: ["C.2101"],
    path: "browser.ed_offered",
  },
  {
    key: "ed_applicants",
    label: "Early Decision applicants",
    category: "admissions",
    source_layer: "cds",
    unit: "applicants",
    value_type: "number",
    definition: "Number of Early Decision applicants reported in the CDS.",
    source_fields: ["C.2110"],
    path: "browser.ed_applicants",
  },
  {
    key: "ed_admitted",
    label: "Early Decision admitted",
    category: "admissions",
    source_layer: "cds",
    unit: "students",
    value_type: "number",
    definition: "Number of Early Decision admitted students reported in the CDS.",
    source_fields: ["C.2111"],
    path: "browser.ed_admitted",
  },
  {
    key: "ea_offered",
    label: "Early Action offered",
    category: "admissions",
    source_layer: "cds",
    unit: null,
    value_type: "boolean",
    definition: "Whether the CDS reports an Early Action plan.",
    source_fields: ["C.2201"],
    path: "browser.ea_offered",
  },
  {
    key: "wait_list_offered",
    label: "Wait-list offered",
    category: "admissions",
    source_layer: "cds",
    unit: "students",
    value_type: "number",
    definition: "Number of applicants offered a place on the wait list.",
    source_fields: ["C.2101"],
    path: "browser.wait_list_offered",
  },
  {
    key: "avg_net_price",
    label: "Average net price",
    category: "cost",
    source_layer: "scorecard",
    unit: "USD",
    value_type: "money",
    definition: "Average annual net price from the federal College Scorecard.",
    source_fields: ["avg_net_price"],
    path: "scorecard.avg_net_price",
  },
  {
    key: "net_price_0_30k",
    label: "Net price for $0-30k income",
    category: "cost",
    source_layer: "scorecard",
    unit: "USD",
    value_type: "money",
    definition: "Average net price for families with $0-30k income from College Scorecard.",
    source_fields: ["net_price_0_30k"],
    path: "scorecard.net_price_0_30k",
  },
  {
    key: "pell_grant_rate",
    label: "Pell Grant share",
    category: "aid",
    source_layer: "scorecard",
    unit: "percent",
    value_type: "percent",
    definition: "Share of undergraduates receiving Pell Grants from College Scorecard.",
    source_fields: ["pell_grant_rate"],
    path: "scorecard.pell_grant_rate",
  },
  {
    key: "federal_loan_rate",
    label: "Federal loan share",
    category: "aid",
    source_layer: "scorecard",
    unit: "percent",
    value_type: "percent",
    definition: "Share of undergraduates taking federal loans from College Scorecard.",
    source_fields: ["federal_loan_rate"],
    path: "scorecard.federal_loan_rate",
  },
  {
    key: "non_need_aid_share_first_year_ft",
    label: "First-year non-need aid share",
    category: "aid",
    source_layer: "cds",
    unit: "percent",
    value_type: "percent",
    definition: "Share of first-year full-time students receiving non-need institutional grant aid.",
    source_fields: ["H.2A"],
    path: "merit.non_need_aid_share_first_year_ft",
    caveat: "CDS H2A excludes some mixed-need merit awards and can understate full merit-aid availability.",
  },
  {
    key: "avg_non_need_grant_first_year_ft",
    label: "Average first-year non-need grant",
    category: "aid",
    source_layer: "cds",
    unit: "USD",
    value_type: "money",
    definition: "Average institutional non-need scholarship/grant for first-year full-time recipients.",
    source_fields: ["H.2A"],
    path: "merit.avg_non_need_grant_first_year_ft",
  },
  {
    key: "retention_rate_ft",
    label: "First-year retention rate",
    category: "outcomes",
    source_layer: "scorecard",
    unit: "percent",
    value_type: "percent",
    definition: "Full-time student retention rate from College Scorecard.",
    source_fields: ["retention_rate_ft"],
    path: "scorecard.retention_rate_ft",
  },
  {
    key: "graduation_rate_6yr",
    label: "Six-year graduation rate",
    category: "outcomes",
    source_layer: "scorecard",
    unit: "percent",
    value_type: "percent",
    definition: "Six-year graduation rate from College Scorecard.",
    source_fields: ["graduation_rate_6yr"],
    path: "scorecard.graduation_rate_6yr",
  },
  {
    key: "earnings_10yr_median",
    label: "Median earnings after 10 years",
    category: "outcomes",
    source_layer: "scorecard",
    unit: "USD",
    value_type: "money",
    definition: "Median earnings ten years after entry from College Scorecard.",
    source_fields: ["earnings_10yr_median"],
    path: "scorecard.earnings_10yr_median",
  },
  {
    key: "median_debt_completers",
    label: "Median debt for completers",
    category: "outcomes",
    source_layer: "scorecard",
    unit: "USD",
    value_type: "money",
    definition: "Median federal debt for completers from College Scorecard.",
    source_fields: ["median_debt_completers"],
    path: "scorecard.median_debt_completers",
  },
];

const FIELD_BY_KEY = new Map(FRIENDLY_FACT_FIELDS.map((field) => [field.key, field]));

export function publicFieldDefinitions(): PublicFieldDefinition[] {
  return FRIENDLY_FACT_FIELDS.map(({ path: _path, ...field }) => field);
}

export function fieldsForCategories(categories: PublicFactCategory[]): string[] {
  const wanted = new Set(categories);
  return FRIENDLY_FACT_FIELDS.filter((field) => wanted.has(field.category)).map((field) => field.key);
}

function normalizeNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const parsed = Number(String(value).replace(/[$,%\s,]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizePercent(value: unknown): number | null {
  const parsed = normalizeNumber(value);
  if (parsed == null) return null;
  return parsed > 1 ? parsed / 100 : parsed;
}

function formatValue(
  value: string | number | boolean | null,
  valueType: PublicFieldDefinition["value_type"],
): string {
  if (value == null) return "Not available";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (valueType === "percent" && typeof value === "number") {
    return `${(value * 100).toFixed(value * 100 < 10 ? 1 : 0)}%`;
  }
  if (valueType === "money" && typeof value === "number") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);
  }
  if (typeof value === "number") return new Intl.NumberFormat("en-US").format(value);
  return value;
}

function storageUrl(storagePath: string | null | undefined): string | null {
  if (!storagePath) return null;
  return `${STORAGE_BASE_URL}/${storagePath}`;
}

function latestPrimaryDoc(docs: ManifestRow[]): ManifestRow | null {
  return docs.find((doc) => doc.sub_institutional == null) ?? docs[0] ?? null;
}

function sourceForDefinition(
  definition: FactDefinitionInput,
  context: PublicSchoolContext,
): PublicFact["source"] {
  if (definition.source_layer === "directory") {
    return {
      layer: "directory",
      name: "CollegeData.FYI institution directory",
      url: `${SITE_URL}/schools/${context.schoolId}`,
    };
  }
  if (definition.source_layer === "scorecard") {
    return {
      layer: "scorecard",
      name: "College Scorecard",
      url: "https://collegescorecard.ed.gov/",
      data_year: scorecardYear(context.scorecard),
    };
  }
  const doc = latestPrimaryDoc(context.docs);
  if (definition.source_layer === "cds" || definition.source_layer === "derived") {
    return {
      layer: definition.source_layer,
      name: definition.source_layer === "derived" ? "Derived from Common Data Set" : "Common Data Set",
      url: doc?.source_url ?? null,
      archive_url: doc?.canonical_year ? `${SITE_URL}/schools/${context.schoolId}/${doc.canonical_year}` : null,
      canonical_year: doc?.canonical_year ?? null,
      field_ids: definition.source_fields,
      derivation: definition.derivation_note ?? null,
    };
  }
  return null;
}

function qualityForDefinition(
  definition: FactDefinitionInput,
  value: unknown,
  context: PublicSchoolContext,
): PublicFact["quality"] {
  if (
    definition.path?.startsWith("browser.") &&
    hasIncoherentAdmissionsCounts(context.browserRow) &&
    isAdmissionsCountKey(definition.path.split(".")[1])
  ) {
    return {
      flag: "low_confidence_extract",
      note: "The projected CDS admissions counts are internally inconsistent, so this field is withheld from the friendly API.",
    };
  }
  if (value == null) {
    const note =
      definition.source_layer === "cds" || definition.source_layer === "derived"
        ? "No public CDS-backed value is available for this field."
        : "No public value is available for this field.";
    return { flag: "not_available", note };
  }
  if (definition.source_layer === "derived") {
    return { flag: "derived", note: definition.derivation_note ?? null };
  }
  if (definition.source_layer === "cds") {
    const doc = latestPrimaryDoc(context.docs);
    return {
      flag: doc?.data_quality_flag && doc.data_quality_flag !== "ok" ? "low_confidence_extract" : "reported",
      note: definition.caveat ?? null,
    };
  }
  return { flag: "reported", note: definition.caveat ?? null };
}

function getByPath(context: PublicSchoolContext, path: string | undefined): unknown {
  if (!path) return null;
  const [scope, key] = path.split(".");
  if (
    scope === "browser" &&
    isAdmissionsCountKey(key) &&
    hasIncoherentAdmissionsCounts(context.browserRow)
  ) {
    return null;
  }
  if (scope === "coverage") return context.coverage?.[key as keyof InstitutionCoverage] ?? null;
  if (scope === "browser") return context.browserRow?.[key] ?? null;
  if (scope === "scorecard") return context.scorecard?.[key as keyof NonNullable<PublicSchoolContext["scorecard"]>] ?? null;
  if (scope === "merit") return context.meritRow?.[key] ?? null;
  return null;
}

function isAdmissionsCountKey(key: string | undefined): boolean {
  return key === "applied" || key === "admitted" || key === "enrolled_first_year";
}

function hasIncoherentAdmissionsCounts(row: BrowserRow | null): boolean {
  if (!row) return false;
  const applied = normalizeNumber(row.applied);
  const admitted = normalizeNumber(row.admitted);
  const enrolled = normalizeNumber(row.enrolled_first_year);
  return (
    (applied != null && admitted != null && admitted > applied) ||
    (admitted != null && enrolled != null && enrolled > admitted)
  );
}

function normalizeValue(
  raw: unknown,
  valueType: PublicFieldDefinition["value_type"],
): string | number | boolean | null {
  if (raw == null) return null;
  if (valueType === "boolean") return typeof raw === "boolean" ? raw : String(raw).toLowerCase() === "true";
  if (valueType === "percent") return normalizePercent(raw);
  if (valueType === "number" || valueType === "money") return normalizeNumber(raw);
  return String(raw);
}

function scorecardYear(scorecard: PublicSchoolContext["scorecard"]): number | null {
  const raw = scorecard?.scorecard_data_year;
  if (!raw) return null;
  const parsed = Number(String(raw).slice(0, 4));
  return Number.isFinite(parsed) ? parsed : null;
}

type BrowserRow = Record<string, any>;
type MeritRow = Record<string, any>;

type PublicSchoolContext = {
  schoolId: string;
  schoolName: string;
  docs: ManifestRow[];
  coverage: InstitutionCoverage | null;
  browserRow: BrowserRow | null;
  meritRow: MeritRow | null;
  scorecard: Awaited<ReturnType<typeof fetchScorecardByIpedsId>>;
  federalFacts: SchoolFactUnifiedRow[];
};

async function fetchBrowserFactsRow(schoolId: string): Promise<BrowserRow | null> {
  const { data, error } = await (supabase as unknown as UntypedSupabase)
    .from("school_browser_rows")
    .select(
      "document_id, school_id, school_name, canonical_year, year_start, source_format, data_quality_flag, archive_url, applied, admitted, enrolled_first_year, acceptance_rate, yield_rate, undergrad_enrollment_scorecard, scorecard_data_year, retention_rate, avg_net_price, pell_rate, sat_submit_rate, act_submit_rate, sat_composite_p25, sat_composite_p50, sat_composite_p75, act_composite_p25, act_composite_p50, act_composite_p75, ed_offered, ed_applicants, ed_admitted, ed_has_second_deadline, ea_offered, ea_restrictive, wait_list_policy, wait_list_offered, wait_list_accepted, wait_list_admitted, app_fee_amount, app_fee_waiver_offered",
    )
    .eq("school_id", schoolId)
    .gte("year_start", 2024)
    .is("sub_institutional", null)
    .order("year_start", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    console.warn(`fetchBrowserFactsRow: ${error.message}`);
    return null;
  }
  return data ?? null;
}

async function fetchMeritFactsRow(schoolId: string): Promise<MeritRow | null> {
  const { data, error } = await (supabase as unknown as UntypedSupabase)
    .from("school_merit_profile")
    .select(
      "school_id, school_name, canonical_year, archive_url, non_need_aid_share_first_year_ft, avg_non_need_grant_first_year_ft, merit_profile_quality",
    )
    .eq("school_id", schoolId)
    .limit(1)
    .maybeSingle();

  if (error) {
    console.warn(`fetchMeritFactsRow: ${error.message}`);
    return null;
  }
  return data ?? null;
}

async function buildSchoolContext(schoolId: string): Promise<PublicSchoolContext | null> {
  const [docs, coverage, browserRow, meritRow, federalFacts] = await Promise.all([
    fetchSchoolDocuments(schoolId),
    fetchInstitutionCoverage(schoolId),
    fetchBrowserFactsRow(schoolId),
    fetchMeritFactsRow(schoolId),
    fetchSchoolFederalFacts(schoolId),
  ]);

  if (docs.length === 0 && !coverage && !browserRow && federalFacts.length === 0) return null;

  const ipedsId =
    coverage?.ipeds_id ?? docs.find((doc) => doc.ipeds_id)?.ipeds_id ?? federalFacts[0]?.ipeds_id ?? null;
  const scorecard = await fetchScorecardByIpedsId(ipedsId);
  const schoolName =
    coverage?.school_name ?? docs[0]?.school_name ?? browserRow?.school_name ?? federalFacts[0]?.school_name ?? schoolId;

  return {
    schoolId,
    schoolName,
    docs,
    coverage,
    browserRow,
    meritRow,
    scorecard,
    federalFacts,
  };
}

function makeStaticFact(definition: FactDefinitionInput, context: PublicSchoolContext): PublicFact {
  const raw = getByPath(context, definition.path);
  const value = normalizeValue(raw, definition.value_type);
  return {
    key: definition.key,
    label: definition.label,
    value,
    display_value: formatValue(value, definition.value_type),
    unit: definition.unit,
    category: definition.category,
    source: value == null ? null : sourceForDefinition(definition, context),
    quality: qualityForDefinition(definition, value, context),
  };
}

function federalCategory(row: SchoolFactUnifiedRow): PublicFactCategory {
  const group = `${row.display_group} ${row.field_key} ${row.field_label}`.toLowerCase();
  if (group.includes("admission")) return "admissions";
  if (group.includes("cost") || group.includes("price") || group.includes("tuition")) return "cost";
  if (group.includes("aid") || group.includes("loan") || group.includes("pell")) return "aid";
  if (group.includes("completion") || group.includes("graduation") || group.includes("outcome")) return "outcomes";
  if (group.includes("enrollment")) return "enrollment";
  return "identity";
}

function makeFederalFact(row: SchoolFactUnifiedRow): PublicFact {
  const value = row.value_numeric ?? row.value_label ?? row.value_text ?? null;
  const isImputed = row.quality_flag === "imputed" || Boolean(row.imputation_label);
  const definitionMismatch =
    row.definition_alignment === "near" ||
    row.definition_alignment === "context_only" ||
    row.definition_alignment === "not_cds_equivalent";
  const flag: PublicFactQualityFlag = isImputed
    ? "imputed"
    : definitionMismatch
      ? "definition_mismatch"
      : row.release_type === "provisional"
        ? "provisional"
        : row.quality_flag === "reported"
          ? "reported"
          : "not_available";

  return {
    key: `ipeds.${row.field_key}`,
    label: row.field_label,
    value,
    display_value: row.display_value ?? formatValue(value, row.unit === "percent" ? "percent" : "string"),
    unit: row.unit,
    category: federalCategory(row),
    source: {
      layer: "ipeds",
      name: "NCES/IPEDS",
      url: "https://nces.ed.gov/ipeds/",
      data_year: row.data_year,
      release_type: row.release_type,
      source_table: row.source_table,
      source_variable: row.source_variable,
      imputation_label: row.imputation_label,
      definition_alignment: row.definition_alignment,
    },
    quality: {
      flag,
      note: row.definition_note ?? row.imputation_label ?? null,
    },
  };
}

export async function searchSchools(query: string, limit = 10) {
  const trimmed = query.trim();
  if (!trimmed) return { query, results: [] };
  const safeLimit = Math.min(Math.max(limit, 1), 25);
  const normalized = trimmed.toLowerCase();
  const exactCoverage = await fetchInstitutionCoverage(normalized);
  const { data, error } = await (supabase as unknown as UntypedSupabase).rpc("search_institutions", {
    p_query: trimmed,
    p_limit: safeLimit,
  });
  if (error) throw new Error(`search_institutions failed: ${error.message}`);
  const rows = (data ?? []) as Array<{
    school_id: string;
    school_name: string;
    city: string | null;
    state: string | null;
    coverage_status: string;
    latest_available_cds_year: string | null;
  }>;

  const rpcResults = await Promise.all(
    rows.map(async (row) => {
      const facts = await fetchSchoolFederalFacts(row.school_id);
      return {
        school_id: row.school_id,
        school_name: row.school_name,
        aliases: [],
        city: row.city,
        state: row.state,
        ipeds_id: facts[0]?.ipeds_id ?? null,
        coverage_status: row.coverage_status,
        has_cds: row.latest_available_cds_year != null,
        has_federal_baseline: facts.length > 0,
        school_url: `${SITE_URL}/schools/${row.school_id}`,
      };
    }),
  );
  const exactResult =
    exactCoverage && !rpcResults.some((row) => row.school_id === exactCoverage.school_id)
      ? [
          {
            school_id: exactCoverage.school_id,
            school_name: exactCoverage.school_name,
            aliases: [],
            city: exactCoverage.city,
            state: exactCoverage.state,
            ipeds_id: exactCoverage.ipeds_id,
            coverage_status: exactCoverage.coverage_status,
            has_cds: exactCoverage.latest_available_cds_year != null,
            has_federal_baseline: (await fetchSchoolFederalFacts(exactCoverage.school_id)).length > 0,
            school_url: `${SITE_URL}/schools/${exactCoverage.school_id}`,
          },
        ]
      : [];
  const results = [...exactResult, ...rpcResults].slice(0, safeLimit);

  return { query: trimmed, results };
}

export async function getSchoolFacts(
  schoolId: string,
  options: { categories?: PublicFactCategory[]; fields?: string[] } = {},
) {
  const context = await buildSchoolContext(schoolId);
  if (!context) return null;

  const categories = options.categories?.length ? new Set(options.categories) : null;
  const fields = options.fields?.length ? new Set(options.fields) : null;
  const staticFacts = FRIENDLY_FACT_FIELDS.map((definition) => makeStaticFact(definition, context));
  const federalFacts = context.federalFacts.map(makeFederalFact);
  const facts = [...staticFacts, ...federalFacts].filter((fact) => {
    if (fields && !fields.has(fact.key)) return false;
    if (categories && !categories.has(fact.category)) return false;
    return true;
  });

  return {
    school_id: context.schoolId,
    school_name: context.schoolName,
    generated_at: new Date().toISOString(),
    facts,
    sources: [
      {
        kind: "school_page",
        url: `${SITE_URL}/schools/${context.schoolId}`,
      },
      ...context.docs.slice(0, 5).map((doc) => ({
        kind: "cds_document",
        canonical_year: doc.canonical_year,
        source_url: doc.source_url,
        archive_url: doc.canonical_year ? `${SITE_URL}/schools/${context.schoolId}/${doc.canonical_year}` : null,
      })),
    ],
  };
}

export async function getSchoolSources(schoolId: string) {
  const [docs, coverage, federalFacts] = await Promise.all([
    fetchSchoolDocuments(schoolId),
    fetchInstitutionCoverage(schoolId),
    fetchSchoolFederalFacts(schoolId),
  ]);
  if (docs.length === 0 && !coverage && federalFacts.length === 0) return null;
  const schoolName = coverage?.school_name ?? docs[0]?.school_name ?? federalFacts[0]?.school_name ?? schoolId;
  return {
    school_id: schoolId,
    school_name: schoolName,
    generated_at: new Date().toISOString(),
    school_page_url: `${SITE_URL}/schools/${schoolId}`,
    coverage: coverage
      ? {
          status: coverage.coverage_status,
          label: coverage.coverage_label,
          latest_available_cds_year: coverage.latest_available_cds_year,
          last_checked_at: coverage.last_checked_at,
        }
      : null,
    cds_documents: docs.map((doc) => ({
      document_id: doc.document_id,
      canonical_year: doc.canonical_year,
      sub_institutional: doc.sub_institutional,
      source_url: doc.source_url,
      archived_source_url: storageUrl(doc.source_storage_path),
      archive_page_url: doc.canonical_year ? `${SITE_URL}/schools/${schoolId}/${doc.canonical_year}` : null,
      source_format: doc.source_format,
      source_provenance: (doc as ManifestRow & { source_provenance?: string | null }).source_provenance ?? null,
      extraction_status: doc.extraction_status,
      data_quality_flag: doc.data_quality_flag,
      discovered_at: doc.discovered_at,
      last_verified_at: doc.last_verified_at,
      removed_at: doc.removed_at,
    })),
    federal_sources: Array.from(
      new Map(
        federalFacts.map((fact) => [
          `${fact.source_layer}:${fact.source_table}:${fact.source_variable}:${fact.release_type}:${fact.data_year}`,
          {
            layer: fact.source_layer,
            name: "NCES/IPEDS",
            data_year: fact.data_year,
            collection_year: fact.collection_year,
            release_type: fact.release_type,
            source_table: fact.source_table,
            source_variable: fact.source_variable,
            source_title: fact.source_title,
            url: "https://nces.ed.gov/ipeds/",
          },
        ]),
      ).values(),
    ),
  };
}

export async function compareSchools(
  schoolIds: string[],
  options: { categories?: PublicFactCategory[]; fields?: string[] } = {},
) {
  const fieldKeys = options.fields?.length
    ? options.fields.filter((key) => FIELD_BY_KEY.has(key))
    : options.categories?.length
      ? fieldsForCategories(options.categories)
      : fieldsForCategories(["admissions", "cost", "aid", "outcomes"]);
  const uniqueSchoolIds = Array.from(new Set(schoolIds.map((id) => id.trim()).filter(Boolean))).slice(0, 25);
  const payloads = await Promise.all(
    uniqueSchoolIds.map((id) => getSchoolFacts(id, { fields: fieldKeys }).then((payload) => [id, payload] as const)),
  );
  const columns = fieldKeys.map((key) => {
    const definition = FIELD_BY_KEY.get(key)!;
    return {
      key,
      label: definition.label,
      category: definition.category,
      unit: definition.unit,
    };
  });
  const rows = payloads.map(([schoolId, payload]) => {
    const factMap = new Map((payload?.facts ?? []).map((fact) => [fact.key, fact]));
    return {
      school_id: schoolId,
      school_name: payload?.school_name ?? schoolId,
      values: Object.fromEntries(
        fieldKeys.map((key) => {
          const definition = FIELD_BY_KEY.get(key)!;
          const existing = factMap.get(key);
          return [
            key,
            existing ?? {
              key,
              label: definition.label,
              value: null,
              display_value: "Not available",
              unit: definition.unit,
              category: definition.category,
              source: null,
              quality: {
                flag: "not_available",
                note: "No public value is available for this requested field.",
              },
            },
          ];
        }),
      ),
    };
  });

  return {
    generated_at: new Date().toISOString(),
    schools: rows.map((row) => ({ school_id: row.school_id, school_name: row.school_name })),
    columns,
    rows,
  };
}
