"use client";

// Discovery rounds (PRD 026 §8-10): six-school rounds composed entirely in
// the browser from the versioned evidence bundle, each school carrying its
// round role and fail-closed, template-grounded reasons. Reactions write
// preference signals that steer the next round; saved schools go to the
// local research-next shelf. There is no rank, match percentage, or "best
// fit" anywhere.

import { useEffect, useMemo, useState } from "react";
import { trackEvent } from "@/lib/analytics";
import { getCachedBundle, loadBundle } from "@/lib/discovery/bundle";
import { DECK_VERSION } from "@/lib/discovery/content";
import {
  cardStatementForKey,
  composeNextRound,
  renderStoredRound,
  type NextRound,
} from "@/lib/discovery/round-session";
import type {
  DiscoverySessionV1,
  EvidenceBundle,
  RoundSchool,
  SchoolReaction,
} from "@/lib/discovery/types";

const CONTROL_LABELS: Record<number, string> = {
  1: "public",
  2: "private nonprofit",
  3: "private for-profit",
};

const ROLE_LABELS: Record<string, string> = {
  anchor: "Anchor pick",
  flexible: "Flexible path",
  contrast: "A different angle",
  affordability: "Affordability context",
  wildcard: "Geographic wildcard",
  exploration: "Worth exploring",
  additional_exploration: "Additional exploration",
  additional_exploration_relaxed: "Additional exploration",
};

export function RoundsStep({
  session,
  onReact,
  onAdvanceRound,
  onRecordRound,
  onOpenShelf,
  onBackToLedger,
  onFixBoundaries,
}: {
  session: DiscoverySessionV1;
  onReact: (reaction: SchoolReaction) => void;
  onAdvanceRound: () => void;
  onRecordRound: (round: NextRound) => void;
  onOpenShelf: () => void;
  onBackToLedger: () => void;
  onFixBoundaries: () => void;
}) {
  const [bundle, setBundle] = useState<EvidenceBundle | null>(getCachedBundle());
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (bundle || loadError) return;
    let cancelled = false;
    loadBundle()
      .then((b) => {
        if (!cancelled) setBundle(b);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [bundle, loadError]);

  // A shown round renders from its stored history entry (recomposing would
  // let its own cooldown records exclude it). Composition happens exactly
  // once, when current_round points past recorded history.
  const storedEntry = session.round_history[session.current_round];
  const round = useMemo(() => {
    if (!bundle) return null;
    return storedEntry
      ? renderStoredRound(session, bundle, storedEntry)
      : composeNextRound(session, bundle);
  }, [bundle, session, storedEntry]);

  // Persist a freshly composed round exactly once (drives cooldowns).
  useEffect(() => {
    if (!round || storedEntry) return;
    if (round.schools.length > 0) {
      trackEvent("discovery_round_shown", {
        deck_version: DECK_VERSION,
        round_index: round.round_index,
      });
      onRecordRound(round);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round?.round_index, Boolean(storedEntry), bundle]);

  if (loadError) {
    return (
      <StepShell>
        <p style={{ color: "var(--ink-2)" }}>
          The school evidence file couldn&apos;t load — check your connection
          and try again. Your profile is untouched.
        </p>
        <button type="button" className="cd-btn" style={{ minHeight: 44 }}
          onClick={() => setLoadError(false)}>
          Retry
        </button>
      </StepShell>
    );
  }
  if (!bundle || !round) {
    return (
      <StepShell>
        <p style={{ color: "var(--ink-3)" }}>Gathering the evidence…</p>
      </StepShell>
    );
  }

  const reactedIds = new Set(session.reactions.map((r) => r.school_id));
  const savedCount = session.reactions.filter(
    (r) => r.reaction === "research_next",
  ).length;

  return (
    <StepShell>
      {round.zip_unresolved && (
        <div className="cd-card" style={{ padding: "12px 16px", margin: "0 0 16px", maxWidth: "64ch" }}>
          <p style={{ margin: 0, fontSize: 14, color: "var(--ink-2)" }}>
            We couldn&apos;t place ZIP {session.geography?.zip} — all distance
            settings are off for this round rather than guessing.
          </p>
          <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44, marginTop: 8 }}
            onClick={onFixBoundaries}>
            Fix my boundaries
          </button>
        </div>
      )}

      <ChangeNote changedKeys={round.changed_keys} onBackToLedger={onBackToLedger} />

      {round.schools.length === 0 ? (
        <div className="cd-card" style={{ padding: "16px 20px", margin: "0 0 16px", maxWidth: "64ch" }}>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "var(--ink-2)" }}>
            You&apos;ve seen every school your current boundaries and interests
            allow. Two reversible ways to keep going: widen your distance
            limit, or add another interest angle. Your shelf and profile are
            untouched.
          </p>
        </div>
      ) : round.schools.length < 4 ? (
        <div className="cd-card" style={{ padding: "12px 16px", margin: "0 0 16px", maxWidth: "64ch" }}>
          <p style={{ margin: 0, fontSize: 14, color: "var(--ink-2)" }}>
            Your current boundaries and interests leave a small pool
            ({round.schools.length} school{round.schools.length === 1 ? "" : "s"}).
            One reversible way to widen it: raise your distance limit or add
            another interest angle.
          </p>
        </div>
      ) : null}

      <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {round.schools.map((s) => (
          <RoundCard
            key={s.school.school_id}
            entry={s}
            roundIndex={round.round_index}
            alreadyReacted={reactedIds.has(s.school.school_id)}
            onReact={onReact}
          />
        ))}
      </ol>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 20 }}>
        {round.schools.length > 0 && (
          <button type="button" className="cd-btn" style={{ minHeight: 44 }} onClick={onAdvanceRound}>
            Next round →
          </button>
        )}
        {round.schools.length === 0 && (
          <button type="button" className="cd-btn" style={{ minHeight: 44 }} onClick={onFixBoundaries}>
            Widen my boundaries
          </button>
        )}
        <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }} onClick={onOpenShelf}>
          Research shelf ({savedCount})
        </button>
        <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }} onClick={onBackToLedger}>
          My profile
        </button>
      </div>
      <p style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 12, maxWidth: "64ch" }}>
        These are research suggestions with their evidence shown — not a
        ranking, an application list, or an admissions prediction.
      </p>
    </StepShell>
  );
}

