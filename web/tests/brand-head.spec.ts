import { expect, test } from "@playwright/test";

// Cutover-blocking: the rendered <head> of the main page types must carry the
// new name and canonical origin and no trace of the old name (title, meta,
// og:site_name, JSON-LD, icons, canonical).
const CANONICAL_ORIGIN = "https://www.quadfile.org";
const PAGES = [
  { label: "home", path: "/" },
  { label: "school page", path: "/schools/mit" },
  { label: "school-year page", path: "/schools/mit/2024-25" },
  { label: "api docs", path: "/api" },
];

for (const { label, path } of PAGES) {
  test(`head of ${label} has no old name and a Quadfile canonical`, async ({ request }) => {
    const res = await request.get(path);
    expect(res.status()).toBe(200);
    const html = await res.text();
    const head = /<head[^>]*>([\s\S]*?)<\/head>/i.exec(html)?.[1] ?? "";
    expect(head.length, "found a <head>").toBeGreaterThan(200);
    expect(head).not.toMatch(/collegedata/i);
    expect(head).toContain("Quadfile");
    const canonical = /<link[^>]+rel="canonical"[^>]+href="([^"]+)"/i.exec(head)?.[1];
    expect(canonical).toBe(path === "/" ? CANONICAL_ORIGIN : `${CANONICAL_ORIGIN}${path}`);
  });
}
