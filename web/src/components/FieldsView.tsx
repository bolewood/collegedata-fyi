import type { FieldValue } from "@/lib/types";
import { FIELD_LABELS } from "@/lib/labels";
import { groupBySection, type SubsectionGroup } from "@/lib/sections";
import { formatFieldValue } from "@/lib/format";
import {
  buildReconstructedTables,
  type ReconstructedTable,
} from "@/lib/reconstructed-tables";

// FieldsView — textbook-gutter layout. Sticky section/subsection index on
// the left, KV groups on the right. Each subsection renders the extracted
// fields as a label/value list with dashed rules between rows. High-value
// subsections can render reconstructed CDS-shaped tables first, while keeping
// the KV rows as the fallback for unsupported or long-tail fields.
export function FieldsView({
  values,
  totalFields,
}: {
  values: Record<string, FieldValue>;
  totalFields?: number;
}) {
  const sections = groupBySection(values);
  const totalExtracted = Object.keys(values).length;

  return (
    <div className="cd-fields">
      <ProvenanceNote
        totalExtracted={totalExtracted}
        totalKnown={totalFields}
      />

      <div className="cd-fields__layout">
        <aside className="cd-fields__gutter">
          <div className="cd-fields__gutter-sticky">
            <div className="meta" style={{ marginBottom: 12 }}>
              § Index
            </div>
            {sections.map((sec) => (
              <div
                key={sec.letter}
                style={{ marginBottom: 16 }}
              >
                <a
                  href={`#sec-${sec.letter}`}
                  className="cd-fields__gutter-section"
                >
                  <span className="cd-fields__gutter-letter">
                    §{sec.letter}
                  </span>
                  <span>{sec.name}</span>
                </a>
                {sec.subsections.map((sub) => (
                  <a
                    key={sub.slug}
                    href={`#sub-${sub.slug}`}
                    className="cd-fields__gutter-sub"
                  >
                    {sub.code ? `${sub.code} · ` : ""}
                    {sub.name}
                  </a>
                ))}
              </div>
            ))}
          </div>
        </aside>

        <div className="cd-fields__body">
          {sections.map((sec) => (
            <section
              key={sec.letter}
              id={`sec-${sec.letter}`}
              style={{ marginBottom: 36, scrollMarginTop: 24 }}
            >
              <header
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 16,
                  borderBottom: "1px solid var(--rule-strong)",
                  paddingBottom: 8,
                  marginBottom: 16,
                }}
              >
                <h2
                  className="serif"
                  style={{
                    fontWeight: 400,
                    fontSize: 24,
                    margin: 0,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {sec.name}
                </h2>
                <span
                  className="mono"
                  style={{
                    fontSize: 11,
                    color: "var(--ink-3)",
                    marginLeft: "auto",
                    letterSpacing: "0.05em",
                  }}
                >
                  {sec.subsections.length} TABLE
                  {sec.subsections.length === 1 ? "" : "S"}
                </span>
              </header>
              {sec.subsections.map((sub) => (
                <SubsectionBlock key={sub.slug} sub={sub} />
              ))}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

function SubsectionBlock({ sub }: { sub: SubsectionGroup }) {
  const subsectionValues = Object.fromEntries(
    sub.fields.map(({ id, field }) => [id, field]),
  );
  const reconstructedTables = buildReconstructedTables(subsectionValues);
  const reconstructedIds = new Set(
    reconstructedTables.flatMap((table) => table.usedFieldIds),
  );
  const fallbackFields = sub.fields.filter(({ id }) => !reconstructedIds.has(id));

  return (
    <div
      id={`sub-${sub.slug}`}
      style={{ marginBottom: 24, scrollMarginTop: 24 }}
    >
      <div className="meta" style={{ marginBottom: 6 }}>
        {sub.code ? `${sub.code} · ` : ""}
        {sub.name}
      </div>
      {reconstructedTables.map((table) => (
        <ReconstructedTableView key={table.key} table={table} />
      ))}
      {fallbackFields.length > 0 && (
        <div style={{ marginTop: reconstructedTables.length > 0 ? 14 : 0 }}>
          {reconstructedTables.length > 0 && (
            <div className="meta" style={{ marginBottom: 6 }}>
              Other extracted fields
            </div>
          )}
          <KVRows fields={fallbackFields} />
        </div>
      )}
    </div>
  );
}

function ReconstructedTableView({ table }: { table: ReconstructedTable }) {
  return (
    <div
      className="cd-reconstructed"
      style={{
        marginBottom: 14,
        border: "1px solid var(--rule)",
        borderRadius: 8,
        minWidth: 0,
        width: "100%",
        maxWidth: "100%",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "10px 12px",
          borderBottom: "1px solid var(--rule)",
        }}
      >
        <div
          className="serif"
          style={{
            fontSize: 18,
            color: "var(--ink)",
            marginBottom: 2,
          }}
        >
          {table.title}
        </div>
        <div
          style={{
            color: "var(--ink-2)",
            fontSize: 13,
            lineHeight: 1.45,
            maxWidth: "100%",
            overflowWrap: "anywhere",
          }}
        >
          {table.caption}
        </div>
      </div>
      <div
        className="cd-reconstructed__table-wrap"
        style={{
          overflowX: "auto",
          width: "100%",
          maxWidth: "100%",
          minWidth: 0,
        }}
      >
        <table
          className="cd-reconstructed__table nums"
          style={{
            width: "100%",
            minWidth: table.columns.length >= 5 ? 760 : 620,
            borderCollapse: "collapse",
            fontSize: 13.5,
          }}
        >
          <caption
            style={{
              position: "absolute",
              width: 1,
              height: 1,
              padding: 0,
              margin: -1,
              overflow: "hidden",
              clip: "rect(0, 0, 0, 0)",
              whiteSpace: "nowrap",
              border: 0,
            }}
          >
            {table.title}. {table.caption}
          </caption>
          <thead>
            <tr>
              <th
                scope="col"
                style={{
                  textAlign: "left",
                  padding: "9px 12px",
                  color: "var(--ink-2)",
                  borderBottom: "1px solid var(--rule)",
                  fontWeight: 600,
                  whiteSpace: "normal",
                }}
              >
                Measure
              </th>
              {table.columns.map((column) => (
                <th
                  key={column}
                  scope="col"
                  style={{
                    textAlign: "right",
                    padding: "9px 12px",
                    color: "var(--ink-2)",
                    borderBottom: "1px solid var(--rule)",
                    fontWeight: 600,
                    whiteSpace: "normal",
                  }}
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr key={row.key}>
                <th
                  scope="row"
                  style={{
                    textAlign: "left",
                    padding: "9px 12px",
                    color: "var(--ink-2)",
                    borderBottom: "1px dashed var(--rule)",
                    fontWeight: 500,
                    width: "28%",
                  }}
                >
                  {row.label}
                </th>
                {row.cells.map((cell, i) => (
                  <td
                    key={`${row.key}-${cell.fieldId ?? i}`}
                    style={{
                      textAlign: "right",
                      padding: "9px 12px",
                      color: cell.missing ? "var(--ink-4)" : "var(--ink)",
                      borderBottom: "1px dashed var(--rule)",
                      fontWeight: cell.missing ? 400 : 500,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {cell.display}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KVRows({ fields }: { fields: SubsectionGroup["fields"] }) {
  return (
    <div>
      {fields.map(({ id, field }, i) => {
        const labelMeta = FIELD_LABELS[id];
        const label =
          field.question?.trim() || labelMeta?.label?.trim() || id;
        const valueType = field.value_type ?? labelMeta?.valueType;
        const raw = field.value_decoded ?? field.value;
        const display = formatFieldValue(raw, valueType);
        const missing =
          display === "" ||
          display === "—" ||
          display.toLowerCase().includes("not provided");
        return (
          <div
            key={id}
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)",
              gap: 16,
              padding: "8px 10px",
              borderBottom:
                i === fields.length - 1
                  ? "none"
                  : "1px dashed var(--rule)",
              fontSize: 13.5,
              alignItems: "baseline",
            }}
          >
            <span
              style={{
                color: "var(--ink-2)",
                lineHeight: 1.45,
                minWidth: 0,
              }}
            >
              {label}
            </span>
            <span
              className="nums"
              style={{
                color: missing ? "var(--ink-4)" : "var(--ink)",
                fontWeight: missing ? 400 : 500,
                textAlign: "right",
                fontVariantNumeric: "tabular-nums",
                overflowWrap: "anywhere",
                minWidth: 0,
                maxWidth: "100%",
              }}
            >
              {display || "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ProvenanceNote({
  totalExtracted,
  totalKnown,
}: {
  totalExtracted: number;
  totalKnown?: number;
}) {
  return (
    <div
      className="cd-card"
      style={{
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        fontSize: 13,
        flexWrap: "wrap",
      }}
    >
      <span className="meta" style={{ color: "var(--forest)" }}>
        § Extraction
      </span>
      <span className="serif stat-num" style={{ fontSize: 18 }}>
        {totalExtracted.toLocaleString("en-US")}
        {totalKnown != null && (
          <>
            {" "}
            <span style={{ color: "var(--ink-3)" }}>
              of ~{totalKnown.toLocaleString("en-US")}
            </span>
          </>
        )}
      </span>
      <span style={{ color: "var(--ink-2)" }}>
        field{totalExtracted === 1 ? "" : "s"} parsed from this CDS.
      </span>
    </div>
  );
}
