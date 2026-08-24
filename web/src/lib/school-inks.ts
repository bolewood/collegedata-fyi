import { cache } from "react";
import {
  PAPER,
  deriveInks,
  inkStyle,
  type DerivedInks,
} from "./derive-inks";
import {
  fetchCanonicalSchoolId,
  fetchSchoolBrandColors,
} from "./queries";

export async function loadSchoolInks(schoolId: string): Promise<DerivedInks> {
  const canonical = (await fetchCanonicalSchoolId(schoolId)) ?? schoolId;
  const hexes = await fetchSchoolBrandColors(canonical);
  return deriveInks(hexes);
}

export const cachedSchoolInks = cache(loadSchoolInks);

export function schoolOgColors(inks: DerivedInks): {
  ground: string;
  accent: string;
  type: string;
} {
  return {
    ground: inks.a,
    type: PAPER,
    accent: inks.bTypeOnA ? inks.b : PAPER,
  };
}

export function schoolInkWrapperProps(inks: DerivedInks): {
  className: string;
  style: Record<string, string>;
  "data-ink-rule": string;
  "data-ink-house": string;
  "data-ink-b-on-a": string;
} {
  return {
    className: "school-record",
    style: inkStyle(inks),
    "data-ink-rule": inks.rule,
    "data-ink-house": inks.house ? "true" : "false",
    "data-ink-b-on-a": inks.bTypeOnA ? "true" : "false",
  };
}
