// Profile strip model (design doc: preference profile strip + spotlight
// attribution). Pure data selection over the same combined card+reaction
// signal pipeline the engine and ledger use, grouped in STEERING language —
// never bucket names, because an "Interesting"-sorted card can cross the
// essential threshold via reactions, and labeling that group "Essential"
// would misquote the student's sort.

import { DECK_CARDS, ESSENTIAL_THRESHOLD } from "./content";
import { SUPPORTED_KEYS } from "./matchers";
import { cardStatementForKey } from "./round-session";
import { aggregateKeys, buildReactionSignals, buildSignals } from "./signals";
import type { DiscoverySessionV1 } from "./types";

// Chip interaction class. Only "spotlight" entries are toggles: rendered
// reasons exist only for keys with a positive aggregate and a firing matcher,
// so away/tension/unsupported chips can never match a reason — a dead toggle
// that always announces zero would be a lie in a product built on receipts.
export type StripEntryKind = "spotlight" | "away" | "tension" | "unsupported";

export interface StripEntry {
  key: string;
  statement: string;
  total: number;
  kind: StripEntryKind;
}

export interface ProfileStripModel {
  strong: StripEntry[]; // total >= ESSENTIAL_THRESHOLD
  gentle: StripEntry[]; // 0 < total < ESSENTIAL_THRESHOLD
  away: StripEntry[]; // total < 0
  tensions: StripEntry[]; // conflicted (contribute zero until resolved)
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
  const glosses: Record<string, string> = {};

  for (const agg of aggregates) {
    const statement = cardStatementForKey(agg.key);
    if (!statement) continue; // fail closed — a chip we can't caption is no chip
    const kind: StripEntryKind = agg.conflicted
      ? "tension"
      : !SUPPORTED_KEYS.has(agg.key)
        ? "unsupported"
        : agg.total > 0
          ? "spotlight"
          : "away";
    const entry: StripEntry = { key: agg.key, statement, total: agg.total, kind };
    if (agg.conflicted) tensions.push(entry);
    else if (agg.total >= ESSENTIAL_THRESHOLD) strong.push(entry);
    else if (agg.total > 0) gentle.push(entry);
    else if (agg.total < 0) away.push(entry);
    // non-conflicted total of exactly 0 cannot occur (same-direction signals
    // only), but if it ever did, it steers nothing and is omitted

    if (!agg.conflicted && agg.total > 0) {
      glosses[agg.key] = cardKeys.has(agg.key)
        ? `Because you said: “${statement}”`
        : "Because you asked for more like this.";
    }
  }

  const byStrength = (a: StripEntry, b: StripEntry) =>
    b.total - a.total || (a.key < b.key ? -1 : 1);
  strong.sort(byStrength);
  gentle.sort(byStrength);
  away.sort((a, b) => a.total - b.total || (a.key < b.key ? -1 : 1));

  const inline = [...strong, ...gentle]
    .filter((e) => e.kind === "spotlight")
    .slice(0, 3);

  return {
    strong,
    gentle,
    away,
    tensions,
    inline,
    counts: { strong: strong.length, away: away.length, tensions: tensions.length },
    glosses,
    empty:
      strong.length === 0 &&
      gentle.length === 0 &&
      away.length === 0 &&
      tensions.length === 0,
  };
}
