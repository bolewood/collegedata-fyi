import type { FieldValue } from "@/lib/types";
import { FIELD_LABELS } from "@/lib/labels";
import { groupBySection, type SubsectionGroup } from "@/lib/sections";
import { formatFieldValue } from "@/lib/format";

// FieldsView — textbook-gutter layout. Sticky section/subsection index on
// the left, KV groups on the right. Each subsection renders the extracted
// fields as a label/value list with dashed rules between rows; future work
// can swap in reconstructed CDS tables for select subsections (B1, C9,
// H2A, etc.) without changing the surrounding layout.
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
  return (
    <div
      id={`sub-${sub.slug}`}
      style={{ marginBottom: 24, scrollMarginTop: 24 }}
    >
      <div className="meta" style={{ marginBottom: 6 }}>
        {sub.code ? `${sub.code} · ` : ""}
        {sub.name}
      </div>
      <KVRows fields={sub.fields} />
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
