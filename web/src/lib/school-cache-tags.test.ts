import { describe, expect, it } from "vitest";
import { isRoutableSchoolSlug, schoolCacheTag } from "./school-cache-tags";

// Sentry COLLEGEDATA-FYI-22: /schools/cal-poly-san-luis-obisp%D0%BE (the last
// letter is a Cyrillic "о") put a non-ASCII tag in x-next-cache-tags and the
// response crashed with "Invalid character in header content".
const CYRILLIC_SLUG = "cal-poly-san-luis-obispо";

describe("school slug guard", () => {
  it("accepts real slugs and the legacy ampersand alias", () => {
    for (const slug of ["yale", "cal-poly-san-luis-obispo", "university-of-hawaii-at-manoa", "w&m"]) {
      expect(isRoutableSchoolSlug(slug)).toBe(true);
    }
  });

  it("rejects non-ASCII, spaces, control characters, empty and oversized slugs", () => {
    for (const slug of [CYRILLIC_SLUG, "é", "a b", "a\nb", "", "a".repeat(121)]) {
      expect(isRoutableSchoolSlug(slug)).toBe(false);
    }
  });

  it("leaves a real slug's tag unchanged", () => {
    expect(schoolCacheTag("yale")).toBe("school:yale");
    expect(schoolCacheTag("w&m")).toBe("school:w&m");
  });

  it("never returns a tag that is invalid in an HTTP header", () => {
    for (const slug of [CYRILLIC_SLUG, "a\r\nx-injected: 1", "日本".repeat(200)]) {
      const tag = schoolCacheTag(slug);
      expect(tag).toMatch(/^[\x21-\x7E]+$/);
      expect(tag.length).toBeLessThanOrEqual(207);
      expect(() => new Headers({ "x-next-cache-tags": tag })).not.toThrow();
    }
  });
});
