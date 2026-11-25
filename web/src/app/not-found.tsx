import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-24 text-center">
      <h1 className="text-5xl">404</h1>
      <p className="mt-4 text-lg text-[var(--ink-2)]">
        Page not found. The school or document you're looking for may not
        exist in our archive yet.
      </p>
      <div className="mt-8 flex justify-center gap-4">
        <Link href="/schools" className="cd-btn">
          Browse schools
        </Link>
        <Link href="/" className="cd-btn cd-btn--ghost">
          Go home
        </Link>
      </div>
    </div>
  );
}
