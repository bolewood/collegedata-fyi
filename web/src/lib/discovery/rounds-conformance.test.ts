// Cross-engine conformance: the TypeScript round composer must reproduce the
// Python reference engine's output exactly — same schools, same roles, same
// order, same slot fills — for every scenario in the versioned corpus, run
// against the committed evidence bundle. Regenerate the fixture with
// tools/discovery/build_conformance_fixture.py whenever policy, ontology,
// scenarios, or the bundle change.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/rounds-conformance.v1.json";
import { composeRound } from "./rounds";
import type { EvidenceBundle, GeographyPreferenceLocal } from "./types";

const bundle: EvidenceBundle = JSON.parse(
  readFileSync(
    join(__dirname, "../../../public/discovery/evidence-v1.json"),
    "utf-8",
  ),
);

describe("rounds engine conformance with the Python reference", () => {
  it("fixture and bundle versions agree", () => {
    expect(fixture.bundle_version).toBe(bundle.bundle_version);
    expect(fixture.policy_version).toBe(bundle.policy_version);
  });

  it.each(fixture.cases.map((c) => [c.scenario_id, c] as const))(
    "%s",
    (_id, c) => {
      const result = composeRound({
        pool: bundle.schools,
        concepts: c.concepts,
        geography: c.geography as GeographyPreferenceLocal,
        origin: c.origin,
        aggregates: c.aggregates as unknown as Record<string, number>,
      });
      expect(
        result.chosen.map((x) => [x.candidate.school.school_id, x.role]),
      ).toEqual(c.expected.schools);
      expect(result.slots).toEqual(c.expected.slots);
      expect(result.eligible_candidates).toBe(c.expected.eligible_candidates);
      expect(result.diagnostics["relaxation_level"] ?? null).toBe(
        c.expected.relaxation_level,
      );
    },
  );
});
