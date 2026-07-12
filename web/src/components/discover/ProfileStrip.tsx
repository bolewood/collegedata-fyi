"use client";

// Floating preference-profile strip for discovery rounds (design doc:
// preference profile strip + spotlight attribution). Read-only v1: the
// collapsed bar keeps the profile's shape ambient while scanning schools;
// the drawer shows the full steering picture; positive chips spotlight the
// reasons they caused across the round. The ledger stays the only editing
// surface — "Edit profile" navigates there.

import { useRef, useState } from "react";
import {
  NON_TOGGLE_COPY,
  type ProfileStripModel,
  type StripEntry,
} from "@/lib/discovery/profile-strip";

const GROUPS: {
  field: "strong" | "gentle" | "away" | "tensions";
  label: string;
  blurb: string;
}[] = [
  { field: "strong", label: "Steering strongly", blurb: "These pull hardest on every round." },
  { field: "gentle", label: "Steering gently", blurb: "These nudge, they don't drive." },
  { field: "away", label: "Steering away", blurb: "Schools like this lose ground." },
  { field: "tensions", label: "Tensions", blurb: "Pulling both ways — counting for nothing until resolved." },
];

export function ProfileStrip({
  model,
  spotlightKey,
  onSpotlight,
  spotlightCounts,
  onEditProfile,
}: {
  model: ProfileStripModel;
  spotlightKey: string | null;
  onSpotlight: (key: string | null) => void;
  // how many rendered reasons / schools the given key would highlight in the
  // round currently on screen (the strip and the reasons share the same live
  // session snapshot, so these counts are exact)
  spotlightCounts: (key: string) => { reasons: number; schools: number };
  onEditProfile: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const disclosureRef = useRef<HTMLButtonElement>(null);

  function toggleSpotlight(key: string) {
    if (spotlightKey === key) {
      onSpotlight(null);
      setAnnouncement("Highlight cleared.");
      return;
    }
    onSpotlight(key);
    const { reasons, schools } = spotlightCounts(key);
    setAnnouncement(
      reasons > 0
        ? `Highlighting ${reasons} reason${reasons === 1 ? "" : "s"} across ${schools} school${schools === 1 ? "" : "s"}.`
        : "No shown reasons come from this in this round — it still shapes scoring.",
    );
  }

  // One rule, no special cases: closing the drawer clears any active
  // spotlight (inline chips can immediately re-activate it).
  function closeDrawer(returnFocus: boolean) {
    setOpen(false);
    if (spotlightKey) {
      onSpotlight(null);
      setAnnouncement("Highlight cleared.");
    }
    if (returnFocus) disclosureRef.current?.focus();
  }

  // Statements are sentences, not labels — keep the chip box but drop the
  // uppercase treatment, and ellipsize inside (inline-flex swallows
  // text-overflow on the box itself).
  const chipStyle = (active: boolean) =>
    ({
      minHeight: 32,
      cursor: "pointer",
      background: active ? "var(--forest)" : undefined,
      color: active ? "var(--paper)" : undefined,
      borderColor: active ? "var(--forest)" : undefined,
      maxWidth: "26ch",
      minWidth: 0,
      textTransform: "none",
      letterSpacing: 0,
      fontSize: 11.5,
    }) as const;

  return (
    <div data-testid="profile-strip">
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>

      {open && (
        <div
          role="region"
          aria-label="Your answers"
          onKeyDown={(e) => {
            if (e.key === "Escape") closeDrawer(true);
          }}
          style={{
            position: "fixed",
            left: 0,
            right: 0,
            bottom: 56,
            zIndex: 40,
            background: "var(--paper)",
            borderTop: "1px solid var(--rule-strong)",
            maxHeight: "70dvh",
            overflowY: "auto",
          }}
        >
          <div className="mx-auto max-w-3xl px-4 sm:px-6" style={{ padding: "14px 16px 18px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <div className="meta">§ Your answers, steering this round</div>
              <button
                type="button"
                className="cd-btn cd-btn--ghost"
                style={{ minHeight: 44, marginLeft: "auto" }}
                onClick={onEditProfile}
              >
                Edit profile
              </button>
            </div>
            <p style={{ margin: "6px 0 2px", fontSize: 13, color: "var(--ink-3)" }}>
              Tap a preference to spotlight the reasons it caused below.
              Reactions change which schools appear starting next round.
            </p>
            {GROUPS.map(({ field, label, blurb }) => {
              const entries = model[field];
              if (entries.length === 0) return null;
              return (
                <div key={field} style={{ margin: "12px 0 0" }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <h2 className="serif" style={{ fontSize: 17, fontWeight: 400, margin: 0 }}>
                      {label}
                    </h2>
                    <span style={{ fontSize: 12, color: "var(--ink-3)" }}>{blurb}</span>
                  </div>
                  <ul style={{ listStyle: "none", margin: "6px 0 0", padding: 0 }}>
                    {entries.map((e) => (
                      <DrawerEntry
                        key={e.key}
                        entry={e}
                        active={spotlightKey === e.key}
                        onToggle={toggleSpotlight}
                      />
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 41,
          background: "var(--paper)",
          borderTop: "1px solid var(--rule-strong)",
          minHeight: 56,
          display: "flex",
          alignItems: "center",
        }}
      >
        <div
          className="mx-auto max-w-3xl px-4 sm:px-6"
          style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}
        >
          <span className="meta nums" style={{ minWidth: 0, lineHeight: 1.5 }}>
            Steering: {model.counts.strong} strong · {model.counts.away} away ·{" "}
            {model.counts.tensions} tension{model.counts.tensions === 1 ? "" : "s"}
          </span>
          <span className="hidden sm:flex" style={{ gap: 6, minWidth: 0, overflow: "hidden" }}>
            {model.inline.map((e) => (
              <button
                key={e.key}
                type="button"
                className="cd-chip"
                aria-pressed={spotlightKey === e.key}
                onClick={() => toggleSpotlight(e.key)}
                style={chipStyle(spotlightKey === e.key)}
                title={e.statement}
              >
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {e.statement}
                </span>
              </button>
            ))}
          </span>
          <button
            ref={disclosureRef}
            type="button"
            className="cd-btn cd-btn--ghost"
            aria-expanded={open}
            style={{ minHeight: 44, marginLeft: "auto", whiteSpace: "nowrap" }}
            onClick={() => (open ? closeDrawer(false) : setOpen(true))}
          >
            Your answers {open ? "▾" : "▴"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DrawerEntry({
  entry,
  active,
  onToggle,
}: {
  entry: StripEntry;
  active: boolean;
  onToggle: (key: string) => void;
}) {
  if (entry.kind !== "spotlight") {
    return (
      <li style={{ padding: "8px 2px", borderBottom: "1px dashed var(--rule)", fontSize: 14 }}>
        “{entry.statement}”{" "}
        <span style={{ color: "var(--ink-3)", fontSize: 13 }}>
          — {NON_TOGGLE_COPY[entry.kind]}
        </span>
      </li>
    );
  }
  return (
    <li style={{ borderBottom: "1px dashed var(--rule)" }}>
      <button
        type="button"
        aria-pressed={active}
        onClick={() => onToggle(entry.key)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          minHeight: 44,
          padding: "8px 2px",
          background: "none",
          border: "none",
          font: "inherit",
          fontSize: 14,
          color: "var(--ink)",
          textAlign: "left",
          cursor: "pointer",
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 10,
            height: 10,
            flexShrink: 0,
            borderRadius: 1,
            border: "1px solid var(--forest)",
            background: active ? "var(--forest)" : "transparent",
          }}
        />
        “{entry.statement}”
        {active && (
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--forest)", whiteSpace: "nowrap" }}>
            spotlighting
          </span>
        )}
      </button>
    </li>
  );
}
