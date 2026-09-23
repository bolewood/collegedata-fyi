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

/**
 * Live crosswalk aliases that resolve unambiguously to `canonicalSchoolId`.
 * Retired aliases are excluded: their documents are stale by review and must
 * never render under the canonical page.
 */
export function liveAliasSlugsFor(
  canonicalSchoolId: string,
  rows: SchoolAliasRow[],
  retiredEntries: RetiredSchoolAlias[] = [],
): string[] {
  const retired = new Set(retiredEntries.map((entry) => entry.alias));
  const candidates = new Set(
    rows
      .filter((row) => row.school_id === canonicalSchoolId && row.alias)
      .map((row) => row.alias as string),
  );
  return [...candidates]
    .filter(
      (alias) =>
        alias !== canonicalSchoolId &&
        !retired.has(alias) &&
        resolveCanonicalSchoolId(alias, rows) === canonicalSchoolId,
    )
    .sort();
}

type AliasMergeableDocument = {
  school_id: string | null;
  ipeds_id: string | null;
  canonical_year: string | null;
  sub_institutional: string | null;
};

/**
 * Serve a canonical school page from its own documents, filling only the
 * year/variant slots it lacks from live alias slugs. Alias documents that
 * carry a different IPEDS id are never merged.
 */
export function mergeAliasDocuments<T extends AliasMergeableDocument>(
  canonicalSchoolId: string,
  rows: T[],
): T[] {
  const own = rows.filter((row) => row.school_id === canonicalSchoolId);
  const canonicalIpeds = own.find((row) => row.ipeds_id)?.ipeds_id ?? null;
  const slotKey = (row: T) =>
    `${row.canonical_year ?? ""}|${row.sub_institutional ?? ""}`;
  const taken = new Set(own.map(slotKey));
  const merged = [...own];
  const aliasRows = rows
    .filter((row) => row.school_id !== canonicalSchoolId)
    .sort((a, b) => (a.school_id ?? "").localeCompare(b.school_id ?? ""));
  for (const row of aliasRows) {
    if (row.ipeds_id && canonicalIpeds && row.ipeds_id !== canonicalIpeds) continue;
    const key = slotKey(row);
    if (taken.has(key)) continue;
    taken.add(key);
    merged.push(row);
  }
  return merged.sort((a, b) => {
    const year = (b.canonical_year ?? "").localeCompare(a.canonical_year ?? "");
    if (year !== 0) return year;
    return (a.sub_institutional ?? "").localeCompare(b.sub_institutional ?? "");
  });
}

/**
 * Re-key corpus rows to the slug that serves them, merging alias rows the
 * same way the school page does. `resolve` returns null for slugs whose rows
 * must not be listed at all (retired aliases).
 */
export function canonicalizeSchoolRows<T extends AliasMergeableDocument>(
  rows: T[],
  resolve: (schoolId: string) => string | null,
): T[] {
  const groups = new Map<string, T[]>();
  for (const row of rows) {
    if (!row.school_id) continue;
    const canonical = resolve(row.school_id);
    if (!canonical) continue;
    const group = groups.get(canonical) ?? [];
    group.push(row);
    groups.set(canonical, group);
  }
  return [...groups].flatMap(([canonical, group]) =>
    mergeAliasDocuments(canonical, group).map((row) =>
      row.school_id === canonical ? row : { ...row, school_id: canonical },
    ),
  );
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
