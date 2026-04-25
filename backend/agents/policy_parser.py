import json
import os
import anthropic
from anthropic.types import TextBlock
from typing import List, Optional, TypedDict, Literal

class PolicyContext(TypedDict):
    raw_text: str
    summary: str
    economic_entities: List[str]
    affected_archetypes: List[str]
    controversy_level: float
    source: Literal["text", "pdf", "news"]
    headline: Optional[str]

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

async def parse_policy(text: str, source: Literal["text", "pdf", "news"] = "text") -> PolicyContext:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""Analyze this policy and return a JSON object with exactly these fields:
- summary: 2-3 sentence plain summary
- economic_entities: list of economic concepts affected (e.g. "wages", "ore prices")
- affected_archetypes: list of Terraria NPC types most impacted (e.g. "merchant", "demolitionist")
- controversy_level: float 0.0-1.0 (how polarizing is this?)

Policy: {text}

Return only valid JSON, no other text."""
        }]
    )

    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise Exception(f"Unexpected response block type: {type(block)}")
    raw = block.text.strip()
    if not raw:
        raise Exception("Empty response from policy parser")
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    parsed = json.loads(raw)
    return PolicyContext(
        raw_text=text,
        summary=parsed["summary"],
        economic_entities=parsed["economic_entities"],
        affected_archetypes=parsed["affected_archetypes"],
        controversy_level=parsed["controversy_level"],
        source=source,
        headline=None,
    )
