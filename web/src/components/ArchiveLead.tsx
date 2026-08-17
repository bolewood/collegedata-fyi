import type { ArchiveLead as ArchiveLeadModel, LeadPart } from "@/lib/archive-lead";
import { officialPageLabel } from "@/lib/archive-lead";

function Part({ part }: { part: LeadPart }) {
  if (part.type === "text") return <>{part.text}</>;
  const title =
    part.external && part.href.startsWith("http")
      ? officialPageLabel(part.href)
      : undefined;
  return (
    <a
      href={part.href}
      title={title}
      target={part.external ? "_blank" : undefined}
      rel={part.external ? "noopener noreferrer" : undefined}
    >
      {part.text}
    </a>
  );
}

export function ArchiveLead({
  lead,
  showHeading = true,
}: {
  lead: ArchiveLeadModel;
  showHeading?: boolean;
}) {
  return (
    <div className="cd-archive-lead">
      {showHeading && (
        <h2 className="cd-archive-lead__heading">{lead.heading}</h2>
      )}
      {lead.paragraphs.map((parts, i) => (
        <p key={i}>
          {parts.map((part, j) => (
            <Part key={j} part={part} />
          ))}
        </p>
      ))}
    </div>
  );
}
