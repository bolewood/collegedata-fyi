import { describe, expect, it } from "vitest";
import { communityAnalyticsUrl, SENSITIVE_PARAMS } from "./community-privacy";

describe("communityAnalyticsUrl", () => {
  it("drops the Match code on /match", () => {
    expect(communityAnalyticsUrl("https://www.collegedata.fyi/match?code=ABC")).toBe(
      "https://www.collegedata.fyi/match",
    );
  });
  it("drops code and q on any path, case-insensitively, keeping other params", () => {
    expect(
      communityAnalyticsUrl("https://www.collegedata.fyi/coverage?state=CA&Code=X&q=yale&code=Y"),
    ).toBe("https://www.collegedata.fyi/coverage?state=CA");
  });
  it("keeps a non-sensitive parameter on another path", () => {
    expect(communityAnalyticsUrl("https://www.collegedata.fyi/coverage?state=CA")).toBe(
      "https://www.collegedata.fyi/coverage?state=CA",
    );
  });
  it("still clears query and hash on /feedback", () => {
    expect(communityAnalyticsUrl("https://www.collegedata.fyi/feedback?school=yale#top")).toBe(
      "https://www.collegedata.fyi/feedback",
    );
  });
  it("returns unparseable input unchanged", () => {
    expect(communityAnalyticsUrl("not a url")).toBe("not a url");
  });
  it("shares its list with Sentry", () => {
    expect([...SENSITIVE_PARAMS].sort()).toEqual(["code", "q"]);
  });
});
