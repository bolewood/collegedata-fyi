#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CDFYI_API_BASE_URL:-https://api.collegedata.fyi}"
ANON_KEY="${SUPABASE_ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}}"

if [[ -z "${ANON_KEY}" ]]; then
  ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs"
fi

curl -fsS \
  "${BASE_URL}/rest/v1/school_browser_rows?select=school_id,school_name,canonical_year,year_start,applied,admitted,yield_rate,ed_offered,ed_applicants,ed_admitted,ed_has_second_deadline,ea_offered,ea_restrictive,wait_list_policy,wait_list_offered,wait_list_accepted,wait_list_admitted,c711_first_gen_factor,c712_legacy_factor,c713_geography_factor,c714_state_residency_factor,c718_demonstrated_interest_factor,app_fee_amount,app_fee_waiver_offered,admission_strategy_card_quality,archive_url&school_id=eq.bowdoin&limit=1" \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  >/dev/null

echo "admission strategy contract ok"
