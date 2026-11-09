# Self-hosted fonts

These are the site's three typefaces, committed so the build never fetches
fonts over the network. `next/font/google` downloaded them from Google on
every Vercel build, and a failed download failed the whole build.

| File | Typeface | Axis range | Source |
|---|---|---|---|
| `newsreader-latin-wght-normal.woff2`, `newsreader-latin-wght-italic.woff2` | Newsreader | wght 200–800 | `@fontsource-variable/newsreader` 5.3.0 |
| `geist-latin-wght-normal.woff2` | Geist | wght 100–900 | `@fontsource-variable/geist` 5.3.0 |
| `jetbrains-mono-latin-wght-normal.woff2` | JetBrains Mono | wght 100–800 | `@fontsource-variable/jetbrains-mono` 5.3.0 |

Latin subset only, matching the old `subsets: ["latin"]`. All three are
licensed under the SIL Open Font License 1.1; see the `OFL-*.txt` files.

To update: `npm pack @fontsource-variable/<name>`, copy the
`files/<name>-latin-wght-*.woff2` files here, and bump the version above.
