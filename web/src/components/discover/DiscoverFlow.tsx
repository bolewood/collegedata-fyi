"use client";

// Guided discovery, slice 1 (PRD 026): geographic boundaries → accessible
// card sort → plain-language preference ledger. Everything runs in the
// browser; the session lives in localStorage only (PRD §12). Discovery
// rounds arrive with the evidence engine in a later slice.
//
// Accessibility contract (PRD §13): no dragging anywhere — the sort is one
// card at a time with four buttons; every bucket change is announced via a
// polite live region; errors are field-associated and never erase input;
// nothing is communicated by color alone; touch targets are ≥44px.

import { useEffect, useMemo, useState } from "react";
import { trackEvent } from "@/lib/analytics";
import { DECK_CARDS, DECK_VERSION, LIMITATIONS } from "@/lib/discovery/content";
import {
  describeGeography,
  validateGeography,
  type GeographyFormInput,
} from "@/lib/discovery/geography";
import {
  clearSession,
  loadSession,
  newSession,
  saveSession,
  SESSION_TTL_DAYS,
} from "@/lib/discovery/session";
import { aggregateKeys, buildLedger, buildSignals } from "@/lib/discovery/signals";
import type {
  Bucket,
  DiscoveryCard,
  DiscoverySessionV1,
} from "@/lib/discovery/types";
import { BUCKET_LABELS, BUCKETS } from "@/lib/discovery/types";

const BUCKET_HINTS: Record<Bucket, string> = {
  essential: "I'd give up other things for this",
  interesting: "I'd like this, not a dealbreaker",
  not_important: "Doesn't move me either way",
  not_for_me: "I'd rather avoid this",
};

// Evidence-backed is the common case, so it stays the quiet outline default
// ("one accent, used rarely"); the caveat states carry the emphasis via an
// ochre BORDER — ochre text at chip size fails WCAG AA contrast on paper.
const EVIDENCE_BADGES = {
  data: { label: "evidence-backed", className: "cd-chip", style: undefined },
  proxy: {
    label: "proxy evidence",
    className: "cd-chip",
    style: { borderColor: "var(--ochre)" } as const,
  },
  reflection_only: {
    label: "reflection only",
    className: "cd-chip",
    style: { borderColor: "var(--ochre)", borderStyle: "dashed" } as const,
  },
} as const;

const ESSENTIAL_NUDGE_TOLERANCE = 2; // "nearly everything": all but a couple

const DECK_INDEX = new Map(DECK_CARDS.map((c, i) => [c.card_id, i]));

function sortComplete(responses: Record<string, Bucket | undefined>): boolean {
  return DECK_CARDS.every((c) => responses[c.card_id]);
}

export function DiscoverFlow() {
  const [session, setSession] = useState<DiscoverySessionV1 | null>(null);

  // Session hydration happens client-side only; render nothing until then so
  // the server and first client render agree.
  useEffect(() => {
    const now = new Date();
    setSession(loadSession(now) ?? newSession(now));
  }, []);

  function update(mutate: (s: DiscoverySessionV1) => DiscoverySessionV1) {
    setSession((prev) => {
      if (!prev) return prev;
      const next = mutate(prev);
      saveSession(next);
      return next;
    });
  }

  function restart() {
    clearSession();
    const fresh = newSession(new Date());
    fresh.step = "geography";
    setSession(fresh);
  }

  if (!session) {
    return (
      <div>
        <div className="meta">§ Discover</div>
        <p style={{ color: "var(--ink-3)" }}>Loading your session…</p>
      </div>
    );
  }

  switch (session.step) {
    case "intro":
      return (
        <Intro
          onStart={() => {
            trackEvent("discovery_started", { deck_version: DECK_VERSION });
            update((s) => ({ ...s, step: "geography" }));
          }}
        />
      );
    case "geography":
      return (
        <GeographyStep
          session={session}
          onDone={(geography) =>
            update((s) => ({
              ...s,
              geography,
              step: sortComplete(s.card_responses) ? "ledger" : "sort",
            }))
          }
        />
      );
    case "sort":
      return (
        <SortStep
          session={session}
          onRespond={(cardId, bucket, nextIndex) =>
            update((s) => ({
              ...s,
              card_responses: { ...s.card_responses, [cardId]: bucket },
              sort_index: nextIndex,
            }))
          }
          onBack={(index) => update((s) => ({ ...s, sort_index: index }))}
          onComplete={() => {
            // Step completion only — bucket distributions are preference-
            // derived and never leave the device (PRD 026 §12).
            trackEvent("discovery_sort_completed", { deck_version: DECK_VERSION });
            update((s) => ({ ...s, step: "ledger" }));
          }}
        />
      );
    case "ledger":
      return (
        <LedgerStep
          session={session}
          onEditCard={(index) =>
            update((s) => ({ ...s, step: "sort", sort_index: index }))
          }
          onEditGeography={() => update((s) => ({ ...s, step: "geography" }))}
          onRestart={restart}
        />
      );
  }
}

