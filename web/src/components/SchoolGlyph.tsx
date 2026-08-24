import { glyphInks, type GlyphInks } from "@/lib/derive-inks";

export type SchoolGlyphSize = "sm" | "md" | "lg";

export function SchoolGlyph({
  brandColors,
  inks: inksProp,
  size = "md",
}: {
  brandColors?: string[] | string | null;
  inks?: GlyphInks;
  size?: SchoolGlyphSize;
}) {
  const inks = inksProp ?? glyphInks(brandColors);
  const className =
    size === "md" ? "school-glyph" : `school-glyph school-glyph--${size}`;

  return (
    <span
      className={className}
      title={inks.unknown ? "Colours not on file" : `${inks.a} · ${inks.b}`}
      aria-hidden="true"
    >
      <i style={{ background: inks.a }} />
      <i
        className={inks.hollowB ? "school-glyph__dot--hollow" : undefined}
        style={inks.hollowB ? { color: inks.b } : { background: inks.b }}
      />
    </span>
  );
}
