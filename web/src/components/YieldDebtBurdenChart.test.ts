import { describe, expect, it } from "vitest";
import {
  nearestPoint,
  radiusForNetPrice,
  ys,
  type Point,
} from "@/components/YieldDebtBurdenChart";
import { panelBSchools } from "@/lib/pricing-power-recipe-analysis";
import { PRICING_POWER_SCHOOLS } from "@/lib/pricing-power-recipe-data";

const PANEL_B = panelBSchools(PRICING_POWER_SCHOOLS);

function pointAt(cx: number, cy: number): Point {
  return { ...PANEL_B[0], cx, cy, r: 3.5 };
}

describe("YieldDebtBurdenChart ys scale", () => {
  it("clamps burden to the 0-16% axis window", () => {
    // Below-zero and above-max burdens pin to the axis ends instead of
    // plotting outside the frame.
    expect(ys(-0.05)).toBe(ys(0));
    expect(ys(0.16)).toBe(ys(0.9));
  });

  it("maps higher burden to smaller y (up the chart)", () => {
    expect(ys(0.12)).toBeLessThan(ys(0.04));
    expect(ys(0)).toBeGreaterThan(ys(0.16));
  });
});

describe("radiusForNetPrice", () => {
  it("returns the uniform radius when size encoding is off", () => {
    expect(radiusForNetPrice(50_000, 10_000, 60_000, false)).toBe(3.5);
  });

  it("returns the uniform radius when the price span is zero", () => {
    expect(radiusForNetPrice(20_000, 20_000, 20_000, true)).toBe(3.5);
  });

  it("scales by sqrt between the min and max radius, clamped", () => {
    const min = radiusForNetPrice(10_000, 10_000, 60_000, true);
    const max = radiusForNetPrice(60_000, 10_000, 60_000, true);
    expect(min).toBe(3.5);
    expect(max).toBe(6.5);
    // sqrt scaling: the midpoint price sits above the midpoint radius.
    const mid = radiusForNetPrice(35_000, 10_000, 60_000, true);
    expect(mid).toBeGreaterThan((min + max) / 2);
    expect(mid).toBeLessThan(max);
    // Out-of-range prices clamp instead of extrapolating.
    expect(radiusForNetPrice(5_000, 10_000, 60_000, true)).toBe(3.5);
    expect(radiusForNetPrice(90_000, 10_000, 60_000, true)).toBe(6.5);
  });
});

describe("nearestPoint", () => {
  const pts = [pointAt(100, 100), pointAt(120, 100), pointAt(500, 400)];

  it("returns the closest point within the max distance", () => {
    expect(nearestPoint(pts, 102, 101, 20)).toBe(pts[0]);
    expect(nearestPoint(pts, 118, 99, 20)).toBe(pts[1]);
  });

  it("returns null when nothing is within the max distance", () => {
    expect(nearestPoint(pts, 300, 250, 20)).toBeNull();
    expect(nearestPoint([], 100, 100, 20)).toBeNull();
  });

  it("treats maxDist as exclusive so a dot exactly at the edge misses", () => {
    expect(nearestPoint([pointAt(100, 100)], 120, 100, 20)).toBeNull();
    expect(nearestPoint([pointAt(100, 100)], 119.9, 100, 20)).not.toBeNull();
  });
});
