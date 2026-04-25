import json
import uuid
from datetime import datetime

import anthropic
from anthropic.types import TextBlock

from agents.loop import agent_graph
from agents.memory import extract_keywords

import os
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def resolve_conversation(agent_a_id: str, agent_b_id: str):
    # load both agents' current state from the checkpointer
    state_a = agent_graph.get_state({"configurable": {"thread_id": agent_a_id}})
    state_b = agent_graph.get_state({"configurable": {"thread_id": agent_b_id}})

    if not state_a.values or not state_b.values:
        return

    a = state_a.values
    b = state_b.values

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""Two people have just had a conversation about a policy.

            Person A — {a["name"]}, {a["occupation"]}
              Personality: {a["personality"]}, communication style: {a["communication_style"]}
              Current mood: {a["mood"]}, emotional volatility: {a["emotional_volatility"]}
              Their opinion: "{a["policy_opinion"]}"

            Person B — {b["name"]}, {b["occupation"]}
              Personality: {b["personality"]}, communication style: {b["communication_style"]}
              Current mood: {b["mood"]}, emotional volatility: {b["emotional_volatility"]}
              Their opinion: "{b["policy_opinion"]}"

            Policy context: {a["policy_summary"]}

            Based on their personalities and opinions, how does this conversation go?
            Who (if anyone) is persuaded? Consider their communication styles and volatility.

            Return only a JSON object:
            {{
              "dialogue": "<2-3 line exchange showing what they actually said>",
              "a_stance_delta": <float -0.3 to 0.3>,
              "a_new_opinion": "<updated one-sentence opinion for person A>",
              "a_mood": "<optimistic|anxious|angry|neutral|hopeful>",
              "a_memory": "<one sentence — what A will remember about this conversation>",
              "b_stance_delta": <float -0.3 to 0.3>,
              "b_new_opinion": "<updated one-sentence opinion for person B>",
              "b_mood": "<optimistic|anxious|angry|neutral|hopeful>",
              "b_memory": "<one sentence — what B will remember about this conversation>"
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
        return

    now = datetime.now().isoformat()

    # build memory objects for each agent
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

    # apply stance delta capped by emotional volatility
    new_stance_a = max(-1.0, min(1.0, a["policy_stance"] + result["a_stance_delta"] * a["emotional_volatility"]))
    new_stance_b = max(-1.0, min(1.0, b["policy_stance"] + result["b_stance_delta"] * b["emotional_volatility"]))

    # update both agents' state in the checkpointer
    await agent_graph.aupdate_state(
        {"configurable": {"thread_id": agent_a_id}},
        {
            "mood": result["a_mood"],
            "policy_stance": new_stance_a,
            "policy_opinion": result["a_new_opinion"],
            "memory_stream": a["memory_stream"] + [memory_a],
        }
    )

    await agent_graph.aupdate_state(
        {"configurable": {"thread_id": agent_b_id}},
        {
            "mood": result["b_mood"],
            "policy_stance": new_stance_b,
            "policy_opinion": result["b_new_opinion"],
            "memory_stream": b["memory_stream"] + [memory_b],
        }
    )

    print(f"\n[Conversation] {a['name']} ↔ {b['name']}")
    print(f"  {result['dialogue']}")
    print(f"  {a['name']}: stance {a['policy_stance']:.2f} → {new_stance_a:.2f} | {result['a_new_opinion']}")
    print(f"  {b['name']}: stance {b['policy_stance']:.2f} → {new_stance_b:.2f} | {result['b_new_opinion']}")
