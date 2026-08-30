"use client";

import {
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";
import {
  placeTooltipAwayFromPointer,
  type TooltipPlacement,
} from "@/lib/chart-tooltip-placement";

const EST_WIDTH = 260;
const EST_HEIGHT = 156;
const GAP = 18;

export function ChartHoverTooltip({
  wrapRef,
  viewW,
  viewH,
  cx,
  cy,
  placementKey,
  testId,
  children,
}: {
  wrapRef: RefObject<HTMLDivElement | null>;
  viewW: number;
  viewH: number;
  cx: number;
  cy: number;
  placementKey: string;
  testId: string;
  children: ReactNode;
}) {
  const tipRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<TooltipPlacement | null>(null);

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const svg = wrap?.querySelector("svg");
    const tip = tipRef.current;
    if (!wrap || !svg) return;

    const update = () => {
      const wrapRect = wrap.getBoundingClientRect();
      const svgRect = svg.getBoundingClientRect();
      const pointerX =
        svgRect.left - wrapRect.left + (cx / viewW) * svgRect.width;
      const pointerY =
        svgRect.top - wrapRect.top + (cy / viewH) * svgRect.height;
      const next = placeTooltipAwayFromPointer({
        pointerX,
        pointerY,
        chartLeft: svgRect.left - wrapRect.left,
        chartTop: svgRect.top - wrapRect.top,
        chartWidth: svgRect.width,
        chartHeight: svgRect.height,
        tooltipWidth: tip?.offsetWidth || EST_WIDTH,
        tooltipHeight: tip?.offsetHeight || EST_HEIGHT,
        gap: GAP,
      });
      setPos((prev) => {
        if (
          prev &&
          prev.side === next.side &&
          Math.abs(prev.left - next.left) < 0.5 &&
          Math.abs(prev.top - next.top) < 0.5
        ) {
          return prev;
        }
        return next;
      });
    };

    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [wrapRef, viewW, viewH, cx, cy, placementKey]);

  const style: CSSProperties = {
    position: "absolute",
    left: pos?.left ?? 0,
    top: pos?.top ?? 0,
    visibility: pos ? "visible" : "hidden",
    pointerEvents: "none",
    background: "var(--ink)",
    color: "var(--paper)",
    padding: "10px 12px",
    fontSize: 13,
    lineHeight: 1.45,
    minWidth: 200,
    maxWidth: 280,
    zIndex: 2,
  };

  return (
    <div
      ref={tipRef}
      data-testid={testId}
      data-tooltip-side={pos?.side ?? "pending"}
      style={style}
    >
      {children}
    </div>
  );
}
