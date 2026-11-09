/** Public, bounded contract. Never add free text to community analytics. */
export const feedbackKinds = ["feedback", "story", "data_issue"] as const;
export const feedbackSources = [
  "direct",
  "footer",
  "usage",
  "api",
  "school",
  "school_year",
  "readme",
  "cli",
  "mcp",
  "match",
] as const;
export type FeedbackKind = (typeof feedbackKinds)[number];
export type FeedbackSource = (typeof feedbackSources)[number];
export const GITHUB_REPOSITORY = "https://github.com/bolewood/collegedata-fyi";
export const FEEDBACK_EMAIL = "mailto:contact@bolewood.com";
export type FeedbackPayload = {
  kind: FeedbackKind;
  from: FeedbackSource;
  message: string;
  email: string;
  name: string;
  projectUrl: string;
  featureInterest: boolean;
  school: string;
  year: string;
  field: string;
  expected: string;
  sourceUrl: string;
};
export type FeedbackErrors = Partial<Record<keyof FeedbackPayload, string>>;
export const fieldLimits = {
  message: 4000,
  email: 254,
  name: 100,
  projectUrl: 2048,
  school: 150,
  year: 20,
  field: 100,
  expected: 500,
  sourceUrl: 2048,
} as const;
export function safeKind(value: unknown): FeedbackKind {
  return feedbackKinds.includes(value as FeedbackKind)
    ? (value as FeedbackKind)
    : "feedback";
}
export function safeSource(value: unknown): FeedbackSource {
  return feedbackSources.includes(value as FeedbackSource)
    ? (value as FeedbackSource)
    : "direct";
}
export function safeHttpUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return (
      ["http:", "https:"].includes(u.protocol) && !u.username && !u.password
    );
  } catch {
    return false;
  }
}
export function validateFeedback(input: unknown): {
  value?: FeedbackPayload;
  errors: FeedbackErrors;
} {
  const errors: FeedbackErrors = {};
  if (!input || typeof input !== "object" || Array.isArray(input))
    return {
      errors: {
        message: "Please check the fields below. Your message is still here.",
      },
    };
  const data = input as Record<string, unknown>;
  const keys = [
    "kind",
    "from",
    "featureInterest",
    ...Object.keys(fieldLimits),
  ];
  if (Object.keys(data).some((k) => !keys.includes(k)))
    errors.message = "Unexpected field. Please reload the form and try again.";
  const cleaned: Record<string, unknown> = {};
  for (const [key, limit] of Object.entries(fieldLimits)) {
    const v = data[key];
    if (typeof v !== "string" || v.trim().length > limit || /\u0000/.test(v))
      errors[key as keyof FeedbackPayload] = `Use at most ${limit} characters.`;
    else cleaned[key] = v.trim();
  }
  if (!cleaned.message && !errors.message)
    errors.message = "Add a message. A sentence is enough.";
  if (!feedbackKinds.includes(data.kind as FeedbackKind))
    errors.kind = "Choose a message type.";
  if (!feedbackSources.includes(data.from as FeedbackSource))
    errors.from = "Choose a known source.";
  if (typeof data.featureInterest !== "boolean")
    errors.featureInterest = "Choose whether you'd like to discuss a story.";
  for (const key of ["projectUrl", "sourceUrl"] as const)
    if (cleaned[key] && !safeHttpUrl(cleaned[key] as string))
      errors[key] = "Use an http or https link without a username or password.";
  if (
    cleaned.email &&
    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleaned.email as string)
  )
    errors.email = "Check the email address.";
  if (data.featureInterest && data.kind !== "story")
    errors.featureInterest = "Feature discussions are for stories.";
  if (data.featureInterest && !cleaned.email)
    errors.email =
      "Add an email so we can discuss featuring your story, or uncheck that option to send without one.";
  if (data.kind !== "story" && cleaned.projectUrl)
    errors.projectUrl = "Project links are for stories.";
  if (
    data.kind !== "data_issue" &&
    ["school", "year", "field", "expected", "sourceUrl"].some((k) => cleaned[k])
  )
    errors.school = "School details are for data problems.";
  if (Object.keys(errors).length) return { errors };
  return {
    value: {
      ...cleaned,
      kind: data.kind,
      from: data.from,
      featureInterest: data.featureInterest,
    } as FeedbackPayload,
    errors,
  };
}
export function emptyFeedback(
  kind: FeedbackKind = "feedback",
  from: FeedbackSource = "direct",
): FeedbackPayload {
  return {
    kind,
    from,
    message: "",
    email: "",
    name: "",
    projectUrl: "",
    featureInterest: false,
    school: "",
    year: "",
    field: "",
    expected: "",
    sourceUrl: "",
  };
}
export function feedbackSubject(payload: FeedbackPayload): string {
  if (payload.kind === "story") return "[Story] collegedata.fyi";
  if (payload.kind === "data_issue") {
    const target = payload.school || "collegedata.fyi";
    return payload.year
      ? `[Data issue] ${target} (${payload.year})`
      : `[Data issue] ${target}`;
  }
  return "[Feedback] collegedata.fyi";
}
export function toFormspreeData(payload: FeedbackPayload): FormData {
  const formData = new FormData();
  formData.set("_subject", feedbackSubject(payload));
  formData.set("kind", payload.kind);
  formData.set("from", payload.from);
  formData.set("message", payload.message);
  if (payload.email) formData.set("email", payload.email);
  if (payload.name) formData.set("name", payload.name);
  if (payload.kind === "story") {
    formData.set("feature_interest", payload.featureInterest ? "yes" : "no");
    if (payload.projectUrl) formData.set("project_url", payload.projectUrl);
  }
  if (payload.kind === "data_issue") {
    if (payload.school) formData.set("school", payload.school);
    if (payload.year) formData.set("year", payload.year);
    if (payload.field) formData.set("field", payload.field);
    if (payload.expected) formData.set("expected", payload.expected);
    if (payload.sourceUrl) formData.set("source_url", payload.sourceUrl);
  }
  return formData;
}