// Round change note (PRD §10): plain-language, and honest about tensions — a
// reaction whose key now opposes a card counts for nothing, and we say so
// instead of claiming a lean the engine isn't applying.
function ChangeNote({
  changedKeys,
  onBackToLedger,
}: {
  changedKeys: NextRound["changed_keys"];
  onBackToLedger: () => void;
}) {
  if (changedKeys.length === 0) return null;
  const leans = changedKeys.filter((c) => !c.conflicted);
  const conflicted = changedKeys.filter((c) => c.conflicted);
  const phrase = (c: (typeof changedKeys)[number]) => {
    const stmt = cardStatementForKey(c.key);
    return stmt
      ? `${c.direction === "seek" ? "toward" : "away from"} “${stmt}”`
      : null;
  };
  const leanPhrases = leans.map(phrase).filter(Boolean);
  return (
    <div style={{ maxWidth: "64ch" }}>
      {leanPhrases.length > 0 && (
        <p style={{ fontSize: 14, color: "var(--ink-2)" }}>
          This round leans {leanPhrases.join(" and ")} because of your last
          choices.
        </p>
      )}
      {conflicted.length > 0 && (
        <p style={{ fontSize: 14, color: "var(--ink-2)" }}>
          Your reaction about{" "}
          {conflicted
            .map((c) => cardStatementForKey(c.key))
            .filter(Boolean)
            .map((stmt) => `“${stmt}”`)
            .join(" and ")}{" "}
          now pulls against your earlier cards, so that preference counts for
          nothing until you resolve the tension in{" "}
          <button
            type="button"
            onClick={onBackToLedger}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              font: "inherit",
              color: "var(--forest)",
              textDecoration: "underline",
              cursor: "pointer",
            }}
          >
            your profile
          </button>
          .
        </p>
      )}
    </div>
  );
}

