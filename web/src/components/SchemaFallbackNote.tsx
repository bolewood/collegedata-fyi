export function SchemaFallbackNote({ note }: { note: string }) {
  return (
    <p
      className="serif"
      style={{
        fontStyle: "italic",
        fontSize: 13,
        color: "var(--ink-3)",
        margin: "12px 0 0",
        lineHeight: 1.5,
        maxWidth: 640,
      }}
    >
      {note}
    </p>
  );
}
