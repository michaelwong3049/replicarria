import asyncio
import json
import uuid
import random
import os
import anthropic
from anthropic.types import TextBlock
from typing import Literal

from agents.loop import agent_graph
from agents.agent import Agent, AgentIdentity, AgentPersonality, AgentBeliefs, AgentSocial, AgentPosition
from agents.policy_parser import PolicyContext

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

ALL_ARCHETYPES = [
    "small business owner", "nurse", "construction worker", "teacher",
    "auto mechanic", "software engineer", "gig worker",
    "retail worker", "artist", "government worker"
]

LAYER_DISTRIBUTION = {
    "sky": 0.12,
    "surface": 0.35,
    "underground": 0.35,
    "deep": 0.18,
}

POLITICAL_HINTS = [
    "strongly right-leaning: you believe free markets solve problems better than government, you distrust regulation, and you see opportunity where others see danger",
    "moderately conservative: you value fiscal responsibility and small-government principles, you worry about economic overreach hurting businesses",
    "centrist and pragmatic: you judge every policy purely on how it hits YOUR wallet and neighborhood — ideology is irrelevant, impact is everything",
    "moderately progressive: you believe workers need protections and communities need real investment, you're suspicious of corporate influence",
    "strongly left-leaning: you see economic inequality as the root problem, you're deeply skeptical of corporate power and believe this is about who benefits",
]

POLITICAL_WEIGHTS = [0.20, 0.15, 0.30, 0.20, 0.15]


def distribute_archetypes(n: int, affected: list[str]) -> list[str]:
    weights = {a: 3 if a in affected else 1 for a in ALL_ARCHETYPES}
    population = list(weights.keys())
    w = list(weights.values())
    return random.choices(population, weights=w, k=n)


def distribute_layers(n: int) -> list[Literal["sky", "surface", "underground", "deep"]]:
    layers = list(LAYER_DISTRIBUTION.keys())
    weights = list(LAYER_DISTRIBUTION.values())
    return random.choices(layers, weights=weights, k=n)  # type: ignore[return-value]


def distribute_political_hints(n: int) -> list[str]:
    return random.choices(POLITICAL_HINTS, weights=POLITICAL_WEIGHTS, k=n)


async def spawn_single_agent(policy: PolicyContext, archetype: str, layer: Literal["sky", "surface", "underground", "deep"], political_hint: str, thread_id: str | None = None) -> tuple[str, Agent]:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""Generate a real city resident who has just heard about a policy or news event. They are a normal person with a real job, not a fantasy character.

            Economic role: {archetype}
            Neighborhood: {layer}
            Political orientation: {political_hint}
            Policy summary: {policy["summary"]}
            Groups most affected: {", ".join(policy["affected_archetypes"])}

            Return a JSON object with exactly these fields:
            - name: string (a realistic first + last name — pick from genuinely diverse backgrounds: Latino, Black American, South Asian, Middle Eastern, Eastern European, Southeast Asian, West African, etc. Do NOT use Chen, Kim, Wang, or other overused placeholder names. Each agent in this simulation must have a unique name.)
            - age: integer (18-70)
            - occupation: string (a specific real-world job title matching the economic role, e.g. "auto mechanic" → "Auto Repair Technician", "nurse" → "Pediatric Nurse", "small business owner" → "Taqueria Owner")
            - income_bracket: one of "low", "middle", "high"
            - personality_description: string (2-4 words describing their character, e.g. "blunt and skeptical")
            - communication_style: one of "aggressive", "passive", "persuasive", "logical"
            - emotional_volatility: float 0.0-1.0
            - political_lean: float -1.0 to 1.0 (left to right)
            - economic_outlook: float -1.0 to 1.0 (dire to optimistic)
            - policy_stance: float -1.0 to 1.0 (how this policy personally affects someone in their situation — right-leaning people often start positive on pro-business/deregulation news, left-leaning people often start negative; but the archetype and actual policy content matters most — a factory worker benefits from tariffs, a consumer is hurt by them)
            - policy_opinion: string (their gut reaction as a real person — how does this hit THEIR wallet, neighborhood, job security, or community? 8-12 words, first person, casual, emotional — NOT "doesn't affect me". MUST reflect their political orientation AND the actual economic impact: right-leaning may see opportunity or bristle at overreach; left-leaning may see protection for workers or corporate handout; centrist just does the math on their own life.)
            - mood: one of "optimistic", "anxious", "angry", "neutral", "hopeful"
            - starting_memory: string (one casual sentence about what this news means for their daily life)

            Return only valid JSON, no other text."""
        }]
    )

    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise Exception(f"Unexpected response block type: {type(block)}")
    raw = block.text.strip()
    if not raw:
        raise Exception(f"Empty response spawning agent {archetype}/{layer}")
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    d = json.loads(raw)

    agent_id = str(uuid.uuid4())
    if thread_id is None:
        thread_id = agent_id

    agent = Agent(
        identity=AgentIdentity(
            id=agent_id,
            name=d["name"],
            age=d["age"],
            occupation=d["occupation"],
            income_bracket=d["income_bracket"],
            layer=layer,
            npc_class=archetype,
        ),
        personality=AgentPersonality(
            description=d["personality_description"],
            communication_style=d["communication_style"],
            emotional_volatility=float(d["emotional_volatility"]),
        ),
        beliefs=AgentBeliefs(
            political_lean=float(d["political_lean"]),
            economic_outlook=float(d["economic_outlook"]),
            policy_stance=float(d["policy_stance"]),
            policy_opinion=d["policy_opinion"],
            mood=d["mood"],
        ),
        social=AgentSocial(
            relationships={},
            conversation_count=0,
        ),
        position=AgentPosition(
            x=random.uniform(0, 100),
            y=random.uniform(0, 100),
        ),
        memory_stream=[],
        reflections=[],
    )

    existing = agent_graph.get_state({"configurable": {"thread_id": thread_id}})
    if not existing.values:
        await agent_graph.ainvoke(
            {
                "agent_id": agent.id,
                "name": agent.identity["name"],
                "occupation": agent.identity["occupation"],
                "personality": agent.personality["description"],
                "communication_style": agent.personality["communication_style"],
                "emotional_volatility": agent.personality["emotional_volatility"],
                "income_bracket": agent.identity["income_bracket"],
                "political_lean": agent.beliefs["political_lean"],
                "mood": agent.beliefs["mood"],
                "policy_stance": agent.beliefs["policy_stance"],
                "policy_opinion": agent.beliefs["policy_opinion"],
                "policy_summary": policy["summary"],
                "memory_stream": [],
                "reflections": [],
                "cumulative_importance": 0.0,
                "round_events": [],
                "top_memories": [],
            },
            config={"configurable": {"thread_id": thread_id}}
        )
    else:
        agent_graph.update_state(
            {"configurable": {"thread_id": thread_id}},
            {"policy_summary": policy["summary"], "round_events": []},
        )

    return thread_id, agent


async def spawn_agents(n: int, policy: PolicyContext, use_memory: bool = False) -> dict[str, Agent]:
    archetypes = distribute_archetypes(n, policy["affected_archetypes"])
    layers = distribute_layers(n)
    political_hints = distribute_political_hints(n)

    agents_by_thread: dict[str, Agent] = {}
    for i in range(n):
        try:
            tid = f"living_city_{i}" if use_memory else None
            thread_id, agent = await spawn_single_agent(policy, archetypes[i], layers[i], political_hints[i], tid)
            agents_by_thread[thread_id] = agent
        except Exception as e:
            print(f"[spawn] agent {i} failed: {e}")
        await asyncio.sleep(0.5)

    return agents_by_thread

