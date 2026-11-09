"use client";
import { useEffect, useRef } from "react";
import { TrackedLink } from "./TrackedLink";
import { trackEvent } from "@/lib/analytics";
import {
  GITHUB_REPOSITORY,
  type FeedbackSource,
} from "@/lib/community-feedback";
export function CommunityLink({
  surface,
  kind = "feedback",
  school,
  year,
  children,
}: {
  surface: FeedbackSource;
  kind?: "feedback" | "story" | "data_issue";
  school?: string;
  year?: string;
  children: React.ReactNode;
}) {
  const query = new URLSearchParams({ from: surface, kind });
  if (school) query.set("school", school);
  if (year) query.set("year", year);
  return (
    <TrackedLink
      href={`/feedback?${query}`}
      analyticsEvent="community_cta_clicked"
      analyticsProperties={{ action: kind, surface, placement: "permanent" }}
    >
      {children}
    </TrackedLink>
  );
}
export function StarLink({ surface }: { surface: FeedbackSource }) {
  return (
    <TrackedLink
      external
      href={GITHUB_REPOSITORY}
      analyticsEvent="star_link_clicked"
      onClick={() =>
        trackEvent("community_cta_clicked", {
          action: "github_star",
          surface,
          placement: "permanent",
        })
      }
      analyticsProperties={{ surface, placement: "permanent" }}
    >
      Star on GitHub
    </TrackedLink>
  );
}
export function CommunityInvitation({ surface }: { surface: "usage" | "api" }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!ref.current || !window.IntersectionObserver) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let sent = false;
    const observer = new IntersectionObserver(
      (entries) => {
        clearTimeout(timer);
        if (!sent && entries[0].intersectionRatio >= 0.5)
          timer = setTimeout(() => {
            sent = true;
            trackEvent("community_invitation_viewed", {
              surface,
              placement: "permanent",
            });
            observer.disconnect();
          }, 1000);
      },
      { threshold: 0.5 },
    );
    observer.observe(ref.current);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [surface]);
  return (
    <section
      ref={ref}
      className="my-8 border-y border-[var(--rule)] py-6"
      aria-label="Share how you use the data"
    >
      <h2 className="serif text-2xl">
        {surface === "api"
          ? "Building something with this data?"
          : "How are you using the data?"}
      </h2>
      <p className="my-3 text-sm leading-relaxed">
        {surface === "api"
          ? "I'd love to see it. Share a link or a sentence about what you're working on, whether it's public or just for you."
          : "Building a tool, advising students, researching colleges, or making your own college list? A link and a sentence are plenty."}
      </p>
      <div className="flex flex-wrap gap-5 text-sm">
        <CommunityLink surface={surface} kind="story">
          {surface === "api"
            ? "Tell us what you're building"
            : "Share how you use it"}
        </CommunityLink>
        <StarLink surface={surface} />
        {surface === "usage" && (
          <a href="#projects">See projects using the data</a>
        )}
      </div>
    </section>
  );
}
