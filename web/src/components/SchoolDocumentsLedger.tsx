"use client";

import { useMemo, useState } from "react";
import { DocumentCard } from "./DocumentCard";
import type { ManifestRow } from "@/lib/types";

export type SchoolDocumentGroup = {
  label: string | null;
  docs: ManifestRow[];
};

const COLLAPSED_COUNT = 3;

function yearStart(doc: ManifestRow): number {
  const value = doc.canonical_year ?? doc.cds_year ?? "";
  const parsed = Number.parseInt(value.split("-")[0] ?? "", 10);
  return Number.isFinite(parsed) ? parsed : -1;
}

export function SchoolDocumentsLedger({ groups }: { groups: SchoolDocumentGroup[] }) {
  const [expanded, setExpanded] = useState(false);
  const total = groups.reduce((sum, group) => sum + group.docs.length, 0);
  const collapsedDocs = useMemo(
    () =>
      groups
        .flatMap((group) => group.docs)
        .slice()
        .sort((a, b) => yearStart(b) - yearStart(a))
        .slice(0, COLLAPSED_COUNT),
    [groups],
  );
  const visibleGroups: SchoolDocumentGroup[] =
    expanded || total <= COLLAPSED_COUNT
      ? groups
      : [{ label: null, docs: collapsedDocs }];

  return (
    <div className="school-documents-ledger rule-2">
      <div className="school-documents-ledger__head">
        <div className="meta">
          § CDS archive
          {total > COLLAPSED_COUNT && !expanded ? (
            <span> · latest {COLLAPSED_COUNT} shown</span>
          ) : null}
        </div>
        {total > COLLAPSED_COUNT ? (
          <button
            className="cd-btn cd-btn--ghost school-documents-ledger__toggle"
            type="button"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Show latest 3" : `Show all ${total}`}
          </button>
        ) : null}
      </div>

      {visibleGroups.map((group, gi) => (
        <div key={group.label ?? `documents-${gi}`}>
          {group.label && (
            <h2 className="school-documents-ledger__group-title serif">
              {group.label}
            </h2>
          )}
          {group.docs.map((doc, i) => (
            <DocumentCard
              key={doc.document_id}
              doc={doc}
              isLast={
                gi === visibleGroups.length - 1 && i === group.docs.length - 1
              }
            />
          ))}
        </div>
      ))}
    </div>
  );
}
