import type { Metadata } from "next";
import Link from "next/link";
import { fetchSiteStats } from "@/lib/queries";
import { formatCount, formatShortDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "API",
  description:
    "Public REST API for the collegedata.fyi Common Data Set archive. PostgREST endpoints, anon key, and example queries.",
  alternates: { canonical: "/api" },
  openGraph: { url: "/api" },
};

const ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs";

const BASE = "https://api.collegedata.fyi";
const API_LINK_CLASS = "text-[var(--forest)] underline hover:text-[var(--forest-ink)]";
const API_LINK_SMALL_CLASS = "text-xs text-[var(--forest)] underline hover:text-[var(--forest-ink)]";

export const revalidate = 3600;

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="mt-2 overflow-x-auto rounded border border-gray-200 bg-gray-50 px-4 py-3 text-xs leading-relaxed text-gray-800">
      <code>{children}</code>
    </pre>
  );
}

export default async function ApiDocsPage() {
  const stats = await fetchSiteStats();
  const scorecardVintage = stats.scorecard_data_year ?? "the current published Scorecard vintage";

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 text-gray-800">
      <h1 className="text-3xl font-bold text-gray-900">API</h1>
      <p className="mt-3 text-base leading-relaxed text-gray-600">
        The full collegedata.fyi corpus is exposed as a public, read-only{" "}
        <a
          className={API_LINK_CLASS}
          href="https://postgrest.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          PostgREST
        </a>{" "}
        API at{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-sm">{BASE}</code>
        . Every page on this site is built from the same endpoints documented
        below.
      </p>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Authentication
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        All requests require a Supabase{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">anon</code>{" "}
        key passed as both an{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">apikey</code>{" "}
        query parameter and an{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
          Authorization
        </code>{" "}
        bearer header. The anon key is public and grants read-only access to
        the published views below.
      </p>
      <CodeBlock>{ANON_KEY}</CodeBlock>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Resources
      </h2>

      <div className="mt-4 space-y-6">
        <Resource
          name="cds_manifest"
          description="One row per archived CDS document. Joins schools, source URLs, format detection, and extraction status. Carries ipeds_id so federal-data joins are one query away."
          fields={[
            "school_id",
            "school_name",
            "ipeds_id",
            "canonical_year",
            "source_format",
            "source_url",
            "extraction_status",
            "data_quality_flag",
          ]}
          allFields={[
            "document_id",
            "school_id",
            "school_name",
            "ipeds_id",
            "sub_institutional",
            "cds_year",
            "detected_year",
            "canonical_year",
            "source_url",
            "source_format",
            "source_storage_path",
            "participation_status",
            "extraction_status",
            "data_quality_flag",
            "latest_canonical_artifact_id",
            "discovered_at",
            "last_verified_at",
            "removed_at",
          ]}
        />
        <Resource
          name="cds_artifacts"
          description="Raw extraction artifacts keyed by document. Most consumers should prefer cds_fields for field-level queries or the selected-result helper semantics documented below."
          fields={[
            "document_id",
            "kind",
            "producer",
            "notes",
            "created_at",
          ]}
          allFields={[
            "id",
            "document_id",
            "kind",
            "producer",
            "producer_version",
            "schema_version",
            "notes",
            "storage_path",
            "sha256",
            "created_at",
          ]}
        />
        <Resource
          name="cds_fields"
          description={`${formatCount(stats.queryable_field_count)} normalized field rows from selected 2024-25+ extraction results. Use this for direct canonical-field queries across schools; derived metrics such as acceptance_rate live in school_browser_rows/browser-search.`}
          fields={[
            "school_id",
            "school_name",
            "canonical_year",
            "field_id",
            "canonical_metric",
            "value_num",
            "value_text",
            "value_kind",
            "sub_institutional",
          ]}
          allFields={[
            "document_id",
            "school_id",
            "school_name",
            "sub_institutional",
            "ipeds_id",
            "canonical_year",
            "year_start",
            "schema_version",
            "field_id",
            "canonical_metric",
            "value_text",
            "value_num",
            "value_bool",
            "value_kind",
            "value_status",
            "source_format",
            "producer",
            "producer_version",
            "data_quality_flag",
            "archive_url",
            "updated_at",
          ]}
        />
        <Resource
          name="school_browser_rows"
          description={`${formatCount(stats.browser_primary_row_count)} primary 2024-25+ rows across ${formatCount(stats.browser_school_count)} schools, refreshed ${formatShortDate(stats.browser_updated_at)}. This is the curated serving layer for the website browser, CSV exports, and the per-school academic positioning and admission strategy cards.`}
          fields={[
            "school_id",
            "school_name",
            "canonical_year",
            "applied",
            "admitted",
            "acceptance_rate",
            "yield_rate",
            "ed_offered",
            "ed_applicants",
            "ed_admitted",
            "ea_offered",
            "avg_net_price",
            "sat_composite_p50",
          ]}
          allFields={[
            "document_id",
            "school_id",
            "school_name",
            "sub_institutional",
            "ipeds_id",
            "canonical_year",
            "year_start",
            "schema_version",
            "source_format",
            "producer",
            "producer_version",
            "data_quality_flag",
            "archive_url",
            "applied",
            "admitted",
            "enrolled_first_year",
            "acceptance_rate",
            "yield_rate",
            "undergrad_enrollment_scorecard",
            "scorecard_data_year",
            "retention_rate",
            "avg_net_price",
            "pell_rate",
            "sat_submit_rate",
            "act_submit_rate",
            "sat_composite_p25",
            "sat_composite_p50",
            "sat_composite_p75",
            "sat_ebrw_p25",
            "sat_ebrw_p50",
            "sat_ebrw_p75",
            "sat_math_p25",
            "sat_math_p50",
            "sat_math_p75",
            "act_composite_p25",
            "act_composite_p50",
            "act_composite_p75",
            "ed_offered",
            "ed_applicants",
            "ed_admitted",
            "ed_has_second_deadline",
            "ea_offered",
            "ea_restrictive",
            "wait_list_policy",
            "wait_list_offered",
            "wait_list_accepted",
            "wait_list_admitted",
            "c711_first_gen_factor",
            "c712_legacy_factor",
            "c713_geography_factor",
            "c714_state_residency_factor",
            "c718_demonstrated_interest_factor",
            "app_fee_amount",
            "app_fee_waiver_offered",
            "admission_strategy_card_quality",
            "updated_at",
          ]}
        />
        <Resource
          name="school_merit_profile"
          description="Latest primary 2024-25+ CDS Section H merit and need-aid facts per school, joined to selected College Scorecard affordability and outcome fields. Used by the school-page merit profile."
          fields={[
            "school_id",
            "school_name",
            "canonical_year",
            "first_year_ft_students",
            "non_need_aid_recipients_first_year_ft",
            "avg_non_need_grant_first_year_ft",
            "non_need_aid_share_first_year_ft",
            "avg_net_price",
            "graduation_rate_6yr",
          ]}
          allFields={[
            "document_id",
            "school_id",
            "school_name",
            "sub_institutional",
            "ipeds_id",
            "canonical_year",
            "year_start",
            "schema_version",
            "source_format",
            "producer",
            "producer_version",
            "data_quality_flag",
            "archive_url",
            "first_year_ft_students",
            "all_ft_undergrads",
            "need_grants_total",
            "non_need_grants_total",
            "aid_recipients_first_year_ft",
            "aid_recipients_all_ft",
            "avg_aid_package_first_year_ft",
            "avg_aid_package_all_ft",
            "avg_need_grant_first_year_ft",
            "avg_need_grant_all_ft",
            "avg_need_self_help_first_year_ft",
            "avg_need_self_help_all_ft",
            "non_need_aid_recipients_first_year_ft",
            "avg_non_need_grant_first_year_ft",
            "non_need_aid_recipients_all_ft",
            "avg_non_need_grant_all_ft",
            "non_need_aid_share_first_year_ft",
            "non_need_aid_share_all_ft",
            "institutional_need_aid_nonresident",
            "institutional_non_need_aid_nonresident",
            "avg_international_aid",
            "institutional_aid_academics",
            "cds_merit_core_count",
            "cds_merit_field_count",
            "merit_profile_quality",
            "scorecard_data_year",
            "earnings_6yr_median",
            "earnings_8yr_median",
            "earnings_10yr_median",
            "earnings_10yr_p25",
            "earnings_10yr_p75",
            "median_debt_completers",
            "median_debt_monthly_payment",
            "avg_net_price",
            "net_price_0_30k",
            "net_price_30k_48k",
            "net_price_48k_75k",
            "net_price_75k_110k",
            "net_price_110k_plus",
            "graduation_rate_6yr",
            "pell_grant_rate",
            "federal_loan_rate",
            "retention_rate_ft",
          ]}
        />
        <Resource
          name="cds_documents"
          description="Raw archive table — one row per (school, sub-institution, year). Most consumers should prefer cds_manifest."
          fields={[
            "id",
            "school_id",
            "ipeds_id",
            "cds_year",
            "detected_year",
            "participation_status",
            "source_sha256",
          ]}
          allFields={[
            "id",
            "school_id",
            "school_name",
            "ipeds_id",
            "sub_institutional",
            "cds_year",
            "detected_year",
            "source_url",
            "source_sha256",
            "source_format",
            "source_page_count",
            "source_provenance",
            "participation_status",
            "extraction_status",
            "data_quality_flag",
            "discovered_at",
            "last_verified_at",
            "removed_at",
            "created_at",
            "updated_at",
          ]}
        />
        <Resource
          name="cds_scorecard"
          description={`CDS manifest left-joined with the federal College Scorecard. One row per archived CDS document with post-graduation earnings, debt, net price by income bracket, completion rate, and retention attached. Currently joined to Scorecard ${scorecardVintage}.`}
          fields={[
            "school_name",
            "ipeds_id",
            "cds_year",
            "earnings_10yr_median",
            "median_debt_completers",
            "avg_net_price",
            "net_price_0_30k",
            "graduation_rate_6yr",
            "pell_grant_rate",
          ]}
          allFields={[
            // CDS side
            "document_id",
            "school_id",
            "school_name",
            "ipeds_id",
            "cds_year",
            "source_format",
            "source_storage_path",
            "extraction_status",
            "data_quality_flag",
            "latest_canonical_artifact_id",
            // Scorecard side
            "scorecard_data_year",
            "earnings_10yr_median",
            "earnings_10yr_p25",
            "earnings_10yr_p75",
            "median_debt_completers",
            "median_debt_monthly_payment",
            "avg_net_price",
            "net_price_0_30k",
            "net_price_30k_48k",
            "net_price_48k_75k",
            "net_price_75k_110k",
            "net_price_110k_plus",
            "graduation_rate_6yr",
            "grad_rate_pell",
            "repayment_rate_3yr",
            "default_rate_3yr",
            "pell_grant_rate",
            "federal_loan_rate",
            "first_generation_share",
            "median_family_income",
            "retention_rate_ft",
            "endowment_end",
            "instructional_expenditure_fte",
          ]}
        />
        <Resource
          name="scorecard_summary"
          description={`Curated federal College Scorecard subset, one row per IPEDS UNITID (${formatCount(stats.scorecard_institution_count)} institutions, not just CDS-archived ones). Refreshed ${formatShortDate(stats.scorecard_refreshed_at)} after the ${scorecardVintage} Scorecard load. For per-program earnings, race-stratified completion, or other fields beyond the curated subset, query Scorecard directly.`}
          fields={[
            "ipeds_id",
            "school_name",
            "scorecard_data_year",
            "earnings_10yr_median",
            "median_debt_completers",
            "avg_net_price",
            "graduation_rate_6yr",
            "endowment_end",
          ]}
          allFields={[
            // Identity
            "ipeds_id",
            "school_name",
            "scorecard_data_year",
            "refreshed_at",
            // Earnings (Treasury/IRS)
            "earnings_6yr_median",
            "earnings_8yr_median",
            "earnings_10yr_median",
            "earnings_10yr_p25",
            "earnings_10yr_p75",
            // Debt (NSLDS)
            "median_debt_completers",
            "median_debt_noncompleters",
            "median_debt_monthly_payment",
            "cumulative_debt_p90",
            "median_debt_pell",
            // Net price (IPEDS)
            "avg_net_price",
            "net_price_0_30k",
            "net_price_30k_48k",
            "net_price_48k_75k",
            "net_price_75k_110k",
            "net_price_110k_plus",
            // Completion
            "graduation_rate_4yr",
            "graduation_rate_6yr",
            "graduation_rate_8yr",
            "grad_rate_pell",
            "transfer_out_rate",
            // Repayment
            "repayment_rate_3yr",
            "default_rate_3yr",
            // Student profile
            "enrollment",
            "pell_grant_rate",
            "federal_loan_rate",
            "first_generation_share",
            "median_family_income",
            "female_share",
            "retention_rate_ft",
            // Institutional context
            "carnegie_basic",
            "locale",
            "historically_black",
            "predominantly_black",
            "hispanic_serving",
            "endowment_end",
            "instructional_expenditure_fte",
            "faculty_salary_avg",
          ]}
        />
      </div>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">Examples</h2>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Search the curated school browser
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        The browser uses an Edge Function so latest-per-school ranking can account
        for required fields and null answerability. Percent and rate values are
        stored as fractions from <code>0</code> to <code>1</code>.
      </p>
      <CodeBlock>{`curl '${BASE}/functions/v1/browser-search' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>' \\
  -H 'content-type: application/json' \\
  --data '{"mode":"latest_per_school","variant_scope":"primary_only","min_year_start":2024,"filters":[{"field":"acceptance_rate","op":"<=","value":0.1}],"page_size":10}'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch academic positioning data for one school
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        The academic positioning card reads the already-public{" "}
        <code>school_browser_rows</code> resource. SAT/ACT submit rates are stored
        as fractions, and the card links to{" "}
        <Link href="/methodology/positioning" className={API_LINK_CLASS}>
          its methodology
        </Link>{" "}
        instead of exposing a separate scoring endpoint.
      </p>
      <CodeBlock>{`curl '${BASE}/rest/v1/school_browser_rows?school_id=eq.bowdoin&select=school_id,school_name,canonical_year,acceptance_rate,sat_submit_rate,act_submit_rate,sat_composite_p25,sat_composite_p50,sat_composite_p75,act_composite_p25,act_composite_p50,act_composite_p75' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch admission strategy data for one school
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        Admission strategy fields are also served from{" "}
        <code>school_browser_rows</code>. ED counts are published when the CDS reports
        them; EA is limited to offered/restrictive flags because CDS C.22 does not
        include EA applicant or admit counts. The card methodology is documented at{" "}
        <Link href="/methodology/admission-strategy" className={API_LINK_CLASS}>
          /methodology/admission-strategy
        </Link>
        .
      </p>
      <CodeBlock>{`curl '${BASE}/rest/v1/school_browser_rows?school_id=eq.bowdoin&select=school_id,school_name,canonical_year,applied,admitted,yield_rate,ed_offered,ed_applicants,ed_admitted,ed_has_second_deadline,ea_offered,ea_restrictive,wait_list_policy,wait_list_offered,wait_list_accepted,wait_list_admitted,c711_first_gen_factor,c712_legacy_factor,c718_demonstrated_interest_factor,app_fee_amount,app_fee_waiver_offered,admission_strategy_card_quality' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch merit-aid context for one school
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        Merit profile data comes from <code>school_merit_profile</code>, a latest
        primary CDS Section H view joined to Scorecard affordability and outcome
        fields. H2A non-need award values are source-reported institutional facts,
        not personalized price estimates. The card methodology is documented at{" "}
        <Link href="/methodology/merit-profile" className={API_LINK_CLASS}>
          /methodology/merit-profile
        </Link>
        .
      </p>
      <CodeBlock>{`curl '${BASE}/rest/v1/school_merit_profile?school_id=eq.bowdoin&select=school_id,school_name,canonical_year,first_year_ft_students,non_need_aid_recipients_first_year_ft,avg_non_need_grant_first_year_ft,non_need_aid_share_first_year_ft,avg_net_price,graduation_rate_6yr,earnings_10yr_median' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        List the most recent year for every school
      </h3>
      <CodeBlock>{`curl '${BASE}/rest/v1/cds_manifest?select=school_id,school_name,canonical_year&order=canonical_year.desc&limit=10' \\
  -H 'apikey: ${ANON_KEY.slice(0, 24)}…' \\
  -H 'Authorization: Bearer ${ANON_KEY.slice(0, 24)}…'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch all archived years for one school
      </h3>
      <CodeBlock>{`curl '${BASE}/rest/v1/cds_manifest?school_id=eq.harvard-university&select=canonical_year,source_format,extraction_status' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h3 className="mt-6 text-base font-semibold text-gray-900">
        Fetch extracted field values for a document
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        The selected extraction contract chooses the deterministic canonical
        artifact first. For Tier 4 Docling extracts, the LLM fallback cleaned row
        can fill gaps, but deterministic values win conflicts. Raw consumers can
        reproduce that behavior by fetching <code>kind=eq.canonical</code> plus
        rows with{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
          producer=eq.tier4_llm_fallback
        </code>{" "}
        and overlaying the canonical values on top.
      </p>
      <CodeBlock>{`curl '${BASE}/rest/v1/cds_artifacts?document_id=eq.<uuid>&kind=eq.canonical&select=notes' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        JavaScript client
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        The same{" "}
        <a
          className={API_LINK_CLASS}
          href="https://github.com/supabase/supabase-js"
          target="_blank"
          rel="noopener noreferrer"
        >
          @supabase/supabase-js
        </a>{" "}
        client this site uses works against the public API:
      </p>
      <CodeBlock>{`import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  "${BASE}",
  "<anon key>"
);

const { data } = await supabase
  .from("cds_manifest")
  .select("school_name, canonical_year")
  .eq("extraction_status", "extracted")
  .limit(20);`}</CodeBlock>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Source documents
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        Original CDS files are hosted on Supabase Storage. Once you have a
        manifest row, build the public URL as{" "}
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
          {BASE}/storage/v1/object/public/sources/&lt;source_storage_path&gt;
        </code>
        . Every file is content-addressed by SHA-256.
      </p>

      <h2 className="mt-10 text-xl font-semibold text-gray-900">
        Schema and licensing
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        Field IDs follow the canonical 1,105-field schema derived from the CDS
        Initiative&apos;s 2025-26 XLSX template. The full schema is checked
        into the repo at{" "}
        <a
          className={API_LINK_CLASS}
          href="https://github.com/bolewood/collegedata-fyi/blob/main/schemas"
          target="_blank"
          rel="noopener noreferrer"
        >
          schemas/
        </a>
        . The dataset is MIT-licensed; the underlying CDS documents are owned
        by their respective institutions and reproduced here under their
        public-document status.
      </p>

      <div className="mt-10 border-t border-gray-200 pt-6 text-sm text-gray-500">
        Found something missing or wrong? Open an issue on{" "}
        <a
          className={API_LINK_CLASS}
          href="https://github.com/bolewood/collegedata-fyi/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
        , or browse the <Link href="/schools" className={API_LINK_CLASS}>school directory</Link>.
      </div>
    </div>
  );
}

function FieldChip({ name }: { name: string }) {
  return (
    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
      {name}
    </code>
  );
}

function Resource({
  name,
  description,
  fields,
  allFields,
}: {
  name: string;
  description: string;
  /** Curated highlight fields shown by default (typically the ones most
      useful for consumer queries). */
  fields: string[];
  /** Complete alphabetized field list exposed by the table or view.
      Revealed behind a `<details>` when strictly larger than `fields`. */
  allFields?: string[];
}) {
  const highlighted = new Set(fields);
  const extras = allFields?.filter((f) => !highlighted.has(f)) ?? [];
  return (
    <div className="rounded border border-gray-200 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <code className="text-sm font-semibold text-gray-900">
          GET /rest/v1/{name}
        </code>
        <a
          href={`${BASE}/rest/v1/${name}?limit=1&apikey=${ANON_KEY}`}
          target="_blank"
          rel="noopener noreferrer"
          className={API_LINK_SMALL_CLASS}
        >
          try it →
        </a>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-gray-700">
        {description}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {fields.map((f) => (
          <FieldChip key={f} name={f} />
        ))}
      </div>
      {extras.length > 0 && (
        <details className="mt-3 group">
          <summary className="cursor-pointer select-none text-xs text-[var(--forest)] hover:text-[var(--forest-ink)]">
            <span className="group-open:hidden">
              Show all {allFields!.length} fields →
            </span>
            <span className="hidden group-open:inline">
              Hide additional fields
            </span>
          </summary>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {extras.map((f) => (
              <FieldChip key={f} name={f} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
