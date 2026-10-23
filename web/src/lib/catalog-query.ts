export type CatalogSectionTarget = {
  code: string;
  label: string;
  anchor: string;
  keywords: string[];
};

export const CDS_CATALOG_SECTIONS: CatalogSectionTarget[] = [
  { code: "§A", label: "General Information", anchor: "#sec-A", keywords: ["a", "general"] },
  { code: "§B1", label: "Institutional Enrollment", anchor: "#sec-b1", keywords: ["b1", "enrollment", "undergrad"] },
  { code: "§B4", label: "Graduation Rate Cohort", anchor: "#sec-b4", keywords: ["b4", "graduation", "cohort"] },
  { code: "§B22", label: "First-Year Retention Rate", anchor: "#sec-b22", keywords: ["b22", "retention", "persist"] },
  { code: "§C1", label: "First-Year Admissions Funnel", anchor: "#sec-c1", keywords: ["c1", "admissions", "acceptance", "admit", "applied", "yield"] },
  { code: "§C2", label: "Wait List", anchor: "#waitlist", keywords: ["c2", "waitlist", "wait"] },
  { code: "§C7", label: "Basis for Selection", anchor: "#sec-c7", keywords: ["c7", "selection", "factors", "gpa", "rigor"] },
  { code: "§C9", label: "SAT & ACT Score Bands", anchor: "#testing", keywords: ["c9", "testing", "sat", "act", "scores", "exams"] },
  { code: "§D2", label: "Transfer Admissions", anchor: "#sec-d2", keywords: ["d2", "transfer"] },
  { code: "§G1", label: "Undergraduate Tuition & Costs", anchor: "#sec-g1", keywords: ["g", "g1", "tuition", "cost", "sticker", "expenses"] },
  { code: "§H2", label: "Financial Aid Awarded", anchor: "#sec-h2", keywords: ["h", "h2", "aid", "need", "grants", "scholarships"] },
  { code: "§H2A", label: "Non-Need Merit Aid", anchor: "#sec-h2a", keywords: ["h2a", "merit", "non-need"] },
  { code: "§I1", label: "Instructional Faculty & Class Size", anchor: "#sec-i1", keywords: ["i", "i1", "i3", "faculty", "class"] },
  { code: "§J", label: "Degrees Conferred", anchor: "#sec-J", keywords: ["j", "j1", "degrees", "majors"] },
  { code: "§FED", label: "Federal Outcomes (Scorecard / FSA)", anchor: "#outcomes", keywords: ["outcomes", "federal", "scorecard", "earnings", "debt"] },
];

export type ParsedCatalogQuery = {
  schoolQuery: string;
  year: string | null;
  sectionTarget: CatalogSectionTarget | null;
  fieldId: string | null;
};

function normalizeYearToken(token: string): string | null {
  const fullMatch = /^(20\d{2})-(\d{2})$/.exec(token);
  if (fullMatch) return `${fullMatch[1]}-${fullMatch[2]}`;
  const singleYear = /^(20\d{2})$/.exec(token);
  if (singleYear) {
    const start = Number(singleYear[1]);
    const endTwo = String((start + 1) % 100).padStart(2, "0");
    return `${start}-${endTwo}`;
  }
  return null;
}

function matchSectionToken(token: string): CatalogSectionTarget | null {
  const cleaned = token.replace(/^§/, "").toLowerCase();
  if (!cleaned) return null;
  for (const sec of CDS_CATALOG_SECTIONS) {
    const codeNorm = sec.code.replace(/^§/, "").toLowerCase();
    if (codeNorm === cleaned || sec.keywords.includes(cleaned)) {
      return sec;
    }
  }
  if (/^[a-j]$/i.test(cleaned) && token.startsWith("§")) {
    const letter = cleaned.toUpperCase();
    return {
      code: `§${letter}`,
      label: `Section ${letter}`,
      anchor: `#sec-${letter}`,
      keywords: [],
    };
  }
  return null;
}

function matchFieldIdToken(token: string): string | null {
  const m = /^([A-J])\.(\d{3}[A-Z]?)$/i.exec(token.trim());
  if (!m) return null;
  return `${m[1].toUpperCase()}.${m[2].toUpperCase()}`;
}

export function parseCatalogQuery(raw: string): ParsedCatalogQuery {
  const tokens = raw
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (tokens.length === 0) {
    return { schoolQuery: "", year: null, sectionTarget: null, fieldId: null };
  }

  let year: string | null = null;
  let sectionTarget: CatalogSectionTarget | null = null;
  let fieldId: string | null = null;
  const remaining: string[] = [];

  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    if (!fieldId) {
      const f = matchFieldIdToken(tok);
      if (f) {
        fieldId = f;
        continue;
      }
    }
    if (!year) {
      const y = normalizeYearToken(tok);
      if (y) {
        year = y;
        continue;
      }
    }
    if (!sectionTarget) {
      const isExplicitCode =
        tok.startsWith("§") || /^[a-j]\d+[a-z]?$/i.test(tok);
      const sec = matchSectionToken(tok);
      if (sec && (isExplicitCode || i === tokens.length - 1)) {
        sectionTarget = sec;
        continue;
      }
    }
    remaining.push(tok);
  }

  return {
    schoolQuery: remaining.join(" "),
    year,
    sectionTarget,
    fieldId,
  };
}
