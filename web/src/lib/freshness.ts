import { formatShortDate } from "./format";

export type FreshnessFacts = {
  source_modification_date?: string | null;
  source_creation_date?: string | null;
  source_http_last_modified?: string | null;
  discovered_at?: string | null;
};

export type FreshnessSignal = {
  at: string;
  kind: "embedded_modification" | "embedded_creation" | "http_last_modified" | "discovered_at";
  label: string;
};

const KIND_LABEL: Record<FreshnessSignal["kind"], string> = {
  embedded_modification: "the archived file's embedded modification date",
  embedded_creation: "the archived file's embedded creation date",
  http_last_modified: "the school's HTTP Last-Modified header",
  discovered_at: "when this archive discovered the file",
};

export function pickFreshnessSignal(facts: FreshnessFacts): FreshnessSignal | null {
  if (facts.source_modification_date) {
    return {
      at: facts.source_modification_date,
      kind: "embedded_modification",
      label: KIND_LABEL.embedded_modification,
    };
  }
  if (facts.source_creation_date) {
    return {
      at: facts.source_creation_date,
      kind: "embedded_creation",
      label: KIND_LABEL.embedded_creation,
    };
  }
  if (facts.source_http_last_modified) {
    return {
      at: facts.source_http_last_modified,
      kind: "http_last_modified",
      label: KIND_LABEL.http_last_modified,
    };
  }
  if (facts.discovered_at) {
    return {
      at: facts.discovered_at,
      kind: "discovered_at",
      label: KIND_LABEL.discovered_at,
    };
  }
  return null;
}

export function freshnessSentence(signal: FreshnessSignal | null): string | null {
  if (!signal) return null;
  const when = formatShortDate(signal.at);
  if (signal.kind === "discovered_at") {
    return `This archive discovered the file on ${when}. The school did not send Last-Modified and the file has no embedded date.`;
  }
  return `File date from ${signal.label}: ${when}.`;
}

export function latestDocumentFreshness<T extends FreshnessFacts & { canonical_year?: string | null }>(
  documents: T[],
): FreshnessSignal | null {
  const sorted = [...documents].sort((a, b) =>
    (b.canonical_year ?? "").localeCompare(a.canonical_year ?? ""),
  );
  for (const doc of sorted) {
    const signal = pickFreshnessSignal(doc);
    if (signal) return signal;
  }
  return null;
}