function Intro({ onStart }: { onStart: () => void }) {
  return (
    <div>
      <div className="meta">§ Discover</div>
      <h1 className="serif" style={{ fontSize: 40, lineHeight: 1.05, margin: "8px 0 12px" }}>
        Find what you value, <em>before</em> you search.
      </h1>
      <p style={{ fontSize: 16, lineHeight: 1.6, color: "var(--ink-2)", maxWidth: "60ch" }}>
        Most college search tools ask you to declare preferences before you have
        seen any real possibilities. This works the other way: you react to
        concrete campus experiences, and your choices become a preference
        profile you can inspect, edit, and — soon — use to discover schools you
        have never heard of, each with its reasons shown.
      </p>
      <div className="cd-card" style={{ padding: "16px 20px", margin: "20px 0", maxWidth: "60ch" }}>
        <div className="meta" style={{ marginBottom: 8 }}>§ How it works</div>
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7, color: "var(--ink-2)", listStyle: "decimal" }}>
          <li>Set distance boundaries — only if your family has them.</li>
          <li>Sort {DECK_CARDS.length} cards describing real campus experiences.</li>
          <li>Review your preference profile in plain language.</li>
        </ol>
        <p style={{ margin: "10px 0 0", fontSize: 13, color: "var(--ink-3)" }}>
          Your answers stay on this device — no account, and nothing you type
          or choose is sent to a server. We count only anonymous step
          completions to know the tool is being used.
        </p>
      </div>
      <button type="button" className="cd-btn" style={{ minHeight: 44 }} onClick={onStart}>
        Start sorting
      </button>
    </div>
  );
}

