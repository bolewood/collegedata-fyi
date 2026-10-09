import Link from "next/link";

/** One-line footer caption on school records. Keep it out of the page hero. */
export function SchoolApiNote() {
  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6">
      <p
        style={{
          margin: 0,
          paddingBottom: 16,
          fontSize: 13,
          lineHeight: 1.5,
          color: "var(--ink-3)",
        }}
      >
        Building something with this data?{" "}
        <Link href="/api">Use the free API</Link>.
      </p>
    </div>
  );
}