function StepShell({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div className="meta">§ Discovery round</div>
      <h1 className="serif" style={{ fontSize: 32, margin: "8px 0 12px" }}>
        Schools worth a look — with receipts.
      </h1>
      {children}
    </div>
  );
}

function RoundCard({
  entry,
  roundIndex,
  alreadyReacted,
  onReact,
}: {
  entry: RoundSchool;
  roundIndex: number;
  alreadyReacted: boolean;
  onReact: (r: SchoolReaction) => void;
}) {
  const [panel, setPanel] = useState<"none" | "save" | "more" | "not">("none");
  const [chosenReason, setChosenReason] = useState<number | null>(null);
  const [familiarity, setFamiliarity] = useState<"yes" | "name_only" | "no" | null>(null);
  const s = entry.school;
  const tunable = entry.reasons.filter((r) => r.tunable_key);

  function submitSave() {
    if (chosenReason === null || familiarity === null) return;
    onReact({
      school_id: s.school_id,
      reaction: "research_next",
      key: entry.reasons[chosenReason].tunable_key,
      saved_reason_text: entry.reasons[chosenReason].text,
      familiarity,
      round_index: roundIndex,
    });
    setPanel("none");
  }

  return (
    <li
      className="cd-card cd-card--cut"
      style={{ padding: "18px 20px", margin: "0 0 16px", maxWidth: "64ch" }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span className="cd-chip">{ROLE_LABELS[entry.role] ?? entry.role}</span>
        {entry.revisit && <span className="cd-chip">Revisit</span>}
        {entry.distance_miles !== null && (
          <span className="meta nums" style={{ marginLeft: "auto" }}>
            ~{entry.distance_miles} mi straight-line
          </span>
        )}
      </div>
      <h2 className="serif" style={{ fontSize: 24, fontWeight: 400, margin: "8px 0 2px" }}>
        {s.name}
      </h2>
      <p style={{ margin: "0 0 10px", fontSize: 14, color: "var(--ink-3)" }}>
        {[s.city, s.state, CONTROL_LABELS[s.control]].filter(Boolean).join(", ")}
        {s.enrollment ? (
          <>
            {" · "}
            <span className="nums">{s.enrollment.toLocaleString("en-US")}</span>
            {" undergrads"}
          </>
        ) : null}
      </p>

      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {entry.reasons.map((r, i) => (
          <li key={r.ref} style={{ padding: "6px 0", borderTop: i > 0 ? "1px dashed var(--rule)" : "none" }}>
            <p style={{ margin: 0, fontSize: 15, lineHeight: 1.5 }}>{r.text}</p>
            <details>
              <summary
                className="meta"
                style={{ cursor: "pointer", fontSize: 11, padding: "8px 0", display: "inline-block" }}
              >
                source &amp; limits
              </summary>
              <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ink-3)" }}>
                {r.evidence_class} data, {r.data_year}. {r.limitation}
              </p>
            </details>
          </li>
        ))}
      </ul>

      {alreadyReacted ? (
        <p style={{ margin: "10px 0 0", fontSize: 13, color: "var(--ink-3)" }}>
          Noted — this shapes your next rounds.
        </p>
      ) : panel === "none" ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }}
            onClick={() => { setPanel("save"); setChosenReason(entry.reasons.length === 1 ? 0 : null); }}>
            Research next
          </button>
          <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }}
            onClick={() => { setPanel("more"); setChosenReason(null); }}>
            More like this
          </button>
          <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }}
            onClick={() => { setPanel("not"); setChosenReason(null); }}>
            Not for me
          </button>
          <a href={`/schools/${s.school_id}`} target="_blank" rel="noopener noreferrer"
            className="cd-btn cd-btn--ghost" style={{ minHeight: 44, display: "inline-flex", alignItems: "center" }}>
            Tell me more
          </a>
        </div>
      ) : panel === "save" ? (
        <div style={{ marginTop: 12 }}>
          <ReasonPicker
            legend="Which reason are you saving this school for?"
            reasons={entry.reasons.map((r) => r.text)}
            chosen={chosenReason}
            onChoose={setChosenReason}
            name={`save-${s.school_id}`}
          />
          <fieldset style={{ border: "none", margin: "10px 0 0", padding: 0 }}>
            <legend style={{ fontSize: 14, fontWeight: 600 }}>
              Was this school already familiar to you?
            </legend>
            {([["yes", "Yes"], ["name_only", "Name only"], ["no", "No"]] as const).map(([v, label]) => (
              <label key={v} style={{ display: "inline-flex", alignItems: "center", gap: 6, marginRight: 14, minHeight: 44 }}>
                <input type="radio" name={`fam-${s.school_id}`} checked={familiarity === v}
                  onChange={() => setFamiliarity(v)} style={{ width: 20, height: 20, accentColor: "var(--forest)" }} />
                {label}
              </label>
            ))}
          </fieldset>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button type="button" className="cd-btn" style={{ minHeight: 44 }}
              disabled={chosenReason === null || familiarity === null} onClick={submitSave}>
              Save to shelf
            </button>
            <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }}
              onClick={() => setPanel("none")}>
              Cancel
            </button>
          </div>
        </div>
      ) : panel === "more" ? (
        tunable.length === 0 ? (
          <div style={{ marginTop: 12 }}>
            <p style={{ fontSize: 14, color: "var(--ink-2)", margin: 0 }}>
              This school matched on your academic interest alone — there&apos;s
              no preference to turn up yet.
            </p>
            <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44, marginTop: 8 }}
              onClick={() => setPanel("none")}>
              Back
            </button>
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            <ReasonPicker
              legend="More schools like this in what way?"
              reasons={tunable.map((r) => r.text)}
              chosen={chosenReason}
              onChoose={setChosenReason}
              name={`more-${s.school_id}`}
            />
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button type="button" className="cd-btn" style={{ minHeight: 44 }}
                disabled={chosenReason === null}
                onClick={() => {
                  onReact({
                    school_id: s.school_id, reaction: "more_like_this",
                    key: tunable[chosenReason as number].tunable_key,
                    saved_reason_text: null, familiarity: null, round_index: roundIndex,
                  });
                  setPanel("none");
                }}>
                Turn it up
              </button>
              <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }}
                onClick={() => setPanel("none")}>
                Cancel
              </button>
            </div>
          </div>
        )
      ) : (
        <div style={{ marginTop: 12 }}>
          <ReasonPicker
            legend="Not for you because of…"
            reasons={[...tunable.map((r) => r.text), "Something else"]}
            chosen={chosenReason}
            onChoose={setChosenReason}
            name={`not-${s.school_id}`}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button type="button" className="cd-btn" style={{ minHeight: 44 }}
              disabled={chosenReason === null}
              onClick={() => {
                const pickedTunable =
                  chosenReason !== null && chosenReason < tunable.length
                    ? tunable[chosenReason]
                    : null;
                onReact({
                  school_id: s.school_id, reaction: "not_for_me",
                  key: pickedTunable?.tunable_key ?? null,
                  saved_reason_text: null, familiarity: null, round_index: roundIndex,
                });
                setPanel("none");
              }}>
              Set it aside
            </button>
            <button type="button" className="cd-btn cd-btn--ghost" style={{ minHeight: 44 }}
              onClick={() => setPanel("none")}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function ReasonPicker({
  legend,
  reasons,
  chosen,
  onChoose,
  name,
}: {
  legend: string;
  reasons: string[];
  chosen: number | null;
  onChoose: (i: number) => void;
  name: string;
}) {
  return (
    <fieldset style={{ border: "none", margin: 0, padding: 0 }}>
      <legend style={{ fontSize: 14, fontWeight: 600 }}>{legend}</legend>
      {reasons.map((text, i) => (
        <label key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", padding: "10px 0", minHeight: 44 }}>
          <input type="radio" name={name} checked={chosen === i} onChange={() => onChoose(i)}
            style={{ width: 20, height: 20, marginTop: 1, accentColor: "var(--forest)", flexShrink: 0 }} />
          <span style={{ fontSize: 14, lineHeight: 1.45 }}>{text}</span>
        </label>
      ))}
    </fieldset>
  );
}
