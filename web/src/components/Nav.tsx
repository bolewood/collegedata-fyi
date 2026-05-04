"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HeaderSchoolSearch } from "./HeaderSchoolSearch";
import { Wordmark } from "./Wordmark";

const PRIMARY_NAV_LINKS = [
  { href: "/match", label: "Match" },
  { href: "/schools", label: "Schools" },
  { href: "/api", label: "API" },
];

const SECONDARY_NAV_LINKS = [
  { href: "/browse", label: "Browser" },
  { href: "/coverage", label: "Coverage" },
  { href: "/recipes", label: "Recipes" },
  { href: "/about", label: "About" },
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
  const secondaryActive = SECONDARY_NAV_LINKS.some((l) => isActive(pathname, l.href));

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
        <HeaderSchoolSearch />
        <div className="cd-nav-links">
          {PRIMARY_NAV_LINKS.map((l) => {
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
          <details className="cd-nav-more" data-active={secondaryActive ? "true" : "false"}>
            <summary aria-current={secondaryActive ? "page" : undefined}>More</summary>
            <div>
              {SECONDARY_NAV_LINKS.map((l) => (
                <Link key={l.href} href={l.href}>
                  {l.label}
                </Link>
              ))}
              <a
                href="https://github.com/bolewood/collegedata-fyi"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub ↗
              </a>
            </div>
          </details>
        </div>
      </div>
    </nav>
  );
}
