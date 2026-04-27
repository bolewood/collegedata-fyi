# PRD 0111A: Docling improvement spike before VLM repair

**Status:** Draft
**Created:** 2026-04-26
**Author:** Codex + Anthony
**Related:** [PRD 011](011-academic-profile-llm-repair.md), [PRD 010](010-queryable-data-browser.md), [PRD 005](005-full-schema-extraction.md), [PRD 006](006-llm-fallback.md), [Extraction Quality](../extraction-quality.md), [Architecture](../ARCHITECTURE.md)

---

## Context

PRD 011 proposes adding GPA, SAT, and ACT fields to the queryable browser, with
DeepSeek-OCR as a targeted local repair layer for flattened-PDF cases where current
Tier 4 extraction misses or mangles the relevant tables.

That plan is directionally sound, but there is a cheaper question to answer first:

> Are we using Docling correctly and completely?

The recent Docling talk notes suggest several places where our current Tier 4 path
may be leaving quality on the table:

- Docling's canonical output is the rich Docling document model, not markdown.
- Markdown export is intentionally lossy.
- Docling documents can be exported as lossless JSON, according to the current docs.
- Docling carries table objects, hierarchy, layout, page numbers, reading order, and
  bounding boxes.
- Docling exposes APIs for custom serialization and enrichment.
- Its PDF pipeline includes specialized layout and table-structure models; the docs
  now call out Heron as the default layout model for faster PDF parsing.
- It has extensive OCR support for scanned PDFs/images.
- It supports visual-language-model paths such as GraniteDocling.
- Its structured information extraction API is documented as beta.
- The beta extraction example currently exposes a `DocumentExtractor` API for PDF and
  image inputs, with schema templates supplied as strings, dictionaries, or Pydantic
  models.

The Docling workshop transcript in `.context/attachments/pasted_text_2026-04-26_21-12-37.txt`
reinforces the same point more concretely. The later Docling talk transcript in
`.context/attachments/pasted_text_2026-04-26_21-14-51.txt` adds the strategic
framing: Docling is meant to be the low-cost, local, structured conversion substrate;
VLMs are most useful when a document is scanned, visually complex, or otherwise not
recoverable through deterministic document conversion. The additional Docling talk
transcript in `.context/attachments/pasted_text_2026-04-26_21-16-54.txt` reinforces
the same architecture and adds one relevant distinction: document conversion and
schema-guided extraction are separate Docling use cases.

The core API path is:

```python
result = DocumentConverter(...).convert(path)
doc = result.document
```

That `DoclingDocument` contains pages, tables, pictures, hierarchy, and item
references. It can be exported to markdown, HTML, text, dict/JSON, or `doc_tags`, but
those exports are downstream views. For our Common Data Set use case, the spike
should treat markdown as one serialization, not the primary representation.

The project currently treats Docling primarily as a markdown producer. The Tier 4
cleaner then tries to reconstruct CDS schema fields from that markdown. If the markdown
export loses table structure that still exists in the Docling document model, we may
be reaching for DeepSeek-OCR too early.

This spike exists to answer that before we add another model stack.

## Thesis

Some of the Tier 4 quality gap may be self-inflicted by:

1. exporting Docling output to markdown too early
2. not persisting Docling JSON/layout metadata
3. not inspecting Docling table objects directly
4. not using the best available Docling options for tables, OCR, page images, or
   enrichment
5. not using Docling layout metadata to target repair crops
6. not preserving Docling item references as extraction provenance
7. treating programmatic PDFs and scanned/bitmap PDFs as one extraction class
8. running a heavier OCR/VLM path before proving the cheaper Docling path has failed

If that thesis is true, the right path is:

```text
Docling document model -> deterministic CDS parser
Docling layout crop -> VLM/OCR repair only when needed
```

instead of:

```text
Docling markdown fails -> VLM/OCR repair
```

## Workshop takeaways to validate

These are concrete practices from the workshop transcript that should be validated
against our codebase before any DeepSeek-OCR implementation.

### Step 0: pin the actual runtime

Before any fixture comparison, verify the exact Docling runtime used by the extraction
worker. The project currently declares `docling>=2.0`, so local docs, a developer
virtualenv, and the production worker may not be using the same behavior.

Required checks:

- run `pip show docling docling-core` inside the worker environment that actually runs
  extraction
