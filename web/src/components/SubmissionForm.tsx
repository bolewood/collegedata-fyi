"use client";

// PRD 015 M5 — public source-submission form for directory-only and
// no-public-CDS-found schools (anywhere can_submit_source is true).
//
// Posts to a Formspree endpoint when NEXT_PUBLIC_FORMSPREE_ENDPOINT is
// configured. If the endpoint is missing, the component renders an honest
// unavailable state instead of falling back to a mailto link.
//
// Form fields:
//   school_id       hidden, identifies the submission
//   school_name     hidden, gives the operator a readable subject
//   coverage_status hidden, lets operator triage (verified_absent vs
//                   no_public_cds_found vs not_checked submissions
//                   warrant different reviews)
//   url             required, the public CDS URL the user found
//   note            optional, free-text context ("This is the IR page
//                   for the Honors College, not the main CDS")
//   submitter_email optional, lets us follow up if needed
//
// PRD M7 will swap the Formspree endpoint for a real backend once the
// public-upload pipeline ships. The component shape stays the same.

import { useState } from "react";
import type { CoverageStatus } from "@/lib/types";

export function SubmissionForm({
  school_id,
  school_name,
  coverage_status,
  compact = false,
}: {
  school_id: string;
  school_name: string;
  coverage_status: CoverageStatus;
  compact?: boolean;
}) {
  const formspreeEndpoint = process.env.NEXT_PUBLIC_FORMSPREE_ENDPOINT;
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [compactFormOpen, setCompactFormOpen] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!formspreeEndpoint) return; // shouldn't happen — form is only rendered when set
    setStatus("submitting");
    setErrorMessage(null);
    const formData = new FormData(e.currentTarget);
    try {
      const response = await fetch(formspreeEndpoint, {
        method: "POST",
        body: formData,
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        setStatus("success");
      } else {
        const body = await response.json().catch(() => ({}));
        setErrorMessage(
          (body as { error?: string })?.error ??
            `Submission failed (HTTP ${response.status}). Please try again.`,
        );
        setStatus("error");
      }
    } catch (err) {
      setErrorMessage(
        `Network error: ${(err as Error).message}. Please try again.`,
      );
      setStatus("error");
    }
  }

  if (compact) {
    return (
      <div style={{ marginTop: 22 }}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 14,
            alignItems: "center",
          }}
        >
          <button
            className="cd-btn"
            type="button"
            disabled={!formspreeEndpoint}
            aria-expanded={formspreeEndpoint ? compactFormOpen : undefined}
            aria-controls={formspreeEndpoint ? `submission-form-${school_id}` : undefined}
            onClick={() => {
              if (formspreeEndpoint) setCompactFormOpen((open) => !open);
            }}
            style={{
              fontSize: 15,
              padding: "12px 16px",
              opacity: formspreeEndpoint ? 1 : 0.62,
              cursor: formspreeEndpoint ? "pointer" : "not-allowed",
            }}
          >
            Email us!
          </button>
          <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 14, lineHeight: 1.5 }}>
            {formspreeEndpoint
              ? "Know where the CDS lives? Send the link and we’ll archive it."
              : "Source submissions are temporarily unavailable."}
          </p>
        </div>
        {status === "success" ? (
          <p style={{ margin: "14px 0 0", fontSize: 14, lineHeight: 1.5, color: "var(--forest)" }}>
            Thanks. We’ll review the link for {school_name} and archive it if it’s a public CDS source.
          </p>
        ) : (
          formspreeEndpoint && compactFormOpen && (
            <div id={`submission-form-${school_id}`}>
              <SubmissionFields
                errorMessage={errorMessage}
                handleSubmit={handleSubmit}
                school_name={school_name}
                school_id={school_id}
                coverage_status={coverage_status}
                status={status}
                compact
              />
            </div>
          )
        )}
      </div>
    );
  }

  if (!formspreeEndpoint) {
    return (
      <div
        className="cd-card"
        style={{ padding: "24px 28px", marginTop: 24 }}
      >
        <div className="meta" style={{ marginBottom: 10 }}>
          § Help us find this one
        </div>
        <p style={{ margin: 0, fontSize: 15, lineHeight: 1.55 }}>
          Source submissions are temporarily unavailable.
        </p>
      </div>
    );
  }

  // ── Success state ─────────────────────────────────────────────────
  if (status === "success") {
    return (
      <div
        className="cd-card"
        style={{ padding: "24px 28px", marginTop: 24 }}
      >
        <div className="meta" style={{ marginBottom: 10 }}>
          § Submitted
        </div>
        <p style={{ margin: 0, fontSize: 15, lineHeight: 1.55 }}>
          {`Thanks. We’ll review the link for ${school_name} and archive it if it’s a public CDS source. If we have questions we’ll reach out to the email you provided.`}
        </p>
      </div>
    );
  }

  // ── Active form ──────────────────────────────────────────────────
  return (
    <SubmissionFields
      errorMessage={errorMessage}
      handleSubmit={handleSubmit}
      school_name={school_name}
      school_id={school_id}
      coverage_status={coverage_status}
      status={status}
    />
  );
}

