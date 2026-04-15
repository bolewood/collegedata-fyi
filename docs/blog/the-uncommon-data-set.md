# The Uncommon Data Set

*Draft — 2026-04-15*

The Common Data Set is a beautiful idea. Twenty-seven years ago, three college-guide publishers — the College Board, Peterson's, and U.S. News — sat down with a bunch of college institutional research offices and agreed on a single template for reporting the numbers that matter about a school. Enrollment. Admissions. Retention. Tuition. Financial aid. Faculty. The problem they were solving was that every guide asked for the same data in slightly different shapes, so every IR office filled out the same numbers fifteen different ways every year. The fix was obvious and good: publish one canonical template, fill it once, link to it from your institutional-research page, and be done.

The CDS Initiative still publishes that template today. It is a 47-page XLSX with 1,105 fields. It has a beautifully structured Answer Sheet tab. It has checkbox decoders for every Btn field. It is, genuinely, one of the cleanest open data standards in American higher education.

The name is "Common Data Set."

The reality is extremely uncommon.

---

I know this because I spent the last week building an index on top of it. The plan, originally, was simple: walk the list of U.S. four-year institutions from IPEDS, find each school's CDS, download it, extract the numbers, publish a public API. I had a canonical schema. I had a working Tier 2 AcroForm extractor that scored 31 out of 31 against hand-verified ground truth on Harvey Mudd. I had infrastructure. How hard could "find the PDF, parse the PDF" really be?

Here is an incomplete list of the ways in which schools publish their Common Data Set:

- As an **unflattened fillable PDF** where every answer lives in a named AcroForm field with the canonical tag the template ships with. You can extract every value in 200 milliseconds with `pypdf.get_fields()`. This is the dream. In our sample of about 500 live CDS files, it's roughly 14% of the corpus.

- As a **flattened PDF** where the form structure has been destroyed and the only way to get the numbers back is to OCR the page or run a layout-aware model like Docling or Reducto across it and then pattern-match the output against the canonical schema. 84% of the corpus.

- As an **image-only scanned PDF**, because someone at the school printed the filled template, signed it, ran it through a scanner, and uploaded the scan. You can tell because `pypdf.get_fields()` returns None and the extracted text from the first three pages is under 100 characters.

- As an **XLSX file**. The same XLSX template the CDS Initiative publishes, filled in directly. This is the theoretically ideal format — the Answer Sheet tab is machine-readable by construction — and I have not once in this project personally seen a school publish this way.

- As a **DOCX file**, because the CDS Initiative also publishes a Word version of the template and some IR offices prefer Word and some of those offices just uploaded the filled Word file.

- As an **HTML page** with the numbers rendered directly into the DOM, behind a JavaScript framework that pulls the data from a REST endpoint after the page loads, which we can't see from a static HTML parser.

- As a **Box embed**, a **SharePoint page**, a **Google Drive share**, a **Bepress Digital Commons item page** (which intercepts scrapers with a 202 Accepted response and an empty body, because 202 is apparently a honeypot now), or a **SharePoint item page behind a headless-browser-only JavaScript gate**.

- As a **direct link to a PDF whose filename has no parseable year**, like `common-data-set.pdf`, or `cds.pdf`, or `kenyon-cds-202425-march-2025.pdf`, or `CDS20162017.pdf`, or UCLA's favorite: `/file/<random-uuid>`.

- As a **multi-year archive on a single IR landing page** with 19 separate PDFs going back to 2007 (Lafayette), or 25 years (Northern Michigan), or 26 years (CMU across 111 distinct PDFs). The schools that do this are doing the right thing. They have the most complete archives in the dataset. Our original resolver walked their pages, found all the candidates, ranked them by year, and threw everything away except the most recent one, because that was the only shape our schema could absorb.

- As a **URL that looks exactly like a CDS link but is actually the blank template**, or the **Summary of Changes memo**, or a **section-only file** containing just questions A1–A6 (enrollment counts by gender) for a request somebody filed last spring.

- As a **test upload** sitting at `/cds/CDS_test_draft_v2.pdf` because the person who uploaded it forgot to swap it out for the production file (this is CSULB, and the "test" file is actually the real CDS — they just never renamed it).

- As **the same physical file** shared between two different schools via a common Google Drive link (University of Maine System and University of Southern Maine, which surfaced as a detected-year "mismatch" and turned out to be a pre-existing archive bug nobody had noticed).

