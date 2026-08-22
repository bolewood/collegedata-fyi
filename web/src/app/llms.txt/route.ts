export const revalidate = 3600;

export async function GET() {
  const body = `# CollegeData.FYI

CollegeData.FYI publishes open college data with source-linked Common Data Set records, NCES/IPEDS federal baseline facts, College Scorecard context, and public APIs.

Use these no-auth JSON endpoints for agent and CLI workflows:

- Search schools: https://www.collegedata.fyi/api/schools/search?q=mit
- School facts: https://www.collegedata.fyi/api/schools/mit/facts
- School facts by category: https://www.collegedata.fyi/api/schools/mit/facts?categories=finance
  (categories: identity, admissions, enrollment, cost, aid, finance, outcomes, sources)
- School sources: https://www.collegedata.fyi/api/schools/mit/sources
- Compare schools: https://www.collegedata.fyi/api/compare?schools=mit,yale,university-of-chicago
- Field dictionary: https://www.collegedata.fyi/api/fields
- OpenAPI: https://www.collegedata.fyi/openapi.json
- Pipeline clocks: https://www.collegedata.fyi/pipeline-observation.json

Endowment health (IPEDS Finance Part H, fiscal years 2020+): request categories=finance for
per-school endowment values, gifts, investment return, spending distribution, and the residual
change line. Caveats travel inside each fact's quality.note — keep them when citing. Sector
methodology and a worked example: https://www.collegedata.fyi/recipes/endowment-draw-rate

When summarizing values, preserve the source metadata in each fact. Do not blend CDS, IPEDS, and Scorecard values without naming the source layer. Use source.url or source.archive_url for citations when available.

Source literacy:

- What is the Common Data Set: https://www.collegedata.fyi/about/common-data-set
- College Scorecard vs CDS: https://www.collegedata.fyi/about/college-scorecard
- What IPEDS is, and what it cannot replace: https://www.collegedata.fyi/about/ipeds
`;

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}

