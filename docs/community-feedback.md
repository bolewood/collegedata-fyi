# Community feedback operations (PRD 037)

- [PRD](prd/037-feedback-stories-and-github-stars.md) ·
  [copy deck](copy/037-feedback-stories-and-github-stars.md) ·
  [verification evidence](community-feedback-verification.md).

## What is implemented

`/feedback` offers a quiet form for general feedback, project/user stories, and
data problems, with optional email except when a visitor checks interest in
discussing being featured.

Just like [`SubmissionForm.tsx`](../web/src/components/SubmissionForm.tsx) on
directory-only school pages, [`FeedbackForm.tsx`](../web/src/components/FeedbackForm.tsx)
posts `FormData` directly from the visitor's browser to Formspree (`fetch(endpoint, { method: "POST", body: formData, headers: { Accept: "application/json" } })`).

- **Endpoint configuration:** Reads `NEXT_PUBLIC_FEEDBACK_FORMSPREE_ENDPOINT`
  first and falls back to `NEXT_PUBLIC_FORMSPREE_ENDPOINT` (already configured
  on Vercel for Production and Preview).
- **Distinct email subjects:** Each submission sets `_subject` to
  `[Feedback] collegedata.fyi`, `[Story] collegedata.fyi`, or
  `[Data issue] <school> (<year>)` so feedback, stories, and CDS link submissions
  are easy to filter even when sharing a Formspree endpoint.
- **Fallback:** If neither env var is set, `/feedback` displays an unavailable
  notice and keeps `mailto:contact@bolewood.com` and the GitHub issue link
  available. With JavaScript disabled, the submit button stays disabled and the
  `<noscript>` message directs visitors to the email link.
- **Privacy & Sentry:** Analytics strips query/hash parameters on `/feedback`
  and emits only bounded event properties (`kind`, `from`, `category`). Sentry
  drops events, transactions, and breadcrumbs originating from `/feedback`.

## Story publication workflow

Submitting a story or checking "I'm interested in being featured on the site"
never publishes anything automatically:

1. Draft the proposed write-up, credit line, project link, and optional quote.
2. Email the author to get explicit written approval of the exact final wording
   and credit under CC BY-SA 4.0.
3. Add only approved public fields to
   [`web/src/data/community/projects.ts`](../web/src/data/community/projects.ts)
   with `kind: "approved_story"`, `publicationStatus: "approved"`, and matching
   `contentVersion` / `approvedVersion`. The loader in `projects.ts` rejects
   unapproved, withdrawn, or mismatched-version stories as well as any private
   contact fields.

## Verification commands

```bash
npm --prefix web run typecheck
npm --prefix web test
PLAYWRIGHT_BROWSER_CHANNEL=chrome npx --prefix web playwright test tests/community-feedback.spec.ts tests/community-invitations.spec.ts
python3 -m unittest tools.ops.test_notify_discord tools.ops.test_automation_health tools.ops.test_lint_gha_heredocs tools.community.test_usage_exclusion
```
