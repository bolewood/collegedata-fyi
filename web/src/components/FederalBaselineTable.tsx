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
          These values come from official NCES/IPEDS tables. They are not Common Data Set fields unless the definition column says the alignment is direct or near.
        </p>
        {releaseLabel && (
          <p className="meta" style={{ margin: "8px 0 0", color: "var(--ink-3)" }}>
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
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", minWidth: 720, borderCollapse: "collapse", fontSize: 14 }}>
              <caption className="sr-only">{group.name} IPEDS baseline facts</caption>
              <thead>
                <tr className="meta" style={{ textAlign: "left", borderBottom: "1px solid var(--rule-strong)" }}>
                  <th style={{ padding: "8px 10px 8px 0", width: "28%" }}>Fact</th>
                  <th style={{ padding: "8px 10px" }}>Value</th>
                  <th style={{ padding: "8px 10px" }}>Status</th>
                  <th style={{ padding: "8px 10px" }}>Definition</th>
                  <th style={{ padding: "8px 0 8px 10px" }}>Source</th>
                </tr>
              </thead>
              <tbody>
                {group.facts.map((fact) => (
                  <tr key={`${fact.field_key}-${fact.source_table}-${fact.source_variable}`} className="rule">
                    <th scope="row" style={{ padding: "11px 10px 11px 0", textAlign: "left", fontWeight: 500 }}>
                      {fact.field_label}
                      {fact.population && (
                        <div className="meta" style={{ marginTop: 3, lineHeight: 1.35 }}>
                          {fact.population}
                        </div>
                      )}
                    </th>
                    <td className="nums" style={{ padding: "11px 10px", whiteSpace: "nowrap" }}>
                      {formatFactValue(fact)}
                    </td>
                    <td style={{ padding: "11px 10px" }}>
                      <StatusBadge fact={fact} />
                    </td>
                    <td style={{ padding: "11px 10px", color: "var(--ink-2)" }}>
                      {definitionLabel(fact.definition_alignment)}
                      {fact.definition_note && (
                        <div className="meta" style={{ marginTop: 4, lineHeight: 1.35 }}>
                          {fact.definition_note}
                        </div>
                      )}
                    </td>
                    <td className="mono" style={{ padding: "11px 0 11px 10px", color: "var(--ink-3)", fontSize: 12 }}>
                      {fact.source_table}.{fact.source_variable}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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

function StatusBadge({ fact }: { fact: SchoolFactUnifiedRow }) {
  const label = fact.quality_flag === "reported" ? "reported" : fact.quality_flag.replaceAll("_", " ");
  const title = fact.imputation_label ?? label;
  return (
    <span className={fact.quality_flag === "imputed" ? "cd-chip" : "meta"} title={title}>
      {label}
    </span>
  );
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

