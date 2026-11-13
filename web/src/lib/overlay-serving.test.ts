import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ArtifactRow } from "./types";
import {
  DEFAULT_OVERLAY_SERVE_CLASSES,
  mergeWithOverlay,
  overlayMatchesBase,
  overlayServeKey,
  parseOverlayServeClasses,
  pickOverlay,
  serveOverlayValues,
  zeroKeepsBase,
} from "./overlay-serving";
import { c1TemplateForArtifact } from "./c1-headline-totals";

type Variant = {
  serve: string[];
  values: Record<string, unknown>;
  overlay_artifact_id: string | null;
  sources?: Record<string, string>;
};
type Case = {
  name: string;
  artifacts: ArtifactRow[];
  base_artifact_id: string;
  variants?: Variant[];
  per_selector?: Record<string, { base_artifact_id: string; values: Record<string, unknown>; serve?: string[]; overlay_artifact_id?: string }>;
};

const FIXTURE = JSON.parse(
  readFileSync(join(process.cwd(), "..", "tools/browser_backend/fixtures/overlay_parity.json"), "utf8"),
) as { cases: Case[]; serve_config_cases: Array<{ raw: string | null; classes: string[] }>; default_serve_classes: string[] };

const plain = (values: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(values).map(([k, v]) => [k, (v as { value?: unknown } | null)?.value ?? v]),
  );

/** What fetchExtract does: newest canonical, the compatible fallback, then the overlay merge. */
function webSelect(artifacts: ArtifactRow[], serve: string[]) {
  const canonicals = artifacts
    .filter((a) => a.kind === "canonical")
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  const canonical = canonicals[0] ?? null;
  const fallback = artifacts.find(
    (a) =>
      a.producer === "tier4_llm_fallback" &&
      (a.notes as { base_artifact_id?: string }).base_artifact_id === canonical?.id,
  );
  const fallbackValues = ((fallback?.notes as { values?: Record<string, never> } | null)?.values ?? {}) as Record<string, never>;
  return {
    canonical,
    ...mergeWithOverlay({
      canonical,
      fallbackValues,
      overlayCandidates: artifacts.filter((a) => a.producer === "tier2_template_overlay"),
      classes: parseOverlayServeClasses(serve.length > 0 ? serve.join(",") : "none"), // an empty resolved set is the `none` off token
    }),
  };
}

describe("overlay serving (parity fixture shared with Python and the SQL runner)", () => {
  for (const c of FIXTURE.cases) {
    if (c.name.startsWith("known_divergence")) continue; // recorded separately below
    for (const variant of c.variants ?? []) {
      it(`${c.name}: serve=[${variant.serve.join(",")}]`, () => {
        const got = webSelect(c.artifacts, variant.serve);
        expect(got.canonical?.id).toBe(c.base_artifact_id);
        expect(plain(got.mergedValues)).toEqual(variant.values);
        expect(got.overlay?.id ?? null).toBe(variant.overlay_artifact_id);
      });
    }
  }

  it("records the existing divergence: the web takes the newest canonical, the view and projection take Tier 2", () => {
    const c = FIXTURE.cases.find((x) => x.name.startsWith("known_divergence"))!;
    const expected = c.per_selector!.web;
    const got = webSelect(c.artifacts, expected.serve!);
    expect(got.canonical?.id).toBe(expected.base_artifact_id);
    expect(plain(got.mergedValues)).toEqual(expected.values);
    expect(got.overlay?.id).toBe(expected.overlay_artifact_id);
    expect(c.base_artifact_id).not.toBe(expected.base_artifact_id);
  });

  it("with the set empty the overlay rows are never even read", () => {
    const c = FIXTURE.cases[0];
    const withOverlays = webSelect(c.artifacts, []);
    const without = webSelect(c.artifacts.filter((a) => a.producer !== "tier2_template_overlay"), []);
    expect(withOverlays.mergedValues).toEqual(without.mergedValues);
    expect(withOverlays.overlay).toBeNull();
  });

  it("the newest matching overlay wins whatever its version (a reversed order would pick the old one)", () => {
    const base = { id: "b", producer: "tier4_docling", schema_version: "2025-26", notes: { source_sha256: "S" } } as unknown as ArtifactRow;
    const mk = (id: string, created_at: string, version: string) =>
      ({ id, kind: "cleaned", producer: "tier2_template_overlay", schema_version: "2025-26", created_at, producer_version: version, notes: { source_sha256: "S", held: false } }) as unknown as ArtifactRow;
    const oldHigh = mk("old", "2026-11-02T00:00:00+00:00", "9.9");
    const newLow = mk("new", "2026-11-03T00:00:00+00:00", "0.1");
    expect(pickOverlay(base, [oldHigh, newLow])?.id).toBe("new");
    expect(pickOverlay(base, [newLow, oldHigh])?.id).toBe("new");
  });
});

