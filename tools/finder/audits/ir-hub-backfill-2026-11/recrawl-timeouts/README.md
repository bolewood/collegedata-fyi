# Timeout recrawl — 2026-11-22

Review-only recrawl of the 446 unclear rows from the first IR-hub backfill.
Nothing was archived, enqueued, written to `schools.yaml`, or sent through
the WAF/headless path.

The first crawl used an 8s HTTP timeout and treated 403s, TLS hangs, and
true timeouts as the same `homepage_unreachable`. This pass used a 25s
timeout, one retry with 2s backoff on the first homepage URL, https/http
and www/non-www variants, and a per-request process kill so hung TLS
could not ignore the socket timeout. Sequential, 0.5 rps.

## Counts

| Outcome | Count |
| --- | ---: |
| yes (CDS listing found) | 0 |
| no (homepage reached, no CDS on IR hubs) | 13 |
| unclear (still unreachable from this VM) | 433 |
| **UNITIDs recrawled** | **446** |

Input was every unclear row whose notes contained `homepage_unreachable`,
`homepage_fail`, `dns_miss`, or `crawl_error`. That is the full unclear
set from the first crawl (429 homepage-fail + 15 DNS mixed into those
notes + 2 `InvalidURL`), not a separate 441+3+2 split.

`published=false`. No new seeds. The open seed PR (#409) does not need
these rows.

## Still unreachable (433)

| Reason | Count |
| --- | ---: |
| HTTP 403 (this VM / finder UA blocked) | 399 |
| HTTP 307/302 not turned into HTML | 9 |
| HTTP 404 on every homepage variant | 8 |
| True timeout after 25s + retry + variants | 7 |
| Network error | 3 |
| HTTP 5xx / 521 / 522 | 3 |
| DNS miss only | 2 |
| HTTP 429 | 1 |
| HTTP 405 | 1 |

Timeouts that survived the longer wait: Alverno, Blackfeet Community
College, Dakota Wesleyan, Dutchess Community College, Instituto
Tecnologico de Puerto Rico-Manati, Marymount Manhattan (`mmm.edu`
timed out; `www.mmm.edu` NXDOMAIN), Southwest Texas College.

DNS-only: City College-Altamonte Springs and City College-Hollywood
(`citycollege.edu` does not resolve).

The two first-pass `InvalidURL` rows (Cerro Coso 111896, Normandale
174428) were path-encoding bugs, not dead sites. Both homepages fetched
this time and classified **no**.

## Reachable with no CDS on IR hubs (13)

These are not seed candidates. Several only became fetchable on `http://`
after `https://` returned 403, then the well-known IR paths 404'd.

| School | UNITID | URL |
| --- | --- | --- |
| American InterContinental University-Houston | 445133 | https://www.aiuniv.edu/ |
| BridgeValley Community & Technical College | 484932 | http://www.bridgevalley.edu/ |
| Carolinas College of Health Sciences | 433174 | https://atriumhealth.org/education/carolinas-college-of-health-sciences |
| Cerro Coso Community College | 111896 | https://www.cerrocoso.edu/ |
| Drury University-College of Continuing Professional Studies | 492801 | http://www.drury.edu/go/ |
| Little Big Horn College | 180328 | http://www.lbhc.edu/ |
| Morris College | 218399 | http://www.morris.edu/ |
| Normandale Community College | 174428 | https://www.normandale.edu/ |
| Palau Community College | 243647 | http://palau.edu/ |
| Robeson Community College | 199476 | http://www.robeson.edu/ |
| Urshan University | 494685 | http://urshan.edu/ |
| West Virginia Wesleyan College | 237969 | https://www.wvwc.edu/ |
| Yeshiva Shaar Ephraim | 490276 | http://shaarephraim.org/ |

## How to re-run

```bash
python tools/finder/backfill_ir_hubs.py \
  --from-csv tools/finder/audits/ir-hub-backfill-2026-11/missing_in_scope.csv \
  --from-review tools/finder/audits/ir-hub-backfill-2026-11/review.csv \
  --timeout 25 --retries 1 --backoff 2 --try-url-variants --resume \
  --rps 0.5 --school-deadline 0 \
  --out scratch/ir-hub-backfill/recrawl-timeouts/review.csv \
  --summary-json scratch/ir-hub-backfill/recrawl-timeouts/summary.json
```

`--from-review` selects unclear timeout/DNS/crawl_error UNITIDs.
`--resume` skips UNITIDs already in `--out`. Incremental CSV after every
school. A later pass from a network that is not 403-blocked would be the
next useful recrawl; longer timeouts on this VM will not.
