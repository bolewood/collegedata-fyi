import type { SchoolFactUnifiedRow } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

type FactGroup = {
  name: string;
  facts: SchoolFactUnifiedRow[];
};

export function FederalBaselineTable({
  facts,
  compact = false,
}: {
  facts: SchoolFactUnifiedRow[];
  compact?: boolean;
}) {
  if (facts.length === 0) return null;

  const groups = groupFacts(facts);
  const releaseLabel = releaseSummary(facts);

  return (
    <section style={{ marginTop: compact ? 36 : 52 }} aria-labelledby="federal-baseline-heading">
      <div className="rule-2" style={{ paddingTop: 18, marginBottom: 18 }}>
        <div className="meta" style={{ marginBottom: 8 }}>
          NCES/IPEDS baseline
        </div>
        <h2
          id="federal-baseline-heading"
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: compact ? 30 : 36,
            lineHeight: 1.05,
            margin: 0,
          }}
        >
          Source-labeled federal facts
        </h2>
        <p style={{ margin: "10px 0 0", maxWidth: 760, color: "var(--ink-2)", lineHeight: 1.55 }}>
          These values come from official NCES/IPEDS tables. They are not Common Data Set fields unless the source note says the alignment is direct or near.
        </p>
        {releaseLabel && (
          <p
            className="mono"
            style={{
              margin: "14px 0 0",
              color: "var(--ink)",
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            {releaseLabel}
          </p>
        )}
      </div>

      {groups.map((group) => (
        <div key={group.name} style={{ marginTop: 24 }}>
          <h3
            className="meta"
            style={{
              margin: "0 0 8px",
              color: "var(--ink)",
              letterSpacing: "0.06em",
            }}
          >
            {group.name}
          </h3>
          <div
            className="cd-reconstructed"
            style={{
              border: "1px solid var(--rule)",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            <div
              className="cd-reconstructed__table-wrap"
              tabIndex={0}
              aria-label={`${group.name} IPEDS baseline facts table. Scroll horizontally to read all columns.`}
              style={{ overflowX: "auto" }}
            >
            <table className="cd-reconstructed__table" style={{ width: "100%", minWidth: 660, borderCollapse: "collapse", fontSize: 14 }}>
              <caption className="sr-only">{group.name} IPEDS baseline facts</caption>
              <thead>
                <tr className="meta" style={{ textAlign: "left", borderBottom: "1px solid var(--rule-strong)" }}>
                  <th style={{ padding: "9px 12px", width: "42%" }}>Fact</th>
                  <th style={{ padding: "9px 12px", width: "18%" }}>Value</th>
                  <th style={{ padding: "9px 12px", width: "40%" }}>Source</th>
                </tr>
              </thead>
              <tbody>
                {group.facts.map((fact) => (
                  <tr key={`${fact.field_key}-${fact.source_table}-${fact.source_variable}`} className="rule">
                    <th scope="row" style={{ padding: "11px 12px", textAlign: "left", fontWeight: 500 }}>
                      {fact.field_label}
                      {fact.population && (
                        <div className="meta" style={{ marginTop: 3, lineHeight: 1.35 }}>
                          {fact.population}
                        </div>
                      )}
                    </th>
                    <td className="nums" style={{ padding: "11px 12px", whiteSpace: "nowrap" }}>
                      {formatFactValue(fact)}
                    </td>
                    <td style={{ padding: "11px 12px" }}>
                      <SourceCell fact={fact} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}

function groupFacts(facts: SchoolFactUnifiedRow[]): FactGroup[] {
  const map = new Map<string, SchoolFactUnifiedRow[]>();
  for (const fact of facts) {
    const group = map.get(fact.display_group) ?? [];
    group.push(fact);
    map.set(fact.display_group, group);
  }
  return Array.from(map, ([name, rows]) => ({ name, facts: rows }));
}

function formatFactValue(fact: SchoolFactUnifiedRow): string {
  if (fact.value_label) return fact.value_label;
  if (fact.unit === "usd" && fact.value_numeric != null) return formatCurrency(fact.value_numeric) ?? String(fact.value_numeric);
  return fact.display_value ?? fact.value_text ?? (fact.value_numeric == null ? "-" : String(fact.value_numeric));
}

function SourceCell({ fact }: { fact: SchoolFactUnifiedRow }) {
  const source = `${fact.source_table}.${fact.source_variable}`;
  const status = statusLabel(fact);
  const definition = definitionLabel(fact.definition_alignment);
  const note = fact.definition_note ? ` ${fact.definition_note}` : "";
  const title = `${source}. Status: ${status}. Definition: ${definition}.${note}`;
  return (
    <span className="federal-source" tabIndex={0} title={title} aria-label={title}>
      <span className="mono" style={{ color: "var(--ink-3)", fontSize: 12 }}>
        {source}
      </span>
      <span className="federal-source__meta" aria-hidden="true">
        <span>Status: {status}</span>
        <span>Definition: {definition}{fact.definition_note ? ` · ${fact.definition_note}` : ""}</span>
      </span>
    </span>
  );
}

function statusLabel(fact: SchoolFactUnifiedRow): string {
  const label = fact.quality_flag === "reported" ? "reported" : fact.quality_flag.replaceAll("_", " ");
  return fact.imputation_label ? `${label} (${fact.imputation_label})` : label;
}

function definitionLabel(value: SchoolFactUnifiedRow["definition_alignment"]): string {
  switch (value) {
    case "direct":
      return "Direct";
    case "near":
      return "Near CDS";
    case "context_only":
      return "Context only";
    case "not_cds_equivalent":
      return "Not CDS-equivalent";
  }
}

function releaseSummary(facts: SchoolFactUnifiedRow[]): string | null {
  const first = facts[0];
  if (!first) return null;
  const releaseType = first.release_type.charAt(0).toUpperCase() + first.release_type.slice(1);
  return `${releaseType} ${first.collection_year} release, data year ${first.data_year}`;
}
