// Opt-in, read-only measurement for PRD 031. Skipped in normal test runs.
//
//   ACCEPTANCE_MEASURE=survey ./node_modules/.bin/vitest run src/lib/acceptance-history.measure.test.ts
//     Corpus-wide usable-year counts from scratch/prd-031/c1-survey.json
//     (written by scratch/prd-031/survey.mjs).
//   ACCEPTANCE_MEASURE=live ./node_modules/.bin/vitest run src/lib/acceptance-history.measure.test.ts
//     Live per-school history for the pilot allowlist through the page's own
//     fetchers, plus a comparison with school_browser_rows for 2024-25+.
//
// Both modes write JSON to scratch/prd-031/.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it } from "vitest";
import {
  acceptanceEligibility,
  buildAcceptanceHistory,
  type HistoryDocument,
  type HistoryExtract,
} from "./acceptance-history";
import type { FieldValue } from "./types";

const MODE = process.env.ACCEPTANCE_MEASURE;
const OUT_DIR = resolve(__dirname, "../../../scratch/prd-031");

function loadEnv() {
  const path = resolve(__dirname, "../../.env.local");
  if (!existsSync(path)) return;
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const at = line.indexOf("=");
    if (at <= 0 || line.startsWith("#")) continue;
    process.env[line.slice(0, at)] ??= line.slice(at + 1).replace(/^"|"$/g, "");
  }
}

describe.skipIf(MODE !== "survey")("acceptance history corpus survey", () => {
  it("counts usable years per school", () => {
    type SurveyArtifact = Record<string, string | null> & { producer: string; sv: string | null };
    const survey = JSON.parse(readFileSync(resolve(OUT_DIR, "c1-survey.json"), "utf8")) as {
      docs: (HistoryDocument & { school_id: string; school_name: string })[];
      artifacts: Record<string, { canonical: SurveyArtifact | null; fallback: SurveyArtifact | null }>;
    };
    const toExtract = (id: string): HistoryExtract | null => {
      const a = survey.artifacts[id];
      if (!a?.canonical) return null;
      const values: Record<string, FieldValue> = {};
      for (const src of [a.fallback, a.canonical]) {
        if (!src) continue;
        for (let i = 101; i <= 130; i++) {
          const raw = src[`c${i}`];
          if (raw != null && raw !== "") values[`C.${i}`] = { value: raw };
        }
      }
      return { values, schemaVersion: a.canonical.sv, producer: a.canonical.producer };
    };
    const bySchool = new Map<string, typeof survey.docs>();
    for (const doc of survey.docs) {
      bySchool.set(doc.school_id, [...(bySchool.get(doc.school_id) ?? []), doc]);
    }
    const rows = [];
    const reasons = new Map<string, number>();
    for (const [school, docs] of bySchool) {
      docs.sort((a, b) => (b.canonical_year ?? "").localeCompare(a.canonical_year ?? ""));
      const history = buildAcceptanceHistory(
        docs.map((doc) => ({ doc, extract: toExtract(doc.document_id ?? "") })),
      );
      for (const ex of history.excluded) reasons.set(ex.reason, (reasons.get(ex.reason) ?? 0) + 1);
      rows.push({
        school,
        name: docs[0].school_name,
        usable: history.years.length,
        latest: history.years[0]?.year ?? null,
        first: history.years.at(-1)?.year ?? null,
        gaps: history.gaps,
        eligible: acceptanceEligibility(history).eligible,
        years: history.years.map((y) => `${y.year}:${(y.rate * 100).toFixed(1)}`),
      });
    }
    rows.sort((a, b) => b.usable - a.usable);
    const summary = {
      schools: rows.length,
      eligible3: rows.filter((r) => r.eligible).length,
      eligible4: rows.filter((r) => r.eligible && r.usable >= 4).length,
      eligible5: rows.filter((r) => r.eligible && r.usable >= 5).length,
      exclusionReasons: Object.fromEntries(reasons),
    };
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(resolve(OUT_DIR, "survey-usable-years.json"), JSON.stringify({ summary, rows }, null, 1));
    console.log(JSON.stringify(summary, null, 1));
  });
});

describe.skipIf(MODE !== "live")("acceptance history live measurement", () => {
  it("reports the allowlist and compares 2024-25+ with school_browser_rows", async () => {
    loadEnv();
    const { fetchAcceptanceHistory } = await import("./acceptance-history-data");
    const { fetchSchoolYearFacts, fetchSchoolDocuments, fetchExtract } = await import("./queries");
    const { ACCEPTANCE_PILOT_SCHOOLS } = await import("./acceptance-pilot");
    const { isHistoryCandidate } = await import("./acceptance-history");
    const extra = (process.env.ACCEPTANCE_EXTRA ?? "").split(",").filter(Boolean);
    const only = process.env.ACCEPTANCE_ONLY_EXTRA === "1";
    const report = [];
    for (const school of [...(only ? [] : ACCEPTANCE_PILOT_SCHOOLS), ...extra]) {
      const [{ schoolName, history }, facts, docs] = await Promise.all([
        fetchAcceptanceHistory(school),
        fetchSchoolYearFacts(school),
        fetchSchoolDocuments(school),
      ]);
      const candidates = docs.filter(isHistoryCandidate);
      const extracts = await Promise.all(candidates.map(async (doc) => {
        const { canonical, mergedValues } = await fetchExtract(doc.document_id as string);
        const notes = canonical?.notes as { schema_version?: string; markdown?: string } | null;
        return canonical
          ? {
              values: mergedValues,
              schemaVersion: notes?.schema_version ?? null,
              producer: canonical.producer ?? null,
              markdown: notes?.markdown ?? null,
            }
          : null;
      }));
      const extractOnly = buildAcceptanceHistory(candidates.map((doc, i) => ({ doc, extract: extracts[i] })));
      const comparisons = extractOnly.years
        .filter((row) => row.yearStart >= 2024)
        .map((row) => {
          const fact = facts.find((f) => f.document_id === row.documentId);
          return {
            year: row.year,
            ours: [row.applied, row.admitted, row.enrolled],
            browser: fact ? [fact.applied, fact.admitted, fact.enrolledFirstYear] : null,
            match: fact
              ? fact.applied === row.applied && fact.admitted === row.admitted &&
                (fact.enrolledFirstYear ?? null) === row.enrolled
              : null,
          };
        });
      report.push({
        school,
        schoolName,
        eligibility: acceptanceEligibility(history),
        usable: history.years.length,
        years: history.years.map((y) => ({
          year: y.year, source: y.source, applied: y.applied, admitted: y.admitted,
          enrolled: y.enrolled, rate: Number((y.rate * 100).toFixed(2)), file: y.sourceStoragePath,
        })),
        gaps: history.gaps,
        excluded: history.excluded,
        comparisons,
      });
      console.log(school, history.years.length, history.years.map((y) => y.year).join(" "));
    }
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(resolve(OUT_DIR, "live-allowlist.json"), JSON.stringify(report, null, 1));
  }, 300_000);
});
