// Server-only: uses node:fs. Import from server components and route handlers.
import fs from "node:fs";
import path from "node:path";
import {
  SnapshotError,
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
 * An empty directory also throws, gate open or closed: a missing snapshot is
 * never shown as "no data, ok".
 */
export function loadLatestSnapshot(dir: string = SNAPSHOT_DIR): QualitySnapshot {
  let names: string[];
  try {
    names = fs.readdirSync(dir).filter((n) => n.endsWith(".json")).sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      names = [];
    } else {
      throw error;
    }
  }
  const files = names.map((name) => {
    try {
      return { name, json: JSON.parse(fs.readFileSync(path.join(dir, name), "utf8")) as unknown };
    } catch (error) {
      throw new SnapshotError(`data-quality snapshot ${name} is not valid JSON: ${(error as Error).message}`);
    }
  });
  return selectSnapshot(files);
}
