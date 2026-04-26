import Link from "next/link";
import { Wordmark } from "./Wordmark";

const NAV_LINKS = [
  { href: "/browse", label: "Browser" },
  { href: "/schools", label: "Schools" },
  { href: "/recipes", label: "Recipes" },
  { href: "/about", label: "About" },
  { href: "/api", label: "API" },
];

export function Nav() {
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
          {NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              style={{
                textDecoration: "none",
                color: "var(--ink-3)",
                paddingBottom: 2,
                borderBottom: "1px solid transparent",
              }}
              className="nav-link"
            >
              {l.label}
            </Link>
          ))}
          <a
            href="https://github.com/bolewood/collegedata-fyi"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              textDecoration: "none",
              color: "var(--ink-3)",
              paddingBottom: 2,
              borderBottom: "1px solid transparent",
            }}
            className="nav-link"
          >
            GitHub
          </a>
        </div>
      </div>
    </nav>
  );
}
