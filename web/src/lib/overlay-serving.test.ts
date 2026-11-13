import { readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ArtifactRow } from "./types";
import {
  mergeWithOverlay,
  overlayMatchesBase,
  overlayServeKey,
  parseOverlayServeClasses,
  serveOverlayValues,
} from "./overlay-serving";
import { c1TemplateForArtifact } from "./c1-headline-totals";

type Variant = {
  serve: string[];
  values: Record<string, string>;
  overlay_artifact_id: string | null;
  sources?: Record<string, string>;
};
type Case = {
  name: string;
  artifacts: ArtifactRow[];
  base_artifact_id?: string;
  variants?: Variant[];
  per_selector?: Record<string, { base_artifact_id: string; values: Record<string, string>; serve?: string[]; overlay_artifact_id?: string }>;
};

const FIXTURE = JSON.parse(
  readFileSync(join(process.cwd(), "..", "tools/browser_backend/fixtures/overlay_parity.json"), "utf8"),
) as { cases: Case[] };

const plain = (values: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(values).map(([k, v]) => [k, (v as { value?: string } | null)?.value ?? v]),
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
  const overlays = artifacts.filter((a) => a.producer === "tier2_template_overlay");
  return {
    canonical,
    ...mergeWithOverlay({
      canonical,
      fallbackValues,
      overlayCandidates: overlays,
      classes: parseOverlayServeClasses(serve.join(",")),
    }),
  };
}

describe("overlay serving (parity fixture shared with Python)", () => {
  for (const c of FIXTURE.cases) {
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
    expect(c.per_selector!.sql.base_artifact_id).not.toBe(expected.base_artifact_id);
  });

  it("with the set empty the overlay rows are never even read", () => {
    const c = FIXTURE.cases[0];
    const withOverlays = webSelect(c.artifacts, []);
    const without = webSelect(c.artifacts.filter((a) => a.producer !== "tier2_template_overlay"), []);
    expect(withOverlays.mergedValues).toEqual(without.mergedValues);
    expect(withOverlays.overlay).toBeNull();
  });
});

describe("served-class configuration", () => {
  it("defaults to empty and fails closed on an unknown name", () => {
    expect(parseOverlayServeClasses(undefined).size).toBe(0);
    expect(parseOverlayServeClasses("").size).toBe(0);
    expect(Array.from(parseOverlayServeClasses(" numeric , choice "))).toEqual(["numeric", "choice"]);
    expect(parseOverlayServeClasses("numeric,bogus").size).toBe(0);
  });

  it("is part of the cache key", () => {
    expect(overlayServeKey(new Set())).toBe("off");
    expect(overlayServeKey(new Set(["numeric", "choice"]))).toBe("on:choice+numeric");
    expect(overlayServeKey(new Set(["numeric"]))).not.toBe(overlayServeKey(new Set(["numeric", "choice"])));
  });

  it("never serves Lane 2 evidence, whatever the set says", () => {
    const values = {
      a: { value: "1", emission_class: "ocr_numeric", lane: 2 },
      b: { value: "2", emission_class: "numeric", lane: "text", derived_lanes: [2, "text"] },
      c: { value: "3", emission_class: "numeric", lane: "text" },
    } as never;
    const every = new Set(["numeric", "choice", "checkbox_box", "checkbox_boxless", "free_text", "ocr_numeric"]);
    expect(Object.keys(serveOverlayValues(values, every))).toEqual(["c"]);
  });

  it("applies the strict sha, held and base rules", () => {
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

describe("c1 headline totals handle the overlay producer explicitly", () => {
  it("uses the recorded template year and never defaults a missing one", () => {
    expect(c1TemplateForArtifact({ schemaVersion: "2025-26", producer: "tier2_template_overlay", yearStart: 2025 })).toEqual({ template: "2025-26" });
    expect(c1TemplateForArtifact({ schemaVersion: "2024-25", producer: "tier2_template_overlay", yearStart: 2024 })).toEqual({ template: "2024-25" });
    const none = c1TemplateForArtifact({ schemaVersion: null, producer: "tier2_template_overlay", yearStart: 2025 });
    expect(none.template).toBeNull();
  });
});

describe("fetchExtract", () => {
  const calls: Array<Record<string, unknown>> = [];
  let artifacts: ArtifactRow[] = [];

  beforeEach(() => {
    vi.resetModules();
    calls.length = 0;
    artifacts = FIXTURE.cases[0].artifacts;
    vi.doMock("next/cache", () => ({ unstable_cache: (fn: () => unknown) => fn }));
    vi.doMock("react", async (orig) => ({ ...(await orig<typeof import("react")>()), cache: (fn: unknown) => fn }));
    vi.doMock("./supabase", () => ({
      supabase: {
        from(table: string) {
          const filters: Record<string, unknown> = { table };
          const chain: Record<string, unknown> = {};
          const resolve = () => {
            calls.push({ ...filters });
            let rows = artifacts.filter((a) => (filters.kind ? a.kind === filters.kind : true) && (filters.producer ? a.producer === filters.producer : true));
            rows = [...rows].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
            return rows;
          };
          for (const name of ["select", "order"]) chain[name] = () => chain;
          chain.eq = (k: string, v: unknown) => {
            filters[k] = v;
            return chain;
          };
          chain.limit = (n: number) => {
            filters.limit = n;
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

  it("with the set empty issues the same two queries and returns no overlay key", async () => {
    vi.stubEnv("OVERLAY_SERVE_CLASSES", "");
    const { fetchExtract } = await import("./queries");
    const out = await fetchExtract("d1", "school-1");
    expect(calls.map((c) => c.producer ?? c.kind)).toEqual(["canonical", "tier4_llm_fallback"]);
    expect("overlay" in out).toBe(false);
    expect(plain(out.mergedValues)).toEqual(FIXTURE.cases[0].variants![0].values);
    vi.unstubAllEnvs();
  });

  it("with a set it adds one overlay query and merges", async () => {
    vi.stubEnv("OVERLAY_SERVE_CLASSES", "numeric,choice,checkbox_box");
    const { fetchExtract } = await import("./queries");
    const out = await fetchExtract("d1", "school-1");
    expect(calls.some((c) => c.producer === "tier2_template_overlay")).toBe(true);
    expect(out.overlay?.id).toBe("ova");
    expect(plain(out.mergedValues)).toEqual(FIXTURE.cases[0].variants![1].values);
    vi.unstubAllEnvs();
  });
});
