"use client";

import { useEffect, useMemo, useState } from "react";
import { track } from "@vercel/analytics";
import {
  scorePosition,
  tierLabel,
  type SchoolAcademicProfile,
  type StudentProfile,
} from "@/lib/positioning";

const STORAGE_KEY = "cdfyi.positioningProfile.v1";

type StoredProfile = StudentProfile & {
  savedAt?: string;
};

function numberOrUndefined(value: FormDataEntryValue | null): number | undefined {
  if (typeof value !== "string" || value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatGpa(value: number | null | undefined): string {
  if (value == null) return "not reported";
  return value.toFixed(2).replace(/0$/, "").replace(/\.0$/, "");
}

function formatPercentile(value: number | null): string {
  return value == null ? "n/a" : `${value}th percentile`;
}

function ordinal(value: number): string {
  const mod100 = value % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${value}TH`;
  switch (value % 10) {
    case 1:
      return `${value}ST`;
    case 2:
      return `${value}ND`;
    case 3:
      return `${value}RD`;
    default:
      return `${value}TH`;
  }
}

function tierBasis(result: ReturnType<typeof scorePosition>, school: SchoolAcademicProfile): string {
  if (result.tier === "unknown") {
    if (result.caveats.includes("sub_15_admit_rate_suppression")) {
      return "TIER SUPPRESSED · ADMIT RATE UNDER 15%, SCORES INSIDE MID-50%";
    }
    return "TIER UNKNOWN · BASIS INCOMPLETE";
  }
  const basis =
    result.satPercentile != null
      ? `SAT ${ordinal(result.satPercentile)} PCTL`
      : result.actPercentile != null
        ? `ACT ${ordinal(result.actPercentile)} PCTL`
        : "TEST POSITION UNKNOWN";
  const admit =
    school.acceptanceRate == null
      ? "ADMIT RATE UNKNOWN"
      : `ADMIT RATE ${Math.round(school.acceptanceRate * 100)}%`;
  const caveat = result.caveats.includes("stale_cds")
    ? " · CDS YEAR OLDER THAN 3 YEARS"
    : "";
  return `TIER · ${tierLabel(result.tier).toUpperCase()} · BASIS: ${basis}, ${admit}${caveat}`;
}

export function PositioningCardProfile({ school }: { school: SchoolAcademicProfile }) {
  const [profile, setProfile] = useState<StoredProfile | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as StoredProfile;
      setProfile(parsed);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const result = useMemo(
    () => (profile ? scorePosition(profile, school) : null),
    [profile, school],
  );

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next: StoredProfile = {
      gpa: numberOrUndefined(form.get("gpa")),
      sat: numberOrUndefined(form.get("sat")),
      act: numberOrUndefined(form.get("act")),
      gpaScale: (form.get("gpaScale") as StudentProfile["gpaScale"]) ?? "unknown",
      savedAt: new Date().toISOString(),
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setProfile(next);
    setEditing(false);
    try {
      track("positioning_profile_entered");
    } catch {
      // Analytics must never block the local-only profile interaction.
    }
  }

  function clearProfile() {
    window.localStorage.removeItem(STORAGE_KEY);
    setProfile(null);
    setEditing(true);
  }

  if (editing || !profile) {
    return (
      <div className="positioning-profile">
        <p className="positioning-profile__lede">
          Add your GPA and test score to compare against this school&apos;s published CDS bands.
        </p>
        <form className="positioning-form" onSubmit={onSubmit}>
          <label>
            <span>GPA</span>
            <input
              name="gpa"
              type="number"
              inputMode="decimal"
              min="0"
              max="5"
              step="0.01"
              defaultValue={profile?.gpa ?? ""}
            />
          </label>
          <label>
            <span>SAT composite</span>
            <input
              name="sat"
              type="number"
              inputMode="numeric"
              min="400"
              max="1600"
              step="10"
              defaultValue={profile?.sat ?? ""}
            />
          </label>
          <label>
            <span>ACT composite</span>
            <input
              name="act"
              type="number"
              inputMode="numeric"
              min="1"
              max="36"
              step="1"
              defaultValue={profile?.act ?? ""}
            />
          </label>
          <label>
            <span>GPA scale</span>
            <select name="gpaScale" defaultValue={profile?.gpaScale ?? "unknown"}>
              <option value="unknown">Unknown</option>
              <option value="unweighted_4">Unweighted 4.0</option>
              <option value="weighted">Weighted</option>
            </select>
          </label>
          <div className="positioning-form__actions">
            <button className="cd-btn" type="submit">
              Show my position
            </button>
            {profile && (
              <button className="cd-btn cd-btn--ghost" type="button" onClick={() => setEditing(false)}>
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="positioning-profile">
      <p className="positioning-profile__sentence">{result?.positionalSentence}</p>
      {result && (
        <div className="positioning-profile__tier mono">
          § {tierBasis(result, school)}
        </div>
      )}
      <div className="positioning-profile__details">
        <div>
          <span className="mono">Your SAT</span>
          <strong>{profile.sat ?? "n/a"}</strong>
          {result && <small>{formatPercentile(result.satPercentile)}</small>}
        </div>
        <div>
          <span className="mono">Your ACT</span>
          <strong>{profile.act ?? "n/a"}</strong>
          {result && <small>{formatPercentile(result.actPercentile)}</small>}
        </div>
        <div>
          <span className="mono">School avg HS GPA</span>
          <strong>{formatGpa(school.avgHsGpa)}</strong>
          <small>Your entered GPA {formatGpa(profile.gpa)}</small>
        </div>
      </div>
      <div className="positioning-profile__actions">
        <button className="cd-btn cd-btn--ghost" type="button" onClick={() => setEditing(true)}>
          Edit scores
        </button>
        <button className="cd-btn cd-btn--ghost" type="button" onClick={clearProfile}>
          Clear
        </button>
      </div>
    </div>
  );
}
