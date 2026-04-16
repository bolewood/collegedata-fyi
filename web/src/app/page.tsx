import Link from "next/link";
import { fetchManifest, aggregateSchools, computeStats } from "@/lib/queries";
import { StatsBar } from "@/components/StatsBar";
import { SchoolSearch } from "@/components/SchoolSearch";

export const revalidate = 3600; // ISR: revalidate every hour

export default async function HomePage() {
  const manifest = await fetchManifest();
  const schools = aggregateSchools(manifest);
  const stats = computeStats(manifest);

  return (
    <div className="mx-auto max-w-5xl px-4">
      {/* Hero */}
      <div className="py-16 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          College data, straight from the source.
        </h1>
        <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
          College facts pulled straight from each school&apos;s Common Data Set,
          archived so the numbers stay public.{" "}
          <Link href="/about" className="text-blue-600 hover:text-blue-800">
            Learn more
          </Link>
        </p>

        <div className="mt-8">
          <SchoolSearch schools={schools} />
        </div>
      </div>

      {/* Stats */}
      <StatsBar stats={stats} />

      {/* CTAs */}
      <div className="flex justify-center gap-4 py-8 flex-wrap">
        <Link
          href="/schools"
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Browse all schools
        </Link>
        <a
          href="https://api.collegedata.fyi/rest/v1/"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          API docs
        </a>
        <a
          href="https://github.com/bolewood/collegedata-fyi"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          View on GitHub
        </a>
      </div>
    </div>
  );
}
