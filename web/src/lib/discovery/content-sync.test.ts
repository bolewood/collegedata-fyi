// The runtime consumes committed mirrors of the canonical CC BY-SA content
// artifacts (see content/README.md). This test runs where the whole repo is
// available (local + CI) and fails whenever a mirror drifts from its source,
// so a stale copy cannot reach a deploy.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import cardsMirror from "./content/cards.v1.json";
import deckMirror from "./content/deck.opening-v1.json";
import ontologyMirror from "./content/ontology.v1.json";
import policyMirror from "./content/policy.v1.json";
import zip3Mirror from "./content/zip3-centroids.v1.json";

const DATA = join(__dirname, "../../../../data/discovery");

const canonical = (rel: string) =>
  JSON.parse(readFileSync(join(DATA, rel), "utf-8"));

describe("discovery content mirrors match their canonical artifacts", () => {
  it.each([
    ["cards/v1.json", cardsMirror],
    ["decks/opening-v1.json", deckMirror],
    ["policy/v1.json", policyMirror],
    ["ontology/v1.json", ontologyMirror],
    ["geo/zip3-centroids-v1.json", zip3Mirror],
  ])("%s", (rel, mirror) => {
    expect(
      mirror,
      `Mirror drifted from data/discovery/${rel} — re-copy per src/lib/discovery/content/README.md`,
    ).toEqual(canonical(rel));
  });
});
