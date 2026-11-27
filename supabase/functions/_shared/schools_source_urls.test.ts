import { assertEquals } from "jsr:@std/assert";
import { fetchSchoolsYaml } from "./schools.ts";

// Pins where the finder data is fetched from, so a repo rename cannot leave
// the edge functions reading a stale or redirected location.
Deno.test("fetchSchoolsYaml reads schools.yaml and the overrides file from bolewood/quadfile", async () => {
  const requested: string[] = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = ((input: string | URL | Request) => {
    requested.push(String(input));
    return Promise.resolve(new Response("schools: []\n", { status: 200 }));
  }) as typeof fetch;
  try {
    await fetchSchoolsYaml();
  } finally {
    globalThis.fetch = realFetch;
  }
  assertEquals(requested, [
    "https://raw.githubusercontent.com/bolewood/quadfile/main/tools/finder/schools.yaml",
    "https://raw.githubusercontent.com/bolewood/quadfile/main/tools/finder/school_overrides.yaml",
  ]);
});
