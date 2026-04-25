import asyncio
import json
import uuid
import random
import os
import anthropic
from typing import Literal

from agents.agent import Agent, AgentIdentity, AgentPersonality, AgentBeliefs, AgentSocial, AgentPosition
from agents.policy_parser import PolicyContext

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

ALL_ARCHETYPES = [
    "merchant", "nurse", "demolitionist", "wizard",
    "mechanic", "goblin_tinkerer", "arms_dealer",
    "dye_trader", "painter", "tax_collector"
]

LAYER_DISTRIBUTION = {
    "sky": 0.12,
    "surface": 0.35,
    "underground": 0.35,
    "deep": 0.18,
}


def distribute_archetypes(n: int, affected: list[str]) -> list[str]:
    weights = {a: 3 if a in affected else 1 for a in ALL_ARCHETYPES}
    population = list(weights.keys())
    w = list(weights.values())
    return random.choices(population, weights=w, k=n)


def distribute_layers(n: int) -> list[Literal["sky", "surface", "underground", "deep"]]:
    layers = list(LAYER_DISTRIBUTION.keys())
    weights = list(LAYER_DISTRIBUTION.values())
    return random.choices(layers, weights=weights, k=n)  # type: ignore[return-value]


async def spawn_single_agent(policy: PolicyContext, archetype: str, layer: Literal["sky", "surface", "underground", "deep"]) -> Agent:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""Generate a Terraria NPC character who lives in this world and has just heard about a new policy.

Archetype: {archetype}
Layer: {layer}
Policy summary: {policy["summary"]}
Affected groups: {", ".join(policy["affected_archetypes"])}

Return a JSON object with exactly these fields:
- name: string (a fitting Terraria-style name)
- age: integer (18-70)
- occupation: string (specific job title fitting the archetype)
- income_bracket: one of "low", "middle", "high"
- personality_description: string (2-4 words, e.g. "stubborn and pragmatic")
- communication_style: one of "aggressive", "passive", "persuasive", "logical"
- emotional_volatility: float 0.0-1.0 (how much conversations move them)
- political_lean: float -1.0 to 1.0 (left to right)
- economic_outlook: float -1.0 to 1.0 (dire to optimistic)
- policy_stance: float -1.0 to 1.0 (oppose to support, based on how this policy affects them)
- mood: one of "optimistic", "anxious", "angry", "neutral", "hopeful"
- starting_memory: string (one sentence — their first reaction to hearing about this policy)

Return only valid JSON, no other text."""
        }]
    )

    raw = response.content[0].text.strip()
    if not raw:
        raise Exception(f"Empty response spawning agent {archetype}/{layer}")
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    d = json.loads(raw)

    return Agent(
        identity=AgentIdentity(
            id=str(uuid.uuid4()),
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


async def spawn_agents(n: int, policy: PolicyContext) -> dict[str, Agent]:
    archetypes = distribute_archetypes(n, policy["affected_archetypes"])
    layers = distribute_layers(n)

    agents = await asyncio.gather(*[
        spawn_single_agent(policy, archetypes[i], layers[i])
        for i in range(n)
    ])

    return {agent.id: agent for agent in agents}
