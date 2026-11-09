# Copy deck: Feedback, stories, and GitHub stars (PRD 037)

> Implementation note (2026-11-08): the approved planning text below is preserved.
> M0 isolated proof and M1/M2 implementation are prepared in this branch; production
> writes remain off and launch checks are outstanding. See
> [implementation and operations](../community-feedback.md) for verified behavior,
> setup dependencies and M3's deliberate deferral. No submitted story is published.

**Status:** Draft for Anthony's reader review. Not shipped.

**Created:** 2026-11-08

**PRD:** [037](../prd/037-feedback-stories-and-github-stars.md)

## Audience and voice

The general feedback page addresses parents, students, and counselors first.
The API invitation addresses developers and researchers. The usage invitation
includes both. Use the [product/professional distinction](../../web/VOICE.md)
without making a visitor learn the pipeline to send a note.

The request is small: a sentence is useful, a project is not required, email is
optional unless the visitor wants a feature conversation. Criticism is welcome.
Never imply a star, story, account, or donation is owed for free access.

No emoji or five-star rating widget. A GitHub star is a named external action.
GitHub stays out of the homepage hero and primary navigation. This deck supplies
wording; the PRD supplies placement, storage, and permission behavior.

## Permanent footer link

**Label:** Feedback

**Destination:** `/feedback?from=footer`

Keep the existing separate `GitHub` link.

## Usage-page invitation

**Heading:** How are you using the data?

**Body:** Building a tool, advising students, researching colleges, or making
your own college list? A link and a sentence are plenty.

**Primary:** Share how you use it

**Secondary:** Star on GitHub

**Nearby section link:** See projects using the data

## API-page invitation

**Heading:** Building something with this data?

**Body:** I'd love to see it. Share a link or a sentence about what you're
working on, whether it's public or just for you.

**Primary:** Tell us what you're building

**Secondary:** Star on GitHub

Do not attach this paragraph to every code block or API response.

## School and school-year pages

**Link:** Found a problem? Send feedback

**Destination:** Data-problem mode with safe school/year context only.

The general footer feedback link still offers feedback and story modes.

## Feedback page

**Title:** Feedback | collegedata.fyi

**Meta description:** Tell us what helped, what needs fixing, or how you use
collegedata.fyi. No account required. Email is optional unless you'd like to
discuss being featured.

**Kicker:** Feedback

**H1:** A note to the maintainer.

**Lead:** Tell us what helped, what was confusing, or what you're doing with
the data. A sentence is enough. No account needed.

**Choices:** Share feedback · Share a story · Report a data problem

| Mode | Message label | Helper |
|---|---|---|
| Feedback | What would you like us to know? | Something useful, something confusing, or something we should change. |
| Story | How are you using the data? | A personal college search, counseling work, research, or an app all count. |
| Data problem | What looks wrong? | Tell us which number or page needs a look. You don't need to know the correct answer. |

**Project link label:** Project or publication link (optional)

**Name label:** Name or organization (optional)

**Email label:** Email (optional)

**Email helper:** Add your email if you'd like a reply. We'll use it only for
this conversation.

**Story checkbox, unchecked:** I'm interested in being featured on the site.

**Checkbox helper:** We'll ask you to approve the write-up and how you're
credited before anything is published.

When checked, use **Email** as the label and: `Add an email so we can discuss
the story with you.` Do not retain the word optional on a required field.

**Data context labels:** School (optional) · Report year (optional) · Field or
section (optional) · Source link or what you expected (optional)

