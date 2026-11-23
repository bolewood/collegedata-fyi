# Browser pass over the 85 user-agent-blocked schools — 2026-11-23

The residential recrawl (`../recrawl-mac/`) left 85 schools unclear because
their sites answer HTTP 403 to the finder's self-identified user agent from
any network. These are public pages any visitor can load, so this pass
loaded the same pages in headless Chromium with a desktop browser user
agent. Review-only: nothing was archived or enqueued.

Same crawl as `tools/finder/backfill_ir_hubs.py` (homepage, one About page,
up to six IR hub URLs); `browser_pass.py` in this folder swaps the fetch for
a browser page load. One request every 3 seconds, one site at a time.

It stops, per page, at anything that is not an ordinary page:

- robots.txt disallows the URL for all agents;
- a visual CAPTCHA or an interstitial challenge page;
- any status other than 200.

Nothing is clicked, solved or waited out.

## Counts

| Outcome | Count |
| --- | ---: |
| yes (CDS listing found) | 1 |
| no, every page tried loaded | 37 |
| no, but an IR or About page was challenged or refused | 34 |
| unclear (homepage challenged, refused or disallowed) | 13 |
| **UNITIDs** | **85** |

The 34 are recorded as "no" by the script (see the note on that branch in
`../recrawl-mac/README.md`) but their IR pages were not all read, so treat
them as unclear. That leaves 37 confirmed without a CDS on the pages
tried, and 47 still open.

Unclear homepages: 11 challenge pages, 1 robots.txt disallow, 1 HTTP 403.

## The yes row

Seattle Pacific University (236577): the Office of Institutional
Effectiveness page links
`https://spu.edu/administration/office-of-institutional-effectiveness/common-data-sets`.
The school was already seeded, with a direct link to its 2024-25 file. The
seed now points at the listing page so later years are found too. Its
files still need the headless archive path, because the plain fetch gets
403.

## Re-run

```bash
python -m venv scratch/venv-headless
scratch/venv-headless/bin/pip install -r tools/finder/requirements-headless.txt
scratch/venv-headless/bin/python -m playwright install chromium
scratch/venv-headless/bin/python \
  tools/finder/audits/ir-hub-backfill-2026-11/recrawl-browser/browser_pass.py \
  tools/finder/audits/ir-hub-backfill-2026-11/recrawl-mac/review.csv \
  scratch/ir-hub-backfill/browser_review.csv
```

About 50 minutes.
