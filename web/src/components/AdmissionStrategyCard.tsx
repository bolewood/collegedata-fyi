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

function shareOf(value: number | null, total: number): number {
  if (value == null || value <= 0 || total <= 0) return 0;
  return Math.max(0, Math.min(100, (value / total) * 100));
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

type FlowLane = {
  label: string;
  tone: "ed" | "other" | "single";
  applicants: number | null;
  admitted: number | null;
  enrolled: number | null;
  admitRate: number | null;
  yieldLabel: string;
};

function FlowCell({
  label,
  value,
  width,
  rate,
  tone,
}: {
  label: string;
  value: number | null;
  width: number;
  rate: string;
  tone: FlowLane["tone"];
}) {
  const cssWidth = `${width}%`;
  return (
    <div className="admission-strategy-flow-cell">
      <span className="admission-strategy-flow-cell__stage">{label}</span>
      <strong>{maybeCount(value)}</strong>
      <span>{rate}</span>
      <div className="admission-strategy-flow-cell__track" aria-hidden="true">
        <i
          className={`admission-strategy-flow-cell__bar admission-strategy-flow-cell__bar--${tone}`}
          style={{ width: cssWidth }}
        />
      </div>
    </div>
  );
}

function AdjustedFlow({
  description,
  lanes,
  titleId,
}: {
  description: string;
  lanes: FlowLane[];
  titleId: string;
}) {
  const applicantTotal = lanes.reduce((sum, lane) => sum + (lane.applicants ?? 0), 0);
  const admittedTotal = lanes.reduce((sum, lane) => sum + (lane.admitted ?? 0), 0);
  const enrolledTotal = lanes.reduce((sum, lane) => sum + (lane.enrolled ?? 0), 0);

  return (
    <div className="admission-strategy-flow" aria-labelledby={titleId}>
      <div>
        <div id={titleId} className="meta">
          § Adjusted admission flow
        </div>
        <p>{description}</p>
        <p className="admission-strategy-flow__scale-note">
          Each column is scaled within that stage. Labels show exact counts.
        </p>
      </div>
      <div className="admission-strategy-flow-matrix">
        <div className="admission-strategy-flow-matrix__head" aria-hidden="true">
          <span />
          <span>Applicants</span>
          <span>Admits</span>
          <span>Class seats</span>
        </div>
        {lanes.map((lane) => (
          <div className="admission-strategy-flow-lane" key={lane.label}>
            <div className="admission-strategy-flow-lane__label meta">{lane.label}</div>
            <div className="admission-strategy-flow-lane__cells">
              <FlowCell
                label="Applicants"
                value={lane.applicants}
                width={shareOf(lane.applicants, applicantTotal)}
                rate="reported count"
                tone={lane.tone}
              />
              <FlowCell
                label="Admits"
                value={lane.admitted}
                width={shareOf(lane.admitted, admittedTotal)}
                rate={maybePct(lane.admitRate)}
                tone={lane.tone}
              />
              <FlowCell
                label="Class seats"
                value={lane.enrolled}
                width={shareOf(lane.enrolled, enrolledTotal)}
                rate={lane.yieldLabel}
                tone={lane.tone}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DataTable({
  rows,
}: {
  rows: Array<{
    label: string;
    applicants: string;
    admitted: string;
    admitRate: string;
    enrolled: string;
    note: string;
  }>;
}) {
  return (
    <details className="admission-strategy-data">
      <summary>Exact admission data</summary>
      <div className="admission-strategy-data__wrap">
        <table>
          <caption className="sr-only">Admission flow data</caption>
          <thead>
            <tr>
              <th>Path</th>
              <th>Applicants</th>
              <th>Admitted</th>
              <th>Admit rate</th>
              <th>Class seats</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>{row.applicants}</td>
                <td>{row.admitted}</td>
                <td>{row.admitRate}</td>
                <td>{row.enrolled}</td>
                <td>{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function WaitListStage({
  label,
  value,
  width,
}: {
  label: string;
  value: number | null;
  width: number;
}) {
  return (
    <div className="admission-strategy-wait-stage">
      <div>
        <span>{label}</span>
        <strong>{maybeCount(value)}</strong>
      </div>
      <div className="admission-strategy-wait-stage__track" aria-hidden="true">
        <i style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function WaitListView({
  accepted,
  admitted,
  anomalous,
  offerRate,
  offered,
  optInRate,
  admitRate,
  policyMissingCounts,
  sourceHref,
}: {
  accepted: number | null;
  admitted: number | null;
  anomalous: boolean;
  offerRate: number | null;
  offered: number | null;
  optInRate: number | null;
  admitRate: number | null;
  policyMissingCounts: boolean;
  sourceHref: string | null;
}) {
  const max = Math.max(offered ?? 0, accepted ?? 0, admitted ?? 0);

  return (
    <div className="admission-strategy-panel admission-strategy-panel--wide">
      <div className="admission-strategy-panel__head">
        <div className="meta">§ Wait list attrition</div>
        {anomalous && <span className="cd-chip cd-chip--brick">Review flagged</span>}
      </div>
      {policyMissingCounts ? (
        <p>Wait-list policy reported, counts unavailable.</p>
      ) : (
        <>
          <div className="admission-strategy-wait" role="img" aria-label={`Wait-list flow: ${maybeCount(offered)} offered a place, ${maybeCount(accepted)} accepted a place, ${maybeCount(admitted)} admitted from the wait list.`}>
            <WaitListStage
              label="Offered a spot"
              value={offered}
              width={shareOf(offered, max)}
            />
            <WaitListStage
              label="Accepted a spot"
              value={accepted}
              width={shareOf(accepted, max)}
            />
            <WaitListStage
              label="Admitted from wait list"
              value={admitted}
              width={shareOf(admitted, max)}
            />
          </div>
          <p>
            {anomalous
              ? "The reported wait-list counts do not follow the usual offered to accepted to admitted order, so rates are withheld pending review."
              : `${maybePct(optInRate)} joined after being offered a spot. ${maybePct(admitRate)} of students who joined were admitted.`}
            {offerRate != null ? ` ${maybePct(offerRate)} of applicants were offered the wait list.` : ""}
          </p>
          {admitted === 0 && (
            <p className="admission-strategy-zero-note">
              Zero students were reported as admitted from the wait list.
            </p>
          )}
          <details className="admission-strategy-data">
            <summary>Exact wait-list data</summary>
            <div className="admission-strategy-data__wrap">
              <table>
                <caption className="sr-only">Wait-list data</caption>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Offered a wait-list spot</td>
                    <td>{maybeCount(offered)}</td>
                  </tr>
                  <tr>
                    <td>Accepted a wait-list spot</td>
                    <td>{maybeCount(accepted)}</td>
                  </tr>
                  <tr>
                    <td>Admitted from wait list</td>
                    <td>{maybeCount(admitted)}</td>
                  </tr>
                  <tr>
                    <td>Joined after being offered</td>
                    <td>{maybePct(optInRate)}</td>
                  </tr>
                  <tr>
                    <td>Admitted after joining</td>
                    <td>{maybePct(admitRate)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
      <p className="admission-strategy-caution">
        Wait-list outcomes can change sharply year to year.
        {anomalous && sourceHref ? (
          <>
            {" "}
            <a href={sourceHref} target="_blank" rel="noopener noreferrer">
              Check the source.
            </a>
          </>
        ) : null}
      </p>
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
  const showWaitList =
    (school.waitListPolicy === true ||
      derived.waitListHasAnyCount ||
      derived.waitListCountsMissing);
  const showAppFee = school.appFeeAmount != null || school.appFeeWaiverOffered != null;
  const showFlow = derived.hasEdFlow || derived.hasSingleApplicantFlow;
  const edClassShareNote =
    school.enrolledFirstYear != null && school.edAdmitted != null
      ? `${maybeCount(school.edAdmitted)} ED admits / ${maybeCount(school.enrolledFirstYear)} enrolled first-years`
      : "Binding-ED estimate";
  const remainingSeatNote =
    school.enrolledFirstYear != null
      ? `of ${maybeCount(school.enrolledFirstYear)} enrolled first-year seats`
      : "after binding-ED assumption";
  const flowLanes: FlowLane[] = derived.hasEdFlow
    ? [
        {
          label: "Early Decision",
          tone: "ed",
          applicants: school.edApplicants,
          admitted: school.edAdmitted,
          admitRate: derived.edAdmitRate,
          enrolled: derived.estimatedEdEnrolled,
          yieldLabel: "assumes ED admits enroll",
        },
        {
          label: "All other rounds",
          tone: "other",
          applicants: derived.nonEarlyApplicants,
          admitted: derived.nonEarlyAdmitted,
          admitRate: derived.nonEarlyResidualAdmitRate,
          enrolled: derived.estimatedNonEarlyEnrolled,
          yieldLabel: `${maybePct(derived.nonEarlyYield)} estimated yield`,
        },
      ]
    : derived.hasSingleApplicantFlow
      ? [
          {
            label: "All applicants",
            tone: "single",
            applicants: school.applied,
            admitted: school.admitted,
            admitRate: school.acceptanceRate,
            enrolled: school.enrolledFirstYear,
            yieldLabel: `${maybePct(school.yieldRate)} yield`,
          },
        ]
      : [];
  const flowDescription = derived.hasEdFlow
    ? "Applicants, admits, and class seats use separate stage scales so Early Decision and all other rounds stay readable."
    : "This school does not report an Early Decision lane, so the flow collapses to the school-reported applicant, admit, and enrolled totals.";
  const flowDataRows = flowLanes.map((lane) => ({
    label: lane.label,
    applicants: maybeCount(lane.applicants),
    admitted: maybeCount(lane.admitted),
    admitRate: maybePct(lane.admitRate),
    enrolled: maybeCount(lane.enrolled),
    note:
      lane.tone === "ed"
        ? "Likely class seats assume ED admits enroll."
        : lane.tone === "other"
          ? "All other rounds are residual CDS totals, not exact Regular Decision."
      : "School-reported totals.",
  }));
  const sectionId = `admission-strategy-${school.schoolId}-${school.cdsYear
    .replace(/[^a-z0-9]+/gi, "-")
    .toLowerCase()}`;
  const titleId = `${sectionId}-title`;
  const flowTitleId = `${sectionId}-flow-title`;

  return (
    <section className="admission-strategy-card rule-2" aria-labelledby={titleId}>
      <div className="meta">§ Admission rounds</div>
      <div className="admission-strategy-card__body cd-card cd-card--cut">
        <div className="admission-strategy-card__head">
          <div>
            <h2 id={titleId} className="serif admission-strategy-card__title">
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

        {(showFlow || derived.edAdmitRate != null) && (
          <div className="admission-strategy-model">
            {derived.edAdmitRate != null && (
              <div className="admission-strategy-insights">
                {derived.edShareOfClass != null && (
                  <InsightBlock
                    label="Likely ED share of class"
                    value={pct(derived.edShareOfClass)}
                    note={edClassShareNote}
                  />
                )}
                {derived.edAdmitRateMultiple != null && (
                  <InsightBlock
                    label="ED admit-rate multiple"
                    value={maybeMultiple(derived.edAdmitRateMultiple)}
                    note={`${pct(derived.edAdmitRate)} ED vs ${pct(derived.nonEarlyResidualAdmitRate)} all other rounds`}
                  />
                )}
                {derived.estimatedNonEarlyEnrolled != null && (
                  <InsightBlock
                    label="Seats left after ED"
                    value={maybeCount(derived.estimatedNonEarlyEnrolled)}
                    note={remainingSeatNote}
                  />
                )}
                {derived.nonEarlyResidualAdmitRate != null && (
                  <InsightBlock
                    label="All-other admit rate"
                    value={pct(derived.nonEarlyResidualAdmitRate)}
                    note={`${maybeCount(derived.nonEarlyAdmitted)} admitted from ${maybeCount(derived.nonEarlyApplicants)} applicants`}
                  />
                )}
              </div>
            )}

            {showFlow && (
              <>
                <AdjustedFlow
                  description={flowDescription}
                  lanes={flowLanes}
                  titleId={flowTitleId}
                />
                <DataTable rows={flowDataRows} />
              </>
            )}

            <div className="admission-strategy-model-notes">
              {derived.hasEdFlow && (
                <div className="admission-strategy-caveat">
                  <strong>Class-seat estimate assumes ED admits enroll.</strong> CDS
                  does not report confirmed ED enrollment, so likely ED class seats
                  are calculated as the smaller of ED admits and enrolled first-years.
                </div>
              )}
              {school.yieldRate != null && (
                <div className="admission-strategy-caveat">
                  <strong>Overall yield: {pct(school.yieldRate)}.</strong> Published
                  yield blends high-commitment ED admits with the rest of the
                  admitted pool.
                </div>
              )}
              {derived.edAdmitRate != null && (
                <div className="admission-strategy-caveat">
                  <strong>Read the ED rate carefully.</strong> Published ED rates can
                  include recruited athletes, legacy applicants, and institutional-priority
                  applicants. The general-pool ED rate can be lower.
                </div>
              )}
            </div>
          </div>
        )}

        <div className="admission-strategy-grid">
          {showWaitList && (
            <WaitListView
              accepted={school.waitListAccepted}
              admitted={school.waitListAdmitted}
              anomalous={derived.waitListCountsAnomalous}
              offerRate={derived.waitListOfferRate}
              offered={school.waitListOffered}
              optInRate={derived.waitListOptInRate}
              admitRate={derived.waitListConditionalAdmitRate}
              policyMissingCounts={derived.waitListCountsMissing}
              sourceHref={sourceHref}
            />
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
