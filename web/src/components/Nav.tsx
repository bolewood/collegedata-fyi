import Link from "next/link";

export function Nav() {
  return (
    <nav className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-5xl px-4 py-4 flex items-center justify-between">
        <Link href="/" className="text-lg font-semibold text-gray-900">
          collegedata.fyi
        </Link>
        <div className="flex gap-6 text-sm">
          <Link
            href="/schools"
            className="text-gray-600 hover:text-gray-900"
          >
            Schools
          </Link>
          <Link
            href="/about"
            className="text-gray-600 hover:text-gray-900"
          >
            About
          </Link>
          <Link
            href="/api"
            className="text-gray-600 hover:text-gray-900"
          >
            API
          </Link>
          <a
            href="https://github.com/bolewood/collegedata-fyi"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-600 hover:text-gray-900"
          >
            GitHub
          </a>
        </div>
      </div>
    </nav>
  );
}
