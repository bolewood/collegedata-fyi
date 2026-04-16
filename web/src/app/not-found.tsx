import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-24 text-center">
      <h1 className="text-4xl font-bold text-gray-900">404</h1>
      <p className="mt-4 text-lg text-gray-600">
        Page not found. The school or document you&apos;re looking for may not
        exist in our archive yet.
      </p>
      <div className="mt-8 flex justify-center gap-4">
        <Link
          href="/schools"
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Browse schools
        </Link>
        <Link
          href="/"
          className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Go home
        </Link>
      </div>
    </div>
  );
}
