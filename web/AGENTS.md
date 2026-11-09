<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Read the design system before writing UI

Before touching any component, page, or CSS, read [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) top to bottom. Before writing or rewriting public prose, read [`VOICE.md`](VOICE.md). The canonical tokens live in [`src/app/tokens.css`](src/app/tokens.css); the live reference page is at [`/design-system/`](public/design-system/index.html); the original handoff archive (HTML + JSX prototypes + screenshots) is at [`../docs/design/`](../docs/design/).

Palette rules you will get wrong otherwise: **no blue anywhere** (forest `#3f5b3a` is the sole accent); card backgrounds use `#faf6ec` via `.cd-card`, not Tailwind `bg-white`; numbers are always tabular (`font-variant-numeric: tabular-nums`) and mono.

Fonts are self-hosted in [`src/app/fonts/`](src/app/fonts/README.md) and loaded with `next/font/local`. **Never use `next/font/google` or a Google Fonts link**: it fetches on every build and a failed fetch fails the deploy. A test (`src/lib/no-remote-fonts.test.ts`) fails CI if one appears.

If you find a conflict between the Markdown doc, the reference page, and `tokens.css` — `tokens.css` wins. Update the doc to match.
