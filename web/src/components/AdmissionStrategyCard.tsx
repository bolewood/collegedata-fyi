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

function maybePct(value: number | null, digits = 0): string {
  return formatRate(value, digits);
}

function maybeMultiple(value: number | null): string {
  return value == null || !Number.isFinite(value) ? "n/a" : `${value.toFixed(1)}x`;
}

function important(value: string | null): boolean {
  return value === "Important" || value === "Very Important";
}

function InsightBlock({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="admission-strategy-insight">
      <span>{label}</span>
      <strong className="serif stat-num">{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function FlowRow({
  admitRate,
  admitted,
  applicants,
  enrolled,
  label,
  yieldLabel,
}: {
  admitRate: number | null;
  admitted: number | null;
  applicants: number | null;
  enrolled: number | null;
  label: string;
  yieldLabel: string;
}) {
  return (
    <div className="admission-strategy-flow-row">
      <div className="admission-strategy-flow-row__label meta">{label}</div>
      <div className="admission-strategy-flow-row__cells">
        <div>
          <strong>{maybeCount(applicants)}</strong>
          <small>applicants</small>
        </div>
        <div>
          <strong>{maybeCount(admitted)}</strong>
          <small>admitted · {maybePct(admitRate)}</small>
        </div>
        <div>
          <strong>{maybeCount(enrolled)}</strong>
          <small>{yieldLabel}</small>
        </div>
      </div>
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
  const hasClassModel =
    derived.edAdmitRate != null &&
    derived.edShareOfClass != null &&
    derived.estimatedNonEarlyEnrolled != null;
  const edWidth = derived.edShareOfClass == null
    ? 0
    : Math.max(0, Math.min(100, derived.edShareOfClass * 100));
  const nonEarlyWidth = 100 - edWidth;
  const edClassShareNote =
    school.enrolledFirstYear != null && school.edAdmitted != null
      ? `${maybeCount(school.edAdmitted)} ED admits / ${maybeCount(school.enrolledFirstYear)} enrolled first-years`
      : "Binding-ED estimate";
  const remainingSeatNote =
    school.enrolledFirstYear != null
      ? `of ${maybeCount(school.enrolledFirstYear)} enrolled first-year seats`
      : "after binding-ED assumption";

  return (
    <section className="admission-strategy-card rule-2" aria-labelledby="admission-strategy-title">
      <div className="meta">§ Admission rounds</div>
      <div className="admission-strategy-card__body cd-card cd-card--cut">
        <div className="admission-strategy-card__head">
          <div>
            <h2 id="admission-strategy-title" className="serif admission-strategy-card__title">
              How the class gets assembled.
            </h2>
            <RoundLine school={school} />
          </div>
        </div>

        {showEdSuppressed && (
          <div className="admission-strategy-note admission-strategy-note--warn">
            ED counts for this school could not be reconciled and have been omitted. Other admissions data below.
          </div>
        )}

        {derived.edAdmitRate != null && (
          <div className="admission-strategy-model">
            <div className="admission-strategy-insights">
              {derived.edShareOfClass != null && (
                <InsightBlock
                  label="Estimated ED share of class"
                  value={pct(derived.edShareOfClass)}
                  note={edClassShareNote}
                />
              )}
              {derived.edAdmitRateMultiple != null && (
                <InsightBlock
                  label="ED admit-rate multiple"
                  value={maybeMultiple(derived.edAdmitRateMultiple)}
                  note={`${pct(derived.edAdmitRate)} ED vs ${pct(derived.nonEarlyResidualAdmitRate)} estimated non-ED`}
                />
              )}
              {derived.estimatedNonEarlyEnrolled != null && (
                <InsightBlock
                  label="Seats left outside ED"
                  value={maybeCount(derived.estimatedNonEarlyEnrolled)}
                  note={remainingSeatNote}
                />
              )}
              {derived.nonEarlyResidualAdmitRate != null && (
                <InsightBlock
                  label="Estimated non-ED admit rate"
                  value={pct(derived.nonEarlyResidualAdmitRate)}
                  note={`${maybeCount(derived.nonEarlyAdmitted)} admitted from ${maybeCount(derived.nonEarlyApplicants)} applicants`}
                />
              )}
            </div>

            {hasClassModel && derived.estimatedEdEnrolled != null && (
              <div className="admission-strategy-class-model">
                <div>
                  <div className="meta">§ Enrolled class model</div>
                  <p>
                    Start with the real enrolled class. If binding ED admits enroll,{" "}
                    <strong>{maybeCount(derived.estimatedEdEnrolled)}</strong> of{" "}
                    <strong> {maybeCount(school.enrolledFirstYear)}</strong> first-year
                    seats are already spoken for before the remaining admission rounds
                    fill the class.
                  </p>
                </div>
                <div
                  className="admission-strategy-seatbar"
                  role="img"
                  aria-label={`${maybeCount(derived.estimatedEdEnrolled)} enrolled seats are estimated Early Decision seats; ${maybeCount(derived.estimatedNonEarlyEnrolled)} are estimated seats outside Early Decision.`}
                >
                  <span
                    className="admission-strategy-seatbar__ed"
                    style={{ width: `${edWidth}%` }}
                  >
                    ED {maybeCount(derived.estimatedEdEnrolled)}
                  </span>
                  <span
                    className="admission-strategy-seatbar__regular"
                    style={{ width: `${nonEarlyWidth}%` }}
                  >
                    Non-ED {maybeCount(derived.estimatedNonEarlyEnrolled)}
                  </span>
                </div>
              </div>
            )}

            <div className="admission-strategy-flow" aria-labelledby="admission-strategy-flow-title">
              <div>
                <div id="admission-strategy-flow-title" className="meta">
                  § Applicant paths
                </div>
                <p>
                  Same class, different denominators: applicant pool, admitted pool,
                  then enrolled seats.
                </p>
              </div>
              <div className="admission-strategy-flow-grid">
                <FlowRow
                  label="Early Decision"
                  applicants={school.edApplicants}
                  admitted={school.edAdmitted}
                  admitRate={derived.edAdmitRate}
                  enrolled={derived.estimatedEdEnrolled}
                  yieldLabel="assumed enrolled"
                />
                <FlowRow
                  label="All other rounds"
                  applicants={derived.nonEarlyApplicants}
                  admitted={derived.nonEarlyAdmitted}
                  admitRate={derived.nonEarlyResidualAdmitRate}
                  enrolled={derived.estimatedNonEarlyEnrolled}
                  yieldLabel={`${maybePct(derived.nonEarlyYield)} estimated yield`}
                />
              </div>
              <table className="sr-only">
                <caption>Admission rounds model</caption>
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>Applicants</th>
                    <th>Admitted</th>
                    <th>Admit rate</th>
                    <th>Estimated enrolled</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Early Decision</td>
                    <td>{maybeCount(school.edApplicants)}</td>
                    <td>{maybeCount(school.edAdmitted)}</td>
                    <td>{pct(derived.edAdmitRate)}</td>
                    <td>{maybeCount(derived.estimatedEdEnrolled)}</td>
                  </tr>
                  <tr>
                    <td>All other rounds</td>
                    <td>{maybeCount(derived.nonEarlyApplicants)}</td>
                    <td>{maybeCount(derived.nonEarlyAdmitted)}</td>
                    <td>{pct(derived.nonEarlyResidualAdmitRate)}</td>
                    <td>{maybeCount(derived.estimatedNonEarlyEnrolled)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="admission-strategy-model-notes">
              <div className="admission-strategy-caveat">
                <strong>Binding ED assumption.</strong> The class-share model uses
                ED admits as estimated enrolled ED seats. CDS does not report
                confirmed ED enrollment, so this is a practical proxy rather than
                a separate school-reported count.
              </div>
              {school.yieldRate != null && (
                <div className="admission-strategy-caveat">
                  <strong>Overall yield: {pct(school.yieldRate)}.</strong> Published
                  yield blends high-commitment ED admits with the rest of the
                  admitted pool.
                </div>
              )}
              <div className="admission-strategy-caveat">
                <strong>Read the ED rate carefully.</strong> Published ED rates can
                include recruited athletes, legacy applicants, and institutional-priority
                applicants. The general-pool ED rate can be lower.
              </div>
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

        <div className="admission-strategy-card__source card-source-actions rule mono">
          <span>§ SOURCE: COMMON DATA SET {school.cdsYear} · §C.21 §C.22 §C.2 §C.7 §C.13</span>
          <span>
            <Link href="/methodology/admission-strategy">METHOD →</Link>
          </span>
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
