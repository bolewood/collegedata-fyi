"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { trackEvent } from "@/lib/analytics";
import { buildSharePayload, isShareCancellation, type ShareSurface } from "@/lib/share";

// PRD 024 M1. One reusable share control: native share where it is the
// natural choice, copy link everywhere, and a selectable URL as the last
// resort. Analytics events carry only low-cardinality properties; never the
// URL, school, Match code or any profile value.

type ShareButtonProps = {
  title: string;
  text?: string;
  /** Path (with optional query). Omit to share the current address-bar URL as it is at click time. */
  path?: string;
  sectionId?: string;
  surface: ShareSurface;
  variant?: "header" | "icon";
  /** Which edge of the button the popover lines up with. Use "start" when the button sits at the left of its column. */
  align?: "start" | "end";
  /** One-line note shown in the popover, e.g. who can open the link. */
  notice?: string;
  /** Optional second copy action (the Match summary). */
  summary?: { label: string; text: string };
  disabled?: boolean;
};

type CopyMethod = "clipboard" | "exec_command";
const COPIED_MS = 1600;

async function copyText(text: string): Promise<CopyMethod | null> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return "clipboard";
    }
  } catch {
    // fall through to the textarea path
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok ? "exec_command" : null;
  } catch {
    return null;
  }
}

function ShareIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <path d="M8 10V2M5 5l3-3 3 3M3 8v5h10V8" strokeLinecap="square" />
    </svg>
  );
}

export function ShareButton({
  title,
  text,
  path,
  sectionId,
  surface,
  variant = "header",
  align = "end",
  notice,
  summary,
  disabled = false,
}: ShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<"link" | "summary" | null>(null);
  const [fallbackUrl, setFallbackUrl] = useState<string | null>(null);
  const [canNativeShare, setCanNativeShare] = useState(false);
  const [coarsePointer, setCoarsePointer] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);
  const timerRef = useRef<number | null>(null);
  const popoverId = useId();

  useEffect(() => {
    setCanNativeShare(typeof navigator !== "undefined" && typeof navigator.share === "function");
    setCoarsePointer(
      typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)").matches,
    );
    return () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
    };
  }, []);

  const props = useCallback(
    (method?: string) => ({
      surface,
      variant,
      has_section: Boolean(sectionId),
      ...(method ? { method } : {}),
    }),
    [surface, variant, sectionId],
  );

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    setFallbackUrl(null);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    firstItemRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close(true);
    }
    function onPointer(event: MouseEvent | TouchEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) close(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("touchstart", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("touchstart", onPointer);
    };
  }, [open, close]);

  function currentPath(): string {
    return path ?? `${window.location.pathname}${window.location.search}`;
  }

  function payload() {
    return buildSharePayload({
      title,
      text,
      origin: window.location.origin,
      path: currentPath(),
      sectionId,
    });
  }

  function flashCopied(kind: "link" | "summary") {
    setCopied(kind);
    if (timerRef.current != null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setCopied(null), COPIED_MS);
  }

  function openPopover() {
    setOpen(true);
    trackEvent("share_opened", props());
  }

  async function nativeShare(): Promise<boolean> {
    try {
      await navigator.share(payload());
      trackEvent("share_native", props("native"));
      return true;
    } catch (error) {
      // Dismissing the share sheet is not a failure.
      if (isShareCancellation(error)) return true;
      trackEvent("share_failed", props("native"));
      return false;
    }
  }

  async function onTriggerClick() {
    if (open) {
      close(true);
      return;
    }
    if (coarsePointer && canNativeShare) {
      const handled = await nativeShare();
      if (!handled) openPopover();
      return;
    }
    openPopover();
  }

  async function onCopyLink() {
    const url = payload().url;
    const method = await copyText(url);
    if (method) {
      trackEvent("share_copy_link", props(method));
      flashCopied("link");
      close(true);
    } else {
      trackEvent("share_failed", props("copy"));
      setFallbackUrl(url);
    }
  }

  async function onCopySummary() {
    if (!summary) return;
    const method = await copyText(summary.text);
    if (method) {
      trackEvent("share_copy_match_summary", props(method));
      flashCopied("summary");
      close(true);
    } else {
      trackEvent("share_failed", props("copy"));
    }
  }

  async function onDeviceShare() {
    const handled = await nativeShare();
    if (handled) close(true);
  }

  const label = copied ? "Copied" : "Share";
  const iconOnly = variant === "icon";
  const itemStyle: React.CSSProperties = {
    display: "block",
    width: "100%",
    textAlign: "left",
    background: "transparent",
    border: 0,
    borderBottom: "1px solid var(--rule)",
    padding: "10px 14px",
    fontFamily: "var(--sans)",
    fontSize: 14,
    color: "var(--ink)",
    cursor: "pointer",
  };

  return (
    <div ref={rootRef} style={{ position: "relative", display: "inline-block" }}>
      <button
        ref={triggerRef}
        type="button"
        className="cd-btn cd-btn--ghost"
        style={{ padding: iconOnly ? "8px 10px" : "8px 14px" }}
        onClick={onTriggerClick}
        disabled={disabled}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        aria-label={iconOnly ? "Share this section" : undefined}
      >
        <ShareIcon />
        {iconOnly ? null : <span>{label}</span>}
      </button>
      <span className="sr-only" role="status" aria-live="polite">
        {copied === "link" ? "Link copied" : copied === "summary" ? "Summary copied" : ""}
      </span>
      {open ? (
        <div
          id={popoverId}
          role="group"
          aria-label="Share options"
          className="cd-card"
          style={{
            position: "absolute",
            ...(align === "end" ? { right: 0 } : { left: 0 }),
            top: "calc(100% + 6px)",
            zIndex: 30,
            width: 280,
            maxWidth: "calc(100vw - 32px)",
          }}
        >
          <button ref={firstItemRef} type="button" style={itemStyle} onClick={onCopyLink}>
            Copy link
          </button>
          {summary ? (
            <button type="button" style={itemStyle} onClick={onCopySummary}>
              {summary.label}
            </button>
          ) : null}
          {canNativeShare ? (
            <button type="button" style={itemStyle} onClick={onDeviceShare}>
              Share with device
            </button>
          ) : null}
          {fallbackUrl ? (
            <div style={{ padding: "10px 14px" }}>
              <label className="meta" htmlFor={`${popoverId}-url`} style={{ display: "block", marginBottom: 6 }}>
                Copy this link
              </label>
              <input
                id={`${popoverId}-url`}
                type="text"
                readOnly
                value={fallbackUrl}
                className="mono"
                style={{ width: "100%", fontSize: 12, padding: "6px 8px", border: "1px solid var(--rule-strong)", background: "var(--paper)" }}
                onFocus={(event) => event.currentTarget.select()}
                autoFocus
              />
            </div>
          ) : null}
          {notice ? (
            <p style={{ margin: 0, padding: "10px 14px", fontSize: 12, lineHeight: 1.5, color: "var(--ink-2)" }}>
              {notice}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