- record `docling`, `docling-core`, OCR backend, and relevant model versions in the
  findings doc
- run the spike fixture set against that pinned version
- if testing newer Docling features such as Heron or lossless JSON requires an upgrade,
  make that a separate `post-upgrade` comparison arm

Do not make a production recommendation based only on a newer local package.

### Verify documented capabilities against our installed version

The current Docling docs advertise several capabilities that matter directly for this
project, but the spike should verify them locally before designing around them:

- lossless JSON export
- Heron layout model as the default PDF layout model
- table structure extraction
- reading order extraction
- OCR support for scanned PDFs/images
- VLM support through GraniteDocling
- structured information extraction beta
- DocTags export

Practical check:

- record `docling` and `docling-core` versions in the findings doc
- run one representative PDF through the CLI and Python API
- confirm which export modes are available: markdown, HTML, DocTags, lossless JSON
- confirm whether Heron is active by default in our environment
- confirm which OCR and VLM integrations are actually installed vs merely documented

### Use Docling's native tables

Docling table items expose the full 2D table grid and can be exported directly to a
pandas DataFrame. For CDS Section C, this matters more than generic markdown quality.
The spike should test whether C9/C11/C12 tables are present as `TableItem` objects
even when the markdown cleaner fails. The talks also specifically call out high-quality
table representation for complex cells, including multi-span cells; the spike should
verify whether that survives in our current Docling version and fixture PDFs.

Practical check:

- iterate through `doc.iterate_items()`
- select table items
- export each table to DataFrame, markdown, and HTML
- retain page number, document reference, and any available box/cell metadata
- compare direct table parsing against current markdown parsing

### Generate page and picture images during conversion

Docling conversion options can include bitmap representations of pictures and full
page images. The workshop framed this as useful for visualization and later cropping.
For us, it is the bridge between deterministic layout detection and targeted VLM
repair.

Practical check:

- enable page image generation for selected fixtures
- persist deterministic page image artifact paths or hashes
- verify whether table/picture references can be mapped back to page images
- use that mapping to propose C9/C11/C12 crop candidates

### Tune pipeline options deliberately

The workshop called the converter format options the main place to change Docling
behavior. Relevant knobs include image scale, table-structure activation, OCR
activation, page image generation, picture image generation, enrichment, and page batch
size.

The most relevant optimization note: if OCR is not needed, it is often the largest
runtime cost. The minimum useful pipeline for many digital PDFs is parsing plus layout;
table-heavy work needs the table-structure model; scanned or bitmap-only pages need
OCR. That suggests a staged strategy:

1. parse/layout/table structure for normal PDFs
2. route bitmap-only or weak-text pages to OCR
3. route validated table failures to targeted VLM repair

The spike should record the exact option set in artifact provenance so later extraction
quality reports can explain behavior changes.

### Preserve visual grounding

Docling chunks/items carry references back to the source document elements. The workshop
used this for visual grounding: answers can be tied back to the page region that
supported them.

For browser data, this should become provenance rather than UX decoration:

- document id
- page number
- Docling item reference
- table id or picture id
- bounding box or crop coordinates when available
- serialized table snippet or repaired markdown used for parsing

This is more useful than inventing confidence scores. It lets a reviewer trace why a
field value entered `cds_fields`.

### Customize table serialization only after preserving structure

The workshop showed that Docling chunking can serialize tables in different ways, such
as markdown tables or row/column/value triplets. For CDS parsing, row/column/value
triplets may be easier to parse deterministically than markdown for some tables.

The spike should compare at least:

- DataFrame/native grid parsing
- markdown table serialization
- row/column/value triplet serialization if available
- current full-document markdown cleaner

### Treat multimodal enrichment as optional repair, not default extraction

Docling can call local or remote VLMs during conversion to describe pictures, and can
also use a VLM pipeline such as Small Docling. That is powerful, but not obviously the
right first move for 4,000 Common Data Set PDFs.

For this project, enrichment should remain downstream of deterministic attempts:

```text
Docling native table/layout succeeds -> deterministic parser
Docling native table/layout fails but locates region -> targeted repair crop
Docling cannot locate region -> broader page OCR/VLM fallback
```

### Deprioritize agent/MCP workflows for this spike

