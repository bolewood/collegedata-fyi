"use client";

import { useMemo, useState } from "react";
import { schoolCountLabel, type SchoolLookupRow } from "@/lib/usage";

const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "");

export function UsageSchoolSearch({
  schools,
  periodLabel,
  sinceLabel,
}: {
  schools: SchoolLookupRow[];
  /** null while the headline period is not a complete month. */
  periodLabel: string | null;
  sinceLabel: string;
}) {
  const [query, setQuery] = useState("");
  const keyed = useMemo(
    () => schools.map((school) => ({ school, key: normalize(`${school.school_name} ${school.school_id}`) })),
    [schools],
  );
  const term = normalize(query);
  const hits = term.length < 3 ? [] : keyed.filter((s) => s.key.includes(term)).slice(0, 8);

  return (
    <div className="usage-search cd-card">
      <label htmlFor="usage-school-q">Look up a school</label>
      <input
        id="usage-school-q"
        type="search"
        placeholder="Start typing a school name"
        autoComplete="off"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <ul className="usage-results" aria-live="polite">
        {term.length < 3 ? null : hits.length ? (
          hits.map(({ school }) => (
            <li key={school.school_id}>
              <span className="usage-nm">{school.school_name}</span>
              <span className="usage-ct">
                {periodLabel ? (
                  <>
                    {schoolCountLabel(school.month)} in {periodLabel}
                    <br />
                  </>
                ) : null}
                {schoolCountLabel(school.total)} since {sinceLabel}, in months with 10 or more
              </span>
            </li>
          ))
        ) : (
          <li className="usage-empty">
            No school by that name reached 10 downloads in a month since {sinceLabel}.
          </li>
        )}
      </ul>
      <p className="usage-search-note">
        Rounded to the nearest 10. Schools are listed for complete months with
        10 or more downloads; other months show &ldquo;fewer than 10&rdquo; (which
        includes none) and are left out of the total. Counts include browser and
        machine downloads, not bots.
      </p>
    </div>
  );
}
