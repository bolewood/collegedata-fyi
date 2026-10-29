import Link from "next/link";
import type { ComponentProps } from "react";

type ListLinkProps = ComponentProps<typeof Link>;

/**
 * next/link with prefetch disabled.
 *
 * App Router prefetches every in-view <Link> in production. After school
 * pages became force-static (PR #236), scrolling an unpaginated school or
 * year list fires one /schools/* request per row — enough to trip the WAF
 * at 120 req/60s. Hover prefetch is also off: a stationary cursor over the
 * table fires mouseenter on each row as it scrolls past.
 *
 * Use for dense lists of school or year links. Isolated nav/breadcrumb
 * links can keep the default.
 */
export function ListLink(props: ListLinkProps) {
  return <Link {...props} prefetch={false} />;
}
