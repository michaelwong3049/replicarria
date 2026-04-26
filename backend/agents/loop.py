import os
import json
import uuid
from datetime import datetime
from typing import TypedDict, List

import anthropic
from anthropic.types import TextBlock
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.memory import extract_keywords, get_top_memories, should_reflect

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

class AgentState(TypedDict):
    agent_id: str
    name: str
    occupation: str
    personality: str
    communication_style: str
    emotional_volatility: float
    income_bracket: str
    political_lean: float
    mood: str
    policy_stance: float
    policy_opinion: str
    policy_summary: str
    memory_stream: List[dict]
    reflections: List[str]
    cumulative_importance: float
    round_events: List[str]
    top_memories: List[str]


# ── Nodes ─────────────────────────────────────────────────────

def retrieve_node(state: AgentState) -> AgentState:
    query = " ".join(state["round_events"])
    top = get_top_memories(state["memory_stream"], query)
    return {"top_memories": top}  # type: ignore[return-value]


def perceive_node(state: AgentState) -> AgentState:
    if not state["round_events"]:
        return {"top_memories": state["top_memories"]}  # type: ignore[return-value]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": f"""You are {state["name"]}, a {state["occupation"]}.
            Your personality: {state["personality"]}.
            Policy you are reacting to: {state["policy_summary"]}

            Events that happened this round:
            {chr(10).join(f"- {e}" for e in state["round_events"])}

            Rate the overall importance of these events to you personally on a scale of 1-10.
            Return only a JSON object: {{"importance": <number>}}"""
        }]
    )

    block = response.content[0]
    raw = block.text.strip() if isinstance(block, TextBlock) else ""
    try:
        result = json.loads(raw)
        importance = float(result.get("importance", 5.0))
    except Exception:
        importance = 5.0

    return {"top_memories": state["top_memories"], "cumulative_importance": state["cumulative_importance"] + importance}  # type: ignore[return-value]


def reflect_node(state: AgentState) -> AgentState:
    last_15 = state["memory_stream"][-15:]
    memory_text = "\n".join(f"- {m['content']}" for m in last_15)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": f"""You are {state["name"]}, a {state["occupation"]}.
            Based on these recent memories, synthesize 2 high-level beliefs you now hold.

            Memories:
            {memory_text}

            Return only a JSON object: {{"beliefs": ["belief 1", "belief 2"]}}"""
        }]
    )

    block = response.content[0]
    raw = block.text.strip() if isinstance(block, TextBlock) else ""
    try:
        result = json.loads(raw)
        new_reflections = result.get("beliefs", [])
    except Exception:
        new_reflections = []

    updated_memories = [dict(m, reflected=True) for m in state["memory_stream"]]

    return {  # type: ignore[return-value]
            "reflections": state["reflections"] + new_reflections,
            "memory_stream": updated_memories,
            "cumulative_importance": 0.0,
            }


def plan_node(state: AgentState) -> AgentState:
    if not state["round_events"]:
        return {}  # type: ignore[return-value]

    recent_reflections = state["reflections"][-2:] if state["reflections"] else []

    lean = state.get("political_lean", 0.0)
    if lean > 0.3:
        lean_voice = (
            "RIGHT-LEANING. Your gut: government overreach, let businesses breathe, taxes already too high, markets work if left alone. "
            "Words you use: 'bureaucrats', 'red tape', 'my business', 'compete', 'freedom', 'enough taxes'. "
            "You may see THIS as opportunity OR as government meddling — pick the angle that fits your job."
        )
    elif lean < -0.3:
        lean_voice = (
            "LEFT-LEANING. Your gut: corporations win again, workers get squeezed, inequality is the real problem, community needs investment. "
            "Words you use: 'working people', 'the rich', 'can't afford', 'my neighborhood', 'exploitation', 'fair shot'. "
            "You see WHO benefits from this — and you're pretty sure it's not people like you."
        )
    else:
        lean_voice = (
            "PRAGMATIST. Zero ideology — you just do the math on YOUR life: rent, grocery bill, job security, kids' school. "
            "Words you use: 'my rent', 'my paycheck', 'prices', 'my job', 'can I afford'. "
            "Skip the politics, just tell us if your wallet is better or worse."
        )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""You are {state["name"]}, {state["occupation"]}, {state.get("income_bracket","middle")} income.
            Political voice: {lean_voice}
            Personality: {state["personality"]}. Mood right now: {state["mood"]}.
            Stance: {state["policy_stance"]} (-1=strongly against, 1=strongly for).
            Situation: {state["policy_summary"]}

            What just happened this round: {chr(10).join(f"- {e}" for e in state["round_events"])}
            Your memories: {chr(10).join(f"- {m}" for m in state["top_memories"])}

            Your PREVIOUS take was: "{state["policy_opinion"]}"
            Has anything changed for you this round? If yes, update your opinion — say something NEW based on what just happened. If no, shift the angle slightly — same worldview, different specific worry or hope.
            Do NOT restate the same sentence. Find a new concrete detail.

            WRITE AS THIS PERSON, NOT AS AN AI.
            BANNED WORDS: "policy", "impacts", "affects", "significant", "concern", "important"
            REQUIRED: one concrete anchor (dollar amount, your job, specific fear or hope, something real).

            Return only valid JSON:
            {{
              "mood": "<optimistic|anxious|angry|neutral|hopeful>",
              "stance_delta": <float -0.3 to 0.3>,
              "policy_opinion": "<8-12 words, first person, casual, concrete — something NEW from last round>",
              "new_memory": "<one blunt casual sentence about what this means for your actual daily life>",
              "importance": <float 1-10>
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
        result = {"mood": state["mood"], "stance_delta": 0.0, "new_memory": "", "importance": 1.0}

    new_memory = {
        "id": str(uuid.uuid4()),
        "content": result["new_memory"],
        "importance": float(result["importance"]),
        "timestamp": datetime.now().isoformat(),
        "keywords": extract_keywords(result["new_memory"]),
        "reflected": False,
    }

    raw_delta = float(result["stance_delta"]) * state["emotional_volatility"]
    new_stance = max(-1.0, min(1.0, state["policy_stance"] + raw_delta))

    return {  # type: ignore[return-value]
            "mood": result["mood"],
            "policy_stance": new_stance,
            "policy_opinion": result.get("policy_opinion", state["policy_opinion"]),
            "memory_stream": state["memory_stream"] + [new_memory],
            "cumulative_importance": state["cumulative_importance"] + float(result["importance"]),
            }


# ── Conditional edge ──────────────────────────────────────────

def should_reflect_edge(state: AgentState) -> str:
    return "reflect" if should_reflect(state["cumulative_importance"]) else "plan"


# ── Graph ─────────────────────────────────────────────────────

_builder = StateGraph(AgentState)
_builder.add_node("retrieve", retrieve_node)
_builder.add_node("perceive", perceive_node)
_builder.add_node("reflect", reflect_node)
_builder.add_node("plan", plan_node)

_builder.set_entry_point("retrieve")
_builder.add_edge("retrieve", "perceive")
_builder.add_conditional_edges("perceive", should_reflect_edge, {"reflect": "reflect", "plan": "plan"})
_builder.add_edge("reflect", "plan")
_builder.add_edge("plan", END)

agent_graph = _builder.compile(checkpointer=MemorySaver())

