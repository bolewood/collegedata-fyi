import { SITE_URL } from "./sitemap-static";

export type SchoolFeedEvent = {
  id: number | string;
  school_id: string;
  school_name: string;
  cds_year: string;
  event_type: "inserted" | "refreshed";
  occurred_at: string;
};

export function schoolFeedPath(schoolId: string): string {
  return `/schools/${schoolId}/feed.xml`;
}

export function schoolFeedUrl(schoolId: string): string {
  return `${SITE_URL}${schoolFeedPath(schoolId)}`;
}

function xmlEscape(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function rfc822(iso: string): string {
  return new Date(iso).toUTCString();
}

export function buildSchoolRss(args: {
  schoolId: string;
  schoolName: string;
  events: SchoolFeedEvent[];
}): string {
  const hub = `${SITE_URL}/schools/${args.schoolId}`;
  const items = args.events
    .map((event) => {
      const verb = event.event_type === "refreshed" ? "replaced" : "published";
      const title = `${args.schoolName} Common Data Set ${event.cds_year} (${verb})`;
      const link = `${hub}/${event.cds_year}`;
      const description =
        event.event_type === "refreshed"
          ? `${args.schoolName} replaced its ${event.cds_year} Common Data Set. This archive recorded new school-published bytes.`
          : `${args.schoolName} published a ${event.cds_year} Common Data Set. This archive recorded the school-published file.`;
      return [
        "    <item>",
        `      <title>${xmlEscape(title)}</title>`,
        `      <link>${xmlEscape(link)}</link>`,
        `      <guid isPermaLink="false">cds-publish-event-${xmlEscape(String(event.id))}</guid>`,
        `      <pubDate>${rfc822(event.occurred_at)}</pubDate>`,
        `      <description>${xmlEscape(description)}</description>`,
        "    </item>",
      ].join("\n");
    })
    .join("\n");

  const channelDescription =
    `School-published Common Data Set files for ${args.schoolName}, archived by collegedata.fyi. ` +
    `Entries appear when the school publishes or replaces a file — not when this archive re-checks an unchanged file, and not for third-party mirrors.`;

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<rss version="2.0">`,
    "  <channel>",
    `    <title>${xmlEscape(`${args.schoolName} Common Data Set — collegedata.fyi`)}</title>`,
    `    <link>${xmlEscape(hub)}</link>`,
    `    <description>${xmlEscape(channelDescription)}</description>`,
    items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");
}