describe("served-class configuration", () => {
  it("parses the shared config cases (default when unset or empty, `none` the only off token)", () => {
    for (const c of FIXTURE.serve_config_cases) {
      expect(Array.from(parseOverlayServeClasses(c.raw)).sort()).toEqual(c.classes);
    }
    expect(Array.from(DEFAULT_OVERLAY_SERVE_CLASSES).sort()).toEqual(FIXTURE.default_serve_classes);
  });

  it("is part of the cache key", () => {
    expect(overlayServeKey(new Set())).toBe("off");
    expect(overlayServeKey(new Set(["numeric", "choice"]))).toBe("on:choice+numeric");
    expect(overlayServeKey(new Set(["numeric"]))).not.toBe(overlayServeKey(new Set(["numeric", "choice"])));
  });

  it("never serves Lane 2 evidence (2, 2.0, \"2\", in derived_lanes), blanks or a non-object values", () => {
    const values = {
      a: { value: "1", emission_class: "ocr_numeric", lane: 2 },
      b: { value: "2", emission_class: "numeric", lane: "text", derived_lanes: [2, "text"] },
      c: { value: "3", emission_class: "numeric", lane: "text" },
      d: { value: "4", emission_class: "numeric", lane: "2" },
      e: { value: "5", emission_class: "numeric", lane: 2.0 },
      f: { value: "6", emission_class: "numeric", lane: "text", derived_lanes: ["2"] },
      g: { value: "  ", emission_class: "numeric", lane: "text" },
      h: { value: null, value_decoded: "", emission_class: "numeric", lane: "text" },
    };
    const every = new Set(["numeric", "choice", "checkbox_box", "checkbox_boxless", "free_text", "ocr_numeric"]);
    expect(Object.keys(serveOverlayValues(values, every))).toEqual(["c"]);
    expect(serveOverlayValues(["x", "y"], every)).toEqual({});
    expect(serveOverlayValues("text", every)).toEqual({});
  });

  it("applies the strict sha, schema, held and base rules", () => {
    const base = { producer: "tier4_docling", schema_version: "2025-26", notes: { source_sha256: "S" } } as unknown as ArtifactRow;
    const good = { kind: "cleaned", producer: "tier2_template_overlay", schema_version: "2025-26", notes: { source_sha256: "S", held: false } } as unknown as ArtifactRow;
    expect(overlayMatchesBase(base, good)).toBe(true);
    expect(overlayMatchesBase(base, { ...good, notes: { source_sha256: "S", held: true } } as never)).toBe(false);
    expect(overlayMatchesBase(base, { ...good, notes: { source_sha256: "S" } } as never)).toBe(false);
    expect(overlayMatchesBase(base, { ...good, notes: { source_sha256: "T", held: false } } as never)).toBe(false);
    expect(overlayMatchesBase({ producer: "tier4_docling", schema_version: "2025-26", notes: {} } as never, good)).toBe(false);
    expect(overlayMatchesBase({ ...base, schema_version: null } as never, good)).toBe(false);
    expect(overlayMatchesBase({ ...base, schema_version: "2024-25" } as never, good)).toBe(false);
    expect(overlayMatchesBase(base, { ...good, schema_version: null } as never)).toBe(false);
    expect(overlayMatchesBase({ ...base, producer: "tier2_acroform" } as never, good)).toBe(false);
  });
});

describe("zero never replaces a positive base value", () => {
  it("treats every spelling of zero alike and keeps non-zero bases (negative included)", () => {
    for (const zero of [0, 0.0, "0", "0.0", "0.00", "0%", "$0", " 0 ", "0,0", { value: "0" }, { value: 0 }]) {
      expect(zeroKeepsBase(typeof zero === "object" ? zero : { value: zero }, { value: "100" })).toBe(true);
    }
    for (const notZero of ["-5", "0.5", "none", "", null, "N/A", "0 1", "00x"]) {
      expect(zeroKeepsBase({ value: notZero }, { value: "100" })).toBe(false);
    }
    for (const base of [{ value: "-3" }, { value: 100 }, { value: "12.5%" }, { value: "$1,200" }]) {
      expect(zeroKeepsBase({ value: "0" }, base)).toBe(true);
    }
    for (const base of [{ value: "0" }, { value: "0.0" }, { value: "" }, { value: "N/A" }, { value: null }, null]) {
      expect(zeroKeepsBase({ value: "0" }, base)).toBe(false);
    }
  });
});

