import Link from "next/link";
import {
  computeAdmissionStrategy,
  formatRate,
  interestIsRelevant,
  type AdmissionFactorImportance,
  type AdmissionStrategySchool,
} from "@/lib/admission-strategy";
import { formatCount, formatCurrency } from "@/lib/format";

type AdmissionStrategyCardProps = {
  school: AdmissionStrategySchool;
  sourceHref: string | null;
};

type Factor = {
  label: string;
  value: AdmissionFactorImportance | null;
};

function pct(value: number | null): string {
  return formatRate(value, 0);
}

function maybeCount(value: number | null): string {
  return value == null ? "n/a" : formatCount(value);
}

function important(value: string | null): boolean {
  return value === "Important" || value === "Very Important";
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
    <div className={muted ? "admission-strategy-stat admission-strategy-stat--muted" : "admission-strategy-stat"}>
      <span>{label}</span>
      <strong className="serif stat-num">{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function RoundLine({ school }: { school: AdmissionStrategySchool }) {
  const edLabel =
    school.edOffered === true
      ? "Early Decision offered"
      : school.edOffered === false
        ? "No Early Decision reported"
        : null;
  const eaLabel =
    school.eaOffered === true
      ? school.eaRestrictive === true
        ? "Restrictive Early Action offered"
        : "Early Action offered"
      : school.eaOffered === false
        ? "No Early Action reported"
        : null;

  if (!edLabel && !eaLabel) return null;
  return (
    <div className="admission-strategy-rounds mono">
      {edLabel && <span>{edLabel}</span>}
      {eaLabel && <span>{eaLabel}</span>}
      {school.edHasSecondDeadline === true && (
        <span>Second binding round indicated; ED rate is blended.</span>
      )}
    </div>
  );
}

function FactorsBlock({ factors }: { factors: Factor[] }) {
  const highlighted = factors.filter((factor) => important(factor.value));
  if (highlighted.length === 0) return null;

  return (
    <div className="admission-strategy-panel">
      <div className="meta">§ Factors this school weighs</div>
      <div className="admission-strategy-factors">
        {highlighted.map((factor) => (
          <span key={factor.label}>
            {factor.label}: <strong>{factor.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export function AdmissionStrategyCard({
  school,
  sourceHref,
}: AdmissionStrategyCardProps) {
  const derived = computeAdmissionStrategy(school);
  if (!derived.hasRenderableContent) return null;

  const factors: Factor[] = [
    { label: "First generation", value: school.firstGenFactor },
    { label: "Legacy", value: school.legacyFactor },
    { label: "Geography", value: school.geographyFactor },
    { label: "State residency", value: school.stateResidencyFactor },
    { label: "Demonstrated interest", value: school.demonstratedInterestFactor },
  ];

  const showEdSuppressed = school.quality === "ed_math_inconsistent";
  const showWaitListSuppressed = school.quality === "wait_list_math_inconsistent";
  const showWaitList =
    !showWaitListSuppressed &&
    (school.waitListPolicy === true ||
      (school.waitListOffered != null &&
        school.waitListAccepted != null &&
        school.waitListAdmitted != null)) &&
    (school.waitListOffered != null ||
      school.waitListAccepted != null ||
      school.waitListAdmitted != null ||
      derived.waitListConditionalAdmitRate != null);
  const showAppFee = school.appFeeAmount != null || school.appFeeWaiverOffered != null;
  const selectiveEd = (school.acceptanceRate ?? 1) < 0.15;

  return (
    <section className="admission-strategy-card rule-2" aria-labelledby="admission-strategy-title">
      <div className="meta">§ Admission rounds</div>
      <div className="admission-strategy-card__body cd-card cd-card--cut">
        <div className="admission-strategy-card__head">
          <div>
            <h2 id="admission-strategy-title" className="serif admission-strategy-card__title">
              How this school shapes its class.
            </h2>
            <RoundLine school={school} />
          </div>
          {school.yieldRate != null && (
            <div className="admission-strategy-yield">
              <span className="meta">Yield</span>
              <strong className="serif stat-num">{pct(school.yieldRate)}</strong>
              <small>
                Enrolled after admission. High yield can mean top-choice demand,
                careful interest prediction, or both.
              </small>
            </div>
          )}
        </div>

        {showEdSuppressed && (
          <div className="admission-strategy-note admission-strategy-note--warn">
            ED counts for this school could not be reconciled and have been omitted. Other admissions data below.
          </div>
        )}

        {derived.edAdmitRate != null && (
          <div className="admission-strategy-ed">
            <div className="admission-strategy-stats">
              <StatBlock
                label="ED admit rate"
                value={pct(derived.edAdmitRate)}
                note={`${maybeCount(school.edAdmitted)} admitted from ${maybeCount(school.edApplicants)} ED applicants`}
                muted={selectiveEd}
              />
              {derived.nonEarlyResidualAdmitRate != null && (
                <StatBlock
                  label="Non-early residual"
                  value={pct(derived.nonEarlyResidualAdmitRate)}
                  note="Applicant and admit totals after subtracting ED counts"
                />
              )}
              {derived.edShareOfAdmitted != null && (
                <StatBlock
                  label="ED share of admits"
                  value={pct(derived.edShareOfAdmitted)}
                  note={derived.hasHighEdShare ? "High relative to the 2024+ corpus" : "Share of admitted class from ED"}
                />
              )}
            </div>
            <div className="admission-strategy-caveat">
              <strong>Read the ED rate carefully.</strong> Published ED rates include
              recruited athletes, legacy applicants, and institutional-priority applicants.
              The general-pool ED rate can be lower than the published number, sometimes substantially.
            </div>
          </div>
        )}

        <div className="admission-strategy-grid">
          {showWaitList && (
            <div className="admission-strategy-panel">
              <div className="meta">§ Wait list</div>
              <div className="admission-strategy-counts mono">
                <span>Offered {maybeCount(school.waitListOffered)}</span>
                <span>Accepted {maybeCount(school.waitListAccepted)}</span>
                <span>Admitted {maybeCount(school.waitListAdmitted)}</span>
              </div>
              <p>
                {derived.waitListOfferRate != null
                  ? `${pct(derived.waitListOfferRate)} of applicants were offered the wait list. `
                  : ""}
                {derived.waitListConditionalAdmitRate != null
                  ? `${pct(derived.waitListConditionalAdmitRate)} of students who accepted a wait-list spot were admitted.`
                  : "Wait-list counts are reported, but the conditional admit rate is not computable."}
              </p>
            </div>
          )}

          {showWaitListSuppressed && (
            <div className="admission-strategy-note admission-strategy-note--warn">
              Wait-list counts for this school could not be reconciled and have been omitted.
            </div>
          )}

          <FactorsBlock factors={factors} />

          {showAppFee && (
            <div className="admission-strategy-panel">
              <div className="meta">§ Application cost</div>
              <p>
                {school.appFeeAmount != null
                  ? `Application fee: ${formatCurrency(school.appFeeAmount)}.`
                  : "Application fee not reported."}
                {school.appFeeWaiverOffered === true
                  ? " Fee waivers are reported as available."
                  : school.appFeeWaiverOffered === false
                    ? " Fee waivers are not reported as available."
                    : ""}
              </p>
            </div>
          )}

          {interestIsRelevant(school.demonstratedInterestFactor) && (
            <div className="admission-strategy-panel admission-strategy-panel--accent">
              <div className="meta">§ Demonstrated interest</div>
              <p>
                This school marks applicant interest as {school.demonstratedInterestFactor}.
                Read yield and wait-list behavior with that policy in mind.
              </p>
            </div>
          )}
        </div>

        <div className="admission-strategy-card__source rule mono">
          § SOURCE: COMMON DATA SET {school.cdsYear} · §C.21 §C.22 §C.2 §C.7 §C.13 ·{" "}
          <Link href="/methodology/admission-strategy">METHOD →</Link>
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
