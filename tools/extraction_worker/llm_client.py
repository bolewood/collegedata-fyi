"""
Thin Anthropic SDK wrapper for the Tier 4 LLM fallback (PRD 006).

Split-prompt design: every call has a cached head (stable across docs for
a given section/schema/prompt version) and an uncached tail (this doc's
markdown slice + gap set). The head is marked with cache_control so the
Anthropic prompt-cache picks it up — PRD 006's cost envelope assumes this
hit rate.

Defaults are set for Haiku 4.5 with prompt caching. Vendor and model are
swappable via env var; pricing lives in a local table so cost estimation
does not require a network call.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


DEFAULT_MODEL = os.getenv("TIER4_FALLBACK_MODEL", "claude-haiku-4-5")


# ---------------------------------------------------------------------------
# Pricing — $/MTok.
#
# Haiku 4.5 list price as of 2026-Q2. Cached-read is ~10% of base input;
# cache-write is 1.25x base input. Update this table when model or pricing
# changes — the benchmark CLI reads it for its cost dashboard.
# ---------------------------------------------------------------------------
PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {
        "input": 0.80,
        "cache_write": 1.00,
        "cache_read": 0.08,
        "output": 4.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
}


@dataclass
class LLMResponse:
    """Structured return from call_structured(). Parsed JSON + token counts."""

    parsed: dict[str, Any]
    raw_text: str
    model: str
    input_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    stop_reason: str | None
    cached: bool
    # Extra fields for audit; never parsed by callers.
    request_id: str | None = field(default=None)


def estimate_cost(
    *,
    input_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    output_tokens: int,
    model: str = DEFAULT_MODEL,
) -> float:
    """Return the estimated USD cost for one call.

    The Anthropic API reports cache-write and cache-read tokens separately
    from uncached input tokens, so this is a straight per-bucket tally.
    """
    p = PRICING_PER_MTOK.get(model)
    if not p:
        return 0.0
    return (
        input_tokens * p["input"]
        + cache_write_tokens * p["cache_write"]
        + cache_read_tokens * p["cache_read"]
        + output_tokens * p["output"]
    ) / 1_000_000


def call_structured(
    *,
    system: str,
    cached_head_blocks: list[str],
    uncached_tail: str,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 4096,
    api_key: str | None = None,
) -> LLMResponse:
    """Call the Anthropic API with prompt caching and parse JSON output.

    Args:
        system: The system prompt (treated as a cached-head block too).
        cached_head_blocks: Ordered text blocks that form the stable prompt
            prefix. The final block gets a cache_control marker so the whole
            prefix up to it is cached. All blocks together must total at
            least 1024 tokens for Anthropic caching to kick in (sonnet/haiku
            minimum); shorter prompts will simply pay uncached rates.
        uncached_tail: The per-doc variable portion (section markdown +
            already-extracted + hints). Never cached.
        model: Model name.
        max_output_tokens: Cap on output tokens.
        api_key: Override for ANTHROPIC_API_KEY. Real deploys should use env.

    Returns:
        LLMResponse with the parsed JSON output. Raises RuntimeError if the
        response is not parseable as JSON.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    # Build the user message as a multi-part content list. The last cached
    # block carries cache_control; the uncached tail is a regular text block
    # after it.
    if not cached_head_blocks:
        raise ValueError("cached_head_blocks must have at least one entry")

    # cache_control marks the END of a cacheable prefix. We mark the LAST
    # head block so the full (glossary + subsection-specific) prefix is
    # cached. Benchmark observation: Haiku 4.5 requires the cached prefix to
    # exceed ~4096 tokens to actually write a cache entry; the glossary
    # alone (~2500 tokens) is below that threshold. The combined prefix
    # (~4500+ tokens for most subsections) clears it. Cache hits compound
    # across many docs running the same subsection — small wins on 2 docs,
    # significant at full-corpus scale.
    content: list[dict[str, Any]] = []
    last_idx = len(cached_head_blocks) - 1
    for i, block in enumerate(cached_head_blocks):
        part: dict[str, Any] = {"type": "text", "text": block}
        if i == last_idx:
            part["cache_control"] = {"type": "ephemeral"}
        content.append(part)
    content.append({"type": "text", "text": uncached_tail})

    resp = client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": content}],
    )

    # Collect the text output.
    raw_text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            raw_text_parts.append(block.text)
    raw_text = "".join(raw_text_parts)

    parsed = _parse_json_response(raw_text)

    usage = resp.usage
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    cost = estimate_cost(
        input_tokens=input_tokens,
        cache_write_tokens=cache_write,
        cache_read_tokens=cache_read,
        output_tokens=output_tokens,
        model=model,
    )

    return LLMResponse(
        parsed=parsed,
        raw_text=raw_text,
        model=model,
        input_tokens=input_tokens,
        cache_write_tokens=cache_write,
        cache_read_tokens=cache_read,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,
        stop_reason=getattr(resp, "stop_reason", None),
        cached=cache_read > 0,
        request_id=getattr(resp, "id", None),
    )


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Extract and parse the model's JSON output.

    Tolerates three observed Haiku behaviors:
      1. Bare JSON object.
      2. JSON wrapped in ``` or ```json fences, with or without trailing
         prose ("Rationale: ...").
      3. JSON inside a fence followed by explanatory prose outside the fence.

    Strategy: try raw json.loads first (fastest), then extract the first
    balanced ``{...}`` block by bracket-counting. Bracket-counting is
    robust against both trailing fences and trailing prose.
    """
    s = raw.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Strip a leading fence if present.
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]

    extracted = _extract_first_json_object(s)
    if extracted is not None:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    raise RuntimeError(f"LLM response was not valid JSON\n---\n{raw[:500]}")


def _extract_first_json_object(s: str) -> str | None:
    """Return the first balanced {...} substring, or None.

    Bracket-counts through the text while respecting string literals and
    escapes. Stops at the matching closing brace of the first opening one.
    """
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None
