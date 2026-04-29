// Coverage status pill for institution_cds_coverage rows. Maps the
// coverage_status_t enum to one of the four .cd-chip variants in
// tokens.css (default outline / forest-filled / ochre / brick), with
// the user-facing copy coming from coverage_status_label() server-side.
//
// Design system (DESIGN_SYSTEM.md):
//   - .cd-chip          outline, neutral — most factual states
//   - .cd-chip--forest  positive — only for cds_available_current
//   - .cd-chip--ochre   rare emphasis — extraction needing review
//   - .cd-chip--brick   alarm/destructive — never used here, since
//                       PRD line 138 warns against accusatory tone

import type { CoverageStatus } from "@/lib/types";

const VARIANT: Record<CoverageStatus, string> = {
  cds_available_current: "cd-chip cd-chip--forest",
  cds_available_stale: "cd-chip",
  cds_found_processing: "cd-chip",
  latest_found_extract_failed_with_prior_available: "cd-chip",
  extract_failed: "cd-chip cd-chip--ochre",
  source_not_automatically_accessible: "cd-chip",
  no_public_cds_found: "cd-chip",
  verified_absent: "cd-chip",
  not_checked: "cd-chip",
  out_of_scope: "cd-chip",
};

export function CoverageBadge({
  status,
  label,
}: {
  status: CoverageStatus;
  label: string;
}) {
  return <span className={VARIANT[status] ?? "cd-chip"}>{label}</span>;
}
