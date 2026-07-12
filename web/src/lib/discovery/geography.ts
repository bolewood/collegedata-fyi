// Boundary-step validation (PRD 026 §1, §3). Everything is optional; errors
// are plain-language and field-associated. The ZIP is held locally only —
// centroid resolution and distance features are deferred until the
// ZIP-centroid source is selected (PRD Q5), so this slice validates shape,
// never resolves.

import type { GeographyPreferenceLocal } from "./types";

export interface GeographyFormInput {
  zip: string;
  preferredMiles: string;
  maximumMiles: string;
  allowWildcards: boolean;
}

export interface GeographyValidation {
  ok: boolean;
  errors: Partial<Record<"zip" | "preferred" | "maximum" | "relation", string>>;
  // The wildcard toggle is ignored without a preferred radius (PRD §3);
  // the UI explains rather than errors.
  wildcardNote: string | null;
  value: GeographyPreferenceLocal | null;
}

function parseMiles(raw: string): number | null | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return null; // left blank — fine
  if (!/^\d{1,5}$/.test(trimmed)) return undefined; // invalid
  const n = parseInt(trimmed, 10);
  return n > 0 ? n : undefined;
}

export function validateGeography(input: GeographyFormInput): GeographyValidation {
  const errors: GeographyValidation["errors"] = {};

  const zip = input.zip.trim();
  if (zip && !/^\d{5}$/.test(zip)) {
    errors.zip = "ZIP codes are five digits — check for typos, or leave it blank.";
  }

  const preferred = parseMiles(input.preferredMiles);
  if (preferred === undefined) {
    errors.preferred = "Use a whole number of miles, or leave it blank.";
  }
  const maximum = parseMiles(input.maximumMiles);
  if (maximum === undefined) {
    errors.maximum = "Use a whole number of miles, or leave it blank.";
  }

  if (
    typeof preferred === "number" &&
    typeof maximum === "number" &&
    preferred > maximum
  ) {
    errors.relation =
      "Your preferred distance is larger than your never-beyond maximum. Raise the maximum or lower the preference.";
  }

  const wildcardNote =
    input.allowWildcards && preferred === null && !errors.preferred
      ? "Wildcards only make sense with a preferred distance — without one, every school is already in range, so this setting is ignored."
      : null;

  const ok = Object.keys(errors).length === 0;
  return {
    ok,
    errors,
    wildcardNote,
    value: ok
      ? {
          zip: zip || null,
          preferred_miles: (preferred as number | null) ?? null,
          maximum_miles: (maximum as number | null) ?? null,
          allow_wildcards: input.allowWildcards,
        }
      : null,
  };
}

export function describeGeography(geo: GeographyPreferenceLocal | null): string {
  if (!geo || (!geo.zip && !geo.preferred_miles && !geo.maximum_miles)) {
    return "No distance settings — schools anywhere in the U.S.";
  }
  const parts: string[] = [];
  if (geo.zip) parts.push(`starting near ${geo.zip}`);
  if (geo.preferred_miles) parts.push(`prefer within ~${geo.preferred_miles} miles`);
  if (geo.maximum_miles) parts.push(`never beyond ~${geo.maximum_miles} miles`);
  if (geo.preferred_miles && geo.allow_wildcards) parts.push("occasional wildcards welcome");
  return parts.join(" · ");
}
