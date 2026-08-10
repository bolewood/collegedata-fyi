export type SchoolAliasRow = {
  school_id: string | null;
  alias: string | null;
  is_primary: boolean | null;
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
