"use client";

import { REPO_URL } from "@/lib/repo";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { HeaderSchoolSearch } from "./HeaderSchoolSearch";
import { CmdKCatalog } from "./CmdKCatalog";
import { Wordmark } from "./Wordmark";
import { dataQualityLaunched } from "@/lib/data-quality";
import { isActive, secondaryNavLinks } from "@/lib/nav-links";

const PRIMARY_NAV_LINKS = [
  { href: "/match", label: "Match" },
  { href: "/schools", label: "Schools" },
  { href: "/api", label: "API" },
];

export function Nav() {
  const pathname = usePathname();
  const secondaryLinks = secondaryNavLinks(dataQualityLaunched());
  const secondaryActive = secondaryLinks.some((l) => isActive(pathname, l.href, l.alsoActiveOn));

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
          <CmdKCatalog />
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
              {secondaryLinks.map((l) => (
                <Link key={l.href} href={l.href}>
                  {l.label}
                </Link>
              ))}
              <a
                href={REPO_URL}
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
