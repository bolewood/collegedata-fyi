"use client";

import { useEffect, useMemo, useState } from "react";
import { track } from "@vercel/analytics";
import {
  DEFAULT_MATCH_FILTERS,
  groupRankedSchools,
  rankMatchSchools,
  rankedSchoolsCsv,
  type CarnegieBucket,
  type MatchBuilderSchool,
  type MatchFilters,
  type Region,
  type SchoolControl,
  type TestPolicySignal,
} from "@/lib/list-builder";
import { decodeProfileCode, encodeProfileCode } from "@/lib/savecode";
import { tierLabel, type StudentProfile, type Tier } from "@/lib/positioning";
import { SchoolListItem } from "./SchoolListItem";

const STORAGE_KEY = "cdfyi.matchProfile.v1";
const TIER_SEQUENCE: Tier[] = ["strong_fit", "likely", "possible", "unlikely", "long_shot", "unknown"];

type MatchProfile = StudentProfile & {
  state?: string;
  intendedMajor?: string;
  savedAt?: string;
};

function numberOrUndefined(value: FormDataEntryValue | null): number | undefined {
  if (typeof value !== "string" || value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function stringOrUndefined(value: FormDataEntryValue | null): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

function selectValue<T extends string>(value: FormDataEntryValue | null, fallback: T): T {
  return typeof value === "string" && value ? (value as T) : fallback;
}

function downloadCsv(filename: string, contents: string) {
  const blob = new Blob([contents], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function MatchListBuilder({
  schools,
  initialCode,
}: {
  schools: MatchBuilderSchool[];
  initialCode?: string;
}) {
  const [profile, setProfile] = useState<MatchProfile | null>(null);
  const [filters, setFilters] = useState<MatchFilters>(DEFAULT_MATCH_FILTERS);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (initialCode) {
      const decoded = decodeProfileCode(initialCode);
      if (decoded) {
        const next = { ...decoded, savedAt: new Date().toISOString() };
        setProfile(next);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return;
      }
    }

    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      setProfile(JSON.parse(raw) as MatchProfile);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [initialCode]);

  const hasScoreInput = profile?.sat != null || profile?.act != null;
  const ranked = useMemo(
    () => (profile && hasScoreInput ? rankMatchSchools(profile, schools, filters) : []),
    [filters, hasScoreInput, profile, schools],
  );
  const grouped = useMemo(() => groupRankedSchools(ranked), [ranked]);
  const shareCode = profile ? encodeProfileCode(profile) : null;
  const shareHref =
    typeof window === "undefined" || !shareCode
      ? ""
      : `${window.location.origin}/match?code=${encodeURIComponent(shareCode)}`;

  function onProfileSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next: MatchProfile = {
      gpa: numberOrUndefined(form.get("gpa")),
      sat: numberOrUndefined(form.get("sat")),
      act: numberOrUndefined(form.get("act")),
      gpaScale: selectValue<NonNullable<StudentProfile["gpaScale"]>>(form.get("gpaScale"), "unknown"),
      state: stringOrUndefined(form.get("state")),
      intendedMajor: stringOrUndefined(form.get("intendedMajor")),
      savedAt: new Date().toISOString(),
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setProfile(next);
    setCopied(false);
    try {
      track("match_profile_entered");
    } catch {
      // Analytics must not block local profile entry.
    }
  }

  function onFilterChange(event: React.ChangeEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    setFilters({
      control: selectValue<MatchFilters["control"]>(form.get("control"), "all"),
      region: selectValue<"all" | Region>(form.get("region"), "all"),
      admitRate: selectValue<MatchFilters["admitRate"]>(form.get("admitRate"), "all"),
      testPolicy: selectValue<"all" | TestPolicySignal>(form.get("testPolicy"), "all"),
      currentOnly: form.get("currentOnly") === "on",
      carnegie: selectValue<"all" | CarnegieBucket>(form.get("carnegie"), "all"),
      sort: selectValue<MatchFilters["sort"]>(form.get("sort"), "fit"),
    });
  }

  async function copyShareLink() {
    if (!shareHref) return;
    try {
      await navigator.clipboard.writeText(shareHref);
      setCopied(true);
      return;
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = shareHref;
      textarea.setAttribute("readonly", "true");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      const ok = document.execCommand("copy");
      textarea.remove();
      setCopied(ok);
    }
  }

  return (
    <div className="match-builder">
      <aside className="match-builder__panel">
        <div className="meta">Student profile</div>
        <form className="match-form" onSubmit={onProfileSubmit}>
          <label>
            <span>GPA</span>
            <input name="gpa" type="number" inputMode="decimal" min="0" max="5" step="0.01" defaultValue={profile?.gpa ?? ""} />
          </label>
          <label>
            <span>GPA scale</span>
            <select name="gpaScale" defaultValue={profile?.gpaScale ?? "unknown"}>
              <option value="unknown">Unknown</option>
              <option value="unweighted_4">Unweighted 4.0</option>
              <option value="weighted">Weighted</option>
            </select>
          </label>
          <label>
            <span>SAT</span>
            <input name="sat" type="number" inputMode="numeric" min="400" max="1600" step="10" defaultValue={profile?.sat ?? ""} />
          </label>
          <label>
            <span>ACT</span>
            <input name="act" type="number" inputMode="numeric" min="1" max="36" step="1" defaultValue={profile?.act ?? ""} />
          </label>
          <label>
            <span>Home state</span>
            <input name="state" type="text" maxLength={2} placeholder="OK" defaultValue={profile?.state ?? ""} />
          </label>
          <label>
            <span>Intended major</span>
            <input name="intendedMajor" type="text" defaultValue={profile?.intendedMajor ?? ""} />
          </label>
          <button className="cd-btn" type="submit">
            Rank schools
          </button>
        </form>

        <form className="match-filter-form rule" onChange={onFilterChange}>
          <div className="meta">Filters</div>
          <label>
            <span>Control</span>
            <select name="control" defaultValue={filters.control}>
              <option value="all">All</option>
              <option value={"public" as SchoolControl}>Public</option>
              <option value={"private_nonprofit" as SchoolControl}>Private nonprofit</option>
              <option value={"private_for_profit" as SchoolControl}>Private for-profit</option>
            </select>
          </label>
          <label>
            <span>School region</span>
            <select name="region" defaultValue={filters.region}>
              <option value="all">All</option>
              <option value="northeast">Northeast</option>
              <option value="midwest">Midwest</option>
              <option value="south">South</option>
              <option value="west">West</option>
            </select>
          </label>
          <label>
            <span>Admit rate</span>
            <select name="admitRate" defaultValue={filters.admitRate}>
              <option value="all">All</option>
              <option value="under_25">Under 25%</option>
              <option value="25_50">25-50%</option>
              <option value="50_plus">50%+</option>
            </select>
          </label>
          <label>
            <span>Tests</span>
            <select name="testPolicy" defaultValue={filters.testPolicy}>
              <option value="all">All</option>
              <option value="effective_optional">Effective optional</option>
              <option value="high_submit">High submit</option>
              <option value="mostly_non_submitters">Mostly non-submitters</option>
            </select>
          </label>
          <label>
            <span>Sort</span>
            <select name="sort" defaultValue={filters.sort}>
              <option value="fit">Fit strength</option>
              <option value="admit_rate">Admit rate</option>
              <option value="name">Name</option>
            </select>
          </label>
          <label>
            <span>Carnegie</span>
            <select name="carnegie" defaultValue={filters.carnegie}>
              <option value="all">All</option>
              <option value="doctoral">Doctoral</option>
              <option value="masters">Master's</option>
              <option value="baccalaureate">Baccalaureate</option>
              <option value="associates">Associates</option>
              <option value="special_focus">Special focus</option>
            </select>
          </label>
          <label className="match-checkbox">
            <input name="currentOnly" type="checkbox" defaultChecked={filters.currentOnly} />
            <span>Latest CDS cycle only</span>
          </label>
        </form>

        <div className="match-actions rule">
          <button
            className="cd-btn cd-btn--ghost"
            type="button"
            onClick={() => downloadCsv("collegedata-match-list.csv", rankedSchoolsCsv(ranked))}
            disabled={ranked.length === 0}
          >
            Export CSV
          </button>
          <button className="cd-btn cd-btn--ghost" type="button" onClick={() => window.print()}>
            Print
          </button>
          <button className="cd-btn cd-btn--ghost" type="button" onClick={copyShareLink} disabled={!shareHref}>
            {copied ? "Copied" : "Copy code"}
          </button>
          {shareCode ? <div className="match-code mono">{shareCode}</div> : null}
        </div>
      </aside>

      <section className="match-builder__results">
        <div className="match-results-head">
          <div>
            <div className="meta">Ranked list</div>
            <h2 className="serif">Schools grouped by fit tier.</h2>
          </div>
          <div className="match-results-count mono">
            {hasScoreInput ? `${ranked.length} schools` : "Enter SAT or ACT"}
          </div>
        </div>

        {!hasScoreInput ? (
          <div className="match-empty cd-card cd-card--cut">
            <p>Add a SAT or ACT score to rank schools against published CDS score bands.</p>
          </div>
        ) : (
          TIER_SEQUENCE.map((tier) => {
            const rows = grouped[tier];
            if (rows.length === 0) return null;
            return (
              <section key={tier} className="match-tier-group">
                <div className="match-tier-group__head">
                  <h3 className="serif">{tierLabel(tier)}</h3>
                  <span className="mono">{rows.length}</span>
                </div>
                <div className="match-tier-group__rows">
                  {rows.map((school) => (
                    <SchoolListItem key={school.documentId} school={school} />
                  ))}
                </div>
              </section>
            );
          })
        )}
      </section>
    </div>
  );
}
