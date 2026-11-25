"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Two small jobs for the year picker on /data-quality, both about the gap before hydration, when a direct ?year= link
 * still shows the default year (the page is static).
 *  - Once hydrated and showing the year asked for, clear the pending state (the attribute on <html> and aria-busy) the page's inline script set.
 *  - Tell a screen reader which year is now shown whenever it changes (by link, chip or back button). A plain load of the
 *    default year has nothing new to say, so it announces nothing.
 */
export function YearStatus({ year, hydrated }: { year: string; hydrated: boolean }) {
  const [announced, setAnnounced] = useState("");
  const shown = useRef(year);
  useEffect(() => {
    if (!hydrated) return;
    document.documentElement.removeAttribute("data-dq-pending");
    document.getElementById("dq-body")?.removeAttribute("aria-busy");
    if (shown.current !== year) {
      shown.current = year;
      setAnnounced(`Showing ${year}`);
    }
  }, [hydrated, year]);
  return (
    <p role="status" aria-live="polite" className="sr-only" id="dq-year-status">
      {announced}
    </p>
  );
}
