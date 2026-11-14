// Campuses whose Common Data Set situation is defined by another campus.
//
// Some institutions file one CDS that is published from a shared page. The
// archive used to attach that file to every campus that pointed at the page,
// so a branch showed the main campus's applicants and admit rate as its own.
// Each entry here was checked against the federal applicant counts:
//
//   not_included  the filing covers the publishing campus only. The file is
//                 hidden on this campus; its page says so and links across.
//   combined      one filing covers this campus together with the others
//                 listed. The file stays, with a note saying what it covers.
//
// Add an entry when the corpus audit (tools/data_quality/corpus_audit.py)
// reports `shared_source_file` for a new group, after checking which case it
// is. Parent ids must be canonical school ids.

export type CampusFiling =
  | {
      kind: "not_included";
      /** The campus that publishes the filing. */
      parentId: string;
      parentName: string;
      /** How to refer to this entry in a sentence. */
      noun: "campus" | "school" | "program";
    }
  | {
      kind: "combined";
      /** The institution that files, as a reader would name it. */
      filerName: string;
      /** Short campus names the filing covers, in the order to print them. */
      campuses: readonly string[];
    };

const kentBranch: CampusFiling = {
  kind: "not_included",
  parentId: "kent-state-university-at-kent",
  parentName: "Kent State University at Kent",
  noun: "campus",
};
const miamiBranch: CampusFiling = {
  kind: "not_included",
  parentId: "miami-university-oxford",
  parentName: "Miami University-Oxford",
  noun: "campus",
};
const fairleighDickinson: CampusFiling = {
  kind: "combined",
  filerName: "Fairleigh Dickinson University",
  campuses: ["Florham", "Metropolitan"],
};

export const CAMPUS_FILINGS: Readonly<Record<string, CampusFiling>> = {
  "kent-state-university-at-ashtabula": kentBranch,
  "kent-state-university-at-east-liverpool": kentBranch,
  "kent-state-university-at-geauga": kentBranch,
  "kent-state-university-at-salem": kentBranch,
  "kent-state-university-at-stark": kentBranch,
  "kent-state-university-at-trumbull": kentBranch,
  "kent-state-university-at-tuscarawas": kentBranch,
  "miami-university-hamilton": miamiBranch,
  "miami-university-middletown": miamiBranch,
  "northeastern-university-professional-programs": {
    kind: "not_included",
    parentId: "northeastern",
    parentName: "Northeastern University",
    noun: "program",
  },
  "middlebury-institute-of-international-studies-at-monterey": {
    kind: "not_included",
    parentId: "middlebury-college",
    parentName: "Middlebury College",
    noun: "school",
  },
  "drury-university-college-of-continuing-professional-studies": {
    kind: "not_included",
    parentId: "drury-university",
    parentName: "Drury University",
    noun: "school",
  },
  "northwest-university-center-for-online-and-extended": {
    kind: "not_included",
    parentId: "northwest-university",
    parentName: "Northwest University",
    noun: "program",
  },
  "fairleigh-dickinson-university-florham-campus": fairleighDickinson,
  "fairleigh-dickinson-university-metropolitan-campus": fairleighDickinson,
};

export function campusFiling(schoolId: string): CampusFiling | null {
  return Object.hasOwn(CAMPUS_FILINGS, schoolId) ? CAMPUS_FILINGS[schoolId] : null;
}

export type CampusLeadPart =
  | { type: "text"; text: string }
  | { type: "link"; href: string; text: string };

/** Lead for a campus page that has no file because the filing is another
 *  campus's. Null when the school has no `not_included` entry. */
export function notIncludedLead(
  schoolId: string,
  hasFederal: boolean,
): CampusLeadPart[] | null {
  const filing = campusFiling(schoolId);
  if (!filing || filing.kind !== "not_included") return null;
  const parts: CampusLeadPart[] = [
    {
      type: "text",
      text:
        `We haven’t found a Common Data Set for this ${filing.noun}. ` +
        `${filing.parentName} publishes one, and it does not include this ${filing.noun}. `,
    },
    {
      type: "link",
      href: `/schools/${filing.parentId}`,
      text: `See ${filing.parentName}`,
    },
    { type: "text", text: "." },
  ];
  if (hasFederal) {
    parts.push({
      type: "text",
      text: ` The federal numbers for this ${filing.noun} are below.`,
    });
  }
  return parts;
}

/** One sentence for a page whose file covers several campuses together.
 *  Null when the school has no `combined` entry. */
export function combinedFilingNote(schoolId: string): string | null {
  const filing = campusFiling(schoolId);
  if (!filing || filing.kind !== "combined") return null;
  const names = filing.campuses;
  const list =
    names.length === 2
      ? `${names[0]} and ${names[1]}`
      : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return (
    `${filing.filerName} publishes one Common Data Set for its ${list} campuses together. ` +
    `The numbers from the school’s report on this page cover ${names.length === 2 ? "both" : "all of them"}; ` +
    `the federal numbers are for this campus alone.`
  );
}