describe("c1 headline totals handle the overlay producer explicitly", () => {
  it("uses the recorded template year and never defaults a missing one", () => {
    expect(c1TemplateForArtifact({ schemaVersion: "2025-26", producer: "tier2_template_overlay", yearStart: 2025 })).toEqual({ template: "2025-26" });
    expect(c1TemplateForArtifact({ schemaVersion: "2024-25", producer: "tier2_template_overlay", yearStart: 2024 })).toEqual({ template: "2024-25" });
    const none = c1TemplateForArtifact({ schemaVersion: null, producer: "tier2_template_overlay", yearStart: 2025 });
    expect(none.template).toBeNull();
  });
});

describe("fetchExtract", () => {
  type Call = { table: string; filters: Record<string, unknown>; range?: [number, number]; limit?: number };
  const calls: Call[] = [];
  const cacheKeys: string[][] = [];
  let artifacts: ArtifactRow[] = [];

  const rowValue = (row: ArtifactRow, key: string): unknown => {
    if (key.startsWith("notes->>")) return ((row.notes ?? {}) as Record<string, unknown>)[key.slice("notes->>".length)];
    return (row as unknown as Record<string, unknown>)[key];
  };

  beforeEach(() => {
    vi.resetModules();
    calls.length = 0;
    cacheKeys.length = 0;
    artifacts = FIXTURE.cases[0].artifacts;
    vi.doMock("next/cache", () => ({
      unstable_cache: (fn: () => unknown, key: string[]) => {
        cacheKeys.push(key);
        return fn;
      },
    }));
    vi.doMock("react", async (orig) => ({ ...(await orig<typeof import("react")>()), cache: (fn: unknown) => fn }));
    vi.doMock("./supabase", () => ({
      supabase: {
        from(table: string) {
          const call: Call = { table, filters: {} };
          const chain: Record<string, unknown> = {};
          let order: Array<[string, boolean]> = [];
          const resolve = () => {
            calls.push({ ...call });
            let rows = artifacts.filter((a) => Object.entries(call.filters).every(([k, v]) => rowValue(a, k) === v));
            rows = [...rows].sort((a, b) => {
              for (const [col, asc] of order) {
                const l = String(rowValue(a, col) ?? "");
                const r = String(rowValue(b, col) ?? "");
                if (l !== r) return (l < r ? -1 : 1) * (asc ? 1 : -1);
              }
              return 0;
            });
            if (call.range) rows = rows.slice(call.range[0], call.range[1] + 1);
            if (call.limit !== undefined) rows = rows.slice(0, call.limit);
            return rows;
          };
          chain.select = () => chain;
          chain.order = (col: string, opts?: { ascending?: boolean }) => {
            order = [...order, [col, opts?.ascending ?? true]];
            return chain;
          };
          chain.eq = (k: string, v: unknown) => {
            call.filters[k] = v;
            return chain;
          };
          chain.limit = (n: number) => {
            call.limit = n;
            return chain;
          };
          chain.range = (from: number, to: number) => {
            call.range = [from, to];
            return chain;
          };
          chain.maybeSingle = () => Promise.resolve({ data: resolve()[0] ?? null, error: null });
          chain.then = (ok: (v: unknown) => unknown) => Promise.resolve({ data: resolve(), error: null }).then(ok);
          return chain;
        },
      },
    }));
  });

  it("fallbackMatchesCanonical never treats the overlay as a fallback", async () => {
    const { fallbackMatchesCanonical } = await import("./queries");
    const canonical = { id: "b", producer: "tier4_docling", producer_version: "1", notes: { markdown: "m" } } as unknown as ArtifactRow;
    const overlay = { id: "o", producer: "tier2_template_overlay", kind: "cleaned", notes: { base_artifact_id: "b" } } as unknown as ArtifactRow;
    expect(fallbackMatchesCanonical(canonical, overlay)).toBe(false);
    expect(fallbackMatchesCanonical(canonical, { ...overlay, producer: "tier4_llm_fallback" } as never)).toBe(true);
  });

  it("with `none` (the rollback lever) issues the same two queries, the original cache key and no overlay key", async () => {
    vi.stubEnv("OVERLAY_SERVE_CLASSES", "none");
    const { fetchExtract } = await import("./queries");
    const out = await fetchExtract("d1", "school-1");
    expect(calls.map((c) => c.filters.producer ?? c.filters.kind)).toEqual(["canonical", "tier4_llm_fallback"]);
    expect(cacheKeys).toEqual([["fetchExtract", "d1"]]);
    expect("overlay" in out).toBe(false);
    expect(plain(out.mergedValues)).toEqual(FIXTURE.cases[0].variants![0].values);
    vi.unstubAllEnvs();
  });

  it("with the variable unset or empty the default set serves: the key carries it and a document without an overlay costs exactly one extra query", async () => {
    for (const value of [undefined, ""]) {
      calls.length = 0;
      cacheKeys.length = 0;
      artifacts = FIXTURE.cases[1].artifacts.filter((a) => a.producer !== "tier2_template_overlay").map((a) => ({ ...a, producer: "tier4_docling", notes: { source_sha256: "sha-B", values: {} } })) as ArtifactRow[];
      if (value === undefined) vi.unstubAllEnvs();
      else vi.stubEnv("OVERLAY_SERVE_CLASSES", value);
      vi.resetModules();
      const { fetchExtract } = await import("./queries");
      const out = await fetchExtract("d2", "school-1");
      expect(calls.map((c) => c.filters.producer ?? c.filters.kind)).toEqual(["canonical", "tier4_llm_fallback", "tier2_template_overlay"]);
      expect(cacheKeys).toEqual([["fetchExtract", "d2", "on:checkbox_box+choice+numeric+ocr_numeric"]]);
      expect(out.overlay ?? null).toBeNull();
    }
    vi.unstubAllEnvs();
  });

  it("with a set it adds overlay queries filtered by producer, kind, schema and sha, and the set is in the cache key", async () => {
    vi.stubEnv("OVERLAY_SERVE_CLASSES", "numeric,choice,checkbox_box");
    const { fetchExtract } = await import("./queries");
    const out = await fetchExtract("d1", "school-1");
    const overlayCalls = calls.filter((c) => c.filters.producer === "tier2_template_overlay");
    expect(overlayCalls).toHaveLength(1);
    expect(overlayCalls[0].filters).toMatchObject({ kind: "cleaned", schema_version: "2025-26", "notes->>source_sha256": "sha-A" });
    expect(cacheKeys).toEqual([["fetchExtract", "d1", "on:checkbox_box+choice+numeric"]]);
    expect(out.overlay?.id).toBe("ova");
    expect(plain(out.mergedValues)).toEqual(FIXTURE.cases[0].variants![1].values);
    vi.unstubAllEnvs();
  });

  it("finds an older eligible overlay behind a run of newer held ones (no truncation before eligibility)", async () => {
    const base = FIXTURE.cases[0].artifacts.find((a) => a.id === "t4a")!;
    const held = Array.from({ length: 30 }, (_, i) => ({
      id: `held-${String(i).padStart(2, "0")}`, document_id: "d1", kind: "cleaned", producer: "tier2_template_overlay",
      producer_version: "0.7.0", schema_version: "2025-26", created_at: `2026-12-${String(i + 1).padStart(2, "0")}T00:00:00+00:00`,
      notes: { source_sha256: "sha-A", held: true, values: { "B.101": { value: "bad", emission_class: "numeric", lane: "text" } } },
    })) as unknown as ArtifactRow[];
    const eligible = { id: "ok", document_id: "d1", kind: "cleaned", producer: "tier2_template_overlay", producer_version: "0.7.0",
      schema_version: "2025-26", created_at: "2026-11-20T00:00:00+00:00",
      notes: { source_sha256: "sha-A", held: false, values: { "B.101": { value: "good", emission_class: "numeric", lane: "text" } } } } as unknown as ArtifactRow;
    artifacts = [base, eligible, ...held];
    vi.stubEnv("OVERLAY_SERVE_CLASSES", "numeric");
    const { fetchExtract } = await import("./queries");
    const out = await fetchExtract("d1", "school-1");
    expect(out.overlay?.id).toBe("ok");
    expect(plain(out.mergedValues)["B.101"]).toBe("good");
    expect(calls.filter((c) => c.filters.producer === "tier2_template_overlay").length).toBeGreaterThan(1); // it paged
    vi.unstubAllEnvs();
  });

  it("issues no overlay query when the base cannot match (no recorded sha)", async () => {
    artifacts = [{ id: "t4", document_id: "d1", kind: "canonical", producer: "tier4_docling", schema_version: "2025-26", created_at: "2026-11-01T00:00:00+00:00", notes: { values: {} } } as unknown as ArtifactRow];
    vi.stubEnv("OVERLAY_SERVE_CLASSES", "numeric");
    const { fetchExtract } = await import("./queries");
    await fetchExtract("d1", "school-1");
    expect(calls.filter((c) => c.filters.producer === "tier2_template_overlay")).toHaveLength(0);
    vi.unstubAllEnvs();
  });
});
