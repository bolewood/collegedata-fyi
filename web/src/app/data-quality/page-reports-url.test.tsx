import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_QUALITY_LAUNCH_DATE, snapshotDay } from "@/lib/data-quality";

// The page decides, on the server, whether the counts are buttons: it hands the view a reports URL only when launched.
const mocks = vi.hoisted(() => ({ props: [] as { reportsUrl?: string | null }[], loadReportsFor: vi.fn() }));
vi.mock("@/components/DataQualityView", () => ({
  DataQualityView: (props: { reportsUrl?: string | null }) => {
    mocks.props.push(props);
    return null;
  },
}));
vi.mock("@/lib/data-quality-snapshots", () => ({
  loadLatestSnapshot: () => FIXTURE_SNAPSHOT,
  loadAllSnapshots: () => [FIXTURE_SNAPSHOT],
  loadReportsFor: mocks.loadReportsFor,
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));

import DataQualityPage from "./page";

const LAUNCH = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);
afterEach(() => {
  vi.useRealTimers();
  mocks.props.length = 0;
  mocks.loadReportsFor.mockReset();
});

function renderAt(ms: number, reports: unknown) {
  mocks.loadReportsFor.mockReturnValue(reports);
  vi.useFakeTimers();
  vi.setSystemTime(ms);
  renderToStaticMarkup(<DataQualityPage />);
  return mocks.props.at(-1)!.reportsUrl;
}

describe("the reports URL the page passes", () => {
  it("is null while the gate is closed, even when the snapshot has a reports file", () => {
    expect(renderAt(LAUNCH - 1000, { some: "reports" })).toBeNull();
  });

  it("is the route for the snapshot's date once launched, built from the one date helper", () => {
    expect(renderAt(LAUNCH, { some: "reports" })).toBe(`/data-quality/reports/${snapshotDay(FIXTURE_SNAPSHOT)}`);
    expect(snapshotDay(FIXTURE_SNAPSHOT)).toBe("2026-11-24");
    expect(snapshotDay({ snapshot_of: "2026-11-25T23:59:59Z" })).toBe("2026-11-25");
    expect(snapshotDay({ snapshot_of: "2026-11-26T00:00:00+02:00" })).toBe("2026-11-25");   // the UTC date, as the file name uses
  });

  it("is null for a snapshot with no reports file, launched or not", () => {
    expect(renderAt(LAUNCH, null)).toBeNull();
    expect(renderAt(LAUNCH - 1000, null)).toBeNull();
  });

  it("is checked at build even before launch: the page always loads the reports for the snapshot", () => {
    renderAt(LAUNCH - 1000, null);
    expect(mocks.loadReportsFor).toHaveBeenCalledWith(FIXTURE_SNAPSHOT);
  });
});
