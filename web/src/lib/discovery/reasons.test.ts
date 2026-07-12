// Fail-closed reason rendering (PRD 026 §9): every rendered reason carries a
// template, a live evidence value with its data year, and limitation copy —
// and anything short of that is omitted, never approximated.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { LIMITATIONS, POLICY } from "./content";
import { matcher } from "./matchers";
import { COMPLETIONS_DISPLAY_YEAR, renderReasons } from "./reasons";
import { edgeSets, type Candidate } from "./rounds";
import type { EvidenceBundle, EvidenceSchool } from "./types";

const bundle: EvidenceBundle = JSON.parse(
  readFileSync(
    join(__dirname, "../../../public/discovery/evidence-v1.json"),
    "utf-8",
  ),
);

const { direct: DIRECT, adjacent: ADJACENT } = edgeSets(["environment-climate"]);
const NO_CIPS = new Set<string>();

function candidate(
  school: EvidenceSchool,
  reasons: [string, string][],
): Candidate {
  return { school, score: 0, distance: null, inPreferred: false, reasons };
}

function findMatching(key: string): EvidenceSchool {
  const s = bundle.schools.find((x) => matcher(key, x) === 1);
  if (!s) throw new Error(`no bundle school matches ${key}`);
  return s;
}

function prefReasons(key: string, school: EvidenceSchool) {
  return renderReasons(
    candidate(school, [[key, `match:${key}`]]),
    [],
    NO_CIPS,
    NO_CIPS,
    { [key]: 3 },
  );
}

describe("preference reason formatting", () => {
  it("formats fraction metrics as whole percentages", () => {
    const school = findMatching("out.retention");
    const [r] = prefReasons("out.retention", school);
    expect(r.kind).toBe("out.retention");
    expect(r.text).toMatch(/first-year retention of \d{2,3}% in /);
    expect(r.tunable_key).toBe("out.retention");
    expect(r.evidence_class).toBe("scorecard");
  });

  it("formats USD metrics with a dollar sign and thousands separators", () => {
    const school = findMatching("cost.low_debt");
    const [r] = prefReasons("cost.low_debt", school);
    expect(r.text).toMatch(/median borrower debt of \$\d{1,3}(,\d{3})+ in /);
    expect(r.limitation).toBe(LIMITATIONS["lim.aid_no_prediction"]);
  });

  it("formats plain counts as localized numbers (no unit prefix)", () => {
    const school = findMatching("scale.small");
    const [r] = prefReasons("scale.small", school);
    expect(r.text).toMatch(/undergraduate enrollment of \d{1,3}(,\d{3})*/);
    expect(r.text).not.toMatch(/\$/);
  });

  it("renders locale categories through their plain-language labels", () => {
    const school = bundle.schools.find(
      (x) => x.scorecard.locale === 11 || x.scorecard.locale === 12,
    );
    expect(school).toBeDefined();
    const [r] = prefReasons("place.big_city", school as EvidenceSchool);
    expect(r.text).toMatch(/a (large|midsize) city/);
    expect(r.text).not.toMatch(/as \d/); // never the raw locale code
    expect(r.limitation).toBe(LIMITATIONS["lim.locale_proxy"]);
  });

  it("uses the school's scorecard vintage, or 'recent' when it is missing", () => {
    const school = findMatching("cost.low_debt");
    const [withYear] = prefReasons("cost.low_debt", school);
    expect(withYear.data_year).toBe(school.scorecard.scorecard_data_year);
    const stripped: EvidenceSchool = {
      ...school,
      scorecard: { ...school.scorecard, scorecard_data_year: null },
    };
    const [withoutYear] = prefReasons("cost.low_debt", stripped);
    expect(withoutYear.data_year).toBe("recent");
    expect(withoutYear.text).toContain("recent");
  });
});

