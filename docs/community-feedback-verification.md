# PRD 037 verification evidence

`/feedback` uses the same browser-to-Formspree `FormData` pattern as
[`SubmissionForm.tsx`](../web/src/components/SubmissionForm.tsx), reading
`NEXT_PUBLIC_FEEDBACK_FORMSPREE_ENDPOINT` with fallback to
`NEXT_PUBLIC_FORMSPREE_ENDPOINT`.

| Check | Result |
|---|---|
| `npm --prefix web run typecheck` | Passed (`tsc --noEmit`) |
| `npm --prefix web test` | 812 passed (82 test files), including `src/lib/community-feedback.test.ts` validating field limits, URL safety, Formspree `FormData` encoding (`_subject`, conditional story/data-issue fields), analytics URL redaction, Sentry filters, and approved-story publication guards |
| `npx --prefix web playwright test tests/community-feedback.spec.ts tests/community-invitations.spec.ts` | 16 passed across desktop Chrome and mobile Pixel 5: WCAG 2 A/AA/2.1 AA/2.2 AA axe checks, 320px responsive width, 200% zoom geometry, no-JS fallback, keyboard-only submission and alert focus, direct Formspree `FormData` POST and thank-you state, error draft retention (429/503/timeout), and invitation links on `/usage`, `/api`, and school pages |
| Python ops & usage tests | 33 passed (`tools.ops.test_notify_discord`, `tools.ops.test_automation_health`, `tools.ops.test_lint_gha_heredocs`, `tools.community.test_usage_exclusion`) |
