// Independent fact-check for acceptance-rate leads (PRD 031). Re-derives
// every claim in a generated lead from the table data, without using the
// generator's logic. Used by tests over all pilot schools and synthetic
// series; returns a list of problems (empty = every claim checks out).

export type AuditRow = { yearStart: number; applied: number; admitted: number };

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

function shown(rate: number): number {
  return Math.round(rate * 1000);
}

function num(text: string): number {
  return Number(text.replace(/,/g, ""));
}

function years(list: string): number[] {
  return Array.from(list.matchAll(/fall (\d{4})/g), (m) => Number(m[1]));
}

export function auditLead(lead: string, rows: AuditRow[]): string[] {
  const problems: string[] = [];
  const series = [...rows].sort((a, b) => a.yearStart - b.yearStart).map((r) => ({ ...r, rate: r.admitted / r.applied }));
  const byYear = new Map(series.map((r) => [r.yearStart, r]));
  const last = series[series.length - 1];
  const prev = series[series.length - 2];
  const hasGaps = last.yearStart - series[0].yearStart + 1 !== series.length;
  const fail = (message: string) => problems.push(message);
  const display = (y: number) => {
    const row = byYear.get(y);
    return row ? (shown(row.rate) / 10).toFixed(1) : null;
  };
  const sameShown = (y: number) => series.filter((r) => shown(r.rate) === shown(byYear.get(y)!.rate)).map((r) => r.yearStart);
  const isExtreme = (y: number, kind: string) =>
    series.every((r) => (kind.startsWith("low") ? shown(r.rate) >= shown(byYear.get(y)!.rate) : shown(r.rate) <= shown(byYear.get(y)!.rate)));
  const checkPhrase = (word: string, noun: string, where: string) => {
    if (WORDS[series.length] !== word) fail(`${where}: "${word} years" but ${series.length} years have figures`);
    if ((noun === "shown") === hasGaps) fail(`${where}: "years ${noun}" with${hasGaps ? "" : "out"} gaps`);
  };
  const sameSet = (a: number[], b: number[]) => a.length === b.length && a.every((y) => b.includes(y));

  // Answer: latest rate and counts.
  const answer = /admitted (\d+\.\d)% of first-year applicants for fall (\d{4}) \(([\d,]+) of ([\d,]+)\)/.exec(lead);
  if (!answer) fail("no answer sentence");
  else {
    if (Number(answer[2]) !== last.yearStart) fail("answer is not the latest year");
    if (num(answer[3]) !== last.admitted || num(answer[4]) !== last.applied) fail("answer counts do not match");
    if (answer[1] !== display(last.yearStart)) fail("answer rate does not match");
  }

  // Every "up/down/unchanged from V% for fall Y" agrees with printed values.
  for (const m of lead.matchAll(/(up|down|unchanged) from (\d+\.\d)% for ((?:fall \d{4}(?:, and |, | and )?)+)/g)) {
    for (const y of years(m[3])) {
      if (display(y) !== m[2]) fail(`"${m[0]}": fall ${y} printed ${display(y)}%`);
      const d = shown(last.rate) - shown(byYear.get(y)!.rate);
      const expected = d > 0 ? "up" : d < 0 ? "down" : "unchanged";
      if (m[1] !== expected) fail(`"${m[0]}": should be ${expected}`);
    }
  }

  // "V% for fall Y[ and fall Z], the lowest in the N years shown/with figures"
  for (const m of lead.matchAll(/(\d+\.\d)% for ((?:fall \d{4}(?:, and |, | and )?)+), the (lowest|highest) in the (\w+) years (shown|with figures)/g)) {
    const listed = years(m[2]);
    for (const y of listed) if (display(y) !== m[1]) fail(`"${m[0]}": fall ${y} printed ${display(y)}%`);
    if (!isExtreme(listed[0], m[3] === "lowest" ? "low" : "high")) fail(`"${m[0]}": not the ${m[3]}`);
    if (!sameSet(listed, sameShown(listed[0]))) fail(`"${m[0]}": tied years not all named (${sameShown(listed[0]).join(", ")})`);
    checkPhrase(m[4], m[5], m[0]);
  }

  // Record: "(A of B), the lowest in the N years …[, tied with fall X]"
  const record = /\(([\d,]+) of ([\d,]+)\), the (lowest|highest) in the (\w+) years (shown|with figures)(?:, tied with ((?:fall \d{4}(?:, and |, | and )?)+))?/.exec(lead);
  if (record) {
    if (!isExtreme(last.yearStart, record[3] === "lowest" ? "low" : "high")) fail("record claim is false");
    const ties = sameShown(last.yearStart).filter((y) => y !== last.yearStart);
    if (!sameSet(ties, record[6] ? years(record[6]) : [])) fail(`record ties not named (${ties.join(", ")})`);
    checkPhrase(record[4], record[5], "record");
  }

  // "a low/high of V% for fall Y" (rates): the extreme of all years shown, all ties named.
  for (const m of lead.matchAll(/a (low|high) of (\d+\.\d)% for ((?:fall \d{4}(?:, and |, | and )?)+)/g)) {
    const listed = years(m[3]);
    for (const y of listed) if (display(y) !== m[2]) fail(`"${m[0]}": fall ${y} printed ${display(y)}%`);
    if (!isExtreme(listed[0], m[1])) fail(`"${m[0]}": not the ${m[1]} of the years shown`);
    if (!sameSet(listed, sameShown(listed[0]))) fail(`"${m[0]}": tied years not all named`);
  }

  // "from V% for fall E, the lowest since fall X[ (W%)]": X is the most recent
  // earlier year beyond E, and no year between X and now is.
  for (const m of lead.matchAll(/(\d+\.\d)% for fall (\d{4}), the (lowest|highest) since fall (\d{4})(?: \((\d+\.\d)%\))?/g)) {
    const e = Number(m[2]);
    const x = Number(m[4]);
    const low = m[3] === "lowest";
    if (display(e) !== m[1]) fail(`"${m[0]}": fall ${e} printed ${display(e)}%`);
    if (m[5] && display(x) !== m[5]) fail(`"${m[0]}": fall ${x} printed ${display(x)}%`);
    const beyond = (y: number) => (low ? shown(byYear.get(y)!.rate) < shown(byYear.get(e)!.rate) : shown(byYear.get(y)!.rate) > shown(byYear.get(e)!.rate));
    if (!byYear.has(x) || !beyond(x)) fail(`"${m[0]}": fall ${x} is not ${low ? "lower" : "higher"} than fall ${e}`);
    for (const r of series) {
      if (r.yearStart > x && r.yearStart !== e && beyond(r.yearStart)) fail(`"${m[0]}": fall ${r.yearStart} is also ${low ? "lower" : "higher"}`);
    }
  }

  // "It was V% for fall Y"
  for (const m of lead.matchAll(/It was (\d+\.\d)% for fall (\d{4})/g)) {
    if (display(Number(m[2])) !== m[1]) fail(`"${m[0]}": printed ${display(Number(m[2]))}%`);
  }

  // Moving down (up) but not the series low (high): that extreme must be named.
  if (prev) {
    const d = Math.sign(shown(last.rate) - shown(prev.rate));
    if (d !== 0) {
      const target = d < 0 ? Math.min(...series.map((r) => shown(r.rate))) : Math.max(...series.map((r) => shown(r.rate)));
      if (shown(last.rate) !== target) {
        const holders = series.filter((r) => shown(r.rate) === target);
        const mentioned = holders.some((r) => lead.includes(`${(target / 10).toFixed(1)}% for`) && lead.includes(`fall ${r.yearStart}`));
        if (!mentioned) fail(`series ${d < 0 ? "low" : "high"} of ${(target / 10).toFixed(1)}% is not named`);
      }
    }
  }

  // Percent changes name their base-year count, and the arithmetic holds.
  for (const m of lead.matchAll(/\b(rose|fell) (\d+\.\d)%/g)) {
    const full = /^(rose|fell) (\d+\.\d)% for fall (\d{4}), to ([\d,]+) from ([\d,]+)/.exec(lead.slice(m.index));
    if (!full) {
      fail(`"${m[0]}" has no base count`);
      continue;
    }
    const to = num(full[4]);
    const from = num(full[5]);
    const y = Number(full[3]);
    const at = byYear.get(y);
    const before = series[series.indexOf(at!) - 1];
    if (!at || at.applied !== to || !before || before.yearStart !== y - 1 || before.applied !== from) {
      fail(`"${full[0]}": counts do not match fall ${y - 1} → fall ${y}`);
    }
    if (((Math.abs(to - from) / from) * 100).toFixed(1) !== full[2]) fail(`"${full[0]}": arithmetic`);
    if (full[1] !== (to > from ? "rose" : "fell")) fail(`"${full[0]}": direction`);
  }

  // Application extremes.
  for (const m of lead.matchAll(/the (most|fewest) in the years (shown|with figures) was ([\d,]+), for ((?:fall \d{4}(?:, and |, | and )?)+)/g)) {
    const n = num(m[3]);
    const target = m[1] === "most" ? Math.max(...series.map((r) => r.applied)) : Math.min(...series.map((r) => r.applied));
    if (n !== target) fail(`"${m[0]}": ${m[1]} is ${target}`);
    if (!sameSet(years(m[4]), series.filter((r) => r.applied === n).map((r) => r.yearStart))) fail(`"${m[0]}": years`);
    if ((m[2] === "shown") === hasGaps) fail(`"${m[0]}": years ${m[2]} with${hasGaps ? "" : "out"} gaps`);
  }
  for (const m of lead.matchAll(/up from a low of ([\d,]+) for ((?:fall \d{4}(?:, and |, | and )?)+)/g)) {
    const n = num(m[1]);
    if (n !== Math.min(...series.map((r) => r.applied))) fail(`"${m[0]}": not the fewest applications`);
  }

  // Missing years named exactly.
  const missing: number[] = [];
  for (let y = series[0].yearStart + 1; y < last.yearStart; y++) if (!byYear.has(y)) missing.push(y);
  const gapSentence = /Usable figures for (.*?) are not in our archive\./.exec(lead);
  if (!sameSet(gapSentence ? years(gapSentence[1]) : [], missing)) fail(`missing years should be ${missing.join(", ") || "none"}`);

  return problems;
}
