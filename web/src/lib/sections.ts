import type { FieldValue } from "./types";
import { FIELD_LABELS, SECTION_NAMES } from "./labels";

export type ExtractedField = {
  id: string;
  field: FieldValue;
};

export type SubsectionGroup = {
  // Slug used for anchor IDs — unique within a section.
  slug: string;
  // CDS table code derived from word_tag prefix (e.g. "B1", "C7", "H2A");
  // null when no extracted field carries one.
  code: string | null;
  // Human name from the schema ("Institutional Enrollment").
  name: string;
  fields: ExtractedField[];
};

export type SectionGroup = {
  letter: string;
  name: string;
  subsections: SubsectionGroup[];
};

// Build the section/subsection tree the textbook FieldsView consumes.
// Ordering is by question_number so sections render in CDS reading order
// (A → B → C → …) and subsections within a section follow the order their
// fields appear, not alphabetical.
export function groupBySection(
  values: Record<string, FieldValue>,
): SectionGroup[] {
  const sectionMap = new Map<
    string,
    {
      letter: string;
      name: string;
      // subsection name → group
      subs: Map<string, SubsectionGroup>;
      // tracks lowest field id per subsection so we can sort
      subOrder: Map<string, string>;
    }
  >();

  const entries = Object.entries(values).sort(([a], [b]) =>
    a.localeCompare(b, undefined, { numeric: true }),
  );

  for (const [id, field] of entries) {
    const letter = id.split(".")[0];
    const sectionName =
      field.section ?? SECTION_NAMES[letter] ?? `Section ${letter}`;
    const subsectionName =
      field.subsection ?? FIELD_LABELS[id]?.subsection ?? "Other";

    let sec = sectionMap.get(letter);
    if (!sec) {
      sec = {
        letter,
        name: sectionName,
        subs: new Map(),
        subOrder: new Map(),
      };
      sectionMap.set(letter, sec);
    }

    let sub = sec.subs.get(subsectionName);
    if (!sub) {
      sub = {
        slug: slugify(`${letter}-${subsectionName}`),
        code: null,
        name: subsectionName,
        fields: [],
      };
      sec.subs.set(subsectionName, sub);
      sec.subOrder.set(subsectionName, id);
    }
    if (sub.code == null) {
      sub.code = subsectionCodeFromWordTag(field.word_tag);
    }
    sub.fields.push({ id, field });
  }

  const sections: SectionGroup[] = [];
  const orderedLetters = Array.from(sectionMap.keys()).sort();
  for (const letter of orderedLetters) {
    const sec = sectionMap.get(letter)!;
    const subs = Array.from(sec.subs.values()).sort((a, b) => {
      const aFirst = sec.subOrder.get(a.name) ?? "";
      const bFirst = sec.subOrder.get(b.name) ?? "";
      return aFirst.localeCompare(bFirst, undefined, { numeric: true });
    });
    sections.push({ letter, name: sec.name, subsections: subs });
  }
  return sections;
}

// word_tag like "b1_gr_ft_first_time_degseek_females" → "B1".
// Returns null when the input is empty or malformed.
function subsectionCodeFromWordTag(tag?: string | null): string | null {
  if (!tag) return null;
  const prefix = tag.split("_")[0];
  if (!prefix || !/^[a-z]\d+[a-z]?$/i.test(prefix)) return null;
  return prefix.toUpperCase();
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
