// Server-only: uses node:fs. Import from server components and route handlers.
import fs from "node:fs";
import path from "node:path";
import {
  SnapshotError,
  selectSnapshot,
  snapshotDay,
  type QualitySnapshot,
} from "./data-quality";
import { ReportsError, reportsAgreementProblems, validateReports, type ReportsFile } from "./data-quality-reports";

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

/**
 * The reports file written with a snapshot (reports/<date>.json), or null when that snapshot has none (one written before
 * this existed). The build fails if the file is not valid or if any count in the snapshot differs from the number of
 * rows the file lists for it, so the lists on the page can never disagree with the numbers beside them.
 */
export function loadReportsFor(snapshot: QualitySnapshot, dir: string = SNAPSHOT_DIR): ReportsFile | null {
  const day = snapshotDay(snapshot);
  const file = path.join(dir, "reports", `${day}.json`);
  let text: string;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch (error) {
    throw new ReportsError(`data-quality reports ${day}.json is not valid JSON: ${(error as Error).message}`);
  }
  const reports = validateReports(json, `${day}.json`);
  const problems = reportsAgreementProblems(snapshot, reports);
  if (problems.length) {
    throw new ReportsError(`data-quality reports ${day}.json disagrees with its snapshot in ${problems.length} places, e.g. ${problems[0]}`);
  }
  return reports;
}
