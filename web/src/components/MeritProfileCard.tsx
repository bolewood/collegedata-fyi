import Link from "next/link";
import type { MeritProfileRow } from "@/lib/types";
import { formatCount, formatCurrency, formatPercent } from "@/lib/format";

type MeritProfileCardProps = {
  profile: MeritProfileRow;
  sourceHref: string | null;
};

function valueOrNa(value: string): string {
  return value || "n/a";
}

function currency(value: number | null): string {
  return valueOrNa(formatCurrency(value));
}

function percent(value: number | null): string {
  return value == null ? "n/a" : formatPercent(value, 0);
}

function count(value: number | null): string {
  return value == null ? "n/a" : formatCount(value);
}

function yesNo(value: boolean | null): string {
  if (value === true) return "Reported";
  if (value === false) return "Not reported";
  return "n/a";
}

function StatBlock({
  label,
  value,
  note,
  muted = false,
}: {
  label: string;
  value: string;
  note: string;
  muted?: boolean;
}) {
  return (
    <div className={muted ? "merit-profile-stat merit-profile-stat--muted" : "merit-profile-stat"}>
      <span>{label}</span>
      <strong className="serif stat-num">{value}</strong>
      <small>{note}</small>
    </div>
  );
}

export function MeritProfileCard({ profile, sourceHref }: MeritProfileCardProps) {
  if (profile.cdsMeritFieldCount === 0) return null;

  const hasFirstYearMerit =
    profile.avgNonNeedGrantFirstYearFt != null ||
    profile.nonNeedAidRecipientsFirstYearFt != null ||
    profile.nonNeedAidShareFirstYearFt != null;
  const qualityLabel =
    profile.meritProfileQuality === "strong"
      ? "Core merit fields reported"
      : profile.meritProfileQuality === "partial"
        ? "Partial merit profile"
        : profile.meritProfileQuality === "limited"
          ? "Limited merit profile"
          : "Merit profile unavailable";

  return (
    <section className="merit-profile-card rule-2" aria-labelledby="merit-profile-title">
      <div className="meta">§ Merit and need aid</div>
      <div className="merit-profile-card__body cd-card cd-card--cut">
        <div className="merit-profile-card__head">
          <div>
            <h2 id="merit-profile-title" className="serif merit-profile-card__title">
              What this school reports giving.
            </h2>
            <div className="merit-profile-flags mono">
              <span>{qualityLabel}</span>
              {profile.institutionalAidAcademics === true && (
                <span>Academic merit aid checked</span>
              )}
              {profile.institutionalNonNeedAidNonresident === true && (
                <span>Non-need aid for nonresidents</span>
              )}
            </div>
          </div>
          <div className="merit-profile-context">
            <span className="meta">No-need grant recipients</span>
            <strong className="serif stat-num">
              {count(profile.nonNeedAidRecipientsFirstYearFt)}
            </strong>
            <small>
              {hasFirstYearMerit
                ? `${percent(profile.nonNeedAidShareFirstYearFt)} of first-year full-time students`
                : "H2A first-year fields not reported"}
            </small>
          </div>
        </div>

        <div className="merit-profile-stats">
          <StatBlock
            label="Avg no-need grant"
            value={currency(profile.avgNonNeedGrantFirstYearFt)}
            note="H2A first-year full-time students with no financial need"
          />
          <StatBlock
            label="Avg aid package"
            value={currency(profile.avgAidPackageFirstYearFt)}
            note="H2 first-year full-time aid recipients"
          />
          <StatBlock
            label="Avg need grant"
            value={currency(profile.avgNeedGrantFirstYearFt)}
            note="H2 first-year full-time need-based grant aid"
          />
          <StatBlock
            label="Avg net price"
            value={currency(profile.avgNetPrice)}
            note="Federal Scorecard, all aided students"
            muted
          />
        </div>

        <div className="merit-profile-grid">
          <div className="merit-profile-panel">
            <div className="meta">§ Scope</div>
            <p>
              CDS H2A counts students who had no financial need and received
              institutional non-need scholarship or grant aid, excluding athletic
              awards and tuition benefits.
            </p>
          </div>
          <div className="merit-profile-panel">
            <div className="meta">§ International aid</div>
            <p>
              Need-based aid for nonresidents:{" "}
              <strong>{yesNo(profile.institutionalNeedAidNonresident)}</strong>.
              {" "}Non-need aid for nonresidents:{" "}
              <strong>{yesNo(profile.institutionalNonNeedAidNonresident)}</strong>.
              {profile.avgInternationalAid != null
                ? ` Average international aid reported: ${currency(profile.avgInternationalAid)}.`
                : ""}
            </p>
          </div>
        </div>

        <div className="merit-profile-caveat">
          <strong>This is not a personalized price estimate.</strong> Merit awards
          are source-reported institutional facts. Your actual cost depends on
          income, assets, residency, application round, program, and school policy.
        </div>

        <div className="merit-profile-card__source rule mono">
          § SOURCE: COMMON DATA SET {profile.cdsYear} · §H.2 §H.2A §H.6 §H.14 ·{" "}
          <Link href="/methodology/merit-profile">METHOD →</Link>
          {sourceHref ? (
            <>
              {" "}·{" "}
              <a href={sourceHref} target="_blank" rel="noopener noreferrer">
                ARCHIVED SOURCE →
              </a>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
