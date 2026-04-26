import json
import uuid
from datetime import datetime

import anthropic
from anthropic.types import TextBlock

from agents.loop import agent_graph
from agents.memory import extract_keywords

import os
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def resolve_conversation(agent_a_id: str, agent_b_id: str) -> tuple[str, str] | None:
    state_a = agent_graph.get_state({"configurable": {"thread_id": agent_a_id}})
    state_b = agent_graph.get_state({"configurable": {"thread_id": agent_b_id}})

    if not state_a.values or not state_b.values:
        return None

    a = state_a.values
    b = state_b.values

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=450,
        messages=[{
            "role": "user",
            "content": f"""Two city residents just ran into each other and have a short conversation.

{a["name"]} ({a["occupation"]}, {a["mood"]}, volatility {a["emotional_volatility"]:.1f}): "{a["policy_opinion"]}"
{b["name"]} ({b["occupation"]}, {b["mood"]}, volatility {b["emotional_volatility"]:.1f}): "{b["policy_opinion"]}"

Situation: {a["policy_summary"]}

Write a 4-line back-and-forth. Each line must react directly to the previous one.
High volatility = more emotional, sharp, reactive. Low volatility = measured, calm.
Casual speech only. 6-10 words per line. No corporate language.

Return only JSON:
{{
  "a_line": "<A opens — states their situation or frustration, 6-10 words>",
  "b_line": "<B reacts DIRECTLY to what A said, agrees or pushes back, 6-10 words>",
  "a_reply": "<A responds to B's reaction — builds on it or defends, 6-10 words>",
  "b_reply": "<B closes — final word, shift or dig in, 6-10 words>",
  "a_stance_delta": <float -0.3 to 0.3>,
  "b_stance_delta": <float -0.3 to 0.3>,
  "a_new_opinion": "<A's updated one-sentence take after this exchange>",
  "b_new_opinion": "<B's updated one-sentence take after this exchange>",
  "a_mood": "<optimistic|anxious|angry|neutral|hopeful>",
  "b_mood": "<optimistic|anxious|angry|neutral|hopeful>",
  "a_memory": "<one casual sentence: what A will remember>",
  "b_memory": "<one casual sentence: what B will remember>"
}}"""
        }]
    )

    block = response.content[0]
    raw = block.text.strip() if isinstance(block, TextBlock) else ""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
    except Exception:
        return None

    now = datetime.now().isoformat()

    memory_a = {
        "id": str(uuid.uuid4()),
        "content": result["a_memory"],
        "importance": 6.0,
        "timestamp": now,
        "keywords": extract_keywords(result["a_memory"]),
        "reflected": False,
    }
    memory_b = {
        "id": str(uuid.uuid4()),
        "content": result["b_memory"],
        "importance": 6.0,
        "timestamp": now,
        "keywords": extract_keywords(result["b_memory"]),
        "reflected": False,
    }

    new_stance_a = max(-1.0, min(1.0, a["policy_stance"] + result["a_stance_delta"] * a["emotional_volatility"]))
    new_stance_b = max(-1.0, min(1.0, b["policy_stance"] + result["b_stance_delta"] * b["emotional_volatility"]))

    agent_graph.update_state(
        {"configurable": {"thread_id": agent_a_id}},
        {
            "mood": result["a_mood"],
            "policy_stance": new_stance_a,
            "policy_opinion": result["a_new_opinion"],
            "memory_stream": a["memory_stream"] + [memory_a],
            "cumulative_importance": a.get("cumulative_importance", 0.0) + 6.0,
        }
    )
    agent_graph.update_state(
        {"configurable": {"thread_id": agent_b_id}},
        {
            "mood": result["b_mood"],
            "policy_stance": new_stance_b,
            "policy_opinion": result["b_new_opinion"],
            "memory_stream": b["memory_stream"] + [memory_b],
            "cumulative_importance": b.get("cumulative_importance", 0.0) + 6.0,
        }
    )

    print(f"[convo] {a['name']} ↔ {b['name']} | stance {a['policy_stance']:.2f}→{new_stance_a:.2f} / {b['policy_stance']:.2f}→{new_stance_b:.2f}")
    return result["a_line"], result["b_line"], result.get("a_reply", ""), result.get("b_reply", "")
