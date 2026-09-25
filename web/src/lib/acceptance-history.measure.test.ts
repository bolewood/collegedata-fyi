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

describe.skipIf(MODE !== "hubs")("hub summaries changed by the printed-total resolver", () => {
  it("counts latest browser rows whose printed counts differ", async () => {
    loadEnv();
    const { supabase } = await import("./supabase");
    const { readAcceptanceYear } = await import("./acceptance-history");
    type Row = { document_id: string; school_id: string; canonical_year: string; year_start: number; applied: number | null; admitted: number | null; enrolled_first_year: number | null; data_quality_flag: string | null };
    const rows: Row[] = [];
    for (let start = 0; ; start += 1000) {
      const { data, error } = await (supabase as unknown as { from: (t: string) => any })
        .from("school_browser_rows")
        .select("document_id,school_id,canonical_year,year_start,applied,admitted,enrolled_first_year,data_quality_flag")
        .is("sub_institutional", null)
        .range(start, start + 999);
      if (error) throw error;
      rows.push(...(data as Row[]));
      if (data.length < 1000) break;
    }
    const survey = JSON.parse(readFileSync(resolve(OUT_DIR, "c1-survey.json"), "utf8")) as {
      artifacts: Record<string, { canonical: (Record<string, string | null> & { producer: string; sv: string | null }) | null }>;
    };
    const latest = new Map<string, Row>();
    for (const row of rows) {
      if (["wrong_file", "blank_template", "low_coverage"].includes(row.data_quality_flag ?? "")) continue;
      const seen = latest.get(row.school_id);
      if (!seen || row.year_start > seen.year_start) latest.set(row.school_id, row);
    }
    const changed = [];
    let compared = 0;
    for (const row of latest.values()) {
      const a = survey.artifacts[row.document_id]?.canonical;
      if (!a) continue;
      const values: Record<string, FieldValue> = {};
      for (let i = 101; i <= 130; i++) if (a[`c${i}`] != null && a[`c${i}`] !== "") values[`C.${i}`] = { value: String(a[`c${i}`]) };
      const reading = readAcceptanceYear(
        { document_id: row.document_id, canonical_year: row.canonical_year, extraction_status: "extracted", data_quality_flag: null, sub_institutional: null, source_storage_path: null, source_format: null },
        { values, schemaVersion: a.sv, producer: a.producer, markdown: a.producer === "tier4_docling" ? "| survey |" : null },
        { applied: row.applied, admitted: row.admitted, enrolled: row.enrolled_first_year },
      );
      compared += 1;
      if (reading.ok && reading.row.source !== "projection" && (reading.row.applied !== row.applied || reading.row.admitted !== row.admitted)) {
        changed.push({ school: row.school_id, year: row.canonical_year, projection: [row.applied, row.admitted], printed: [reading.row.applied, reading.row.admitted] });
      }
    }
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(resolve(OUT_DIR, "hub-changes.json"), JSON.stringify({ schools: latest.size, compared, changed }, null, 1));

    // Gate every non-pilot hub (ACCEPTANCE_MEASURE=hubs also writes hub-gate.json).
    const { gateC1Counts, ipedsAdmissions } = await import("./c1-hub-gate");
    const { isAcceptancePilotSchool } = await import("./acceptance-pilot");
    const factRows: { school_id: string; ipeds_id: string; field_key: string; value_numeric: number | null; value_label: string | null; data_year: number }[] = [];
    for (let start = 0; ; start += 1000) {
      const { data, error } = await (supabase as unknown as { from: (t: string) => any })
        .from("school_facts_unified")
        .select("school_id,ipeds_id,field_key,value_numeric,value_label,data_year")
        .in("field_key", ["applicants_total", "admissions_total", "open_admissions_policy", "sector", "degree_granting_status"])
        .in("school_id", Array.from(latest.keys()))
        .range(start, start + 999);
      if (error) throw error;
      factRows.push(...data);
      if (data.length < 1000) break;
    }
    const { data: manifestIpeds } = await (supabase as unknown as { from: (t: string) => any })
      .from("cds_manifest").select("document_id,ipeds_id").in("document_id", Array.from(latest.values()).map((r) => r.document_id));
    const ipedsByDoc = new Map((manifestIpeds as { document_id: string; ipeds_id: string | null }[]).map((r) => [r.document_id, r.ipeds_id]));
    const report = [];
    const sane = (a: number | null, b: number | null) => a != null && b != null && a >= 50 && b > 0 && b <= a;
    for (const row of latest.values()) {
      if (isAcceptancePilotSchool(row.school_id)) continue;
      const a = survey.artifacts[row.document_id]?.canonical;
      let resolver = null;
      if (a) {
        const values: Record<string, FieldValue> = {};
        for (let i = 101; i <= 130; i++) if (a[`c${i}`] != null && a[`c${i}`] !== "") values[`C.${i}`] = { value: String(a[`c${i}`]) };
        const reading = readAcceptanceYear(
          { document_id: row.document_id, canonical_year: row.canonical_year, extraction_status: "extracted", data_quality_flag: null, sub_institutional: null, source_storage_path: null, source_format: null },
          { values, schemaVersion: a.sv, producer: a.producer, markdown: a.producer === "tier4_docling" ? "| survey |" : null },
          { applied: row.applied, admitted: row.admitted, enrolled: row.enrolled_first_year },
        );
        if (reading.ok && reading.row.source !== "projection") resolver = { applied: reading.row.applied, admitted: reading.row.admitted, enrolled: reading.row.enrolled };
      }
      const ipeds = ipedsAdmissions(factRows.filter((f) => f.school_id === row.school_id) as never, ipedsByDoc.get(row.document_id) ?? null);
      const projection = { applied: row.applied, admitted: row.admitted, enrolled: row.enrolled_first_year };
      const result = gateC1Counts({ pilot: false, yearStart: row.year_start, projection, resolver, ipeds });
      const shown = result.counts;
      const productionShown = sane(row.applied, row.admitted);
      const outcome = !shown
        ? productionShown ? "suppress_was_shown" : "suppress_was_hidden"
        : shown.applied === row.applied && shown.admitted === row.admitted
          ? "keep_old"
          : "accept_new";
      report.push({ school: row.school_id, year: row.canonical_year, reason: result.reason, outcome, projection, resolver, shown, ipeds });
    }
    // Schools whose counts mirror another school's for the same year.
    const byCounts = new Map<string, string[]>();
    for (const row of rows) {
      if (!row.applied || !row.admitted) continue;
      const key = `${row.canonical_year}|${row.applied}|${row.admitted}`;
      byCounts.set(key, [...(byCounts.get(key) ?? []), row.school_id]);
    }
    const mirrors = Array.from(byCounts.entries())
      .filter(([, ids]) => new Set(ids).size > 1)
      .map(([key, ids]) => ({ key, schools: Array.from(new Set(ids)) }));
    writeFileSync(resolve(OUT_DIR, "hub-gate.json"), JSON.stringify({ report, mirrors }, null, 1));
  }, 300_000);
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
        reportYears: docs.filter((doc) => doc.sub_institutional == null).map((doc) => doc.canonical_year),
        excluded: history.excluded,
        comparisons,
      });
      console.log(school, history.years.length, history.years.map((y) => y.year).join(" "));
    }
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(resolve(OUT_DIR, "live-allowlist.json"), JSON.stringify(report, null, 1));
  }, 300_000);
});