The workshop's MCP, Llama Stack, LM Studio, and Pydantic AI examples are useful for
general document-AI applications, but they are not central to our extraction pipeline.
The relevant lesson is structured schema extraction plus traceable provenance, not the
agent framework itself.

### Route programmatic and scanned PDFs differently

The later talk draws a useful distinction:

- cheap PDF parsers are fast but lose structure
- general VLMs preserve more visual semantics but can skip content because they are
  autoregressive
- Docling's value is the middle path: local structured conversion into a consistent
  pydantic document model

For Common Data Set extraction, that implies a routing policy:

```text
programmatic PDF -> Docling parse/layout/table structure -> deterministic parser
bitmap/scanned PDF -> Docling OCR or OCR model plugin -> deterministic parser
Docling failure with known region -> targeted VLM/table repair
unlocalized failure -> backlog/manual review
```

The spike should explicitly classify fixture documents by source type before comparing
results. Otherwise we risk averaging together easy programmatic PDFs and genuinely hard
scanned PDFs, which would hide the right intervention.

### Evaluate Docling-core as the downstream dependency

The talk mentions `docling-core` as the lightweight package that contains the shared
type definitions for downstream work on Docling documents. If the extraction worker
persists a Docling document dict/JSON, later parsing and validation may not need the
full converter/runtime dependency.

Practical check:

- can Tier 4 persist a compact `DoclingDocument` dict/JSON artifact?
- can a browser-field parser load that artifact using `docling-core` only?
- does this reduce coupling between conversion and projection?
- can artifact version/config metadata be stored beside the document model?

### Validate model-plugin claims before separate DeepSeek-OCR plumbing

The talk claims Docling has been integrating several OCR/document models, including
Falcon OCR, GLM OCR, and DeepSeek-OCR. Treat that as a lead to verify in current
official docs and code, not as an accepted dependency decision.

If DeepSeek-OCR can run inside Docling's pipeline or enrichment interface and still
produce a normal Docling document model, that may be cleaner than building a separate
sidecar format. If it only emits markdown or bespoke JSON, PRD 011's separate repair
candidate table remains the safer boundary.

Validation question:

```text
Can DeepSeek-OCR be used through Docling while preserving page/table/item provenance?
```

If yes, prefer that integration path for the pilot. If no, keep DeepSeek-OCR behind a
provider adapter and store its output as repair candidates only.

### Evaluate schema extraction as a benchmark, not the source of truth

The latest transcript distinguishes full document conversion from schema-guided
information extraction: in extraction mode, the caller supplies a document and a
concrete schema for the desired fields. The current docs also mark structured
information extraction as beta, which is useful but should keep it out of the primary
promotion path for now.

This is not on the critical path for this spike. Test it only if the native
Docling-document/table inspection leaves time. The main work is determining whether
Docling JSON and native tables contain recoverable C9/C11/C12 structure.

The current beta example uses:

```python
from docling.datamodel.base_models import InputFormat
from docling.document_extractor import DocumentExtractor

extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])
result = extractor.extract(source=file_path, template=Template)
```

The returned shape is page-organized. Each page result includes at least:

- `page_no`
- `extracted_data`
- `raw_text`
- `errors`

That is useful, but the public example does not show bounding boxes, Docling item
references, table references, or evidence spans. Until verified otherwise, this means
schema extraction should be treated as page-local candidate generation, not as a
provenance-complete extraction path.

One important footgun: the Pydantic template examples allow defaults and optional
fields. For CDS extraction, defaults must not be interpreted as extracted facts. Any
schema-extraction pilot should use nullable fields with explicit missing semantics and
must reject default-filled values unless the raw model output clearly supports them.

This is relevant to CDS, but the trust boundary should stay conservative. A
schema-guided extractor could be useful as:

- a comparison arm in the spike
- a repair candidate generator for missing C9/C11/C12 fields
- a way to identify likely page/table regions

It should not directly promote browser values unless the same deterministic validators
and provenance requirements pass.

Practical check:

- can Docling's extraction API express a C9/C11/C12 academic-profile schema?
- does it return evidence/provenance, or only values?
- does `raw_text` preserve the original generated JSON well enough for auditing?
- does it preserve the distinction between missing, not reported, and failed
  extraction?
- does it outperform native table parsing on malformed CDS fixtures?
- can we prevent Pydantic defaults from being mistaken for extracted values?