describe("fail-closed omissions", () => {
  it("omits a reason whose matcher does not actually fire", () => {
    const school = bundle.schools.find((x) => matcher("cost.low_debt", x) !== 1);
    expect(school).toBeDefined();
    expect(prefReasons("cost.low_debt", school as EvidenceSchool)).toEqual([]);
  });

  it("omits a reason when its template has an unresolvable placeholder", () => {
    const school = findMatching("cost.low_debt");
    const tpl = POLICY.reason_templates["tpl.numeric_low_good.v1"];
    if (typeof tpl === "string") throw new Error("unexpected template shape");
    const original = tpl.text;
    tpl.text = "Reported {metric_label} of {value_typo} in {data_year}.";
    try {
      expect(prefReasons("cost.low_debt", school)).toEqual([]);
    } finally {
      tpl.text = original;
    }
  });

  it("omits reasons for keys without display labels or templates", () => {
    // offering_any keys resolve to a template but the CDS evidence behind
    // them has not shipped: evidenceValue is null, so nothing renders.
    const school = bundle.schools[0];
    expect(prefReasons("academic.honors_program", school)).toEqual([]);
    expect(prefReasons("totally.unknown_key", school)).toEqual([]);
  });
});

describe("academic reasons", () => {
  const directSchool = bundle.schools.find((s) =>
    Object.keys(s.direct).some((cip) => DIRECT.has(cip)),
  ) as EvidenceSchool;

  it("grounds a direct match in the ontology edge, concept, and award count", () => {
    const reasons = renderReasons(
      candidate(directSchool, [["academic_direct", "program.recent_awards_direct"]]),
      ["environment-climate"],
      DIRECT,
      ADJACENT,
      {},
    );
    expect(reasons).toHaveLength(1);
    const [r] = reasons;
    expect(r.kind).toBe("academic_direct");
    expect(r.evidence_class).toBe("program");
    expect(r.data_year).toBe("2023-24");
    expect(r.text).toMatch(/\(\d{1,3}(,\d{3})* degrees\)$/);
    expect(r.tunable_key).toBeNull(); // interest matches are not tunable
  });

  it("omits the academic reason when no ontology edge matches the selected concepts", () => {
    // The CIP hit exists, but no edge connects it to the (bogus) concept the
    // student selected — fail closed rather than invent a connection.
    const reasons = renderReasons(
      candidate(directSchool, [["academic_direct", "program.recent_awards_direct"]]),
      ["nonexistent-concept"],
      DIRECT,
      ADJACENT,
      {},
    );
    expect(reasons).toEqual([]);
  });

  it("omits the academic reason when the school has no awards in the wanted CIPs", () => {
    const reasons = renderReasons(
      candidate(directSchool, [["academic_direct", "program.recent_awards_direct"]]),
      ["environment-climate"],
      NO_CIPS,
      NO_CIPS,
      {},
    );
    expect(reasons).toEqual([]);
  });
});

describe("reason selection", () => {
  it("caps rendered reasons at three, strongest preference contributions first", () => {
    const keys = [
      "scale.small", "scale.tight_knit", "out.retention", "out.four_year_grad",
      "out.career_track_record", "cost.low_debt", "cost.need_aid_strength",
      "people.first_gen_common",
    ];
    const school = bundle.schools.find(
      (s) =>
        keys.filter((k) => matcher(k, s) === 1).length >= 4 &&
        Object.keys(s.direct).some((cip) => DIRECT.has(cip)),
    ) as EvidenceSchool;
    expect(school).toBeDefined();
    const matched = keys.filter((k) => matcher(k, school) === 1);
    const aggregates = Object.fromEntries(matched.map((k, i) => [k, 5 - i]));
    const reasons = renderReasons(
      candidate(school, [
        ["academic_direct", "program.recent_awards_direct"],
        ...matched.map((k): [string, string] => [k, `match:${k}`]),
      ]),
      ["environment-climate"],
      DIRECT,
      ADJACENT,
      aggregates,
    );
    expect(reasons).toHaveLength(3);
    expect(reasons[0].kind).toBe("academic_direct");
    // Preference slots follow aggregate strength order.
    expect(reasons[1].kind).toBe(matched[0]);
    expect(reasons[2].kind).toBe(matched[1]);
  });
});

describe("completions display year", () => {
  it("matches the bundle's completions_release cycle", () => {
    // Regenerating the bundle onto a new completions cycle must not leave
    // reasons attributing program counts to the old year.
    const release = (bundle as unknown as { completions_release: string })
      .completions_release;
    expect(release).toContain(COMPLETIONS_DISPLAY_YEAR);
  });
});
