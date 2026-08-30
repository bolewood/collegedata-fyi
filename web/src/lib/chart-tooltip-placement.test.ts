import { describe, expect, it } from "vitest";
import {
  placeTooltipAwayFromPointer,
  tooltipCoversPointer,
} from "./chart-tooltip-placement";

const CHART = {
  chartLeft: 0,
  chartTop: 0,
  chartWidth: 920,
  chartHeight: 580,
  tooltipWidth: 260,
  tooltipHeight: 150,
  gap: 18,
};

describe("placeTooltipAwayFromPointer", () => {
  it("puts a right-side point's box to the left, clear of the pointer", () => {
    const placed = placeTooltipAwayFromPointer({
      ...CHART,
      pointerX: 860,
      pointerY: 220,
    });
    expect(placed.side).toBe("left");
    expect(placed.left + 260).toBeCloseTo(860 - 18, 5);
    expect(placed.top).toBeLessThan(220);
    expect(placed.top + 150).toBeGreaterThan(220);
    expect(
      tooltipCoversPointer(
        { left: placed.left, top: placed.top, width: 260, height: 150 },
        860,
        220,
        18,
      ),
    ).toBe(false);
  });

  it("puts a left-side point's box to the right, clear of the pointer", () => {
    const placed = placeTooltipAwayFromPointer({
      ...CHART,
      pointerX: 80,
      pointerY: 300,
    });
    expect(placed.side).toBe("right");
    expect(placed.left).toBeCloseTo(80 + 18, 5);
    expect(
      tooltipCoversPointer(
        { left: placed.left, top: placed.top, width: 260, height: 150 },
        80,
        300,
        18,
      ),
    ).toBe(false);
  });

  it("does not slide a clamped left-side box back over a far-right point", () => {
    const placed = placeTooltipAwayFromPointer({
      ...CHART,
      pointerX: 900,
      pointerY: 40,
      tooltipWidth: 400,
      tooltipHeight: 180,
    });
    expect(
      tooltipCoversPointer(
        { left: placed.left, top: placed.top, width: 400, height: 180 },
        900,
        40,
        18,
      ),
    ).toBe(false);
    expect(placed.side).not.toBe("right");
  });

  it("keeps the box inside the chart", () => {
    const placed = placeTooltipAwayFromPointer({
      ...CHART,
      pointerX: 880,
      pointerY: 540,
    });
    expect(placed.left).toBeGreaterThanOrEqual(0);
    expect(placed.top).toBeGreaterThanOrEqual(0);
    expect(placed.left + 260).toBeLessThanOrEqual(920);
    expect(placed.top + 150).toBeLessThanOrEqual(580);
  });
});
