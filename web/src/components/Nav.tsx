"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wordmark } from "./Wordmark";

const NAV_LINKS = [
  { href: "/browse", label: "Browser" },
  { href: "/schools", label: "Schools" },
  { href: "/coverage", label: "Coverage" },
  { href: "/recipes", label: "Recipes" },
  { href: "/about", label: "About" },
  { href: "/api", label: "API" },
];

// A nav link is "active" when the user is on that section. Section pages
// (e.g. /recipes/acceptance-vs-yield) keep the parent (/recipes) lit so
// the nav reads as "you are here" instead of "you are nowhere."
function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (pathname === href) return true;
  return pathname.startsWith(href + "/");
}

export function Nav() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        borderBottom: "1px solid var(--rule)",
        background: "var(--paper)",
      }}
    >
      <div
        className="mx-auto max-w-5xl cd-nav-row"
        style={{ padding: "18px 24px" }}
      >
        <Link href="/" style={{ textDecoration: "none" }}>
          <Wordmark variant="dotted" size={20} />
        </Link>
        <div className="cd-nav-links">
          {NAV_LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                style={{
                  textDecoration: "none",
                  color: active ? "var(--ink)" : "var(--ink-3)",
                  paddingBottom: 2,
                  borderBottom: active
                    ? "1px solid var(--ink)"
                    : "1px solid transparent",
                }}
                className="nav-link"
              >
                {l.label}
              </Link>
            );
          })}
          <a
            href="https://github.com/bolewood/collegedata-fyi"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub (opens in new tab)"
            style={{
              textDecoration: "none",
              color: "var(--ink-3)",
              paddingBottom: 2,
              borderBottom: "1px solid transparent",
              display: "inline-flex",
              alignItems: "baseline",
              gap: 4,
            }}
            className="nav-link"
          >
            GitHub
            <span
              aria-hidden="true"
              style={{
                fontSize: "0.75em",
                color: "var(--ink-4)",
                lineHeight: 1,
              }}
            >
              ↗
            </span>
          </a>
        </div>
      </div>
    </nav>
  );
}
