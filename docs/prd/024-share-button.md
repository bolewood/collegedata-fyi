# PRD 024: Share button

**Status:** Draft
**Created:** 2026-05-21
**Author:** Anthony + Codex
**Related:** [PRD 002](002-frontend.md), [PRD 013](013-analytics-and-abuse-signal.md), [PRD 015](015-institution-directory-and-cds-coverage.md), [PRD 017](017-match-list-builder.md), [PRD 020](020-accessible-cds-table-view.md), [PRD 023](023-admission-visualization-upgrades.md)

---

## Context

CollegeData.fyi is increasingly becoming a page people want to send to someone else:

- a parent sending a school page to a student
- a student sending a CDS year page to a counselor
- a counselor sending a Match list to a family
- a journalist or researcher citing a source-backed admissions or aid fact
- an IR professional sharing a coverage/missing-CDS page internally

The site has canonical URLs and good page metadata, and `/match` already has a stateless share-code pattern. That code is useful but not anonymous: the current implementation reversibly packs GPA, SAT, ACT, and GPA scale into the code. Sharing is inconsistent: most pages require users to manually copy the browser URL, and there is no reusable pattern for sharing the exact page or source-backed fact that prompted the user to share.

The share button should be a small utility surface, not a social growth gimmick. Its job is to help a user send the right CollegeData.fyi artifact with enough context that the recipient understands what they are opening. For Match, that means going beyond a naked URL while being honest that the current code is a sensitive, reversible profile payload.

## Problem

Users can technically share any page today, but the experience is brittle:

1. Manual URL copying is awkward on mobile and easy to get wrong.
2. School pages contain several distinct artifacts, but the URL usually lands at the top instead of the relevant section.
3. Match sharing uses a special "Copy code" control that is not visually or behaviorally aligned with the rest of the site.
4. A copied URL alone does not explain whether the user is sharing a school profile, a CDS source document, an admissions visualization, a merit-aid card, or a filtered coverage view.
5. We have no clean product signal for which pages and artifacts users find worth sharing.

## Goals

1. Add a consistent, accessible Share button to high-value public pages.
2. Let users share the current page-level artifact first: school overview, year detail, Match list, and coverage filter state. Section-level sharing comes after stable anchors exist.
3. Prefer native sharing on devices that support it, with reliable copy-link fallback everywhere.
4. Preserve the project's privacy posture by treating Match share codes as sensitive profile payloads: do not log them, do not send them to analytics, and do not imply they anonymize student stats.
5. Add a Wordle-like Match share card that summarizes only URL-reproducible result distribution and includes the share URL.
6. Make Match links eligible for polished unfurls only after the privacy posture is explicit and preview data is URL-reproducible.
7. Add low-cardinality analytics events that show share intent without collecting sensitive payloads.

## Non-goals

- No login, contacts import, email sending, or server-side saved shares.
- No third-party social SDKs or embedded share widgets.
- No automatic posting to Facebook, X, LinkedIn, Reddit, TikTok, or similar networks.
- No public short-link service in MVP.
- No code-specific image-generation pipeline for dynamic Match social cards until the Match preview privacy gate is cleared.
- No claim that Match share codes anonymize student stats. The existing stateless code is reversible and must be treated as sensitive.
- No public leaderboard, virality loop, or gamified ranking pressure around student profiles.

## Users and Jobs

### Parent or student

"I found the page for a school we are considering and want to text it to someone with a short explanation."

### Counselor

"I built or found a useful view and want to send the exact list or source-backed section to a family without exposing more student data than necessary."

### Researcher or journalist

"I need a stable link or citation snippet for the exact data point I am referencing."

### IR professional

"I want to share a school's coverage status or archived document page with a colleague who may not know CollegeData.fyi."

## UX

### Placement

MVP placements:

1. `/schools/[school_id]` header: share the school overview.
2. `/schools/[school_id]/[year]` header: share the exact CDS year page.
3. `/match`: replace or wrap the existing "Copy code" control with the shared component, preserving the stateless profile code and clearly labeling it as shareable with anyone who has the link.
4. `/coverage`: share the current filtered view, since PRD 015 made filters URL-persisted.

Nice-to-have after MVP:

- school-page section actions after stable anchors ship: admissions strategy, positioning, merit profile, what changed, federal baseline, and documents ledger
- recipe pages under `/recipes`
- API examples and public-data pages
- reconstructed CDS tables from PRD 020

