import { beforeEach, describe, expect, it, vi } from "vitest";

const { revalidateTag, revalidatePath } = vi.hoisted(() => ({
  revalidateTag: vi.fn(),
  revalidatePath: vi.fn(),
}));
vi.mock("next/cache", () => ({ revalidateTag, revalidatePath }));

const { fetchCanonicalSchoolId } = vi.hoisted(() => ({
  fetchCanonicalSchoolId: vi.fn(async (id: string) => (id === "old-alias" ? "canon" : null)),
}));
vi.mock("@/lib/queries", () => ({ fetchCanonicalSchoolId }));

import { POST } from "../app/api/revalidate/route";
import {
  MAX_SCHOOL_IDS,
  isAuthorized,
  parseRevalidateBody,
} from "./revalidate-schools";
import { schoolCacheTag } from "./school-cache-tags";

function req(body: unknown, auth: string | null = "Bearer s3cret", raw?: string) {
  return new Request("https://example.test/api/revalidate", {
    method: "POST",
    headers: auth ? { authorization: auth } : {},
    body: raw ?? JSON.stringify(body),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  process.env.REVALIDATE_SECRET = "s3cret";
});

describe("isAuthorized", () => {
  it("accepts only the exact bearer secret", () => {
    expect(isAuthorized("Bearer s3cret", "s3cret")).toBe(true);
    expect(isAuthorized("Bearer s3cre", "s3cret")).toBe(false);
    expect(isAuthorized("Bearer s3cret2", "s3cret")).toBe(false);
    expect(isAuthorized("s3cret", "s3cret")).toBe(false);
    expect(isAuthorized(null, "s3cret")).toBe(false);
  });
});

describe("parseRevalidateBody", () => {
  it("validates shapes", () => {
    expect(parseRevalidateBody(null).ok).toBe(false);
    expect(parseRevalidateBody([]).ok).toBe(false);
    expect(parseRevalidateBody({}).ok).toBe(false);
    expect(parseRevalidateBody({ all: false }).ok).toBe(false);
    expect(parseRevalidateBody({ all: true, school_ids: ["a"] }).ok).toBe(false);
    expect(parseRevalidateBody({ school_ids: [] }).ok).toBe(false);
    expect(parseRevalidateBody({ school_ids: ["../x", "A b"] }).ok).toBe(false);
    expect(
      parseRevalidateBody({ school_ids: Array(MAX_SCHOOL_IDS + 1).fill("yale") }).ok,
    ).toBe(false);
  });

  it("dedupes and separates rejected slugs", () => {
    expect(parseRevalidateBody({ school_ids: ["yale", "yale", "Bad/Slug", 5] })).toEqual({
      ok: true,
      request: { kind: "schools", schoolIds: ["yale"], rejected: ["Bad/Slug", "5"] },
    });
  });
});

describe("POST /api/revalidate", () => {
  it("503s when the secret is unset", async () => {
    delete process.env.REVALIDATE_SECRET;
    const res = await POST(req({ all: true }));
    expect(res.status).toBe(503);
    expect(revalidateTag).not.toHaveBeenCalled();
  });

  it("401s without a valid token and does nothing", async () => {
    expect((await POST(req({ all: true }, null))).status).toBe(401);
    expect((await POST(req({ all: true }, "Bearer nope"))).status).toBe(401);
    expect(revalidateTag).not.toHaveBeenCalled();
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("400s on bad JSON or bad bodies", async () => {
    expect((await POST(req(null, "Bearer s3cret", "{nope"))).status).toBe(400);
    expect((await POST(req({ school_ids: [] }))).status).toBe(400);
  });

  it("expires per-school tags and paths", async () => {
    const res = await POST(req({ school_ids: ["yale", "mit", "BAD"] }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      revalidated: true,
      schools: 2,
      tags: 2,
      paths: 4,
      rejected: ["BAD"],
    });
    expect(revalidateTag).toHaveBeenCalledWith(schoolCacheTag("yale"), { expire: 0 });
    expect(revalidateTag).toHaveBeenCalledWith(schoolCacheTag("mit"), { expire: 0 });
    expect(revalidatePath).toHaveBeenCalledWith("/schools/yale");
    expect(revalidatePath).toHaveBeenCalledWith("/schools/yale/opengraph-image");
    expect(revalidatePath).toHaveBeenCalledWith("/schools/mit");
  });

  it("also revalidates the canonical slug of a live alias, tolerating resolver errors", async () => {
    fetchCanonicalSchoolId.mockRejectedValueOnce(new Error("db down"));
    const res = await POST(req({ school_ids: ["old-alias", "yale"] }));
    expect(res.status).toBe(200);
    // first call (old-alias) rejects -> raw ids only
    expect(revalidateTag).toHaveBeenCalledWith(schoolCacheTag("old-alias"), { expire: 0 });
    vi.clearAllMocks();
    const res2 = await POST(req({ school_ids: ["old-alias"] }));
    expect((await res2.json()).schools).toBe(2);
    expect(revalidateTag).toHaveBeenCalledWith(schoolCacheTag("canon"), { expire: 0 });
    expect(revalidatePath).toHaveBeenCalledWith("/schools/canon");
  });

  it("expires the global tag and all school layouts for all:true", async () => {
    const res = await POST(req({ all: true }));
    expect(res.status).toBe(200);
    expect(revalidateTag).toHaveBeenCalledWith("school-data", { expire: 0 });
    expect(revalidatePath).toHaveBeenCalledWith("/schools/[school_id]", "layout");
  });
});
