import { FIELD_LABELS, SECTION_NAMES, type FieldLabel } from "./labels";
import { FIELD_LABELS_2024_25 } from "./labels-2024-25";
import type { FieldValue } from "./types";

function clean(value?: string | null): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

export function normalizeSchemaVersion(
  schemaVersion?: string | null,
): string | null {
  if (!schemaVersion) return null;
  return schemaVersion.trim();
}

export function isSchema2024_25(schemaVersion?: string | null): boolean {
  return normalizeSchemaVersion(schemaVersion) === "2024-25";
}

export function getFieldLabel(
  id: string,
  schemaVersion?: string | null,
): FieldLabel | undefined {
  if (isSchema2024_25(schemaVersion)) {
    return FIELD_LABELS_2024_25[id] ?? FIELD_LABELS[id];
  }
  return FIELD_LABELS[id];
}

export function getFieldDisplayLabel(
  id: string,
  field: FieldValue,
  schemaVersion?: string | null,
): string {
  const labelMeta = getFieldLabel(id, schemaVersion);
  return clean(labelMeta?.label) ?? clean(field.question) ?? id;
}

export function getFieldValueType(
  id: string,
  field: FieldValue,
  schemaVersion?: string | null,
): string | undefined {
  const labelMeta = getFieldLabel(id, schemaVersion);
  return clean(labelMeta?.valueType) ?? clean(field.value_type);
}

export function getFieldSectionName(
  id: string,
  field: FieldValue,
  schemaVersion?: string | null,
): string {
  const letter = id.split(".")[0];
  const labelMeta = getFieldLabel(id, schemaVersion);
  return (
    clean(labelMeta?.section) ??
    clean(field.section) ??
    SECTION_NAMES[letter] ??
    `Section ${letter}`
  );
}

export function getFieldSubsectionName(
  id: string,
  field: FieldValue,
  schemaVersion?: string | null,
): string {
  const labelMeta = getFieldLabel(id, schemaVersion);
  return clean(labelMeta?.subsection) ?? clean(field.subsection) ?? "Other";
}
