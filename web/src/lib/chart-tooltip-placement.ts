export type TooltipSide = "left" | "right" | "above" | "below";

export type TooltipPlacement = {
  left: number;
  top: number;
  side: TooltipSide;
};

export type TooltipPlacementInput = {
  pointerX: number;
  pointerY: number;
  chartLeft: number;
  chartTop: number;
  chartWidth: number;
  chartHeight: number;
  tooltipWidth: number;
  tooltipHeight: number;
  gap?: number;
};

export function tooltipCoversPointer(
  box: { left: number; top: number; width: number; height: number },
  pointerX: number,
  pointerY: number,
  gap = 0,
): boolean {
  return (
    pointerX >= box.left - gap &&
    pointerX <= box.left + box.width + gap &&
    pointerY >= box.top - gap &&
    pointerY <= box.top + box.height + gap
  );
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.max(min, Math.min(value, max));
}

/**
 * Place a hover box so it stays inside the chart and never covers the
 * pointer. Prefer the opposite horizontal side of a right- or left-edge
 * point so neighboring dots stay reachable.
 */
export function placeTooltipAwayFromPointer(
  input: TooltipPlacementInput,
): TooltipPlacement {
  const gap = input.gap ?? 18;
  const {
    pointerX: px,
    pointerY: py,
    chartLeft: cl,
    chartTop: ct,
    chartWidth: cw,
    chartHeight: ch,
    tooltipWidth: tw,
    tooltipHeight: th,
  } = input;

  const chartRight = cl + cw;
  const chartBottom = ct + ch;
  const maxLeft = chartRight - tw;
  const maxTop = chartBottom - th;

  const fit = (left: number, top: number) => ({
    left: clamp(left, cl, maxLeft),
    top: clamp(top, ct, maxTop),
  });

  const covers = (left: number, top: number) =>
    tooltipCoversPointer(
      { left, top, width: tw, height: th },
      px,
      py,
      gap,
    );

  const trySide = (side: TooltipSide): TooltipPlacement | null => {
    let left = 0;
    let top = 0;
    if (side === "left") {
      left = px - gap - tw;
      top = py - th / 2;
    } else if (side === "right") {
      left = px + gap;
      top = py - th / 2;
    } else if (side === "above") {
      left = px - tw / 2;
      top = py - gap - th;
    } else {
      left = px - tw / 2;
      top = py + gap;
    }
    const next = fit(left, top);
    if (covers(next.left, next.top)) return null;
    return { ...next, side };
  };

  const preferLeft = px >= cl + cw / 2;
  const order: TooltipSide[] = preferLeft
    ? ["left", "above", "below", "right"]
    : ["right", "above", "below", "left"];

  for (const side of order) {
    const hit = trySide(side);
    if (hit) return hit;
  }

  const left = preferLeft ? cl : maxLeft;
  const top = py >= ct + ch / 2 ? ct : maxTop;
  return { left, top, side: preferLeft ? "left" : "right" };
}
