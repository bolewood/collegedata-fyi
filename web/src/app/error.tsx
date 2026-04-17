"use client";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-5xl px-4 py-24 text-center">
      <h1 className="text-2xl font-bold text-gray-900">
        Something went wrong
      </h1>
      <p className="mt-4 text-gray-600">
        Unable to load data. This is usually temporary.
      </p>
      <button
        onClick={reset}
        className="mt-8 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        Try again
      </button>
    </div>
  );
}
