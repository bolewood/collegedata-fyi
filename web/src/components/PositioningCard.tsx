import Link from "next/link";
import { PositioningCardProfile } from "./PositioningCardProfile";
import type { SchoolAcademicProfile } from "@/lib/positioning";

type PositioningCardProps = {
  school: SchoolAcademicProfile;
  sourceHref: string | null;
};

const HIDDEN_QUALITY_FLAGS = new Set(["wrong_file", "blank_template", "low_coverage"]);

function formatPercent(value: number | null): string {
  if (value == null) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function formatScore(value: number | null): string {
  return value == null ? "-" : value.toLocaleString();
}

function submitRateCaption(label: string, submitRate: number | null): string {
  const testName = label.split(" ")[0] ?? "Test";
  return submitRate == null
    ? "SUBMIT RATE NOT REPORTED"
    : `${formatPercent(submitRate)} OF ADMITS SUBMITTED ${testName} SCORES`;
}

function RangeStrip({
  label,
  p25,
  p50,
  p75,
  submitRate,
  year,
}: {
  label: string;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  submitRate: number | null;
  year: string;
}) {
  const hasRange = p25 != null && p50 != null && p75 != null;
  const values = [
    { label: "25th", value: p25 },
    { label: "Median", value: p50 },
    { label: "75th", value: p75 },
  ];

  return (
    <div className="positioning-range">
      <div className="positioning-range__head">
        <span>{label}</span>
        <span>{hasRange ? "Middle 50% of score submitters" : "Not reported"}</span>
      </div>
      {hasRange && (
        <>
          <div className="positioning-range__track" aria-hidden="true">
            <span style={{ left: "0%" }} />
            <span style={{ left: "50%" }} />
            <span style={{ left: "100%" }} />
          </div>
          <div className="positioning-range__values" aria-label={`${label} percentile scores`}>
            {values.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{formatScore(item.value)}</strong>
              </div>
            ))}
          </div>
        </>
      )}
      <div className="positioning-range__caption">
        {hasRange ? (
          <>
            § {submitRateCaption(label, submitRate)} · {year} CDS ·{" "}
            <Link href="/methodology/positioning">METHOD →</Link>
          </>
        ) : (
          <>§ {label} NOT REPORTED IN THIS CDS YEAR</>
        )}
      </div>
    </div>
  );
}
export function PositioningCard({ school, sourceHref }: PositioningCardProps) {
  if (HIDDEN_QUALITY_FLAGS.has(school.dataQualityFlag ?? "")) return null;
  const hasTestData =
    school.satCompositeP50 != null ||
    school.actCompositeP50 != null;
  if (!hasTestData) return null;

  return (
    <section className="positioning-card rule-2" aria-labelledby="positioning-title">
      <div className="meta">§ Academic profile</div>
      <div className="positioning-card__body cd-card cd-card--cut">
        <div className="positioning-card__grid">
          <div>
            <h2 id="positioning-title" className="serif positioning-card__title">
              Where you&apos;d land in this school&apos;s admitted class.
            </h2>
            <div className="positioning-card__ranges">
              <RangeStrip
                label="SAT composite"
                p25={school.satCompositeP25}
                p50={school.satCompositeP50}
                p75={school.satCompositeP75}
                submitRate={school.satSubmitRate}
                year={school.cdsYear}
              />
              <RangeStrip
                label="ACT composite"
                p25={school.actCompositeP25}
                p50={school.actCompositeP50}
                p75={school.actCompositeP75}
                submitRate={school.actSubmitRate}
                year={school.cdsYear}
              />
            </div>
            <div className="positioning-card__stats mono">
              <span>ADMIT RATE {formatPercent(school.acceptanceRate)}</span>
              <span>SAT SUBMIT {formatPercent(school.satSubmitRate)}</span>
              <span>ACT SUBMIT {formatPercent(school.actSubmitRate)}</span>
            </div>
          </div>

          <PositioningCardProfile school={school} />
        </div>

        <div className="positioning-card__source card-source-actions rule mono">
          <span>§ SOURCE: COMMON DATA SET {school.cdsYear} · §C.7 §C.9 §C.11 §C.12</span>
          {sourceHref ? (
            <span>
              <a href={sourceHref} target="_blank" rel="noopener noreferrer">
                ARCHIVED SOURCE →
              </a>
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}
