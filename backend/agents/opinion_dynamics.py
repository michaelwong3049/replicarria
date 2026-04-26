import random
from agents.loop import agent_graph


def apply_deffuant(agent_ids: list[str], epsilon: float = 0.45, mu: float = 0.25) -> dict[str, float]:
    stances: dict[str, float] = {}
    for aid in agent_ids:
        state = agent_graph.get_state({"configurable": {"thread_id": aid}})
        if state.values:
            stances[aid] = float(state.values.get("policy_stance", 0.0))

    ids = list(stances.keys())
    random.shuffle(ids)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if abs(stances[a] - stances[b]) < epsilon:
                delta = mu * (stances[b] - stances[a])
                stances[a] = max(-1.0, min(1.0, stances[a] + delta))
                stances[b] = max(-1.0, min(1.0, stances[b] - delta))

    return stances


def push_stances(new_stances: dict[str, float]) -> None:
    for aid, stance in new_stances.items():
        try:
            agent_graph.update_state(
                {"configurable": {"thread_id": aid}},
                {"policy_stance": stance},
            )
        except Exception as e:
            print(f"[deffuant] could not update {aid}: {e}")


def social_influence_event(stances: dict[str, float]) -> str:
    if not stances:
        return ""
    vals = list(stances.values())
    avg = sum(vals) / len(vals)
    spread = max(vals) - min(vals)
    if spread > 1.0:
        return "Social update: Your neighborhood is deeply divided on this policy — people are arguing in the streets."
    if avg > 0.3:
        return "Social update: Most people around you seem to support this policy, though some are uneasy."
    if avg < -0.3:
        return "Social update: The mood in your area is skeptical — many neighbors are unhappy with this policy."
    return "Social update: Opinion is split where you live. Hard to know what to think."
