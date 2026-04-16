import type { CorpusStats } from "@/lib/types";
import { yearRange } from "@/lib/format";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}

export function StatsBar({ stats }: { stats: CorpusStats }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 py-6">
      <Stat label="Schools archived" value={stats.total_schools.toLocaleString()} />
      <Stat label="CDS documents" value={stats.total_documents.toLocaleString()} />
      <Stat
        label="Year range"
        value={yearRange(stats.earliest_year, stats.latest_year)}
      />
      <Stat label="Extracted" value={`${stats.extraction_pct}%`} />
    </div>
  );
}
