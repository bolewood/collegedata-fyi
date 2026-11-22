# Recrawl from a residential network — 2026-11-22

The cloud recrawl in `../recrawl-timeouts/` got HTTP 403 on 399 of 446
homepages. This is the same 446 UNITIDs, the same script, flags and finder
user agent, run from a residential connection. Review-only: nothing was
archived or enqueued, and nothing went through the WAF/headless path.

## Counts

| Outcome | Cloud VM | Residential |
| --- | ---: | ---: |
| yes (CDS listing found) | 0 | 6 |
| no (homepage reached, no CDS on IR hubs) | 13 | 325 |
| unclear | 433 | 115 |

So most of the first crawl's unclear rows were the VM's network, not the
schools.

## The 6 yes rows, checked by hand

| School | UNITID | Result |
| --- | --- | --- |
| Drew University | 184348 | New seed. `https://drew.edu/about/institutional-research/` lists its own CDS for 2013-14 to 2021-22 as Google Drive files. |
| Great Falls College Montana State University | 180249 | New seed. The IR page links `https://www.gfcmsu.edu/campus-departments/institutional-effectiveness/common-data-set/`, which lists PDFs from 2010-11 on. |
| Southeastern Louisiana University | 160612 | Already seeded; the stored seed redirects to the live page. The CDS is published as one PDF per section (A to J), which the archiver does not assemble. |
| Southern Oregon University | 210146 | Already seeded. |
| University of Wisconsin-Superior | 240426 | Already seeded. The only CDS link is a SharePoint file. |
| Drury University-College of Continuing Professional Studies | 492801 | Parent collision: the page is Drury University's own listing. Not seeded. |

## Still unclear (115)

| Reason | Count |
| --- | ---: |
| HTTP 403 | 85 |
| HTTP 404 on every homepage variant | 8 |
| HTTP 307 / 302 not resolved to a page | 9 |
| Timeout after 25s + retry + variants | 4 |
| DNS miss only | 2 |
| Network error | 2 |
| HTTP 5xx / 521 | 3 |
| HTTP 429 | 1 |
| HTTP 405 | 1 |

The 85 that answer 403 from a residential address as well are refusing
the finder's self-identified user agent. They are not confirmed misses.
Reaching them means a browser fetch, which this audit deliberately left
out.

## What a "no" means here

A school is "no" once its homepage loads and no fetched page lists a CDS.
The script then tries real IR links from the homepage and up to six
well-known paths; a 404 on a guessed path is the normal case. In this run
4 of the 325 "no" rows had a hub or About fetch refused (403 or 500)
rather than missing, so their IR pages were not all read. The branch in
`crawl_school` meant to return "unclear" for that case never fires
(`unclear and not hubs` is always false once a hub was tried); it is left
as is here and noted for a follow-up, because changing it changes the
meaning of the first crawl's 1,771 "no" rows too.

## Re-run

```bash
python tools/finder/backfill_ir_hubs.py \
  --from-csv tools/finder/audits/ir-hub-backfill-2026-11/missing_in_scope.csv \
  --from-review tools/finder/audits/ir-hub-backfill-2026-11/review.csv \
  --timeout 25 --retries 1 --backoff 2 --try-url-variants --resume \
  --rps 0.5 --school-deadline 0 \
  --out scratch/ir-hub-backfill/mac-recrawl/review.csv \
  --summary-json scratch/ir-hub-backfill/mac-recrawl/summary.json
```

About 4.5 hours at 0.5 requests per second.
