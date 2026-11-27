import { REPO_URL } from "./repo";

/**
 * The one place web code states what our licenses cover. Every public surface
 * (site copy, llms.txt, API envelopes, OpenAPI, MCP, snapshots, spreadsheets)
 * imports from here so the wording can't drift. A test pins DATA_ATTRIBUTION
 * and the effective date to /DATA_LICENSE.md.
 *
 * What we license: our code (MIT) and the structured Common Data Set extracts
 * we derive (CC BY 4.0, ADR 0009). What we can't: the schools' Common Data Set
 * documents and the federal IPEDS, College Scorecard and FSA records.
 */

export const CODE_LICENSE_NAME = "MIT";
export const CODE_LICENSE_URL = "https://opensource.org/licenses/MIT";

/** SPDX identifier for the derived dataset. */
export const DATA_LICENSE = "CC-BY-4.0";
export const DATA_LICENSE_NAME = "CC BY 4.0";
export const DATA_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/";
export const DATA_LICENSE_DOC_URL = `${REPO_URL}/blob/main/DATA_LICENSE.md`;
/** Releases before this date were published under MIT and stay reusable under MIT. */
export const DATA_LICENSE_EFFECTIVE_DATE = "2026-11-23";

/** The canonical credit line. Includes the license link, which CC BY requires. */
export const DATA_ATTRIBUTION =
  "Common Data Set extracts from Quadfile (https://www.quadfile.org), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Figures as published in each school's Common Data Set.";

/** What the data license covers, for machine-readable envelopes. */
export const DATA_LICENSE_SCOPE =
  "Covers the structured Common Data Set extracts, field documentation and derived-metric definitions authored by Quadfile. Does not cover the schools' Common Data Set documents, CDS Initiative template text, or federal IPEDS, College Scorecard and FSA facts. Say so if you changed the data.";

/** Our code and the structured CDS extracts we derive. */
export const DERIVED_DATA_LICENSE_SENTENCE =
  "Our code is MIT-licensed, and the structured Common Data Set extracts we derive are licensed CC BY 4.0.";

/** Who owns what our license does not cover. */
export const SOURCE_OWNERSHIP_SENTENCE =
  "The Common Data Set documents belong to the schools that published them, and the IPEDS, College Scorecard and FSA figures come from federal sources; our licenses cover neither.";

/**
 * Added to friendly API envelopes, snapshot manifests and MCP payloads as one
 * nested `data_license` block. It is nested, not top-level `license`, because
 * the same payloads carry federal facts the license doesn't cover.
 */
export function dataLicenseFields() {
  return {
    data_license: {
      applies_to: "cds_extracts",
      license: DATA_LICENSE,
      license_url: DATA_LICENSE_URL,
      scope: DATA_LICENSE_SCOPE,
      attribution: DATA_ATTRIBUTION,
    },
  } as const;
}

/** HTTP Link header value for downloads (CSV) where a credit row would break parsers. */
export const DATA_LICENSE_LINK_HEADER = `<${DATA_LICENSE_URL}>; rel="license"`;
