// Server-only: uses node:fs. Import from server components and route handlers.
import fs from "node:fs";
import path from "node:path";
import {
  SnapshotError,
  isDataQualityLaunched,
  selectSnapshot,
  type QualitySnapshot,
} from "./data-quality";

/** Where committed snapshots live. See the README in that directory. */
export const SNAPSHOT_DIR = path.join(process.cwd(), "src", "data", "data-quality");

/**
 * Newest committed snapshot, read at build (and on ISR re-render).
 *
 * Failure rules (PRD 040): two files with one date, a file with a
 * `public_format` this page doesn't know, or a malformed file always throw.
 * An empty directory throws once the page is launched; before launch it
 * returns null so the repo can build while the lead hasn't committed the
 * first snapshot yet. A null result means "no data", never "zero".
 */
export function loadLatestSnapshot(): QualitySnapshot | null {
  let names: string[];
  try {
    names = fs.readdirSync(SNAPSHOT_DIR).filter((n) => n.endsWith(".json")).sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      names = [];
    } else {
      throw error;
    }
  }
  const files = names.map((name) => {
    try {
      return { name, json: JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, name), "utf8")) as unknown };
    } catch (error) {
      throw new SnapshotError(`data-quality snapshot ${name} is not valid JSON: ${(error as Error).message}`);
    }
  });
  return selectSnapshot(files, isDataQualityLaunched());
}