Default decision: out of scope unless Outcomes A/B/C cannot be distinguished from
native document/table parsing alone.

### Track benchmark and annotation ecosystem, but do not wait for it

The talk mentions an upcoming evaluation framework, structured-output standard, and
annotation workflows. These are relevant to long-term extraction quality, but they
should not block this spike.

Backlog implication:

- monitor Docling's evaluation framework once available
- consider a tiny human-labeled CDS benchmark for C1/C9/C11/C12
- compare Docling upgrades against that benchmark before broad reprocessing

For now, the project should use its own small fixture set and deterministic validators.

## Goals

1. Synthesize current Docling best practices from docs, talks, and examples.
2. Audit the current collegedata.fyi Tier 4/Tier 5 code against those practices.
3. Run a small measured comparison on browser-relevant failures.
4. Decide what belongs in PRD 011, what belongs in a separate Tier 4 improvement
   PRD, and what should remain backlog-only.

## Non-goals

- Rewriting the Tier 4 cleaner during the spike.
- Fully adopting Small Docling.
- Replacing Docling with DeepSeek-OCR.
- Running a full-corpus re-extraction.
- Adding GPA/SAT/ACT fields to production.
- Building a generalized document-AI benchmark suite.

## Questions to answer

### Docling representation

- What is the full Docling document model shape today?
- What table, cell, section, group, page, and bounding-box metadata does it expose?
- How are multi-span table cells represented?
- What do we lose when exporting to markdown?
- Can we serialize and persist the Docling document model compactly enough for our
  corpus?
- Does the JSON include enough page/table locality to support crop generation for
  repair models?

### Tables and layout

- How should code access Docling table structure directly?
- Do C9/C11/C12 failures already have useful table objects in Docling JSON?
- Does `TableItem.export_to_dataframe()` or equivalent expose a cleaner grid than
  markdown for CDS parsing?
- Are row spans, column spans, header cells, and cell bounding boxes available?
- Does Docling preserve enough hierarchy to know that a table belongs to Section C9,
  C11, or C12?
- Are current failures caused by Docling itself, the markdown serializer, or our
  cleaner's markdown parser?

### OCR and scanned PDFs

- Are we using the best OCR configuration for Tier 5?
- Should some Tier 4 PDFs with weak text layers be routed through OCR or hybrid OCR?
- Are there Docling options for selecting OCR engine, force OCR, bitmap handling, or
  table structure that we are not using?
- Can OCR/model configuration be recorded in artifact provenance?
- Can we classify PDFs as programmatic, weak-text, or scanned/bitmap-heavy before
  choosing extraction cost?
- Does the current Docling version expose OCR/model plugins that would let us test
  DeepSeek-OCR inside the Docling pipeline?

### Page and crop targeting

- Can Docling layout metadata identify likely C9/C11/C12 page regions?
- Can we crop table regions directly from Docling boxes?
- Would Docling JSON make DeepSeek-OCR repair cheaper by sending table crops instead
  of full pages?

### Enrichment

- Does Docling's enrichment interface fit our repair-candidate architecture?
- Could DeepSeek-OCR or Small Docling be integrated as a Docling enrichment model
  rather than a separate sidecar pipeline?
- What is the cleanest provenance model if a value comes from Docling plus an
  enrichment pass?

### Schema extraction

- Does Docling's schema-guided extraction API exist in the current release we can use?
- Can it return evidence/provenance sufficient for repair candidates?
- Is output limited to page-level provenance, or can it expose boxes/items/tables?
- Does it handle C9/C11/C12 better than native table parsing, or does it mainly add
  model risk?
- Should it be included in PRD 011 as an optional pilot mode?
- Does it require `docling[vlm]`, and is that feasible on the M5 Pro overnight path?

### Small Docling

- Is Small Docling or GraniteDocling available and runnable in our environment?
- Does it produce `doc_tags` or a Docling document model that is easier to parse than
  current markdown?
- Is it mature enough to test on a few C9/C11/C12 pages?
- What failure modes does it introduce, such as repetition loops or hallucination?

### Coming-soon features

- Are chart-understanding, metadata extraction, or other coming-soon features relevant
  to CDS now?
- Should any of them be tracked as backlog only?

Initial answer: chart understanding is not needed for GPA/SAT/ACT browser fields and
should not affect this spike unless a CDS table is represented as a chart image.

