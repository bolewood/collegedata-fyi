import { SITE_URL } from "./sitemap-static";

/**
 * /llms.txt body in the llmstxt.org format.
 * Endpoint list is the no-auth friendly surface from openapi.json — do not invent paths.
 */
export const LLMS_TXT = `# CollegeData.FYI

> The most comprehensive free college data we know of — each school’s Common Data Set, plus IPEDS and College Scorecard, in one public place.

Structured Common Data Set data, NCES/IPEDS federal baseline facts, and College Scorecard context are available as no-auth JSON from the public API. Please use the API rather than scraping HTML school pages: \`/schools*\` pages are limited to 120 requests per minute per IP. Send a short X-CollegeData-Client header naming your app, and follow 308 redirects (alias school slugs redirect to the canonical school_id).

\`/api/schools*\` and \`/api/compare\` allow 300 requests per minute per IP. Exceeding that returns HTTP 429; wait a minute and retry. Cache responses when you can, or email contact@bolewood.com for bulk needs.

When summarizing values, preserve the source metadata in each fact. Do not blend CDS, IPEDS, and Scorecard values without naming the source layer. Use source.url or source.archive_url for citations when available.

The dataset is MIT-licensed. Underlying Common Data Set documents are owned by their respective institutions and reproduced here under their public-document status.

Endowment health (IPEDS Finance Part H, fiscal years 2020+): request categories=finance for per-school endowment values, gifts, investment return, spending distribution, and the residual change line. Caveats travel inside each fact's quality.note — keep them when citing.

## API

- [API docs](${SITE_URL}/api): Human-readable documentation for the no-auth JSON surface, MCP connector, snapshots, and PostgREST archive
- [MCP](${SITE_URL}/api/mcp): Streamable HTTP; paste as a Claude custom connector. No API key
- [Search schools](${SITE_URL}/api/schools/search?q=mit): Find a school by name or alias
- [Look up a school by IPEDS id](${SITE_URL}/api/schools/search?ipeds_id=166683): Exact match on the six-digit federal unit id
- [School facts](${SITE_URL}/api/schools/mit/facts): Source-labeled facts for one school
- [School facts by category](${SITE_URL}/api/schools/mit/facts?categories=finance): categories: identity, admissions, enrollment, cost, aid, finance, outcomes, sources
- [School sources](${SITE_URL}/api/schools/mit/sources): Source ledger for one school
- [Compare schools](${SITE_URL}/api/compare?schools=mit,yale,university-of-chicago): Sparse comparison matrix
- [Field dictionary](${SITE_URL}/api/fields): V1 friendly field definitions
- [Snapshots](${SITE_URL}/api/snapshots): Bulk files (schools, school_facts, sources, field dictionary), usually regenerated within the hour from live data; check generated_at
- [Latest snapshot manifest](${SITE_URL}/snapshots/latest/manifest.json): Links to the JSONL and JSON files
- [PostgREST archive docs](${SITE_URL}/api): The full read-only database API at api.collegedata.fyi (needs the public anon key; see the API docs)
- [OpenAPI](${SITE_URL}/openapi.json): Machine-readable spec for the friendly endpoints

## Optional

- [What is the Common Data Set](${SITE_URL}/about/common-data-set): School-authored yearly report
- [College Scorecard vs CDS](${SITE_URL}/about/college-scorecard): Federal outcomes vs the school's own filing
- [What IPEDS is, and what it cannot replace](${SITE_URL}/about/ipeds): Federal baseline facts
- [Coverage](${SITE_URL}/coverage): Which schools have a Common Data Set archived, and which years
- [Changes](${SITE_URL}/changes): Year-over-year changes in reported fields
- [Methodology](${SITE_URL}/methodology): How fields are read and what each card means
- [Recipes](${SITE_URL}/recipes): Worked analyses with sources
- [API usage](${SITE_URL}/usage): Aggregate public API usage counts
- [Per-school RSS](${SITE_URL}/schools/mit/feed.xml): New or refreshed filings for one school
- [Endowment draw-rate recipe](${SITE_URL}/recipes/endowment-draw-rate): Sector methodology and a worked example
- [Pipeline clocks](${SITE_URL}/pipeline-observation.json): Operator freshness board
`;
