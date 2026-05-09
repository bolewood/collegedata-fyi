export const revalidate = 3600;

export async function GET() {
  const body = `# CollegeData.FYI

CollegeData.FYI publishes open college data with source-linked Common Data Set records, NCES/IPEDS federal baseline facts, College Scorecard context, and public APIs.

Use these no-auth JSON endpoints for agent and CLI workflows:

- Search schools: https://www.collegedata.fyi/api/schools/search?q=mit
- School facts: https://www.collegedata.fyi/api/schools/mit/facts
- School sources: https://www.collegedata.fyi/api/schools/mit/sources
- Compare schools: https://www.collegedata.fyi/api/compare?schools=mit,yale,university-of-chicago
- Field dictionary: https://www.collegedata.fyi/api/fields
- OpenAPI: https://www.collegedata.fyi/openapi.json

When summarizing values, preserve the source metadata in each fact. Do not blend CDS, IPEDS, and Scorecard values without naming the source layer. Use source.url or source.archive_url for citations when available.
`;

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}