function GeographyStep({
  session,
  onDone,
}: {
  session: DiscoverySessionV1;
  onDone: (geo: DiscoverySessionV1["geography"]) => void;
}) {
  const [form, setForm] = useState<GeographyFormInput>({
    zip: session.geography?.zip ?? "",
    preferredMiles: session.geography?.preferred_miles?.toString() ?? "",
    maximumMiles: session.geography?.maximum_miles?.toString() ?? "",
    allowWildcards: session.geography?.allow_wildcards ?? false,
  });
  const [attempted, setAttempted] = useState(false);
  const validation = validateGeography(form);
  const showErrors = attempted && !validation.ok;
  const relationError = showErrors && validation.errors.relation;
  const hasSavedGeography = Boolean(
    session.geography &&
      (session.geography.zip ||
        session.geography.preferred_miles ||
        session.geography.maximum_miles),
  );

  function describedBy(fieldId: string, fieldError: unknown): string | undefined {
    const ids = [
      fieldError ? `${fieldId}-error` : null,
      relationError ? "geo-relation-error" : null,
    ].filter(Boolean);
    return ids.length ? ids.join(" ") : undefined;
  }

  function submit() {
    setAttempted(true);
    if (validation.ok) onDone(validation.value);
  }

  const inputStyle = {
    fontFamily: "var(--mono)",
    fontSize: 15,
    padding: "10px 12px",
    minHeight: 44,
    border: "1px solid var(--rule-strong)",
    borderRadius: 2,
    background: "#faf6ec",
    color: "var(--ink)",
    width: "100%",
    maxWidth: 220,
  } as const;

  return (
    <div>
      <div className="meta">§ Step 1 of 3 · Boundaries</div>
      <h1 className="serif" style={{ fontSize: 32, margin: "8px 0 12px" }}>
        How far from home?
      </h1>
      <p style={{ color: "var(--ink-2)", lineHeight: 1.6, maxWidth: "60ch" }}>
        Distance is a boundary, not a preference — some families have a real
        limit, and we will never suggest a school beyond yours. All of this is
        optional; skip it and schools anywhere are fair game. Distances are
        approximate straight-line miles, not driving time.
      </p>

      <div className="cd-card" style={{ padding: "20px", margin: "20px 0", display: "grid", gap: 18, maxWidth: "60ch" }}>
        <div>
          <label htmlFor="geo-zip" style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
            Home ZIP code <span style={{ fontWeight: 400, color: "var(--ink-3)" }}>(optional, stays on this device)</span>
          </label>
          <input
            id="geo-zip"
            inputMode="numeric"
            autoComplete="postal-code"
            value={form.zip}
            onChange={(e) => setForm({ ...form, zip: e.target.value })}
            aria-describedby={showErrors && validation.errors.zip ? "geo-zip-error" : undefined}
            aria-invalid={showErrors && !!validation.errors.zip}
            style={inputStyle}
          />
          {showErrors && validation.errors.zip && (
            <p id="geo-zip-error" role="alert" style={{ color: "var(--brick)", fontSize: 13, margin: "6px 0 0" }}>
              {validation.errors.zip}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="geo-preferred" style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
            Prefer within about <span style={{ fontWeight: 400, color: "var(--ink-3)" }}>(miles, optional)</span>
          </label>
          <input
            id="geo-preferred"
            inputMode="numeric"
            value={form.preferredMiles}
            onChange={(e) => setForm({ ...form, preferredMiles: e.target.value })}
            aria-describedby={describedBy("geo-preferred", showErrors && validation.errors.preferred)}
            aria-invalid={(showErrors && !!validation.errors.preferred) || !!relationError}
            style={inputStyle}
          />
          {showErrors && validation.errors.preferred && (
            <p id="geo-preferred-error" role="alert" style={{ color: "var(--brick)", fontSize: 13, margin: "6px 0 0" }}>
              {validation.errors.preferred}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="geo-maximum" style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>
            Never beyond about <span style={{ fontWeight: 400, color: "var(--ink-3)" }}>(miles, optional — a hard boundary)</span>
          </label>
          <input
            id="geo-maximum"
            inputMode="numeric"
            value={form.maximumMiles}
            onChange={(e) => setForm({ ...form, maximumMiles: e.target.value })}
            aria-describedby={describedBy("geo-maximum", showErrors && validation.errors.maximum)}
            aria-invalid={(showErrors && !!validation.errors.maximum) || !!relationError}
            style={inputStyle}
          />
          {showErrors && validation.errors.maximum && (
            <p id="geo-maximum-error" role="alert" style={{ color: "var(--brick)", fontSize: 13, margin: "6px 0 0" }}>
              {validation.errors.maximum}
            </p>
          )}
        </div>

        <div>
          <label style={{ display: "flex", gap: 10, alignItems: "flex-start", minHeight: 44 }}>
            <input
              type="checkbox"
              checked={form.allowWildcards}
              onChange={(e) => setForm({ ...form, allowWildcards: e.target.checked })}
              style={{ width: 22, height: 22, marginTop: 2, accentColor: "var(--forest)" }}
            />
            <span>
              <span style={{ fontWeight: 600 }}>Show an occasional wildcard</span>
              <span style={{ display: "block", fontSize: 13, color: "var(--ink-3)" }}>
                A clearly labeled school beyond your preferred distance — never
                beyond your maximum.
              </span>
            </span>
          </label>
          {validation.wildcardNote && (
            <p style={{ color: "var(--ink-3)", fontSize: 13, margin: "6px 0 0 32px" }}>
              {validation.wildcardNote}
            </p>
          )}
        </div>

        {relationError && (
          <p
            id="geo-relation-error"
            role="alert"
            style={{ color: "var(--brick)", fontSize: 14, margin: 0 }}
          >
            {validation.errors.relation}
          </p>
        )}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button type="button" className="cd-btn" style={{ minHeight: 44 }} onClick={submit}>
          {sortComplete(session.card_responses)
            ? "Save boundaries"
            : "Continue to the cards"}
        </button>
        <button
          type="button"
          className="cd-btn cd-btn--ghost"
          style={{ minHeight: 44 }}
          onClick={() =>
            onDone({ zip: null, preferred_miles: null, maximum_miles: null, allow_wildcards: false })
          }
        >
          {hasSavedGeography
            ? "Clear distance settings"
            : "Skip — no distance limits"}
        </button>
      </div>
      <p style={{ fontSize: 13, color: "var(--ink-3)", marginTop: 12, maxWidth: "60ch" }}>
        Distance-based suggestions activate when discovery rounds ship; your
        boundary is saved locally so it will be respected from day one.
      </p>
    </div>
  );
}

function SortStep({
  session,
  onRespond,
  onBack,
  onComplete,
}: {
  session: DiscoverySessionV1;
  onRespond: (cardId: string, bucket: Bucket, nextIndex: number) => void;
  onBack: (index: number) => void;
  onComplete: () => void;
}) {
  const index = Math.min(session.sort_index, DECK_CARDS.length - 1);
  const card = DECK_CARDS[index];
  const total = DECK_CARDS.length;
  const answered = Object.keys(session.card_responses).length;
  const [announcement, setAnnouncement] = useState("");

  const allAnswered = DECK_CARDS.every((c) => session.card_responses[c.card_id]);

  function choose(bucket: Bucket) {
    const previous = session.card_responses[card.card_id];
    const moved = previous && previous !== bucket
      ? ` Moved out of ${BUCKET_LABELS[previous]}.`
      : "";
    setAnnouncement(
      `Sorted “${card.statement}” into ${BUCKET_LABELS[bucket]}.${moved} Card ${Math.min(index + 2, total)} of ${total}.`,
    );
    const merged = { ...session.card_responses, [card.card_id]: bucket };
    const nextUnanswered = DECK_CARDS.findIndex(
      (c, i) => i > index && !merged[c.card_id],
    );
    if (index + 1 < total) {
      onRespond(card.card_id, bucket, nextUnanswered === -1 ? index + 1 : nextUnanswered);
    } else {
      onRespond(card.card_id, bucket, index);
    }
  }

  const currentBucket = session.card_responses[card.card_id];

  return (
    <div>
      <div className="meta">§ Step 2 of 3 · Card sort</div>
      <div
        style={{ display: "flex", alignItems: "baseline", gap: 12, margin: "8px 0 4px" }}
      >
        <h1 className="serif" style={{ fontSize: 28, margin: 0 }}>
          What matters to you?
        </h1>
        <span className="meta nums" aria-hidden="true" style={{ marginLeft: "auto" }}>
          Card {index + 1} / {total}
        </span>
      </div>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      <p style={{ color: "var(--ink-3)", fontSize: 13, margin: "0 0 16px" }}>
        Card {index + 1} of {total} · {answered} sorted. There are no right
        answers — sort by instinct, revise later.
      </p>

      <div className="cd-card cd-card--cut" style={{ padding: "24px", maxWidth: "60ch" }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          § {card.group.replace(/-/g, " ")}
        </div>
        <h2
          className="serif"
          style={{ fontSize: 24, lineHeight: 1.3, margin: "0 0 8px", fontWeight: 400 }}
        >
          “{card.statement}”
        </h2>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: 0 }}>
          {card.explanation}
        </p>
      </div>

      <div
        role="group"
        aria-label={`Sort “${card.statement}”`}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: 10,
          margin: "16px 0",
          maxWidth: "60ch",
        }}
      >
        {BUCKETS.map((bucket) => {
          const selected = currentBucket === bucket;
          return (
            <button
              key={bucket}
              type="button"
              className={selected ? "cd-btn" : "cd-btn cd-btn--ghost"}
              aria-pressed={selected}
              onClick={() => choose(bucket)}
              style={{ display: "block", minHeight: 44, textAlign: "left", padding: "10px 14px" }}
            >
              <span style={{ display: "block", fontWeight: 600 }}>
                {BUCKET_LABELS[bucket]}
                {selected ? " ✓" : ""}
              </span>
              <span style={{ display: "block", fontSize: 12, opacity: 0.85 }}>
                {BUCKET_HINTS[bucket]}
              </span>
            </button>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        {index > 0 && (
          <button
            type="button"
            className="cd-btn cd-btn--ghost"
            style={{ minHeight: 44 }}
            onClick={() => onBack(index - 1)}
          >
            ← Previous card
          </button>
        )}
        {index < total - 1 && currentBucket && (
          <button
            type="button"
            className="cd-btn cd-btn--ghost"
            style={{ minHeight: 44 }}
            onClick={() => onBack(index + 1)}
          >
            Next card →
          </button>
        )}
        {allAnswered && (
          <button type="button" className="cd-btn" style={{ minHeight: 44 }} onClick={onComplete}>
            See my preference profile
          </button>
        )}
      </div>
    </div>
  );
}

function LedgerStep({
  session,
  onEditCard,
  onEditGeography,
  onRestart,
}: {
  session: DiscoverySessionV1;
  onEditCard: (deckIndex: number) => void;
  onEditGeography: () => void;
  onRestart: () => void;
}) {
  const ledger = useMemo(
    () => buildLedger(session.card_responses, DECK_CARDS),
    [session.card_responses],
  );
  const aggregates = useMemo(
    () => aggregateKeys(buildSignals(session.card_responses, DECK_CARDS)),
    [session.card_responses],
  );
  const conflicts = aggregates.filter((a) => a.conflicted);
  const conflictCards = conflicts.flatMap((a) =>
    a.signal_ids
      .map((id) => id.split(":")[1])
      .map((cardId) => DECK_CARDS[DECK_INDEX.get(cardId) ?? -1])
      .filter(Boolean),
  );
  const everythingEssential =
    ledger.essential.length >= DECK_CARDS.length - ESSENTIAL_NUDGE_TOLERANCE;

  const sections: { bucket: Bucket; blurb: string }[] = [
    { bucket: "essential", blurb: "You'd trade other things for these." },
    { bucket: "interesting", blurb: "Nice to have, not dealbreakers." },
    { bucket: "not_for_me", blurb: "You'd rather avoid these." },
    { bucket: "not_important", blurb: "These don't move you either way." },
  ];

  return (
    <div>
      <div className="meta">§ Step 3 of 3 · Your preference profile</div>
      <h1 className="serif" style={{ fontSize: 32, margin: "8px 0 12px" }}>
        Here's what you told us.
      </h1>
      <p style={{ color: "var(--ink-2)", lineHeight: 1.6, maxWidth: "60ch" }}>
        This ledger is yours to edit — nothing here is hidden or inferred
        without your say. When discovery rounds ship, every school suggestion
        will trace back to lines on this page.
      </p>

      <p style={{ fontSize: 13, color: "var(--ink-3)", maxWidth: "60ch" }}>
        Badges: <strong>evidence-backed</strong> — public data can verify this
        · <strong>proxy evidence</strong> — an imperfect stand-in exists ·{" "}
        <strong>reflection only</strong> — no data yet, so it shapes how we
        read you but can't pick schools.
      </p>

      <div className="cd-card" style={{ padding: "14px 18px", margin: "18px 0", maxWidth: "60ch" }}>
        <div className="meta" style={{ marginBottom: 6 }}>§ Boundaries</div>
        <p style={{ margin: 0, fontSize: 14 }}>{describeGeography(session.geography)}</p>
        <button
          type="button"
          className="cd-btn cd-btn--ghost"
          style={{ minHeight: 44, marginTop: 10 }}
          onClick={onEditGeography}
        >
          Change boundaries
        </button>
      </div>

      {everythingEssential && (
        <div className="cd-card" style={{ padding: "14px 18px", margin: "18px 0", maxWidth: "60ch" }}>
          <p style={{ margin: 0, fontSize: 14, color: "var(--ink-2)" }}>
            Nearly everything is marked essential. When everything is
            essential, nothing can stand out — consider moving a few cards to
            “Interesting” so your strongest preferences can actually steer.
          </p>
        </div>
      )}

      {conflicts.length > 0 && (
        <div className="cd-card" style={{ padding: "14px 18px", margin: "18px 0", maxWidth: "60ch" }}>
          <div className="meta" style={{ marginBottom: 6 }}>§ Tensions</div>
          <p style={{ margin: 0, fontSize: 14, color: "var(--ink-2)" }}>
            These choices pull in opposite directions. They stay visible and
            count for nothing until you revise one of the cards involved:
          </p>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20, fontSize: 14, color: "var(--ink-2)" }}>
            {conflictCards.map((card) => (
              <li key={card.card_id}>“{card.statement}”</li>
            ))}
          </ul>
        </div>
      )}

      {sections.map(({ bucket, blurb }) => {
        const rows = ledger[bucket];
        if (rows.length === 0) return null;
        return (
          <section key={bucket} style={{ margin: "24px 0", maxWidth: "60ch" }}>
            <header
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 10,
                borderBottom: "1px solid var(--rule-strong)",
                paddingBottom: 6,
                marginBottom: 4,
              }}
            >
              <h2 className="serif" style={{ fontSize: 22, fontWeight: 400, margin: 0 }}>
                {BUCKET_LABELS[bucket]}
              </h2>
              <span className="meta nums" style={{ marginLeft: "auto" }}>
                {rows.length}
              </span>
            </header>
            <p style={{ fontSize: 13, color: "var(--ink-3)", margin: "0 0 8px" }}>{blurb}</p>
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {rows.map(({ card }) => {
                const badge = EVIDENCE_BADGES[card.evidence_status];
                const deckIndex = DECK_INDEX.get(card.card_id) ?? 0;
                return (
                  <li
                    key={card.card_id}
                    style={{
                      display: "flex",
                      gap: 10,
                      alignItems: "center",
                      padding: "10px 2px",
                      borderBottom: "1px dashed var(--rule)",
                      flexWrap: "wrap",
                    }}
                  >
                    <span style={{ flex: "1 1 24ch", fontSize: 14, lineHeight: 1.45 }}>
                      {card.statement}
                    </span>
                    <span
                      className={badge.className}
                      style={badge.style}
                      title={LIMITATIONS[card.limitation_id]}
                    >
                      {badge.label}
                    </span>
                    <button
                      type="button"
                      className="cd-btn cd-btn--ghost"
                      style={{ minHeight: 44 }}
                      onClick={() => onEditCard(deckIndex)}
                    >
                      Change
                    </button>
                  </li>
                );
              })}
            </ul>
            {bucket === "essential" &&
              rows.some((r) => r.card.evidence_status === "reflection_only") && (
                <p style={{ fontSize: 13, color: "var(--ink-3)", margin: "8px 0 0" }}>
                  Items marked “reflection only” shape how we understand you,
                  but no public data can verify them yet — they won't pick
                  schools until that changes. We say so rather than guess.
                </p>
              )}
          </section>
        );
      })}

      <div className="cd-card cd-card--cut" style={{ padding: "16px 20px", margin: "28px 0", maxWidth: "60ch" }}>
        <div className="meta" style={{ marginBottom: 8 }}>§ What happens next</div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "var(--ink-2)" }}>
          Discovery rounds are coming: small, varied sets of schools chosen by
          transparent rules, each with its reasons and sources shown — never a
          ranking. Your profile is saved in this browser for {SESSION_TTL_DAYS}{" "}
          days, so you can return and revise anytime.
        </p>
      </div>

      <button
        type="button"
        className="cd-btn cd-btn--ghost"
        style={{ minHeight: 44 }}
        onClick={onRestart}
      >
        Start over
      </button>
    </div>
  );
}
