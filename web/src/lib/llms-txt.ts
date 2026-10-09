import { SITE_URL } from "./sitemap-static";

/**
 * /llms.txt body in the llmstxt.org format.
 * Endpoint list is the no-auth friendly surface from openapi.json — do not invent paths.
 */
export const LLMS_TXT = `# CollegeData.FYI

> The most comprehensive free college data we know of — each school’s Common Data Set, plus IPEDS and College Scorecard, in one public place.

Structured Common Data Set data, NCES/IPEDS federal baseline facts, and College Scorecard context are available as no-auth JSON from the public API. Please use the API rather than scraping HTML school pages.

When summarizing values, preserve the source metadata in each fact. Do not blend CDS, IPEDS, and Scorecard values without naming the source layer. Use source.url or source.archive_url for citations when available.

The dataset is MIT-licensed. Underlying Common Data Set documents are owned by their respective institutions and reproduced here under their public-document status.

Endowment health (IPEDS Finance Part H, fiscal years 2020+): request categories=finance for per-school endowment values, gifts, investment return, spending distribution, and the residual change line. Caveats travel inside each fact's quality.note — keep them when citing.

## API

- [API docs](${SITE_URL}/api): Human-readable documentation for the no-auth JSON surface, MCP connector, snapshots, and PostgREST archive
- [MCP](${SITE_URL}/api/mcp): Streamable HTTP; paste as a Claude custom connector. No API key
- [Search schools](${SITE_URL}/api/schools/search?q=mit): Find a school by name or alias
- [School facts](${SITE_URL}/api/schools/mit/facts): Source-labeled facts for one school
- [School facts by category](${SITE_URL}/api/schools/mit/facts?categories=finance): categories: identity, admissions, enrollment, cost, aid, finance, outcomes, sources
- [School sources](${SITE_URL}/api/schools/mit/sources): Source ledger for one school
- [Compare schools](${SITE_URL}/api/compare?schools=mit,yale,university-of-chicago): Sparse comparison matrix
- [Field dictionary](${SITE_URL}/api/fields): V1 friendly field definitions
- [Snapshots](${SITE_URL}/api/snapshots): Public snapshot manifest links
- [OpenAPI](${SITE_URL}/openapi.json): Machine-readable spec for the friendly endpoints

## Optional

- [What is the Common Data Set](${SITE_URL}/about/common-data-set): School-authored yearly report
- [College Scorecard vs CDS](${SITE_URL}/about/college-scorecard): Federal outcomes vs the school's own filing
- [What IPEDS is, and what it cannot replace](${SITE_URL}/about/ipeds): Federal baseline facts
- [Endowment draw-rate recipe](${SITE_URL}/recipes/endowment-draw-rate): Sector methodology and a worked example
- [Pipeline clocks](${SITE_URL}/pipeline-observation.json): Operator freshness board
`;