describe.skipIf(MODE !== "gpa")("gpa live measurement", () => {
  it("reports C11 years for distinctive-name candidates", async () => {
    loadEnv();
    const { fetchAcceptanceHistory } = await import("./acceptance-history-data");
    const { buildGpaHistory, gpaEligibility } = await import("./c11-gpa");
    const { fetchSchoolDocuments, fetchExtract } = await import("./queries");
    const { isHistoryCandidate } = await import("./acceptance-history");
    const extra = (process.env.ACCEPTANCE_EXTRA ?? "").split(",").filter(Boolean);
    const only = process.env.ACCEPTANCE_ONLY_EXTRA === "1";
    const { ACCEPTANCE_PILOT_SCHOOLS } = await import("./acceptance-pilot");
    const distinctive = [
      "harvard",
      "princeton",
      "yale",
      "stanford",
      "dartmouth",
      "vanderbilt",
      "cornell",
      "duke",
      "brown",
      "northwestern",
      "uchicago",
      "caltech",
      "mit",
      "columbia",
      "upenn",
      "johns-hopkins",
      "georgetown",
      "notre-dame",
      "university-of-notre-dame",
      "rice",
      "bowdoin",
      "amherst",
      "williams",
    ];
    const schools = [
      ...new Set(only ? extra : [...distinctive, ...ACCEPTANCE_PILOT_SCHOOLS, ...extra]),
    ];
    const report = [];
    for (const school of schools) {
      const docs = await fetchSchoolDocuments(school);
      const candidates = docs.filter(isHistoryCandidate);
      const extracts = await Promise.all(
        candidates.map(async (doc) => {
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
        }),
      );
      const history = buildGpaHistory(candidates.map((doc, i) => ({ doc, extract: extracts[i] })));
      const eligibility = gpaEligibility(history);
      const { schoolName } = await fetchAcceptanceHistory(school);
      report.push({
        school,
        schoolName,
        eligible: eligibility.eligible,
        reason: eligibility.eligible ? null : eligibility.reason,
        years: history.years.map((y) => ({
          year: y.year,
          column: y.bands.column,
          gpa4: Number(y.bands.percents.gpa4.toFixed(1)),
          average: y.average,
          submitted: y.submittedPct,
        })),
        excluded: history.excluded,
      });
      console.warn(
        school,
        eligibility.eligible ? "yes" : eligibility.reason,
        history.years.map((y) => `${y.year}${y.average != null ? `@${y.average}` : ""}`).join(" "),
      );
    }
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(resolve(OUT_DIR, "gpa-allowlist.json"), JSON.stringify(report, null, 1));
  }, 300_000);
});

