"use client";

// Interest selection (PRD 026 §4, chips-only path). The v1 lake covers one
// reviewed family; the student picks the concepts that fit, or all of them.
// Free-text reflection (and its AI path) is a later slice.

import { useState } from "react";
import { ONTOLOGY } from "@/lib/discovery/content";

export function InterestsStep({
  initial,
  onDone,
  onBack,
}: {
  initial: string[];
  onDone: (concepts: string[]) => void;
  onBack: () => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set(initial));

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div>
      <div className="meta">§ Interests · pilot lake</div>
      <h1 className="serif" style={{ fontSize: 32, margin: "8px 0 12px" }}>
        What keeps pulling you back?
      </h1>
      <p style={{ color: "var(--ink-2)", lineHeight: 1.6, maxWidth: "60ch" }}>
        This pilot covers one interest family — the environment, climate, and
        everything around them. Pick the angles that sound like you (or none,
        and we&apos;ll use the whole family). More interest areas arrive as
        their data passes review.
      </p>

      <div
        role="group"
        aria-label="Interest areas"
        style={{ display: "flex", flexWrap: "wrap", gap: 10, margin: "20px 0", maxWidth: "60ch" }}
      >
        {ONTOLOGY.concepts.map((c) => {
          const active = selected.has(c.concept_id);
          return (
            <button
              key={c.concept_id}
              type="button"
              className={active ? "cd-btn" : "cd-btn cd-btn--ghost"}
              aria-pressed={active}
              onClick={() => toggle(c.concept_id)}
              style={{ minHeight: 44 }}
            >
              {c.label}
              {active ? " ✓" : ""}
            </button>
          );
        })}
      </div>

      <p style={{ fontSize: 13, color: "var(--ink-3)", maxWidth: "60ch" }}>
        Interested in something else entirely? Evidence-backed discovery for
        other fields isn&apos;t ready yet — browse the whole archive at{" "}
        <a href="/browse">the school browser</a> in the meantime.
      </p>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
        <button
          type="button"
          className="cd-btn"
          style={{ minHeight: 44 }}
          onClick={() => onDone([...selected].sort())}
        >
          {selected.size > 0
            ? "See my first round"
            : "Use the whole family — see my first round"}
        </button>
        <button
          type="button"
          className="cd-btn cd-btn--ghost"
          style={{ minHeight: 44 }}
          onClick={onBack}
        >
          ← Back to my profile
        </button>
      </div>
    </div>
  );
}
