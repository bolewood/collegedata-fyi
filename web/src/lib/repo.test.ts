import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO_SLUG, REPO_URL } from "./repo";

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe("repository link", () => {
  it("points at bolewood/quadfile", () => {
    expect(REPO_SLUG).toBe("bolewood/quadfile");
    expect(REPO_URL).toBe("https://github.com/bolewood/quadfile");
  });

  it("is the only non-test file in web/src that hard-codes a bolewood repository", () => {
    const offenders = sourceFiles(__dirname + "/..")
      .filter((f) => !/\.test\.tsx?$/.test(f))
      .filter((f) => !f.endsWith("/lib/repo.ts"))
      .filter((f) => /github\.com\/bolewood|bolewood\/(collegedata|quadfile)/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});
