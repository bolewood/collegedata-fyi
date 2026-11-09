import { describe, expect, it } from "vitest";
import {
  emptyFeedback,
  feedbackSubject,
  toFormspreeData,
  validateFeedback,
  safeKind,
  safeSource,
} from "./community-feedback";
import { communityAnalyticsUrl } from "./community-privacy";
import { sentryBeforeSend, sentryInitOptions } from "./sentry";
import {
  publicProjects,
  communityProjects,
  type CommunityProject,
} from "@/data/community/projects";

const valid = () => ({
  ...emptyFeedback(),
  message: "Thanks for the data",
});

describe("private feedback contract", () => {
  it("allows anonymous plain feedback; rejects unexpected keys and all bounded types", () => {
    expect(validateFeedback(valid()).value).toBeDefined();
    expect(validateFeedback({ ...valid(), kind: "story" }).value).toBeDefined();
    expect(
      validateFeedback({
        ...valid(),
        kind: "story",
        projectUrl: "https://example.test/?" + "x".repeat(2000),
      }).value,
    ).toBeDefined();
    for (const change of [
      { message: " " },
      { message: "x".repeat(4001) },
      { email: true },
      { email: "bad" },
      { from: "https://private.test" },
      { kind: "rating" },
      { featureInterest: "true" },
      { test: true },
      { name: "x".repeat(101) },
      { school: "unrelated" },
    ])
      expect(validateFeedback({ ...valid(), ...change }).value).toBeUndefined();
    for (const key of [
      "email",
      "name",
      "projectUrl",
      "school",
      "year",
      "field",
      "expected",
      "sourceUrl",
    ] as const)
      expect(
        validateFeedback({
          ...valid(),
          kind: "data_issue",
          [key]: "x".repeat(2049),
        }).value,
      ).toBeUndefined();
  });

  it("requires contact only for feature interest; rejects unsafe URL schemes and credentials", () => {
    expect(
      validateFeedback({ ...valid(), kind: "story", featureInterest: true })
        .errors.email,
    ).toBeTruthy();
    expect(
      validateFeedback({
        ...valid(),
        kind: "story",
        featureInterest: true,
        email: "canary@example.test",
      }).value,
    ).toBeDefined();
    for (const projectUrl of [
      "javascript:alert(1)",
      "file:///private",
      "https://user:password@example.test",
    ])
      expect(
        validateFeedback({ ...valid(), kind: "story", projectUrl }).errors
          .projectUrl,
      ).toBeTruthy();
  });

  it("formats Formspree FormData with distinct subjects and conditional fields", () => {
    const plain = toFormspreeData({
      ...emptyFeedback("feedback", "footer"),
      message: "Helpful archive",
    });
    expect(plain.get("_subject")).toBe("[Feedback] collegedata.fyi");
    expect(plain.get("kind")).toBe("feedback");
    expect(plain.get("from")).toBe("footer");
    expect(plain.get("message")).toBe("Helpful archive");
    expect(plain.get("email")).toBeNull();
    expect(plain.get("feature_interest")).toBeNull();

    const story = toFormspreeData({
      ...emptyFeedback("story", "usage"),
      message: "Built a scholarship explorer",
      email: "author@example.test",
      projectUrl: "https://example.test/explorer",
      featureInterest: true,
    });
    expect(story.get("_subject")).toBe("[Story] collegedata.fyi");
    expect(story.get("email")).toBe("author@example.test");
    expect(story.get("project_url")).toBe("https://example.test/explorer");
    expect(story.get("feature_interest")).toBe("yes");

    const issue = toFormspreeData({
      ...emptyFeedback("data_issue", "school_year"),
      message: "Section C1 total looks swapped",
      school: "MIT",
      year: "2024-25",
      field: "C1",
      expected: "1,100",
      sourceUrl: "https://ir.mit.edu/cds",
    });
    expect(issue.get("_subject")).toBe("[Data issue] MIT (2024-25)");
    expect(issue.get("school")).toBe("MIT");
    expect(issue.get("year")).toBe("2024-25");
    expect(issue.get("field")).toBe("C1");
    expect(issue.get("expected")).toBe("1,100");
    expect(issue.get("source_url")).toBe("https://ir.mit.edu/cds");
    expect(feedbackSubject({ ...emptyFeedback("data_issue"), message: "x" })).toBe(
      "[Data issue] collegedata.fyi",
    );
    expect(safeSource("gpa=4.0")).toBe("direct");
    expect(safeKind(["story"])).toBe("feedback");
  });

  it("redacts analytics URLs and suppresses Sentry feedback events, transactions and breadcrumbs", () => {
    const url =
      "https://www.collegedata.fyi/feedback?email=canary@example.test&match=private#student";
    expect(communityAnalyticsUrl(url)).toBe(
      "https://www.collegedata.fyi/feedback",
    );
    const event = {
      request: { url },
      extra: { message: "PII CANARY" },
      breadcrumbs: [{ data: { body: "PII CANARY" } }],
    };
    expect(sentryBeforeSend(event)).toBeNull();
    expect(
      communityAnalyticsUrl(
        "https://www.collegedata.fyi/%66eedback?email=canary@example.test",
      ),
    ).toBe("https://www.collegedata.fyi/%66eedback");
    expect(
      sentryBeforeSend({
        request: { url: "https://www.collegedata.fyi/api/%66eedback" },
      }),
    ).toBeNull();
    const options = sentryInitOptions();
    expect(options.beforeSendTransaction(event)).toBeNull();
    expect(options.beforeBreadcrumb({ data: { url } })).toBeNull();
  });

  it("renders only separately approved matching-version stories and no private fields", () => {
    const story = {
      ...communityProjects[0],
      kind: "approved_story",
      credit: "Approved credit",
      publicationStatus: "awaiting_approval",
      contentVersion: "v1",
      approvedVersion: "v1",
    } as CommunityProject;
    expect(publicProjects([story])).toHaveLength(0);
    expect(
      publicProjects([
        { ...story, publicationStatus: "withdrawn" } as CommunityProject,
      ]),
    ).toHaveLength(0);
    expect(
      publicProjects([
        {
          ...story,
          publicationStatus: "approved",
          approvedVersion: "v2",
        } as CommunityProject,
      ]),
    ).toHaveLength(0);
    expect(
      publicProjects([
        { ...story, publicationStatus: "approved" } as CommunityProject,
      ]),
    ).toHaveLength(1);
    expect(() =>
      publicProjects([
        {
          ...communityProjects[0],
          description: "Contact me at canary@example.test",
        },
      ]),
    ).toThrow("Private contact");
    expect(() =>
      publicProjects([
        {
          ...communityProjects[0],
          email: "private-field-value",
        } as unknown as CommunityProject,
      ]),
    ).toThrow("Private community field");
  });
});
