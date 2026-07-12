# Discovery content mirrors

Build-time copies of the versioned discovery artifacts from
[`data/discovery/`](../../../../../data/discovery/) (the canonical,
CC BY-SA 4.0–licensed source — see its LICENSE and README). The web app
cannot import across the repo root (the Vercel project root is `web/`),
so the runtime consumes these mirrors instead.

**Do not edit these files.** Edit the canonical artifact under
`data/discovery/` and re-copy:

```bash
cd /path/to/collegedata-fyi
cp data/discovery/cards/v1.json web/src/lib/discovery/content/cards.v1.json
cp data/discovery/decks/opening-v1.json web/src/lib/discovery/content/deck.opening-v1.json
cp data/discovery/policy/v1.json web/src/lib/discovery/content/policy.v1.json
```

`content-sync.test.ts` fails the suite whenever a mirror drifts from its
canonical source, so a stale copy cannot ship.
