import type { FieldValue } from "@/lib/types";
import { SECTION_NAMES } from "@/lib/labels";

export function FieldsView({
  values,
  totalFields,
}: {
  values: Record<string, FieldValue>;
  totalFields?: number;
}) {
  const entries = Object.entries(values);

  // Group fields by section (from the field value's own section metadata)
  const grouped = new Map<string, { id: string; field: FieldValue }[]>();

  for (const [id, field] of entries) {
    const section = field.section ?? sectionLetterToName(id.split(".")[0]);
    const group = grouped.get(section) ?? [];
    group.push({ id, field });
    grouped.set(section, group);
  }

  // Sort sections by the field ID prefix (A before B before C...)
  const sortedSections = Array.from(grouped.entries()).sort(([, a], [, b]) => {
    const aMin = a[0]?.id ?? "";
    const bMin = b[0]?.id ?? "";
    return aMin.localeCompare(bMin);
  });

  for (const [, fields] of sortedSections) {
    fields.sort((a, b) => a.id.localeCompare(b.id));
  }

  return (
    <div>
      {totalFields != null && (
        <p className="mb-4 text-sm text-gray-500">
          {entries.length} of ~{totalFields} fields extracted
        </p>
      )}

      {sortedSections.map(([sectionName, fields]) => {
        const letter = fields[0]?.id.split(".")[0] ?? "";
        return (
          <div key={sectionName} className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 border-b border-gray-200 pb-1 mb-2">
              {letter}. {sectionName}
            </h3>
            <dl className="space-y-1">
              {fields.map(({ id, field }) => {
                const label = field.question ?? id;
                const displayValue = field.value_decoded ?? field.value;
                return (
                  <div
                    key={id}
                    className="flex justify-between py-1.5 text-sm border-b border-gray-50"
                  >
                    <dt className="text-gray-600 pr-4 min-w-0">
                      {label}
                    </dt>
                    <dd className="font-medium text-gray-900 shrink-0 text-right max-w-[50%]">
                      {displayValue}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </div>
        );
      })}
    </div>
  );
}

function sectionLetterToName(letter: string): string {
  return SECTION_NAMES[letter] ?? `Section ${letter}`;
}
