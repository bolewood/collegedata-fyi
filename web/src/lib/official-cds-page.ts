import officialPages from "@/data/official-cds-pages.json";

export type OfficialCdsAccess = "request" | "public" | "unknown";

export type OfficialCdsPage = {
  url: string;
  access: OfficialCdsAccess;
};

type OfficialCdsPagesFile = {
  bySchoolId: Record<string, OfficialCdsPage>;
  byIpedsId: Record<string, OfficialCdsPage>;
};

const pages = officialPages as OfficialCdsPagesFile;

function isHttpUrl(url: string): boolean {
  return url.startsWith("https://") || url.startsWith("http://");
}

export function getOfficialCdsPage(
  schoolId: string,
  ipedsId?: string | null,
): OfficialCdsPage | null {
  const bySchool = pages.bySchoolId[schoolId];
  if (bySchool?.url && isHttpUrl(bySchool.url)) return bySchool;
  if (ipedsId) {
    const byIpeds = pages.byIpedsId[ipedsId];
    if (byIpeds?.url && isHttpUrl(byIpeds.url)) return byIpeds;
  }
  return null;
}
