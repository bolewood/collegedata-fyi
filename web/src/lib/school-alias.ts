export type SchoolAliasRow = {
  school_id: string | null;
  alias: string | null;
  is_primary: boolean | null;
};

export type RetiredSchoolAlias = {
  alias: string;
  school_id: string;
};

export type SchoolAliasRedirect = {
  source: string;
  destination: string;
  permanent: true;
};

/** Resolve one requested slug without guessing across ambiguous aliases. */
export function resolveCanonicalSchoolId(
  requestedSchoolId: string,
  rows: SchoolAliasRow[],
): string | null {
  const matching = rows.filter(
    (row): row is SchoolAliasRow & { school_id: string } =>
      row.alias === requestedSchoolId && Boolean(row.school_id),
  );
  const primaryIds = new Set(
    matching.filter((row) => row.is_primary).map((row) => row.school_id),
  );
  if (primaryIds.size === 1) return [...primaryIds][0];
  if (primaryIds.size > 1) return null;

  const canonicalIds = new Set(matching.map((row) => row.school_id));
  return canonicalIds.size === 1 ? [...canonicalIds][0] : null;
}

/** Replace only the path for a same-origin permanent redirect; preserve query parameters. */
export function schoolRedirectUrl(requestUrl: string, pathname: string): URL {
  const url = new URL(requestUrl);
  url.pathname = pathname;
  return url;
}

/** Resolve only reviewed, durable aliases from the checked-in redirect corpus. */
export function resolveRetiredSchoolAlias(
  requestedSchoolId: string,
  entries: RetiredSchoolAlias[],
): string | null {
  const canonicalIds = new Set(
    entries
      .filter((entry) => entry.alias === requestedSchoolId)
      .map((entry) => entry.school_id),
  );
  return canonicalIds.size === 1 ? [...canonicalIds][0] : null;
}

const SCHOOL_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Build deterministic page redirects from the reviewed retired-alias corpus. */
export function buildRetiredSchoolRedirects(
  entries: RetiredSchoolAlias[],
): SchoolAliasRedirect[] {
  const destinations = new Map<string, string>();
  for (const { alias, school_id: schoolId } of entries) {
    if (!SCHOOL_SLUG.test(alias) || !SCHOOL_SLUG.test(schoolId)) {
      throw new Error(`Invalid retired school redirect: ${alias} -> ${schoolId}`);
    }
    if (alias === schoolId) {
      throw new Error(`Retired school alias duplicates its canonical slug: ${alias}`);
    }
    const existing = destinations.get(alias);
    if (existing && existing !== schoolId) {
      throw new Error(
        `Ambiguous retired school redirect: ${alias} -> ${existing}, ${schoolId}`,
      );
    }
    destinations.set(alias, schoolId);
  }

  return [...destinations]
    .sort(([left], [right]) => left.localeCompare(right))
    .flatMap(([alias, schoolId]) => [
      {
        source: `/schools/${alias}`,
        destination: `/schools/${schoolId}`,
        permanent: true as const,
      },
      {
        source: `/schools/${alias}/:year`,
        destination: `/schools/${schoolId}/:year`,
        permanent: true as const,
      },
    ]);
}
