from datetime import datetime
from typing import List

STOPWORDS = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "it", "this", "that"}


def extract_keywords(text: str) -> List[str]:
    words = text.lower().split()
    return [w.strip(".,!?") for w in words if w not in STOPWORDS and len(w) > 3]


def score_memory(memory: dict, query_keywords: List[str], now: datetime) -> float:
    hours_since = (now - datetime.fromisoformat(memory["timestamp"])).total_seconds() / 3600
    recency = 0.99 ** hours_since
    importance = memory["importance"] / 10.0
    overlap = len(set(memory["keywords"]) & set(query_keywords))
    relevance = overlap / max(len(query_keywords), 1)
    return recency * 0.4 + importance * 0.4 + relevance * 0.2


def get_top_memories(memory_stream: List[dict], query: str, k: int = 8) -> List[str]:
    if not memory_stream:
        return []
    keywords = extract_keywords(query)
    now = datetime.now()
    scored = sorted(memory_stream, key=lambda m: score_memory(m, keywords, now), reverse=True)
    return [m["content"] for m in scored[:k]]


def should_reflect(cumulative_importance: float) -> bool:
    return cumulative_importance >= 25
