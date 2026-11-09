import { createHash, timingSafeEqual } from "node:crypto";
import { revalidatePath, revalidateTag } from "next/cache";
import { SCHOOL_DATA_TAG, schoolCacheTag } from "./school-cache-tags";

/** Max school ids per request. The extraction worker batches at the same size. */
export const MAX_SCHOOL_IDS = 100;

const SCHOOL_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const MAX_SLUG_LENGTH = 100;

/** Tags are expired immediately (not stale-while-revalidate): the next render
 *  must read fresh data, not the stale entry we are trying to replace. */
const EXPIRE_NOW = { expire: 0 } as const;

export function isValidSchoolSlug(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= MAX_SLUG_LENGTH &&
    SCHOOL_SLUG.test(value)
  );
}

/** Constant-time bearer check; hashing equalizes lengths so none leak. */
export function isAuthorized(header: string | null, secret: string): boolean {
  const match = /^Bearer (.+)$/.exec(header ?? "");
  if (!match) return false;
  const digest = (v: string) => createHash("sha256").update(v).digest();
  return timingSafeEqual(digest(match[1]), digest(secret));
}

export type RevalidateRequest =
  | { kind: "all" }
  | { kind: "schools"; schoolIds: string[]; rejected: string[] };

export type ParseResult =
  | { ok: true; request: RevalidateRequest }
  | { ok: false; error: string };

export function parseRevalidateBody(body: unknown): ParseResult {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return { ok: false, error: "Body must be a JSON object." };
  }
  const { all, school_ids: schoolIds } = body as Record<string, unknown>;
  if (all !== undefined && all !== true) {
    return { ok: false, error: '"all" must be true when present.' };
  }
  if (all === true) {
    if (schoolIds !== undefined) {
      return { ok: false, error: 'Pass either "all" or "school_ids", not both.' };
    }
    return { ok: true, request: { kind: "all" } };
  }
  if (!Array.isArray(schoolIds) || schoolIds.length === 0) {
    return { ok: false, error: 'Pass {"school_ids": [...]} or {"all": true}.' };
  }
  if (schoolIds.length > MAX_SCHOOL_IDS) {
    return { ok: false, error: `At most ${MAX_SCHOOL_IDS} school_ids per request.` };
  }
  const valid = new Set<string>();
  const rejected: string[] = [];
  for (const id of schoolIds) {
    if (isValidSchoolSlug(id)) valid.add(id);
    else rejected.push(String(id).slice(0, 40));
  }
  if (valid.size === 0) {
    return { ok: false, error: "No valid school_ids (expected lowercase slugs)." };
  }
  return {
    ok: true,
    request: { kind: "schools", schoolIds: [...valid], rejected },
  };
}

export type RevalidateCounts = { schools: number; tags: number; paths: number };

/**
 * Expire cached data and mark pages stale. Marking is lazy: nothing is
 * re-rendered until the next visit, so this never causes a query burst.
 */
export function applyRevalidation(request: RevalidateRequest): RevalidateCounts {
  if (request.kind === "all") {
    revalidateTag(SCHOOL_DATA_TAG, EXPIRE_NOW);
    revalidatePath("/schools/[school_id]", "layout");
    return { schools: 0, tags: 1, paths: 1 };
  }
  let tags = 0;
  let paths = 0;
  for (const id of request.schoolIds) {
    revalidateTag(schoolCacheTag(id), EXPIRE_NOW);
    tags += 1;
    // A layout revalidation covers every page nested under the school: hub,
    // year pages, early-decision, gpa, acceptance-rate, feed and downloads.
    revalidatePath(`/schools/${id}`, "layout");
    revalidatePath(`/schools/${id}`);
    revalidatePath(`/schools/${id}/opengraph-image`);
    paths += 3;
  }
  return { schools: request.schoolIds.length, tags, paths };
}