**Privacy note:** Your message is private. Please leave out student names,
grades, test scores, financial details, and other sensitive information.
[How we handle feedback](/privacy#feedback).

**Retention helper:** We keep messages and reply contact details for up to
180 days. Approved publication permissions are kept separately while a story
is featured. See the privacy page for details.

**Submit:** Send message

**Alternative:** Prefer email? [contact@bolewood.com](mailto:contact@bolewood.com)

**Optional specialist path:** You can also [report a data problem on
GitHub](https://github.com/bolewood/collegedata-fyi/issues/new?template=report-extraction-error.yml).
GitHub issues are public and require an account.

## Submission states

**Sending:** Sending your message…

**Saved heading:** Thanks. Your message reached us.

**Saved body:** Your reference is `{receipt}`. If you included an email, we may
reply there. We read messages, but can't promise a reply to every one.

**Saved story note, only when opted in:** Nothing will be published without
your approval of the final write-up and credit.

**Optional link after success:** You can also star the project on GitHub.

**Validation summary:** Please check the fields below. Your message is still here.

**Empty message:** Add a message. A sentence is enough.

**Email required for feature discussion:** Add an email so we can discuss
featuring your story, or uncheck that option to send without one.

**Rate limit:** You've sent several messages recently. Please try again in
`{retry interval}`, or email contact@bolewood.com.

**Timeout:** We couldn't confirm whether your message arrived. It's still
here. Try again, or email contact@bolewood.com.

**Service error:** We couldn't send your message right now. It's still here.
Please try again, or email contact@bolewood.com.

**Website writes disabled:** The website form is unavailable right now. You
can still send a note to contact@bolewood.com.

Never say `Email sent`, `Review posted`, or `Star added` for these actions.

## Maintainer notification email

**Recipient:** contact@bolewood.com

**Subject:** CollegeData.fyi: {count} new feedback message(s)

**Body:** There are {count} new messages waiting for review.

**Link:** Open the private feedback inbox

Use a fixed, verified Supabase dashboard destination that requires operator
sign-in. No sender names, submitted addresses, messages, project links, or
student context in the email. Do not use a sender-supplied `Reply-To`.
Notifications are batched on an hourly schedule and retried after failures;
the website confirmation refers to saved messages, not delivered email.

## Public usage-page project section

**Section heading:** Projects using the data

**Intro:** Some of the ways people are putting the data to work. Public
references link to the project's own documentation. Stories shared with us
are published with the sender's approval.

**Subheading:** Public project references

Candidate factual summaries, rechecked before publication:

- **AidAtlas:** Its college-search client uses the public API and credits
  collegedata.fyi as a data source.
- **UniCoach:** Includes an importer for merit aid, admissions factors, and
  other facts from the Common Data Set archive.
- **College Stats:** Its October 2026 release note credits the archive with
  finding 231 additional Common Data Set links. It reads the figures itself.
- **CollegeIQDashboard:** An October 2026 update credits the document index
  with finding reports for 120 schools. It reads the figures itself.

Each entry links its exact supporting source and says `Checked {date}`.
Avoid `Trusted by`, customer logos, unsupported audience counts, or describing
an unverified deployment as live.

**Approved-story subheading:** Stories shared with us

Omit until at least one final write-up has approval. Do not fill it with
quotes taken from public research notes or README files.

**Invitation:** Using the data in a different way? Tell us about it.

**License note:** Usage statistics are CC0. Curated project write-ups are
CC BY-SA 4.0. Linked projects and their content keep their own terms.

## Final publication approval message

This is a proposed template for individual correspondence after a visitor
asks to discuss being featured. It is not sent automatically by the form.

> Thanks for sharing how you use collegedata.fyi. Here's the short write-up
> we'd like to publish, with the name and link shown below.
>
> `{final write-up, exact credit, project link, and optional exact quote}`
>
> It would appear on collegedata.fyi and in the public source repository under
> [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), which allows
> reuse with credit under the license's terms. Your original private message
> and email won't be published. You keep ownership of your contribution.
>
> Please reply if you approve this text and credit, or tell us what to change.
> We can remove it from the live site and current source later, but public Git
> history and copies other people have already reused may remain.

Silence does not authorize publication. Substantial changes need renewed
approval. Use the actual license and final wording that will ship.

## Optional export-adjacent prompt

Only for the later experiment specified in the PRD.

**Heading:** Was this useful?

**Body:** A short note helps us understand what to improve. You can also star
the project on GitHub to show your support.

**Primary:** Share feedback

**Secondary:** Star on GitHub

**Dismiss:** Not now

This heading is an invitation, not a yes/no question that gates the actions.
No positive-only review path. The prompt never claims a download completed.

## Repository and integration documentation

**Heading:** Using the data?

**Body:** Tell us what you're building, researching, or using in your work.
A link and a sentence are plenty: https://www.collegedata.fyi/feedback.
You can also open an issue or star this repository. No account or response
is required to use the data.

## Privacy-page additions

Add a stable `feedback` anchor and explain in plain language:

- The form collects the message and optional fields the visitor chooses to
  submit; reply email is optional except for a feature discussion.
- Messages are private, accessible to the maintainer and necessary service
  providers, and are not sold, used for marketing, or put in public exports.
- A transactional email service sends the maintainer counts and a private
  inbox link. The message and submitted contact details are not in those
  notification emails. No automatic email is sent to the submitter.
- Contact information is used for that conversation, not a mailing list.
- Raw messages and reply details expire within 180 days; spam within 30 days.
- Final publication permission records are retained while a story remains
  live and removed within 90 days of withdrawal.
- Rate protection briefly uses a daily-changing network code, retained for
  at most 48 hours; ordinary hosting/security logs remain separately covered.
- Only a separately approved final story and credit can be published.
- Give contact@bolewood.com for feedback/privacy/removal requests. GitHub is
  optional and public, not the required privacy-support channel.

If the prompt experiment ships, also explain its local display/dismissal
timestamps and that they contain no visitor id, student profile, or message.
Update the effective date and metadata alongside the text. Do not claim the
whole site collects no contact information after the form launches.