### Interaction

Desktop:

- A compact icon+text button labeled "Share" in page headers.
- Section-level share controls, once they ship, can be icon-only with an accessible label and tooltip.
- Clicking opens a small popover:
  - Copy link
  - Share with device, shown only when `navigator.share` is available
  - Copy citation, shown for source-backed school/year artifacts

Mobile:

- Tapping Share calls `navigator.share()` directly when supported.
- If native share fails or is unsupported, open the same popover with copy controls.

Feedback:

- After copy, the button reads "Copied" for about 1.6 seconds.
- Do not use modal confirmations.
- Do not block sharing if analytics fails.

### Match share card

For `/match`, add a second share action: "Copy summary". This copies a compact text block modeled on Wordle's share output. The summary must be computed from the exact URL-reproducible state represented by the shared URL.

```text
CollegeData.fyi Match K9F-3XQ
42 source-backed schools ranked

Strong fit  ████████ 8
Above range █████ 5
In range    ███████████████ 15
Below range █████████ 9
Unknown     █████ 5

https://www.collegedata.fyi/match?code=K9F-3XQ
```

The exact visual treatment can use block characters or simple colored squares if they render cleanly across iMessage, Slack, Gmail, and plain SMS. Default to ASCII/block characters over emoji if emoji alignment looks noisy.

The share card may include:

- profile code
- total ranked schools
- counts by academic-fit bucket
- active non-sensitive filters, only if they are part of the URL
- the share URL

The share card must not include:

- SAT, ACT, GPA, home state, intended major, or any free-form student profile text
- top-school names by default
- school IDs or document IDs
- hidden JSON payloads or base64 blobs beyond the existing profile code
- counts computed from filters or state that the URL cannot reproduce

Top-school names can be a later opt-in variant ("Include top 5 schools") after privacy review. The MVP should keep the card spoiler-light: enough to make the share legible, not enough to disclose a student's exact list in a notification preview.

MVP default: compute the copied summary from `rankMatchSchools(profile, schools, DEFAULT_MATCH_FILTERS)` unless allowed filter params have been added to the URL. Do not summarize transient client-only filter state.

### Rich link preview

When the Match URL is pasted into Slack, iMessage, Discord, LinkedIn, or similar clients, the URL should unfurl into a visual card using Open Graph metadata. This is separate from the copied Wordle-like text: the copied text gives a readable plain-text summary, while the URL preview gives the polished card.

MVP preview behavior:

- `/match?code=K9F-3XQ` uses generic Match metadata by default.
- `openGraph.title`: `CollegeData.fyi Match List Builder`
- `openGraph.description`: `Build a college match list from source-backed admissions data.`
- `openGraph.images`: a generic Match card, not code-specific.
- `twitter.card`: `summary_large_image` if the route metadata supports it cleanly.

Code-specific preview behavior is gated. It can ship only after an explicit product decision that Match links are sensitive share links and that preview platforms may fetch, cache, and display derived Match results. If that gate clears, the code-specific card may show:

- prominent `CollegeData.fyi Match`
- share code
- total ranked schools
- a horizontal distribution chart by academic-fit bucket
- small source line: `Built from Common Data Set score bands`
- no SAT, ACT, GPA, home state, intended major, top-school names, or full school list

Implementation default:

- Add generic Match Open Graph metadata to `web/src/app/match/page.tsx`.
- Optionally add `web/src/app/match/og/route.tsx` for the generic 1200x630 Match card.
- Do not point `openGraph.images` at a code-specific `/match/og?code=...` route in M1.
- Do not decode profile codes in an Open Graph image route in M1.
- If the code is missing or invalid, render a generic Match card instead of erroring.
- Keep `revalidate = 3600` unless preview bots need fresher results.

Post-MVP code-specific preview implementation, if approved:

- Add `generateMetadata()` to `web/src/app/match/page.tsx` so `/match?code=...` can produce code-specific `openGraph` and Twitter metadata.
- Add `web/src/app/match/og/route.tsx` as a dynamic image route that returns an `ImageResponse` and reads `code` from `request.url`.
- Point `openGraph.images` at `/match/og?code=K9F-3XQ`.
- Decode `code`, compute ranked groups from `fetchMatchBuilderSchools()`, and render the visual distribution.
- Show copy near the share action: `Anyone with this link, and some preview services, can open or process this Match code.`