function SubmissionFields({
  errorMessage,
  handleSubmit,
  school_name,
  school_id,
  coverage_status,
  status,
  compact = false,
}: {
  errorMessage: string | null;
  handleSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  school_name: string;
  school_id: string;
  coverage_status: CoverageStatus;
  status: "idle" | "submitting" | "success" | "error";
  compact?: boolean;
}) {
  return (
    <form
      onSubmit={handleSubmit}
      className={compact ? undefined : "cd-card"}
      style={{
        padding: compact ? "14px 0 0" : "24px 28px",
        marginTop: compact ? 0 : 24,
      }}
    >
      {!compact && (
        <>
          <div className="meta" style={{ marginBottom: 10 }}>
            § Help us find this one
          </div>
          <p style={{ margin: "0 0 20px", fontSize: 15, lineHeight: 1.55 }}>
            {`Know where ${school_name} publishes its Common Data Set? Send us the link and we’ll archive it.`}
          </p>
        </>
      )}

      <input type="hidden" name="school_id" value={school_id} />
      <input type="hidden" name="school_name" value={school_name} />
      <input type="hidden" name="coverage_status" value={coverage_status} />
      <input
        type="hidden"
        name="_subject"
        value={`[CDS source] ${school_name}`}
      />

      <FormField label="CDS URL" required>
        <input
          name="url"
          type="url"
          required
          placeholder="https://ir.example.edu/cds/2024-25.pdf"
          style={inputStyle}
        />
      </FormField>

      <FormField label="Where did you find it? (optional)">
        <textarea
          name="note"
          rows={3}
          placeholder="e.g., linked from the IR page, or sent to me by the registrar"
          style={{ ...inputStyle, fontFamily: "var(--sans)", resize: "vertical" }}
        />
      </FormField>

      <FormField label="Your email (optional, for follow-up)">
        <input
          name="submitter_email"
          type="email"
          placeholder="you@example.com"
          style={inputStyle}
        />
      </FormField>

      {status === "error" && errorMessage && (
        <p
          style={{
            margin: "0 0 14px",
            fontSize: 13,
            color: "var(--brick)",
          }}
        >
          {errorMessage}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="cd-btn"
        style={{ marginTop: 4 }}
      >
        {status === "submitting" ? "Sending…" : "Send the link"}
      </button>
    </form>
  );
}

function FormField({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label style={{ display: "block", marginBottom: 16 }}>
      <span
        className="meta"
        style={{ display: "block", marginBottom: 6, color: "var(--ink-2)" }}
      >
        {label}
        {required && <span style={{ color: "var(--ink-3)" }}> *</span>}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "9px 12px",
  border: "1px solid var(--rule-strong)",
  background: "var(--paper)",
  color: "var(--ink)",
  fontFamily: "var(--sans)",
  fontSize: 15,
  borderRadius: 2,
  outline: "none",
};
