import type { FieldValue } from "@/lib/types";
import { c1HeadlineTotals } from "@/lib/c1-headline-totals";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}

function getNum(values: Record<string, FieldValue>, id: string): number | null {
  const field = values[id];
  if (!field) return null;
  const v = field.value_decoded ?? field.value;
  const n = parseFloat(v.replace(/,/g, ""));
  return isNaN(n) ? null : n;
}

export function KeyStats({
  schemaVersion,
  values,
}: {
  schemaVersion?: string;
  values: Record<string, FieldValue>;
}) {
  const stats: { label: string; value: string }[] = [];

  const { applied: totalApplied, admitted: totalAdmitted, enrolled: totalEnrolled } =
    c1HeadlineTotals(values, schemaVersion);

  // Acceptance rate
  if (totalApplied && totalAdmitted && totalApplied > 0) {
    const rate = ((totalAdmitted / totalApplied) * 100).toFixed(1) + "%";
    stats.push({ label: "Acceptance Rate", value: rate });
  }

  if (totalApplied) {
    stats.push({ label: "Applications", value: totalApplied.toLocaleString() });
  }
  if (totalAdmitted) {
    stats.push({ label: "Admitted", value: totalAdmitted.toLocaleString() });
  }
  if (totalEnrolled) {
    stats.push({ label: "Enrolled", value: totalEnrolled.toLocaleString() });
  }

  // SAT Composite (C.905 = 25th, C.907 = 75th)
  const sat25 = getNum(values, "C.905");
  const sat75 = getNum(values, "C.907");
  if (sat25 && sat75) {
    stats.push({ label: "SAT Composite", value: `${sat25}-${sat75}` });
  } else if (sat25) {
    stats.push({ label: "SAT Composite 25th", value: sat25.toLocaleString() });
  }

  // SAT Math (C.911 = 25th, C.913 = 75th if exists)
  const satMath25 = getNum(values, "C.911");
  const satMath75 = getNum(values, "C.913");
  if (satMath25 && satMath75) {
    stats.push({ label: "SAT Math", value: `${satMath25}-${satMath75}` });
  }

  // SAT Reading (C.908 = 25th, C.910 = 75th)
  const satRead25 = getNum(values, "C.908");
  const satRead75 = getNum(values, "C.910");
  if (satRead25 && satRead75) {
    stats.push({ label: "SAT Reading", value: `${satRead25}-${satRead75}` });
  }

  // ACT Composite (C.914 = 25th, C.916 = 75th)
  const act25 = getNum(values, "C.914");
  const act75 = getNum(values, "C.916");
  if (act25 && act75) {
    stats.push({ label: "ACT Composite", value: `${act25}-${act75}` });
  }

  if (stats.length === 0) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {stats.slice(0, 8).map((s) => (
        <StatCard key={s.label} label={s.label} value={s.value} />
      ))}
    </div>
  );
}
