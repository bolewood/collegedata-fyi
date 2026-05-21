"use client";

import Link from "next/link";
import type { ComponentProps, MouseEvent } from "react";
import { type AnalyticsProperties, trackEvent } from "@/lib/analytics";

type LinkProps = ComponentProps<typeof Link>;
type AnchorProps = ComponentProps<"a">;

type TrackedInternalLinkProps = LinkProps & {
  analyticsEvent: string;
  analyticsProperties?: AnalyticsProperties;
  external?: false;
};

type TrackedExternalLinkProps = AnchorProps & {
  analyticsEvent: string;
  analyticsProperties?: AnalyticsProperties;
  external: true;
};

type TrackedLinkProps = TrackedInternalLinkProps | TrackedExternalLinkProps;

export function TrackedLink(props: TrackedLinkProps) {
  const { analyticsEvent, analyticsProperties, onClick } = props;

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    trackEvent(analyticsEvent, analyticsProperties);
    onClick?.(event);
  }

  if (props.external) {
    const { analyticsEvent: _event, analyticsProperties: _properties, external: _external, ...anchorProps } = props;
    return <a {...anchorProps} onClick={handleClick} />;
  }

  const { analyticsEvent: _event, analyticsProperties: _properties, external: _external, ...linkProps } = props;
  return <Link {...linkProps} onClick={handleClick} />;
}
