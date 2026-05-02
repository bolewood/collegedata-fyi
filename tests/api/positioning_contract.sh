#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CDFYI_API_BASE_URL:-https://api.collegedata.fyi}"
ANON_KEY="${SUPABASE_ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}}"

if [[ -z "${ANON_KEY}" ]]; then
  ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs"
fi

curl -fsS \
  "${BASE_URL}/rest/v1/school_browser_rows?select=school_id,school_name,canonical_year,year_start,acceptance_rate,sat_submit_rate,act_submit_rate,sat_composite_p25,sat_composite_p50,sat_composite_p75,act_composite_p25,act_composite_p50,act_composite_p75,data_quality_flag,archive_url&school_id=eq.bowdoin&limit=1" \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  >/dev/null

echo "positioning contract ok"
