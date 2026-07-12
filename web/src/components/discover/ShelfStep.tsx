"use client";

// Research-next shelf (PRD 026 §11): saved schools with the student's own
// saved reason and declared familiarity. Local to this browser; comparison
// and downstream cost/positioning handoffs are later slices.

import type { DiscoverySessionV1, EvidenceBundle } from "@/lib/discovery/types";

export function ShelfStep({
  session,
  bundle,
  onRemove,
  onBackToRounds,
}: {
  session: DiscoverySessionV1;
  bundle: EvidenceBundle | null;
  onRemove: (schoolId: string) => void;
  onBackToRounds: () => void;
}) {
  const saved = session.reactions.filter((r) => r.reaction === "research_next");
  const byId = new Map(bundle?.schools.map((s) => [s.school_id, s]) ?? []);
  const FAMILIARITY = {
    yes: "knew it already",
    name_only: "knew the name only",
    no: "new to me",
  } as const;

  return (
    <div>
      <div className="meta">§ Research shelf</div>
      <h1 className="serif" style={{ fontSize: 32, margin: "8px 0 12px" }}>
        Your shortlist to dig into.
      </h1>
      <p style={{ color: "var(--ink-2)", lineHeight: 1.6, maxWidth: "60ch" }}>
        Each school here carries the reason <em>you</em> chose to save it.
        Saving never changes your preferences — it just parks the school for
        real research.
      </p>

      {saved.length === 0 ? (
        <p style={{ color: "var(--ink-3)" }}>
          Nothing saved yet — “Research next” on any round card puts it here.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: "16px 0", padding: 0 }}>
          {saved.map((r) => {
            const school = byId.get(r.school_id);
            return (
              <li
                key={r.school_id}
                className="cd-card"
                style={{ padding: "14px 18px", margin: "0 0 12px", maxWidth: "60ch" }}
              >
                <h2 className="serif" style={{ fontSize: 20, fontWeight: 400, margin: 0 }}>
                  {school?.name ?? r.school_id}
                </h2>
                {school && (
                  <p style={{ margin: "2px 0 6px", fontSize: 13, color: "var(--ink-3)" }}>
                    {[school.city, school.state].filter(Boolean).join(", ")}
                    {r.familiarity ? ` · ${FAMILIARITY[r.familiarity]}` : ""}
                  </p>
                )}
                {r.saved_reason_text && (
                  <p style={{ margin: "0 0 8px", fontSize: 14, lineHeight: 1.5 }}>
                    Saved because: {r.saved_reason_text}
                  </p>
                )}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <a
                    href={`/schools/${r.school_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="cd-btn cd-btn--ghost"
                    style={{ minHeight: 44, display: "inline-flex", alignItems: "center" }}
                  >
                    Source documents
                  </a>
                  <button
                    type="button"
                    className="cd-btn cd-btn--ghost"
                    style={{ minHeight: 44 }}
                    onClick={() => onRemove(r.school_id)}
                  >
                    Remove
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <button type="button" className="cd-btn" style={{ minHeight: 44 }} onClick={onBackToRounds}>
        ← Back to rounds
      </button>
    </div>
  );
}
