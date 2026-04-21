# docs/design/

Source-of-truth archive for the collegedata.fyi visual system.

This folder holds the original export from a Claude Design session (April 2026) that produced the current design language. It's kept here so future designers and coding agents can see the intent behind every palette choice, component, and layout decision without guessing from the shipped code.

## What's here

- [`HANDOFF_README.md`](HANDOFF_README.md) — the original read-me from the design session, explaining how the bundle was assembled and how a coding agent should interpret it.
- [`reference/design-system.html`](../../web/public/design-system/index.html) (served at [`/design-system/`](https://collegedata.fyi/design-system/)) — the canonical visual reference page. Also mirrored under [`web/public/design-system/`](../../web/public/design-system/) so it ships to production.
- [`reference/`](reference/) — the full set of HTML/JSX prototypes the designer built during the handoff session. **Prototypes, not production code.** They illustrate intent; the actual production implementation is in `web/src/`.
  - `design-system.html` — source for the live reference page
  - `collegedata-redesign.html` — the first unified visual concept
  - `home-v1.jsx`, `home-v2.jsx`, `home-v3.jsx` — three hero variants explored in the session
  - `school.jsx` — per-school page with ledger-style document rows and forest-highlighted net-price bars
  - `recipe.jsx` — acceptance-vs-yield scatter with ink primary series and forest callouts
  - `shared.jsx` — common nav/search/sparkline pieces
  - `sparkline.jsx` — inline typographic sparkline
  - `wordmark.jsx`, `wordmark-compare.jsx` — wordmark glyph variants
  - `tokens.css` — snapshot of the original token file (the live one at [`web/src/app/tokens.css`](../../web/src/app/tokens.css) has since added anchor-specificity overrides for buttons and responsive nav rules)
- [`screenshots/`](screenshots/) — visual snapshots the designer captured during the session. Kept for historical context.

## For agents and contributors

If you're about to write any UI, the document you want is [`web/DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md). It distills everything in this folder into an implementation-ready reference and flags the known deltas between the prototypes and what has shipped.

**Authority order** when two sources disagree:

1. [`web/src/app/tokens.css`](../../web/src/app/tokens.css) — the live system. Always wins.
2. [`web/DESIGN_SYSTEM.md`](../../web/DESIGN_SYSTEM.md) — the markdown companion. Should be updated to match `tokens.css` when it drifts.
3. The reference page at [`/design-system/`](../../web/public/design-system/index.html) — a standalone preview; authoritative for visual hierarchy and copy examples.
4. Prototypes in [`reference/`](reference/) — frozen snapshots from the handoff session. Historical record, not current truth.
