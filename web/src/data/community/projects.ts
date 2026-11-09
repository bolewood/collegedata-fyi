import { safeHttpUrl } from "@/lib/community-feedback";
export type CommunityProject = {
  slug: string;
  name: string;
  url: string;
  description: string;
  evidenceUrl: string;
  checked: string;
} & (
  | { kind: "public_reference" }
  | {
      kind: "approved_story";
      publicationStatus: "approved" | "withdrawn" | "awaiting_approval";
      contentVersion: string;
      approvedVersion: string;
      credit: string;
      quote?: string;
    }
);
const projects: CommunityProject[] = [
  {
    slug: "aidatlas",
    name: "AidAtlas",
    url: "https://github.com/munkhtumur-spec/AidAtlas",
    description: "Its college-search client uses the public API.",
    evidenceUrl:
      "https://github.com/munkhtumur-spec/AidAtlas/blob/main/backend/app/services/collegedata.py",
    checked: "2026-11-08",
    kind: "public_reference",
  },
  {
    slug: "unicoach",
    name: "UniCoach",
    url: "https://github.com/ian-shafer/unicoach",
    description:
      "Includes an importer for merit aid, admissions factors, and other facts from the Common Data Set archive.",
    evidenceUrl:
      "https://github.com/ian-shafer/unicoach/blob/main/bin/fetch-cds-seed",
    checked: "2026-11-08",
    kind: "public_reference",
  },
  {
    slug: "college-stats",
    name: "College Stats",
    url: "https://github.com/raywross/college-stats",
    description:
      "Its October 2026 release note credits the archive with finding 231 additional Common Data Set links. It reads the figures itself.",
    evidenceUrl:
      "https://github.com/raywross/college-stats/blob/main/release-notes/cds-urls-collegedata.md",
    checked: "2026-11-08",
    kind: "public_reference",
  },
  {
    slug: "college-iq-dashboard",
    name: "CollegeIQDashboard",
    url: "https://github.com/mpromisel002/CollegeIQDashboard",
    description:
      "An October 2026 update credits the document index with finding reports for 120 schools. It reads the figures itself.",
    evidenceUrl: "https://github.com/mpromisel002/CollegeIQDashboard/pull/6",
    checked: "2026-11-08",
    kind: "public_reference",
  },
];
export function publicProjects(records: CommunityProject[]) {
  const slugs = new Set<string>();
  for (const p of records) {
    if (
      !/^[a-z0-9-]+$/.test(p.slug) ||
      slugs.has(p.slug) ||
      !safeHttpUrl(p.url) ||
      !safeHttpUrl(p.evidenceUrl) ||
      !/^\d{4}-\d{2}-\d{2}$/.test(p.checked) ||
      !p.name.trim() ||
      !p.description.trim()
    )
      throw new Error("Invalid community content");
    slugs.add(p.slug);
    if (/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(JSON.stringify(p)))
      throw new Error("Private contact in community content");
    if (p.kind !== "public_reference" && p.kind !== "approved_story")
      throw new Error("Invalid community kind");
    if (
      p.kind === "approved_story" &&
      (!p.credit || !p.contentVersion || !p.approvedVersion)
    )
      throw new Error("Invalid story approval");
    // Final public data has no private evidence reference, contact or receipt id.
    const allowed = [
      "slug",
      "name",
      "url",
      "description",
      "evidenceUrl",
      "checked",
      "kind",
      ...(p.kind === "approved_story"
        ? [
            "publicationStatus",
            "contentVersion",
            "approvedVersion",
            "credit",
            "quote",
          ]
        : []),
    ];
    if (Object.keys(p).some((key) => !allowed.includes(key)))
      throw new Error("Private community field");
  }
  return records.filter(
    (p) =>
      p.kind === "public_reference" ||
      (p.publicationStatus === "approved" &&
        p.contentVersion === p.approvedVersion),
  );
}
export const communityProjects = publicProjects(projects);
