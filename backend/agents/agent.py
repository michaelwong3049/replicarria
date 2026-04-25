from typing import TypedDict, List, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime

# ── Core agent identity ───────────────────────────────────────

class AgentIdentity(TypedDict):
    id: str
    name: str
    age: int
    occupation: str
    income_bracket: Literal["low", "middle", "high"]
    layer: Literal["sky", "surface", "underground", "deep"]
    npc_class: str              # "merchant", "nurse", "engineer", etc.

class AgentPersonality(TypedDict):
    description: str            # "stubborn and pragmatic"
    communication_style: Literal["aggressive", "passive", "persuasive", "logical"]
    emotional_volatility: float # 0.0–1.0

class AgentBeliefs(TypedDict):
    political_lean: float       # -1.0 (left) to 1.0 (right)
    economic_outlook: float     # -1.0 (dire) to 1.0 (optimistic)
    policy_stance: float        # -1.0 (oppose) to 1.0 (support)
    mood: str                   # "optimistic", "anxious", "angry", etc.

class AgentSocial(TypedDict):
    relationships: dict         # { agent_id: trust_score -1.0 to 1.0 }
    conversation_count: int     # total conversations this simulation

class AgentPosition(TypedDict):
    x: float
    y: float

class Memory(TypedDict):
    id: str
    content: str
    importance: float           # 1–10
    timestamp: datetime
    keywords: List[str]
    reflected: bool             # has this been synthesized into a reflection

@dataclass
class Agent:
    identity: AgentIdentity
    personality: AgentPersonality
    beliefs: AgentBeliefs
    social: AgentSocial
    position: AgentPosition
    memory_stream: List[Memory] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)
    cumulative_unreflected_importance: float = 0.0

    @property
    def id(self) -> str:
        return self.identity["id"]

    def to_dict(self) -> dict:
        # Full serialization for SQLite persistence
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
        # Reconstruct from SQLite for Living City mode
        ...

