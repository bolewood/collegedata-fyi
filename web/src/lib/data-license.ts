/**
 * The one place web code states what our licenses cover. Every public surface
 * (site copy, llms.txt, API docs) imports from here so the wording can't drift.
 *
 * What we can license: our own code and the structured extracts we derive.
 * What we can't: the schools' Common Data Set documents (the schools own them)
 * and the federal IPEDS, College Scorecard and FSA records.
 */

export const CODE_LICENSE_NAME = "MIT";
export const CODE_LICENSE_URL = "https://opensource.org/licenses/MIT";

/** Our code and the structured CDS extracts we derive. */
export const DERIVED_DATA_LICENSE_SENTENCE =
  "Our code and the structured Common Data Set extracts we derive are MIT-licensed.";

/** Who owns what our license does not cover. */
export const SOURCE_OWNERSHIP_SENTENCE =
  "The Common Data Set documents belong to the schools that published them, and the IPEDS, College Scorecard and FSA figures come from federal sources; our license covers neither.";
