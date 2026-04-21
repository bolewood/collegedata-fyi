# collegedata.fyi — Design system

> **Read this before touching any frontend UI.** Same spirit as `AGENTS.md`.

**Canonical tokens:** [`web/src/app/tokens.css`](src/app/tokens.css)
**Live reference page:** [`/design-system/`](https://collegedata.fyi/design-system/) (also in repo at [`web/public/design-system/index.html`](public/design-system/index.html))
**Source handoff archive:** [`docs/design/`](../docs/design/) — original HTML/JSX prototypes from the Claude Design session

This system was hand-built in April 2026 from a Claude Design handoff. The short name for it is "paper, ink, and one quiet green."

---

## Philosophy

> Read like a library, not a SaaS landing page.

Five principles, verbatim from the handoff:

1. **Read like a library, not a SaaS landing page.**
2. **One accent, used rarely.** When forest appears, it means *this*.
3. **Numbers are always tabular**, always next to their source section (§C, §H…).
4. **Rules, not shadows.** Density earned, not decorated.
5. **Never hide a source.** Every number links back to its CDS cell.

---

## Palette

Warm cream paper, near-black ink, one muted forest green. No blue. Ochre and brick are held back for rare emphasis — don't use them casually.

| Variable | Hex | Role |
|---|---|---|
| `--paper` | `#f1ece1` | page background (warm cream) |
| `--paper-2` | `#e9e3d4` | card tint / rule fill |
| `--paper-3` | `#ded6c3` | strong separator |
| `--ink` | `#1c1e1b` | primary text |
| `--ink-2` | `#3a3b37` | secondary text |
| `--ink-3` | `#6b6a63` | tertiary / meta |
| `--ink-4` | `#a8a59a` | faint / placeholder |
| `--forest` | `#3f5b3a` | **sole accent** |
| `--forest-2` | `#5a7a52` | lighter forest |
| `--forest-ink` | `#27321f` | button-hover, link-hover |
| `--ochre` | `#8a6a2b` | rare emphasis |
| `--brick` | `#8c2a1f` | alarm/destructive only |
| `--rule` | `rgba(28,30,27,.12)` | hairline between list items |
| `--rule-strong` | `rgba(28,30,27,.28)` | above section bands |

Card tint for index-card–style panels: `#faf6ec` (pale cream, slightly lighter than `--paper`). Apply via the `.cd-card` class, not raw hex.

**Chart palette** (`--chart-ink`, `--chart-accent`, `--chart-grid`, `--chart-axis`, `--chart-faint`): primary series is always ink; callouts are forest; grid is near-transparent ink. See [`docs/design/reference/recipe.jsx`](../docs/design/reference/recipe.jsx) for the reference scatter implementation.

**No blue anywhere.** Any blue that appears in current code (`bg-blue-500` on NetPriceByIncome, `text-blue-700` on "try it →" links) is a palette bug and should migrate to forest + ink.

---

## Typography

Production stack, wired through Next/font in [`web/src/app/layout.tsx`](src/app/layout.tsx):

| Family | Via `--font-*` var | Role |
|---|---|---|
| Newsreader | `--font-newsreader` → `--serif` | display headings, lede, pull-lines |
| Geist | `--font-geist` → `--sans` | body |
| JetBrains Mono | `--font-jetbrains` → `--mono` | meta captions, ledger rows, numbers |

> **Intentional variance from the standalone reference page:** `web/public/design-system/index.html` inline-overrides the font vars to IBM Plex for its own preview render. The designer did this inside the HTML file itself — the canonical token file uses Newsreader/Geist/JetBrains Mono. If you're not sure, `tokens.css` wins.

### Type scale (literal from the reference)

| Role | Family | Size / line-height / tracking |
|---|---|---|
| Display h1 | serif 400 | 56–76 / 1.0 / −0.02em |
| Section h2 | serif 400 | 30 / 1.1 / −0.015em |
| Lede (italic) | serif italic | 18 / 1.55 |
| Body | sans | 15–16 / 1.6 |
| Meta / caption | mono, uppercase | 11 / 0.08em tracking |

Numbers always use `font-variant-numeric: tabular-nums` — apply via `.nums`, `.stat-num`, or the `.cd-theme table` selector.

---

## Components

All `.cd-*` classes live in [`tokens.css`](src/app/tokens.css). Compose them; don't duplicate their styles.

### Wordmark

`<Wordmark variant="dotted" size={20} />` — the "call-number" dotted variant is the default used in the nav and footer. Other shipped variants: `stamp`, `corner`, `bracket`, `rule`, `monogram`, `plain`. See [`web/src/components/Wordmark.tsx`](src/components/Wordmark.tsx).

### Buttons — `.cd-btn`, `.cd-btn--ghost`

Ink-filled rectangle, 2 px border radius (never more). Hover: background swaps to `--forest-ink`. The ghost variant is transparent with a `--rule-strong` border.

```html
<a class="cd-btn">Primary</a>
<a class="cd-btn cd-btn--ghost">Ghost</a>
```

### Chips — `.cd-chip`, `.cd-chip--solid`, `.cd-chip--forest`

Small mono-cased pills. Default is outline-only. Use `--forest` to stamp "Extracted" status and `--solid` (ink-filled) to stamp "Verified" or similar high-signal positives.

### Cards — `.cd-card`, `.cd-card--cut`

Index-card panel on `#faf6ec` with `--rule-strong` border. Add `.cd-card--cut` for the corner-cut affect that mimics catalog-drawer stacking. Used for recipe cards.

### Rules — `.rule`, `.rule-2`, `.rule-d`

Flat separators. Use strong (`.rule-2`) above section bands, hairline (`.rule`) between ledger rows, dashed (`.rule-d`) for dense tabular context. No shadows anywhere.

### Sparkline

Inline typographic sparkline, baseline-aligned with prose numbers. Intended usage is **inside a sentence**, not as a chart chrome — e.g. *"The archive holds 697 schools ⤵ and 3,924 documents ⤵ covering 1998 through 2025."* See [`web/src/components/Sparkline.tsx`](src/components/Sparkline.tsx). Only use with **real time-series data** — the handoff's synthetic `HX` arrays were explicitly called out as placeholder.

### Nav row — `.cd-nav-row`, `.cd-nav-links`

Wordmark on the left, links on the right. Stacks under the wordmark at ≤ 640 px so it doesn't collide on mobile.

---

## Voice

Marginalia, ledger entries, catalog cards, editorial serif headlines with an italic accent word. Literally:

- **"College data, *straight from the source.*"** (home hero, italic on the second clause)
- **"Worked *examples*."** (recipes hero)
- **"The *Uncommon* Data Set"** (about hero)
- **"§ Latest drain"** (mono caption before a ledger section)

Mono captions always lead with `§` and use uppercase tracking (0.08em). Numbers and IDs are mono; names are serif.

---

## Known deltas (the live site vs. the reference)

Tracked as follow-ups, in priority order:

1. **NetPriceByIncome bars** use `bg-blue-500` — should be ink with one forest-highlighted row per the [`school.jsx`](../docs/design/reference/school.jsx) reference.
2. **API page `Show all N fields →` toggle** uses `text-blue-700` — should inherit `--ink` with `--rule-strong` underline like the default `.cd-theme a`.
3. **KeyStats / OutcomesBand / document cards** on school pages still use Tailwind `bg-white` + `border-gray-200` — migrate to `.cd-card` for warm-cream consistency.
4. **Acceptance-vs-yield recipe demo** uses Tailwind blue dots — should be ink with forest highlights per [`recipe.jsx`](../docs/design/reference/recipe.jsx).

None of these break functionality; they're palette-consistency debt.

---

## How to consult the reference

Two ways to look at the system:

1. **Live page:** run `npm --prefix web run dev`, open [http://localhost:3000/design-system/](http://localhost:3000/design-system/). Same file that ships to production at `collegedata.fyi/design-system/`.
2. **Source handoff:** [`docs/design/`](../docs/design/) holds the original Claude Design export — HTML prototypes, JSX reference components, screenshots, the handoff README. Read [`docs/design/HANDOFF_README.md`](../docs/design/HANDOFF_README.md) first.

If the live page and `tokens.css` disagree with a prototype, `tokens.css` is the authority. If `tokens.css` and this document disagree, `tokens.css` is still the authority — update the doc.
