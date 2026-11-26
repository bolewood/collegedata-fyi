import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO_SLUG, REPO_URL } from "./repo";

const OLD_REPO = "bolewood/collegedata-fyi";

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

  it("is the only place web/src names the repository (tests may use the old name as a fixture)", () => {
    const offenders = sourceFiles(__dirname + "/..")
      .filter((f) => !/\.test\.tsx?$/.test(f))
      .filter((f) => readFileSync(f, "utf8").includes(OLD_REPO));
    expect(offenders).toEqual([]);
  });
});
