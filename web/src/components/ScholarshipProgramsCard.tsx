import Link from "next/link";
import { externalLinkRel } from "@/lib/client-info";
import {
  SCHOLARSHIP_CORRECTION_URL,
  SCHOLARSHIP_LICENSE_LINE,
  applicationLines,
  authorityLine,
  awardCountLines,
  consideredLines,
  coverageSummary,
  deadlineLine,
  freshnessLine,
  otherDateLines,
  otherInfoItems,
  relatedItems,
  renewalSummary,
  residencyLine,
  sourceLabel,
  stackingLines,
  statusChip,
  type ScholarshipDirectoryRow,
} from "@/lib/scholarships";

type Props = {
  programs: ScholarshipDirectoryRow[];
  /** School id to display name, for the other schools in a joint program. */
  names: Record<string, string>;
  /** The CDS year the merit card above describes, when that card is shown. */
  cdsYear?: string | null;
  schoolId: string;
  /** YYYY-MM-DD; a date before this reads as past. Injected so tests and renders agree. */
  today?: string;
};

function Offers({ row }: { row: ScholarshipDirectoryRow }) {
  const multi = row.offers.length > 1;
  if (row.offers.length === 0) {
    return <p className="sch-line">Benefits not documented for this program.</p>;
  }
  return (
    <div className="sch-offers">
      {row.offers.map((offer) => {
        const summary = coverageSummary(offer, row.offers, row.evidence);
        const considered = consideredLines(offer);
        const residency = residencyLine(offer);
        return (
          <div key={offer.offer_id} className="sch-offer">
            {multi && summary.variantName ? (
              <h4 className="sch-offer__name serif">{summary.variantName}</h4>
            ) : null}
            <div className="meta">§ What it covers</div>
            {summary.parentName ? (
              <p className="sch-line sch-line--muted">Includes everything in {summary.parentName}, plus:</p>
            ) : null}
            {summary.benefits.length === 0 ? (
              <p className="sch-line">Benefits not documented for this offer.</p>
            ) : (
              <ul className="sch-list">
                {summary.benefits.map((b, i) => (
                  <li key={i} className="sch-line">
                    <strong>{b.label}:</strong> {b.text}
                    {b.quotedLabel ? <> The school calls it “{b.quotedLabel}”.</> : null}
                    {b.scope ? <span className="sch-scope"> {b.scope}</span> : null}
                  </li>
                ))}
              </ul>
            )}
            {summary.quotedTotals.map((t, i) => (
              <p key={i} className="sch-line sch-quote">
                As the school quotes the total: “{t.quote}”
                {t.scope ? <> ({t.scope})</> : null}. Not added up by Quadfile.
              </p>
            ))}
            <div className="meta sch-gap">§ How you are considered</div>
            <ul className="sch-list">
              {considered.map((line) => (
                <li key={line} className="sch-line">{line}</li>
              ))}
              {residency ? <li className="sch-line">{residency}</li> : null}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function Program({
  row,
  names,
  schoolId,
  today,
  namesById,
}: {
  row: ScholarshipDirectoryRow;
  names: Record<string, string>;
  schoolId: string;
  today: string;
  namesById: Record<string, string>;
}) {
  const fresh = freshnessLine(row);
  const deadline = deadlineLine(row, today);
  const renewal = renewalSummary(row.renewal_rules);
  const stacking = stackingLines(row.stacking_rules);
  const counts = awardCountLines(row.award_counts);
  const appLines = applicationLines(row.application);
  const status = statusChip(row);
  const closed = (row.program_status_for_entry ?? row.program_status) === "closed_to_new_entrants";
  const authority = authorityLine(row.awarding_authority);
  const related = relatedItems(row, namesById);
  const others = row.participating_school_ids.filter((id) => id !== schoolId);
  const otherInfo = otherInfoItems(row.other_info, row.sources);
  const hasTerms = row.offers.some((o) => (o.benefits ?? []).length > 0);

  return (
    <article className="sch-program" id={`scholarship-${row.program_id}`}>
      <header className="sch-program__head">
        <h3 className="serif sch-program__name">{row.official_name}</h3>
        {status ? <span className="cd-chip">{status}</span> : null}
      </header>
      {closed ? (
        <p className="sch-line">
          The school’s page lists this program as closed to new entrants.{" "}
          {hasTerms ? " Terms below are kept for reference." : ""}
        </p>
      ) : null}
      {others.length > 0 ? (
        <p className="sch-line sch-line--muted">
          Part of a shared program with{" "}
          {others.map((id, i) => (
            <span key={id}>
              {i > 0 ? ", " : ""}
              <Link href={`/schools/${id}`}>{names[id] ?? id}</Link>
            </span>
          ))}
          .
        </p>
      ) : null}
      {authority ? <p className="sch-line sch-line--muted">{authority}</p> : null}
      {related.length > 0 ? (
        <ul className="sch-list sch-list--muted">
          {related.map((r) => (
            <li key={`${r.lead}-${r.programId}`} className="sch-line">
              {r.lead}{" "}
              {r.onPage ? <a href={`#scholarship-${r.programId}`}>{r.name}</a> : r.name}
            </li>
          ))}
        </ul>
      ) : null}

      {closed && !hasTerms ? (
        <p className="sch-line">No award terms listed for new entrants.</p>
      ) : (
        <Offers row={row} />
      )}

      <div className="sch-grid">
        <div className="sch-panel">
          <div className="meta">§ Deadline</div>
          <p className={`sch-line${deadline.past ? " sch-line--amber" : ""}`}>{deadline.text}</p>
          {deadline.past ? <p className="sch-line sch-line--amber">Past. Check the official page for the next cycle.</p> : null}
          {otherDateLines(row.application).map((line) => (
            <p key={line} className="sch-line sch-line--muted">{line}</p>
          ))}
          {appLines.map((line) => (
            <p key={line} className="sch-line">{line}</p>
          ))}
        </div>
        <div className="sch-panel">
          <div className="meta">§ Renewal</div>
          {renewal.map((line) => (
            <p key={line} className="sch-line">{line}</p>
          ))}
          {stacking.map((line) => (
            <p key={line} className="sch-line">{line}</p>
          ))}
        </div>
      </div>

      {otherInfo.length > 0 ? (
        <div className="sch-panel">
          <div className="meta">§ Other info</div>
          {otherInfo.map((item, i) => (
            <p key={i} className="sch-line">
              {item.text}
              {item.url ? (
                <>
                  {" "}
                  <a
                    href={item.url}
                    target="_blank"
                    rel={externalLinkRel(item.url)}
                    aria-label={`${row.official_name}, note ${i + 1}: ${(item.label ?? "").replace(" ↗", "")} (opens in a new tab)`}
                  >
                    {item.label}
                  </a>
                </>
              ) : null}
            </p>
          ))}
        </div>
      ) : null}

      {counts.length > 0 ? (
        <div className="sch-panel">
          <div className="meta">§ Counts the school published</div>
          {counts.map((line) => (
            <p key={line} className="sch-line">{line}</p>
          ))}
        </div>
      ) : null}

      <div className={`sch-note${fresh.tone === "amber" ? " sch-note--amber" : ""}`}>
        <p className="sch-line">{fresh.text}</p>
        <p className="sch-links mono">
          {row.sources.map((s) => (
            <a
              key={s.source_id}
              href={s.url}
              target="_blank"
              rel={externalLinkRel(s.url)}
              aria-label={`${row.official_name}: ${sourceLabel(s.authority).replace(" ↗", "")} (opens in a new tab)`}
            >
              {sourceLabel(s.authority)}
            </a>
          ))}{" "}
          <span>Confirm on the official page</span>
          <a href={SCHOLARSHIP_CORRECTION_URL} target="_blank" rel={externalLinkRel(SCHOLARSHIP_CORRECTION_URL)}>
            Report an update
          </a>
        </p>
      </div>
    </article>
  );
}

export function ScholarshipProgramsCard({ programs, names, cdsYear, schoolId, today }: Props) {
  // No rows, no card: a blank card on thousands of pages would read as "this school has none".
  if (programs.length === 0) return null;
  const todayIso = today ?? new Date().toISOString().slice(0, 10);
  const namesById: Record<string, string> = {};
  for (const p of programs) namesById[p.program_id] = p.official_name;

  return (
    <section id="scholarships" className="sch-card rule-2" aria-labelledby="scholarships-title">
      <div className="meta">§ Named scholarship programs</div>
      <div className="sch-card__body cd-card cd-card--cut">
        <div className="sch-card__head">
          <h2 id="scholarships-title" className="serif sch-card__title">
            Programs this school publishes, <span style={{ fontStyle: "italic" }}>as it published them.</span>
          </h2>
          <span className="cd-chip">
            {programs.length} {programs.length === 1 ? "program" : "programs"}
          </span>
        </div>
        <p className="sch-lede">
          {cdsYear
            ? `School-wide CDS figures above describe ${cdsYear}. The programs below are documented separately, each with its own terms and date, and are not an estimate of any student's award.`
            : "The programs below are documented separately from the school's Common Data Set figures, each with its own terms and date. They are not an estimate of any student's award."}
        </p>

        {programs.map((row) => (
          <Program
            key={`${row.program_id}-${row.school_id}`}
            row={row}
            names={names}
            schoolId={schoolId}
            today={todayIso}
            namesById={namesById}
          />
        ))}

        <div className="sch-card__source card-source-actions rule mono">
          <span>§ SOURCE: THE SCHOOL’S OWN PAGES</span>
          <span>
            <Link href="/methodology/scholarships">METHOD →</Link>
          </span>
          <span>
            <Link href="/scholarships">ALL SCHOLARSHIP PROGRAMS →</Link>
          </span>
          <span>
            {SCHOLARSHIP_LICENSE_LINE.replace(" how to cite", "")}{" "}
            <Link href="/methodology/scholarships#reuse">how to cite</Link>
          </span>
        </div>
      </div>
    </section>
  );
}