---

None of this is malicious. None of it is even incompetent. It's what happens when you take a beautiful canonical template and you release it into a distributed system of 800-plus institutional-research offices, each with their own webmaster, each with their own CMS, each with their own IT policies, each with their own understanding of how "publishing data" works. Over twenty years. The CDS Initiative built a Schelling point. A Schelling point is a place you go because everyone else is going there. It is a coordination primitive. It is not a physical law. The natural state of 800-plus humans who are coordinating loosely on a standard is that some of them will drift, and the drifted ones will not be punished, and over twenty years the drift is cumulative.

Here is my favorite example. The canonical CDS PDF template prints the academic year in the top header of page 1. It says "Common Data Set 2024-2025" in 14-point type. You can extract it with a two-line regex. It is the single most reliable piece of metadata on the document.

Our original resolver didn't read it. It parsed the year out of the URL. Because when you're at the discovery layer, standing outside the PDF, the URL is all you have. Which means that when a school posts a 2024-25 CDS at `https://institutionalresearch.school.edu/sites/default/files/2020-04/CDS2009_2010.pdf`, where `2020-04` is the Drupal CMS's upload-month directory and has nothing to do with the academic year, our resolver has to work very hard to not misread the span as `2020-2004`. (The way it does this is by validating `y2 = y1 + 1`, which is exactly the kind of hack that feels clever until you realize you wrote it because the simple thing didn't work.)

We eventually moved year authority to the content layer — `detect_year_from_pdf_bytes()` reads page 1 of the PDF, matches a strict "Common Data Set YYYY-YYYY" prefix, and validates the span. It corrected seven schools whose URL-parsed year silently disagreed with the actual document year. Those seven weren't corner cases — they were documents we'd been indexing wrong for weeks without knowing it.

The detector's precision on the PDFs it can read is 100%. Its recall is 80%. The other 20% are documents where the canonical header wasn't on page 1, or was wrapped behind a respondent-information cover page, or was present but not within the same extracted-text run as the "Common Data Set" prefix, or appeared three separate times in three different academic years on the same page because the school published a comparison grid. One school (American University) has a 47-page flattened CDS whose only parseable year span in the entire extractable text is `2006-07`, appearing on page 20 as a section J reference year. If we'd enabled a more permissive regex to catch the 20% we miss, we would have silently mis-dated American University by 18 years.

Every one of these is a real story. Every one of them has a commit. Every one of them is a few hours of someone going "wait, that can't be right" followed by a small careful fix that makes the system dumber and more strict and therefore more correct.

---

Here is the thing I want anyone reading this to understand.

The consumer of this dataset — a parent, a journalist, a researcher, a student — wants to ask one question: *what was Yale's 2024-25 first-year enrollment?* They expect one number back. They do not want to hear about AcroForm fields, `pypdf.get_fields()`, the y2 = y1 + 1 invariant, the strict prefix-anchored regex ladder, the Bepress 202 honeypot, the American University reference trap, Lafayette's 19 year archive, the SHA-addressed storage bucket that has to preserve every version forever because we can't trust any URL to be stable, or the unique constraint on `(school_id, sub_institutional, cds_year)` that we had to invent a sentinel for because the resolver can't always tell what year a file is when it's first archived.

They want one number. One query. One answer.

The abstraction they want is backed by about 2,000 lines of code that exists precisely because the "Common" Data Set isn't. That code is not overbuilt. It is not even close to overbuilt. Every single feature in it — every edge case, every fallback, every strict invariant, every deliberately-missed-recall — is there because a real school did a real thing that broke the previous version of the resolver.

This is what it takes to build an index on top of an open standard that was agreed upon by humans rather than enforced by code.

The CDS Initiative did the hard thing twenty-seven years ago: they got three publishers and a bunch of IR offices in a room and got everyone to agree on 1,105 fields. They built the Schelling point. Twenty-seven years of distributed drift later, the Schelling point still exists — it's still the single most complete higher-education data standard in the country — but it needs an index.

That index is us. We're absorbing the drift so you don't have to.

And honestly? If this post is how you found out about it, you should know that "the Common Data Set is a beautiful idea that shattered into a thousand slightly different pieces the moment it left the room" is the *best* story I've gotten to tell about an engineering project in years. The evidence is in the code. The vision is in the name. The reality is the project.

The "Common" in Common Data Set is doing a lot of work. We're doing the rest.