## Work plan

### Step 1: Synthesize minimum best practices

Read and summarize:

- official Docling docs
- Docling core / `DoclingDocument` serialization docs
- Docling table extraction docs/examples
- Docling JSON/document model docs
- Docling OCR configuration docs
- Docling conversion/pipeline options docs
- Docling feature/what's-new page only for version-sensitive claims
- the already-read 2026-04-26 transcript notes as context

Deliverable:

`docs/plans/docling-improvement-spike-findings.md`

This should include a practical checklist, not just notes.

Suggested checklist columns:

| Area | Best practice | Why it matters for CDS | Source |
|---|---|---|---|
| document model | Persist JSON before markdown | Avoid losing table/layout metadata | Docling docs/talk |
| export | Prefer lossless JSON for artifacts | Gives parser iterations a stable source | Docling docs |
| layout | Verify Heron default behavior | Layout model changes can alter table recovery | Docling docs |
| tables | Parse table objects directly | C9/C11/C12 are table-heavy | Docling docs/talk |
| layout | Use boxes/page numbers for crops | Cheaper targeted VLM repair | Docling docs/talk |
| runtime | Avoid OCR unless needed | Keeps overnight processing feasible | Docling workshop |
| provenance | Preserve item references | Lets values be traced without fake confidence | Docling workshop |
| routing | Classify programmatic vs scanned PDFs | Apply the cheapest reliable extractor first | Docling overview talk |
| dependency | Use `docling-core` downstream if possible | Decouples parsing from conversion runtime | Docling overview talk |
| extraction | Treat beta schema extraction as candidate generation | Useful, but values still need validation | Docling docs/talk |
| extraction | Avoid default-filled extracted facts | Pydantic defaults can mask missing values | Docling extraction docs |

### Step 2: Audit current code

Audit at minimum:

- `tools/extraction_worker/tier4_extractor.py`
- `tools/extraction_worker/tier4_cleaner.py`
- `tools/extraction_worker/worker.py`
- Tier 5 OCR routing and options
- `cds_artifacts.notes` shape for Tier 4/Tier 5 artifacts
- any code that drops page numbers, table objects, bounding boxes, or provenance
- current Docling conversion options: OCR, table structure, page images, picture
  images, image scale, enrichment, and batch/page handling
- current Docling version and whether Heron/lossless JSON/DocTags/schema extraction
  are available in this environment
- whether `DocumentExtractor` requires the VLM extra and what model/runtime it uses by
  default
- whether `DocumentExtractor` outputs more provenance than `page_no`, `raw_text`,
  `extracted_data`, and `errors`
- whether Tier 4 artifacts retain the source `DoclingDocument` dict/JSON, not only
  markdown/text
- whether current artifacts or notes record enough information to tell programmatic,
  weak-text, and scanned PDFs apart
- whether a persisted Docling artifact can be parsed later without rerunning conversion

Deliverable:

A gap table:

| Area | Current behavior | Best practice | Gap | Impact | Recommendation |
|---|---|---|---|---|---|

Classify each recommendation:

- `implement now`
- `include in PRD 011`
- `separate PRD`
- `backlog`
- `do not do`

### Step 3: Run a small comparison

Use a tiny failure-stratified fixture set. Do not headline Harvard/Yale/Dartmouth
unless they are known Tier 4 failures for the fields under test.

Suggested sample:

- 8-12 `producer='tier4_docling'` flattened-PDF artifacts from the bottom quartile of
  `notes.stats.schema_fields_populated`
- at least 5 documents where C9/C11/C12 SAT/ACT/GPA fields are missing or malformed
- 2 scanned or OCR-sensitive PDFs if easy to include
- 1-2 elite/high-quality docs as sanity checks only
- avoid XLSX/fillable-PDF fixtures unless testing regression from routing mistakes

Preferred selection query shape:

```sql
select d.id, d.school_id, d.source_format, a.notes
from public.cds_artifacts a
join public.cds_documents d on d.id = a.document_id
where a.producer = 'tier4_docling'
  and a.kind = 'canonical'
  and d.source_format = 'pdf_flat'
order by (a.notes->'stats'->>'schema_fields_populated')::int asc
limit 50;
```

Compare:

1. Current Docling markdown + current cleaner
2. Docling document JSON/table objects + a throwaway narrow C9 parser
3. Docling table DataFrame/native grid + the same narrow C9 parser
4. Docling document JSON/layout targeting + current cleaner context
5. Alternate Docling layout/OCR/table/page-image options, including Heron/default
   behavior if configurable
6. Optional, time permitting: Docling schema-guided extraction for C9/C11/C12
7. Optional: GraniteDocling/Small Docling on selected page images

Important scope guard:

- If no parser is written, this spike can only conclude "native structure is present"
  or "native structure is absent." It cannot claim JSON/table parsing beats the
  production markdown cleaner.
- If a parser is written, keep it intentionally narrow: C9 SAT/ACT rows first. C11/C12
  can be inspected for structure presence unless time remains.

Metrics:

- C1 admissions fields recovered or regressed
- C9 SAT/ACT fields recovered
- C11/C12 GPA fields recovered
- table object availability
- page/box locality availability
- parser complexity
- artifact size if JSON is persisted
- lossless JSON artifact usability
- runtime
- page/crop localization availability
- provenance quality: can a value be traced back to a page/table/item?
- extraction-route appropriateness: did we use the cheapest route that can plausibly
  preserve structure for this source type?
- schema-extraction evidence quality if tested
- schema-extraction default/missing-value behavior if tested
- regression risk to existing Tier 4 behavior
- Docling conversion failure rate on the sampled corpus
- whether production adoption invalidates existing `tier4_llm_fallback` cache entries
- artifact storage size for markdown-only vs markdown + Docling JSON

### Step 4: Decision memo

Write a concise decision memo with:

1. what Docling best practices we were missing
2. what our code currently throws away
3. measured impact on the fixture set
4. recommendations by priority
5. how PRD 011 should change
6. whether DeepSeek-OCR is still justified after Docling improvements
7. cache, storage, and producer-precedence implications of any recommended production
   change

## Decision thresholds

Set these thresholds before running the comparison:

- **Outcome A: Docling JSON/native tables should become the primary academic-profile
  path** if a narrow parser recovers at least 70% of target C9/C11/C12 fields on the
  failure-stratified fixtures without OCR/VLM repair, with no C1 regression on sanity
  fixtures.
- **Outcome B: Docling config change is enough** if changing conversion options improves
  target-field recovery by at least 20 percentage points over the current baseline and
  does not materially increase runtime or regress existing cleaner output.
- **Outcome C: Docling layout should feed repair** if field recovery stays below 70%
  but Docling can localize at least 80% of missing target-field sections/pages/tables
  well enough to generate repair crops.
- **Outcome D: DeepSeek-OCR remains primary repair path** if native structure recovery
  is below 70% and localization is below 80%, or if parser/storage/migration cost is
  disproportionate to measured recovery.

These are spike thresholds, not permanent product-quality gates. They exist to prevent
post-hoc interpretation of a small sample.

## Expected outcomes

### Outcome A: Docling JSON fixes enough

If Docling table objects meet the Outcome A threshold, then:

- update PRD 011 to make Docling JSON parsing the primary academic-profile path
- use DeepSeek-OCR only as a fallback for pages where Docling JSON fails validation
- add a Tier 4 improvement task to persist Docling JSON for new artifacts
- write a follow-on PRD for the JSON-mode cleaner, including dual-mode operation for
  existing markdown-only artifacts
- estimate `tier4_llm_fallback` cache invalidation cost before changing the markdown
  serializer or producer output

### Outcome B: Docling config fixes enough

If better Docling options materially improve output, then:

- implement the option changes in Tier 4/Tier 5
- record extraction config in artifact provenance
- run a targeted re-projection before considering VLM repair
- bump producer/config version deliberately and document cache implications

### Outcome C: Docling layout helps, but parsing still fails

If Docling cannot recover the table but can locate the page/region, then:

- keep DeepSeek-OCR repair in PRD 011
- use Docling layout metadata for crop targeting
- avoid full-page/full-PDF VLM calls where table crops are available
- generate page images/crops on demand for repair, not by default across the corpus

### Outcome D: Docling is already maximized

If our current usage is close to best practice and JSON/table objects do not help,
then:

- PRD 011 remains the right direction
- the spike becomes justification for adding DeepSeek-OCR repair
- backlog only small Docling/Docling Serve exploration

## Implementation notes to validate

These are hypotheses, not accepted facts:

- Markdown is likely losing table metadata important for CDS C9/C11/C12.
- Docling JSON likely contains page/table/cell locality we can use.
- Persisting Docling JSON may be storage-affordable if compressed or limited to
  Tier 4/Tier 5.
- A Docling-JSON parser may be simpler than a VLM repair path for some academic
  profile fields.
- Small Docling is probably not production-ready for this workflow, but may be worth
  a small side experiment.
- Native Docling tables may let us parse C9/C11/C12 from DataFrames even when the
  markdown export is malformed.
- Page image generation plus item references may give us deterministic repair crops
  without running a VLM over whole PDFs.
- OCR should probably be conditional, not always-on, for cost and runtime reasons.
- Persisted Docling artifacts plus `docling-core` may let us iterate on CDS parsing
  without rerunning expensive conversion.
- DeepSeek-OCR may fit better as a Docling pipeline/enrichment option than as a
  bespoke sidecar, but that must be verified against current docs/code.
- Docling's schema-guided extraction may be useful for candidate generation, but
  direct value promotion would violate the current validation-first design.
- The beta extraction example appears to provide page-level output but not visual
  grounding; if that is all the API exposes, it is weaker provenance than Docling
  document/table parsing.
- Pydantic validation validates shape/type, not whether the model read the document
  correctly. It must be followed by CDS-specific deterministic validation.
- Pydantic defaults in extraction templates are dangerous for CDS and should be
  avoided or explicitly marked as non-extracted defaults.
- The official docs' "lossless JSON" claim, if available in our installed version,
  strengthens the case for persisting Docling artifacts before markdown.
- Heron may improve speed or layout quality, but any model-default change needs
  fixture comparison before broad reprocessing.
- Chart understanding is backlog-only for now; it is not on the critical path for
  C9/C11/C12 unless schools publish those values only as chart images.
- A JSON-first production path would need a migration plan: dual-mode cleaner support,
  backfill/reprocessing cost, fallback cache strategy, storage strategy, and
  producer-precedence semantics.

## Candidate provenance shape

Any follow-on implementation should make provenance explicit before exposing it through
`cds_fields` or browser APIs.

Candidate shape:

```json
{
  "document_id": "uuid",
  "artifact_id": "uuid",
  "source_storage_path": "school/year/hash.pdf",
  "page_no": 12,
  "docling_item_ref": "#/texts/123",
  "table_id": "table-7",
  "cell_ref": {"row": 4, "col": 2},
  "bbox": {"l": 10.0, "t": 20.0, "r": 200.0, "b": 260.0, "coord_origin": "top-left"},
  "source_serializer": "docling-json",
  "docling_version": "x.y.z",
  "docling_core_version": "x.y.z",
  "extraction_config_version": "tier4-docling-json-c9-v0"
}
```

Treat this as a contract candidate, not an implementation requirement for the spike.

## Deliverables

1. `docs/plans/docling-improvement-spike-findings.md`
2. Current-code audit table
3. Small fixture comparison results
4. PRD 011 revision recommendations
5. Backlog updates for any deferred work
6. Storage strategy recommendation: inline JSONB vs sidecar artifact vs object storage
7. Producer-precedence recommendation for any new Tier 4 producer/version
8. Cache-invalidation note for `tier4_llm_fallback`

## Timebox

This should be a one- to two-day spike.

If the spike takes longer, it is probably turning into implementation. Stop and write
the decision memo before changing production extraction behavior.

Budget guidance:

- Step 0/1 should take less than 25% of the spike.
- Step 2/3 should take more than 60% of the spike.
- Schema extraction, GraniteDocling, Small Docling, and DeepSeek-OCR integration are
  optional only after the native table/document question is answered.

## Acceptance criteria

The spike is complete when:

- Docling best practices have been summarized with sources.
- Current Tier 4/Tier 5 code has been audited against those practices.
- At least 10 representative documents/pages have been compared.
- Fixtures were selected from real Tier 4 failure populations, not only elite/high
  quality schools.
- At least one comparison arm either includes a narrow parser or explicitly limits its
  conclusion to structure presence.
- We can answer whether to prioritize:
  - Docling JSON/table parsing
  - Docling option/config changes
  - DeepSeek-OCR repair
  - Small Docling exploration
- PRD 011 has been updated or explicitly left unchanged based on findings.