Preview card quality bar:

- 1200x630 image.
- Text readable at Slack sidebar width and phone notification/card width.
- High contrast, no tiny table text.
- Looks like a result artifact, not a marketing banner.
- Works when the client crops or letterboxes the image.
- Uses the same bucket labels as the Match UI if the card is code-specific.

Important platform caveat: the sender cannot force Slack, iMessage, or every texting app to show a preview. Many clients cache unfurls, suppress previews in some contexts, or let users disable previews. CollegeData.fyi can only provide strong Open Graph metadata and a valid preview image.

### Shared Text

Payload examples:

- School page title: `Yale University Common Data Set archive`
- School page text: `Source-linked admissions, enrollment, aid, and CDS documents from CollegeData.fyi.`
- Section title: `Yale University admission strategy`
- Year page title: `Yale University Common Data Set 2024-25`
- Match title: `CollegeData.fyi match list`
- Coverage title: `CollegeData.fyi CDS coverage view`

The copied URL should be canonical and absolute. Section shares append a stable hash such as:

- `/schools/yale#admission-strategy`
- `/schools/yale#merit-profile`
- `/schools/yale#documents`

## Functional Requirements

### Reusable component

Create a single client component, likely `web/src/components/ShareButton.tsx`, with this shape:

```ts
type ShareButtonProps = {
  title: string;
  text?: string;
  path: string;
  sectionId?: string;
  citation?: string;
  surface: "school" | "school_year" | "school_section" | "match" | "coverage" | "recipe" | "api";
  variant?: "header" | "icon";
};
```

The component builds an absolute URL from `window.location.origin` plus `path` and optional `sectionId`.

### Copy behavior

1. Try `navigator.clipboard.writeText(url)`.
2. Fall back to a hidden `textarea` and `document.execCommand("copy")`, matching the current `/match` behavior.
3. If both fail, render the URL in a selectable field inside the popover.

### Native share behavior

Use `navigator.share({ title, text, url })` only when available. Treat cancellation as a non-error.

### Match integration

The existing Match URL remains:

`/match?code={statelessCode}`

The Share button may show the code in the UI, but the code must be treated as a sensitive profile payload because it is reversible. The share UI should say: `Anyone with this link can open this Match profile.`

Add a small formatter, likely in `web/src/lib/match-share.ts`, that takes URL-reproducible ranked result groups and returns the share-card text. This should be a pure function so it can be snapshot-tested against stable fixtures.

MVP summary state rule:

- If the URL is `/match?code=...`, compute the summary from default filters only.
- If the product wants summaries for active filters, first encode allowed filters into the shared URL and load them on page open.
- Encode only low-sensitivity UI state such as school type, region, admit-rate bucket, Carnegie bucket, current-cycle-only, and sort.
- Do not encode home state or intended major unless a separate privacy review decides they are safe and product-critical.

### Section anchors

School-page modules must expose stable `id` attributes before section-level share ships:

- `academic-positioning`
- `admission-strategy`
- `merit-profile`
- `what-changed`
- `federal-baseline`
- `documents`

Changing these IDs later is a breaking URL change.

### Metadata

Existing Next.js page metadata is mostly sufficient. MVP should audit:

- `metadataBase` remains `https://www.collegedata.fyi`
- school pages include `openGraph.title`, `openGraph.description`, and `openGraph.url`
- year pages include title, description, canonical, and Open Graph URL
- `/match` and `/coverage` have meaningful descriptions
- `/match?code=...` uses generic metadata in M1; code-specific title, description, and image metadata are gated until preview privacy is approved

Do not block the generic Share button MVP on dynamic OG images for every route. A generic Match preview card can ship in M1. Code-specific Match cards are post-MVP unless the privacy gate is explicitly cleared.

## Analytics

Use Vercel Analytics through the existing analytics posture from PRD 013.

Events:

- `share_opened`
- `share_copy_link`
- `share_native`
- `share_copy_match_summary`
- `share_copy_citation`
- `share_failed`

Properties:

- `surface`
- `variant`
- `has_section`
- `method`

Do not send:

- full URL
- school name
- school id
- Match code
- Match summary text
- student profile values
- citation text

## Accessibility

- Button is reachable by keyboard.
- Popover has a focus path and closes on Escape.
- Icon-only variants have `aria-label="Share this section"`.
- Copy status is announced with an `aria-live="polite"` region.
- The fallback URL field is selectable and labeled.
- No keyboard trap.

