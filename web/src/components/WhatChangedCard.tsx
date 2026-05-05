import type { ChangeEventRow, ChangeEventSeverity, ChangeEventType } from "@/lib/types";

type WhatChangedCardProps = {
  events: ChangeEventRow[];
};

function severityLabel(severity: ChangeEventSeverity): string {
  switch (severity) {
    case "major":
      return "Major";
    case "notable":
      return "Notable";
    case "watch":
      return "Watch";
  }
}

function eventTypeLabel(eventType: ChangeEventType): string {
  switch (eventType) {
    case "material_delta":
      return "Changed";
    case "newly_missing":
      return "Newly missing";
    case "newly_reported":
      return "Newly reported";
    case "reappeared":
      return "Reappeared";
    case "format_changed":
      return "Format";
    case "producer_changed":
      return "Extraction";
    case "quality_regression":
      return "Quality";
    case "quality_recovered":
      return "Recovered";
    case "card_quality_changed":
      return "Card quality";
  }
}

function valuePair(event: ChangeEventRow): string | null {
  if (event.eventType === "newly_missing") {
    return event.fromValue ? `${event.fromValue} to not reported` : "No longer reported";
  }
  if (event.eventType === "newly_reported" || event.eventType === "reappeared") {
    return event.toValue ? `not reported to ${event.toValue}` : "Reported again";
  }
  if (event.fromValue != null && event.toValue != null) {
    return `${event.fromValue} to ${event.toValue}`;
  }
  return null;
}

export function WhatChangedCard({ events }: WhatChangedCardProps) {
  if (events.length === 0) return null;

  const latestYear = events[0]?.toYear;
  const visibleEvents = events.slice(0, 5);

  return (
    <section className="what-changed-card rule-2" aria-labelledby="what-changed-title">
      <div className="meta">§ Change intelligence</div>
      <div className="what-changed-card__body cd-card cd-card--cut">
        <div className="what-changed-card__head">
          <div>
            <h2 id="what-changed-title" className="serif what-changed-card__title">
              What changed in the latest CDS.
            </h2>
            <p>
              Source-linked year-over-year changes that have cleared the public
              review gate{latestYear ? ` for ${latestYear}` : ""}.
            </p>
          </div>
          <div className="what-changed-card__count">
            <span className="meta">Published signals</span>
            <strong className="serif stat-num">{visibleEvents.length}</strong>
            <small>Generated from extracted Common Data Set fields.</small>
          </div>
        </div>

        <div className="what-changed-list">
          {visibleEvents.map((event) => {
            const values = valuePair(event);
            return (
              <article key={event.id} className="what-changed-event">
                <div className="what-changed-event__meta mono">
                  <span className={`what-changed-severity what-changed-severity--${event.severity}`}>
                    {severityLabel(event.severity)}
                  </span>
                  <span>{eventTypeLabel(event.eventType)}</span>
                  <span>
                    {event.fromYear} to {event.toYear}
                  </span>
                </div>
                <h3>{event.fieldLabel}</h3>
                <p>{event.summary}</p>
                {values && <div className="what-changed-event__values mono">{values}</div>}
                <div className="what-changed-event__sources mono">
                  {event.fromArchiveUrl ? (
                    <a href={event.fromArchiveUrl} target="_blank" rel="noopener noreferrer">
                      PRIOR SOURCE →
                    </a>
                  ) : null}
                  {event.toArchiveUrl ? (
                    <a href={event.toArchiveUrl} target="_blank" rel="noopener noreferrer">
                      LATEST SOURCE →
                    </a>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>

        <div className="what-changed-card__source card-source-actions rule mono">
          <span>§ SOURCE: COMMON DATA SET YEAR-OVER-YEAR FIELD PROJECTION</span>
        </div>
      </div>
    </section>
  );
}
