import type { FieldValue } from "@/lib/types";

const KEY_FIELDS: { id: string; displayLabel: string }[] = [
  { id: "C.105", displayLabel: "Applications" },
  { id: "C.107", displayLabel: "Admitted" },
  { id: "C.109", displayLabel: "Enrolled" },
  { id: "C.901", displayLabel: "SAT Math 25th" },
  { id: "C.902", displayLabel: "SAT Math 75th" },
  { id: "C.905", displayLabel: "SAT Reading 25th" },
  { id: "C.906", displayLabel: "SAT Reading 75th" },
];

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}

function getVal(values: Record<string, FieldValue>, id: string): string | null {
  const field = values[id];
  if (!field) return null;
  return field.value_decoded ?? field.value;
}

function getNum(values: Record<string, FieldValue>, id: string): number | null {
  const v = getVal(values, id);
  if (!v) return null;
  const n = parseInt(v.replace(/,/g, ""), 10);
  return isNaN(n) ? null : n;
}

export function KeyStats({ values }: { values: Record<string, FieldValue> }) {
  const apps = getNum(values, "C.105");
  const admits = getNum(values, "C.107");
  const acceptanceRate =
    apps && admits && apps > 0
      ? ((admits / apps) * 100).toFixed(1) + "%"
      : null;

  const stats: { label: string; value: string }[] = [];

  if (acceptanceRate) {
    stats.push({ label: "Acceptance Rate", value: acceptanceRate });
  }

  for (const field of KEY_FIELDS) {
    const v = getVal(values, field.id);
    if (!v || v === "0") continue;
    const num = parseInt(v.replace(/,/g, ""), 10);
    const displayValue = isNaN(num) ? v : num.toLocaleString();
    stats.push({ label: field.displayLabel, value: displayValue });
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