## Privacy and Security

- Do not put literal raw student scores, GPA, home state, intended major, or free-form profile data into share URLs.
- Treat current Match codes as reversible student-profile payloads, not anonymized IDs.
- Do not place Match codes in Open Graph titles, descriptions, or images in M1.
- Do not decode Match codes in preview-bot routes in M1.
- Do not persist share records server-side in MVP.
- Do not use third-party share SDKs.
- Treat citations as plain text only.
- Avoid `dangerouslySetInnerHTML`; the share component renders only strings.

## Rollout

### M1: Page-level share

- Ship `ShareButton`.
- Add header-level share to school pages, school-year pages, `/match`, and `/coverage`.
- Replace `/match` copy-code logic with the shared component or a thin adapter around it.
- Add `/match` "Copy summary" using the Wordle-like text formatter, computed from URL-reproducible default filter state.
- Add generic Match Open Graph metadata; optionally add a generic `web/src/app/match/og/route.tsx`.

### M2: Section-level share

- Add stable anchors to school-page modules.
- Add section-level share controls to admissions, positioning, merit, changes, federal facts, and documents.
- Add copy-citation for source-backed sections.

### M3: Code-specific Match preview, gated

- Decide whether Match codes remain reversible stateless payloads, move to an opaque/stateful share architecture, or keep previews generic.
- If retaining reversible codes, add explicit user-facing copy before code-specific preview sharing.
- If using an opaque/stateful share architecture, design retention, deletion, abuse controls, and privacy copy before implementation.
- Add code-specific Match Open Graph metadata and `web/src/app/match/og/route.tsx` only after this gate.

### M4: Polish and expansion

- Add recipe/API page share where it feels natural.
- Review Open Graph previews.
- Consider static per-route OG images if shared-page traffic becomes meaningful.

## Success Metrics

Within 30 days of ship:

- At least 2% of school-page visitors click Share.
- At least 60% of opened share menus result in copy or native share.
- Match share uses increase without a rise in invalid-code loads.
- No support reports that Match code sensitivity was unclear.
- Shared-section links land on the intended module on desktop and mobile once M2 ships.

## Implementation Notes

Likely files:

- `web/src/components/ShareButton.tsx`
- `web/src/components/CopyButton.tsx` may be simplified or made an internal primitive
- `web/src/app/schools/[school_id]/page.tsx`
- `web/src/app/schools/[school_id]/[year]/page.tsx`
- `web/src/app/match/page.tsx`
- `web/src/app/match/og/route.tsx`
- `web/src/components/MatchListBuilder.tsx`
- `web/src/lib/match-share.ts`
- `web/src/app/coverage/page.tsx`
- `web/src/lib/analytics.ts` if the current analytics helper lands before this work

Tests:

- unit test URL building and hash behavior
- snapshot test Match summary formatting for empty, small, and large result sets
- snapshot test that Match summaries ignore transient filters unless filters are encoded into the URL
- screenshot test generic Match OG image at 1200x630
- component test copy fallback where possible
- browser QA on Chrome desktop, Safari desktop, iOS Safari, and Android Chrome
- verify Match share UI labels the code/link as shareable to anyone with the link
- verify no Match raw profile values appear in copied summary text
- verify no Match code or raw profile values appear in M1 Open Graph title, description, or image
- verify section anchors scroll cleanly below the fixed nav, if the nav remains fixed

## Open Questions

1. Should "Copy citation" ship in M1 for year pages, or wait for PRD 020 reconstructed tables?
2. Should section-level share controls be always visible or appear on hover/focus?
3. Do we want a small "Copied from CollegeData.fyi" text snippet, or only the URL?
4. Should `/coverage` share include all filter params or only non-default filters?
5. Should Match URL sharing preserve filters in addition to the profile code?
6. Should "Include top 5 schools" exist as an explicit opt-in, or is that too easy to overshare?
7. What explicit privacy/product gate would justify code-specific Match OG cards later: reversible-code warning, opaque share architecture, or no code-specific previews at all?

## Default Decision

Ship M1 first. The smallest useful version is a reusable Share button on school, year, Match, and coverage pages that uses native share when possible and copy-link everywhere else. Match gets a URL-reproducible Wordle-like text summary plus generic Open Graph preview only. Section-level links, citations, active-filter Match summaries, and code-specific Match preview cards are later gates.
