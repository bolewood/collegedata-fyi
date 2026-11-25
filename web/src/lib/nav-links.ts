// Pure helpers for the header nav, kept out of the client component so tests
// can import them without pulling in the search box and its Supabase client.

type NavLink = { href: string; label: string; alsoActiveOn?: string[] };

// PRD 040: before the launch gate the item stays "Coverage". After it, the item
// is "Archive status" and stays lit on both tabs (/coverage and /data-quality).
export function secondaryNavLinks(launched: boolean): NavLink[] {
  return [
    { href: "/browse", label: "Compare" },
    launched
      ? { href: "/coverage", label: "Archive status", alsoActiveOn: ["/data-quality"] }
      : { href: "/coverage", label: "Coverage" },
    { href: "/recipes", label: "Recipes" },
    { href: "/about", label: "About" },
  ];
}

// A nav link is "active" when the user is on that section. Section pages
// (e.g. /recipes/acceptance-vs-yield) keep the parent (/recipes) lit so
// the nav reads as "you are here" instead of "you are nowhere."
export function isActive(pathname: string | null, href: string, alsoActiveOn: string[] = []): boolean {
  if (!pathname) return false;
  return [href, ...alsoActiveOn].some((h) => pathname === h || pathname.startsWith(h + "/"));
}