describe.skipIf(MODE !== "ed")("early-decision live measurement", () => {
  it("reports C21 years and notes for distinctive-name candidates", async () => {
    loadEnv();
    const { fetchAcceptanceHistory } = await import("./acceptance-history-data");
    const { isOwnEdNote } = await import("./c21-ed-note");
    const extra = (process.env.ACCEPTANCE_EXTRA ?? "").split(",").filter(Boolean);
    const only = process.env.ACCEPTANCE_ONLY_EXTRA === "1";
    const { ACCEPTANCE_PILOT_SCHOOLS } = await import("./acceptance-pilot");
    const { edEligibility } = await import("./acceptance-history");
    const schools = [...new Set(only ? extra : [...ACCEPTANCE_PILOT_SCHOOLS, ...extra])];
    const report = [];
    for (const school of schools) {
      const { schoolName, history } = await fetchAcceptanceHistory(school);
      const edYears = history.years.filter((y) => y.ed);
      const notes = history.years
        .filter((y) => y.edNote)
        .map((y) => ({
          year: y.year,
          own: isOwnEdNote(y.edNote),
          preview: y.edNote ? y.edNote.slice(0, 180) : null,
        }));
      const latestOwn = notes.find((n) => n.own);
      const eligibility = edEligibility(history);
      report.push({
        school,
        schoolName,
        eligible: eligibility.eligible,
        reason: eligibility.eligible ? null : eligibility.reason,
        edYears: edYears.length,
        latestEd: edYears[0]?.year ?? null,
        years: edYears.map((y) => ({
          year: y.year,
          applied: y.ed!.applied,
          admitted: y.ed!.admitted,
          rate: Number((y.ed!.rate * 100).toFixed(2)),
        })),
        notes,
        hasOwnNote: notes.some((n) => n.own),
        latestOwnYear: latestOwn?.year ?? null,
      });
    }
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(resolve(OUT_DIR, "ed-allowlist.json"), JSON.stringify(report, null, 1));
  }, 300_000);
});
