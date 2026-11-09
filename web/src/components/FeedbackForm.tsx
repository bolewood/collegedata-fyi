"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  emptyFeedback,
  fieldLimits,
  submissionIdentity,
  validateFeedback,
  type FeedbackPayload,
  type FeedbackKind,
  type FeedbackSource,
  type FeedbackErrors,
} from "@/lib/community-feedback";
import { trackEvent } from "@/lib/analytics";
import { StarLink } from "./CommunityInvitation";
const modeCopy = {
  feedback: [
    "Share feedback",
    "What would you like us to know?",
    "Something useful, something confusing, or something we should change.",
  ],
  story: [
    "Share a story",
    "How are you using the data?",
    "A personal college search, counseling work, research, or an app all count.",
  ],
  data_issue: [
    "Report a data problem",
    "What looks wrong?",
    "Tell us which number or page needs a look. You don't need to know the correct answer.",
  ],
};
export function FeedbackForm({
  enabled,
  kind,
  from,
  school = "",
  year = "",
}: {
  enabled: boolean;
  kind: FeedbackKind;
  from: FeedbackSource;
  school?: string;
  year?: string;
}) {
  const [draft, setDraft] = useState({
    ...emptyFeedback(kind, from),
    school,
    year,
  });
  const [ready, setReady] = useState(false);
  const [sending, setSending] = useState(false);
  const [errors, setErrors] = useState<FeedbackErrors>({});
  const [notice, setNotice] = useState("");
  const [receipt, setReceipt] = useState("");
  const [savedInterest, setSavedInterest] = useState(false);
  const identity = useRef<
    { serialized: string; requestId: string } | undefined
  >(undefined);
  const started = useRef(false);
  const inFlight = useRef(false);
  const summary = useRef<HTMLDivElement>(null);
  useEffect(() => setReady(true), []);
  useEffect(() => {
    if (notice) summary.current?.focus();
  }, [notice, errors]);
  function edit<K extends keyof FeedbackPayload>(
    key: K,
    value: FeedbackPayload[K],
  ) {
    if (!started.current) {
      started.current = true;
      trackEvent("community_form_started", { kind: draft.kind, from });
    }
    setDraft((d) => ({ ...d, [key]: value }));
  }
  const inputClass =
    "block w-full mt-2 border border-[var(--rule-strong)] rounded-sm bg-[var(--paper)] px-3 py-2 text-base";
  function field(
    key: keyof typeof fieldLimits,
    label: string,
    type = "text",
    help?: string,
  ) {
    return (
      <div className="my-5">
        <label htmlFor={`feedback-${key}`}>{label}</label>
        <input
          id={`feedback-${key}`}
          className={inputClass}
          type={type}
          disabled={sending}
          value={draft[key]}
          maxLength={fieldLimits[key]}
          required={
            key === "email" && draft.kind === "story" && draft.featureInterest
          }
          autoComplete={
            key === "email" ? "email" : key === "name" ? "name" : "off"
          }
          onChange={(e) => edit(key, e.target.value)}
          aria-invalid={!!errors[key]}
          aria-describedby={help || errors[key] ? `${key}-help` : undefined}
        />
        {(help || errors[key]) && (
          <p id={`${key}-help`} className="mt-2 text-sm">
            {errors[key] ?? help}
          </p>
        )}
      </div>
    );
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    const payload: FeedbackPayload = {
      ...draft,
      projectUrl: draft.kind === "story" ? draft.projectUrl : "",
      featureInterest: draft.kind === "story" && draft.featureInterest,
      ...(draft.kind !== "data_issue"
        ? { school: "", year: "", field: "", expected: "", sourceUrl: "" }
        : {}),
    };
    identity.current = submissionIdentity(payload, identity.current);
    const body = { ...payload, requestId: identity.current.requestId };
    const checked = validateFeedback(body);
    if (!checked.value) {
      setErrors(checked.errors);
      setNotice("Please check the fields below. Your message is still here.");
      trackEvent("community_form_error", { category: "invalid" });
      return;
    }
    setErrors({});
    setNotice("");
    setSending(true);
    inFlight.current = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
        referrerPolicy: "no-referrer",
      });
      const result = await response.json();
      if (response.ok && typeof result.receipt === "string") {
        setReceipt(result.receipt);
        setSavedInterest(payload.featureInterest);
        trackEvent("community_form_saved", { kind: draft.kind, from });
      } else {
        const category =
          response.status === 429
            ? "limited"
            : response.status === 400
              ? "invalid"
              : response.status === 409
                ? "conflict"
                : "unavailable";
        trackEvent("community_form_error", { category });
        if (response.status === 400) setErrors(result.fields ?? {});
        // Fixed local copy only; never render upstream/provider error text.
        setNotice(
          category === "limited"
            ? `You've sent several messages recently. Please try again in ${Math.max(1, Math.ceil(Number(response.headers.get("Retry-After") ?? 600) / 60))} minutes, or email contact@bolewood.com.`
            : category === "invalid"
              ? "Please check the fields below. Your message is still here."
              : category === "conflict"
                ? "This version couldn't be sent. Your message is still here. Edit it and try again, or email contact@bolewood.com."
                : "We couldn't send your message right now. It's still here. Please try again, or email contact@bolewood.com.",
        );
      }
    } catch {
      setNotice(
        "We couldn't confirm whether your message arrived. It's still here. Try again, or email contact@bolewood.com.",
      );
      trackEvent("community_form_error", { category: "timeout" });
    } finally {
      clearTimeout(timer);
      setSending(false);
      inFlight.current = false;
    }
  }
  if (!enabled)
    return (
      <p role="status" className="my-6">
        The website form is unavailable right now. You can still send a note to
        contact@bolewood.com.
      </p>
    );
  if (receipt)
    return (
      <section
        role="status"
        aria-live="polite"
        className="my-8 border-y border-[var(--rule)] py-6"
      >
        <h2 className="serif text-3xl">Thanks. Your message reached us.</h2>
        <p className="my-4 break-words">
          Your reference is <span className="mono">{receipt}</span>. If you
          included an email, we may reply there. We read messages, but
          can&apos;t promise a reply to every one.
        </p>
        {savedInterest && (
          <p className="mb-4">
            Nothing will be published without your approval of the final
            write-up and credit.
          </p>
        )}
        <StarLink surface={from} />
      </section>
    );
  return (
    <>
      {!enabled && (
        <p role="status" className="my-6">
          The website form is unavailable right now. You can still send a note
          to contact@bolewood.com.
        </p>
      )}
      <form onSubmit={submit} noValidate className="my-8">
        <div
          ref={summary}
          tabIndex={-1}
          role={notice ? "alert" : undefined}
          className="mb-5 focus:outline-2 focus:outline-[var(--forest)]"
        >
          {notice}
          <ul>
            {Object.entries(errors).map(([key, error]) => (
              <li key={key}>
                <a href={`#feedback-${key}`}>{error}</a>
              </li>
            ))}
          </ul>
        </div>
        <fieldset disabled={sending}>
          <legend className="font-medium">What would you like to share?</legend>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-3">
            {(Object.keys(modeCopy) as FeedbackKind[]).map((k) => (
              <label key={k} className="flex items-center gap-2">
                <input
                  type="radio"
                  className="accent-[var(--forest)]"
                  name="kind"
                  value={k}
                  checked={draft.kind === k}
                  onChange={() => edit("kind", k)}
                />
                {modeCopy[k][0]}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="my-6">
          <label htmlFor="feedback-message">{modeCopy[draft.kind][1]}</label>
          <p id="message-help" className="mt-2 text-sm">
            {modeCopy[draft.kind][2]}
          </p>
          <textarea
            id="feedback-message"
            className={inputClass}
            rows={6}
            disabled={sending}
            required
            maxLength={4000}
            value={draft.message}
            onChange={(e) => edit("message", e.target.value)}
            aria-invalid={!!errors.message}
            aria-describedby={`message-help${errors.message ? " message-error" : ""}`}
          />
          {errors.message && <p id="message-error">{errors.message}</p>}
        </div>
        {field(
          "email",
          draft.kind === "story" && draft.featureInterest
            ? "Email"
            : "Email (optional)",
          "email",
          draft.kind === "story" && draft.featureInterest
            ? "Add an email so we can discuss the story with you."
            : "Add your email if you'd like a reply. We'll use it only for this conversation.",
        )}
        {draft.kind === "story" && (
          <>
            {field(
              "projectUrl",
              "Project or publication link (optional)",
              "url",
            )}
            <label className="flex items-start gap-3">
              <input
                className="mt-1 accent-[var(--forest)]"
                type="checkbox"
                disabled={sending}
                checked={draft.featureInterest}
                onChange={(e) => edit("featureInterest", e.target.checked)}
              />
              I&apos;m interested in being featured on the site.
            </label>
            <p className="mt-2 text-sm">
              We&apos;ll ask you to approve the write-up and how you&apos;re
              credited before anything is published.
            </p>
          </>
        )}
        {draft.kind === "data_issue" && (
          <>
            {field("school", "School (optional)")}
            {field("year", "Report year (optional)")}
            {field("field", "Field or section (optional)")}
            {field("expected", "What you expected (optional)")}
            {field("sourceUrl", "Source link (optional)", "url")}
          </>
        )}
        <details className="my-6">
          <summary>Optional details</summary>
          {field("name", "Name or organization (optional)")}
        </details>
        <p className="my-4 text-sm">
          Your message is private. Please leave out student names, grades, test
          scores, financial details, and other sensitive information.{" "}
          <a href="/privacy#feedback">How we handle feedback</a>.
        </p>
        <p className="my-4 text-sm">
          We keep messages and reply contact details for up to 180 days.
          Approved publication permissions are kept separately while a story is
          featured. See the privacy page for details.
        </p>
        <button
          className="cd-btn"
          disabled={!ready || !enabled || sending}
          type="submit"
        >
          {sending ? "Sending your message…" : "Send message"}
        </button>
        <span role="status" aria-live="polite" className="ml-3">
          {sending ? "Sending your message…" : ""}
        </span>
        <noscript>
          <p className="my-4">
            The website form needs JavaScript. Please use the email link below
            to send your note.
          </p>
        </noscript>
      </form>
    </>
  );
}
