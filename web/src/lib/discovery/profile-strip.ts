// Profile strip model (design doc: preference profile strip + spotlight
// attribution). Pure data selection over the same combined card+reaction
// signal pipeline the engine and ledger use, grouped in STEERING language —
// never bucket names, because an "Interesting"-sorted card can cross the
// essential threshold via reactions, and labeling that group "Essential"
// would misquote the student's sort.

import { DECK_CARDS, ESSENTIAL_THRESHOLD } from "./content";
import { ACTIONABLE_KEYS } from "./matchers";
import { cardStatementForKey } from "./round-session";
import { aggregateKeys, buildReactionSignals, buildSignals } from "./signals";
import type { DiscoverySessionV1 } from "./types";

// Chip interaction class. Only "spotlight" entries are toggles: rendered
// reasons exist only for keys with a positive aggregate and a firing matcher,
// so away/tension/unsupported chips can never match a reason — a dead toggle
// that always announces zero would be a lie in a product built on receipts.
// "Unsupported" here means not ACTIONABLE: a key with no matcher at all OR a
// matcher whose evidence has no resolver yet (12 of 24 deck keys today —
// cds.*, ipeds.ic.*, distance.*) — either way it can't score or produce
// reasons, and its honest copy is "not yet used for matching."
export type StripEntryKind = "spotlight" | "away" | "tension" | "unsupported";

export interface StripEntry {
  key: string;
  statement: string;
  total: number;
  kind: StripEntryKind;
  // An active CARD signal backs this entry. When false (reaction-only after
  // a ledger edit), the statement must NOT be rendered in quotes as "your
  // answer" — the student withdrew it.
  quoted: boolean;
}

export interface ProfileStripModel {
  strong: StripEntry[]; // total >= ESSENTIAL_THRESHOLD (actionable only)
  gentle: StripEntry[]; // 0 < total < ESSENTIAL_THRESHOLD (actionable only)
  away: StripEntry[]; // total < 0 (actionable only)
  tensions: StripEntry[]; // conflicted (contribute zero until resolved)
  // Non-actionable keys (no matcher, or matcher without resolvable evidence)
  // regardless of sign. They steer NOTHING today — putting them in a
  // steering group would make the counts lie, so they get their own
  // disclosed group instead.
  recorded: StripEntry[];
  // 2-3 strongest positive, matcher-supported chips for the collapsed bar —
  // never away/tension/unsupported (non-toggle) entries.
  inline: StripEntry[];
  counts: { strong: number; away: number; tensions: number };
  // Attribution gloss per positive key, source-precedence so the gloss can
  // never misquote: card statement only while an active CARD signal exists;
  // a reaction-only positive aggregate (possible after a ledger edit) gets
  // the reaction wording instead.
  glosses: Record<string, string>;
  // Zero aggregates and zero tensions — an all-zeros strip would be noise.
  empty: boolean;
}

export const NON_TOGGLE_COPY: Record<Exclude<StripEntryKind, "spotlight">, string> = {
  away: "shapes scoring, not the reasons shown",
  tension: "pulls both ways and counts for nothing until you resolve it in your profile",
  unsupported: "recorded in your profile — not yet used for matching",
};

export function buildProfileStripModel(
  session: DiscoverySessionV1,
): ProfileStripModel {
  const cardSignals = buildSignals(session.card_responses, DECK_CARDS);
  const cardKeys = new Set(cardSignals.map((s) => s.key));
  const aggregates = aggregateKeys([
    ...cardSignals,
    ...buildReactionSignals(session.reactions),
  ]);

  const strong: StripEntry[] = [];
  const gentle: StripEntry[] = [];
  const away: StripEntry[] = [];
  const tensions: StripEntry[] = [];
  const recorded: StripEntry[] = [];
  const glosses: Record<string, string> = {};

  for (const agg of aggregates) {
    const statement = cardStatementForKey(agg.key);
    if (!statement) continue; // fail closed — a chip we can't caption is no chip
    const kind: StripEntryKind = agg.conflicted
      ? "tension"
      : !ACTIONABLE_KEYS.has(agg.key)
        ? "unsupported"
        : agg.total > 0
          ? "spotlight"
          : "away";
    const entry: StripEntry = {
      key: agg.key,
      statement,
      total: agg.total,
      kind,
      quoted: cardKeys.has(agg.key),
    };
    if (kind === "tension") tensions.push(entry);
    // Non-actionable keys steer nothing — counting them as strong/away would
    // claim influence scoreSchool never applies.
    else if (kind === "unsupported") recorded.push(entry);
    else if (agg.total >= ESSENTIAL_THRESHOLD) strong.push(entry);
    else if (agg.total > 0) gentle.push(entry);
    else if (agg.total < 0) away.push(entry);
    // non-conflicted total of exactly 0 cannot occur (same-direction signals
    // only), but if it ever did, it steers nothing and is omitted

    if (kind === "spotlight") {
      glosses[agg.key] = entry.quoted
        ? `Because you said: “${statement}”`
        : "Because you asked for more like this.";
    }
  }

  const byStrength = (a: StripEntry, b: StripEntry) =>
    b.total - a.total || (a.key < b.key ? -1 : 1);
  strong.sort(byStrength);
  gentle.sort(byStrength);
  away.sort((a, b) => a.total - b.total || (a.key < b.key ? -1 : 1));
  recorded.sort(byStrength);

  // strong/gentle are actionable-positive by construction, so every entry
  // here is a spotlight toggle.
  const inline = [...strong, ...gentle].slice(0, 3);

  return {
    strong,
    gentle,
    away,
    tensions,
    recorded,
    inline,
    counts: { strong: strong.length, away: away.length, tensions: tensions.length },
    glosses,
    empty:
      strong.length === 0 &&
      gentle.length === 0 &&
      away.length === 0 &&
      tensions.length === 0 &&
      recorded.length === 0,
  };
}

// Strip geometry, shared between ProfileStrip (bar/drawer) and RoundsStep
// (content clearance) so a resize is a one-line change. CLEARANCE must stay
// >= BAR_MIN_HEIGHT + breathing room.
export const STRIP_BAR_MIN_HEIGHT = 56;
export const STRIP_CLEARANCE = 88;

// How many rendered reasons (and schools) an active spotlight key would
// highlight in the round on screen. Pure so the announcement copy can be
// unit-tested against the same numbers the UI shows.
export function spotlightCountsForRound(
  schools: { reasons: { tunable_key: string | null }[] }[],
  key: string,
): { reasons: number; schools: number } {
  let reasons = 0;
  let hitSchools = 0;
  for (const s of schools) {
    const hits = s.reasons.filter((r) => r.tunable_key === key).length;
    if (hits > 0) {
      reasons += hits;
      hitSchools += 1;
    }
  }
  return { reasons, schools: hitSchools };
}
