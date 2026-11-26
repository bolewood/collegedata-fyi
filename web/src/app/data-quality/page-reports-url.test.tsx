import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { snapshotDay } from "@/lib/data-quality";

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
import { setLaunchGate } from "@/lib/__fixtures__/data-quality-gate";

afterEach(() => {
  mocks.props.length = 0;
  mocks.loadReportsFor.mockReset();
});

function renderAt(launched: boolean, reports: unknown) {
  mocks.loadReportsFor.mockReturnValue(reports);
  setLaunchGate(launched);
  renderToStaticMarkup(<DataQualityPage />);
  return mocks.props.at(-1)!.reportsUrl;
}

describe("the reports URL the page passes", () => {
  it("is null while the gate is closed, even when the snapshot has a reports file", () => {
    expect(renderAt(false, { some: "reports" })).toBeNull();
  });

  it("is the route for the snapshot's date once launched, built from the one date helper", () => {
    expect(renderAt(true, { some: "reports" })).toBe(`/data-quality/reports/${snapshotDay(FIXTURE_SNAPSHOT)}`);
    expect(snapshotDay(FIXTURE_SNAPSHOT)).toBe("2026-11-24");
    expect(snapshotDay({ snapshot_of: "2026-11-25T23:59:59Z" })).toBe("2026-11-25");
    expect(snapshotDay({ snapshot_of: "2026-11-26T00:00:00+02:00" })).toBe("2026-11-25");   // the UTC date, as the file name uses
  });

  it("is null for a snapshot with no reports file, launched or not", () => {
    expect(renderAt(true, null)).toBeNull();
    expect(renderAt(false, null)).toBeNull();
  });

  it("is checked at build even before launch: the page always loads the reports for the snapshot", () => {
    renderAt(false, null);
    expect(mocks.loadReportsFor).toHaveBeenCalledWith(FIXTURE_SNAPSHOT);
  });
});
