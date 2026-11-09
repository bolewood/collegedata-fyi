import { describe, expect, it, vi } from "vitest";
import {
  emptyFeedback,
  validateFeedback,
  submissionIdentity,
  safeKind,
  safeSource,
} from "./community-feedback";
import {
  handleFeedback,
  type FeedbackDependencies,
} from "./community-feedback-handler";
import { communityAnalyticsUrl } from "./community-privacy";
import { sentryBeforeSend, sentryInitOptions } from "./sentry";
import {
  publicProjects,
  communityProjects,
  type CommunityProject,
} from "@/data/community/projects";
const id = "11111111-1111-4111-8111-111111111111";
const valid = () => ({
  ...emptyFeedback(),
  message: "Thanks for the data",
  requestId: id,
});
const request = (body: unknown = valid(), headers = {}) =>
  new Request("https://www.collegedata.fyi/api/feedback", {
    method: "POST",
    headers: {
      Origin: "https://www.collegedata.fyi",
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  });
const deps = (): FeedbackDependencies => ({
  enabled: true,
  origins: ["https://www.collegedata.fyi"],
  secret: "test-only-secret-with-at-least-32-characters",
  clientIp: () => "192.0.2.1",
  save: vi.fn(async () => ({ status: "created" as const, receipt: "receipt" })),
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
      { requestId: "bad" },
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
  it("normalizes order and whitespace before hashing, keeps retries in memory, rotates changed payload", () => {
    const payload = emptyFeedback();
    const uuid = vi.fn(() => id);
    const first = submissionIdentity(payload, undefined, uuid);
    expect(submissionIdentity({ ...payload }, first, uuid)).toBe(first);
    expect(
      submissionIdentity({ ...payload, message: "edit" }, first, uuid),
    ).not.toBe(first);
    expect(uuid).toHaveBeenCalledTimes(2);
    expect(safeSource("gpa=4.0")).toBe("direct");
    expect(safeKind(["story"])).toBe("feedback");
  });
  it("requires exact configured Origin and JSON; fails closed on config/IP/storage", async () => {
    for (const origin of [
      "https://evil.test",
      "https://www.collegedata.fyi.evil.test",
      "null",
      "",
    ])
      expect(
        (await handleFeedback(request(valid(), { Origin: origin }), deps()))
          .status,
      ).toBe(403);
    expect(
      (
        await handleFeedback(
          request(valid(), { "Content-Type": "text/plain" }),
          deps(),
        )
      ).status,
    ).toBe(415);
    for (const change of [
      { enabled: false },
      { secret: undefined },
      { clientIp: () => null },
      { clientIp: () => "spoofed, 192.0.2.1" },
      {
        save: async () => {
          throw new Error("SECRET CANARY");
        },
      },
    ]) {
      const response = await handleFeedback(request(), {
        ...deps(),
        ...change,
      });
      expect(response.status).toBe(503);
      expect(await response.text()).not.toContain("CANARY");
    }
  });
  it("bounds streaming body even without Content-Length", async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("x".repeat(65537)));
        controller.close();
      },
    });
    const req = new Request("https://www.collegedata.fyi/api/feedback", {
      method: "POST",
      headers: {
        Origin: "https://www.collegedata.fyi",
        "Content-Type": "application/json",
      },
      body: stream,
      duplex: "half",
    } as RequestInit);
    expect((await handleFeedback(req, deps())).status).toBe(413);
  });
  it("returns committed receipts, duplicate/conflict/limit with no-store and no content", async () => {
    for (const [status, code] of [
      ["created", 201],
      ["duplicate", 200],
      ["conflict", 409],
      ["limited", 429],
    ] as const) {
      const d = deps();
      d.save = vi.fn(async () => ({
        status,
        receipt: "private-reference",
        retry_after: 42,
      }));
      const response = await handleFeedback(
        request({ ...valid(), email: "canary@example.test" }),
        d,
      );
      expect(response.status).toBe(code);
      expect(response.headers.get("Cache-Control")).toBe("no-store");
      if (code === 429) expect(response.headers.get("Retry-After")).toBe("42");
      expect(await response.text()).not.toContain("canary");
      const args = vi.mocked(d.save).mock.calls[0][0];
      expect(args.bucket).toMatch(/^[a-f0-9]{64}$/);
      expect(args.bucket).not.toBe(args.previousBucket);
    }
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
