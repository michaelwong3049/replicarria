import asyncio
from typing import List
from agents.loop import agent_graph
from agents.policy_parser import PolicyContext

NUM_ROUNDS = 10

def build_round_events(round_num: int, policy: PolicyContext) -> List[str]:
    return [
        f"Round {round_num} of the simulation.",
        f"Policy still in effect: {policy['summary']}",
    ]

def summarize_round(agents_by_id: dict, round_num: int):
    print(f"\n── Round {round_num} Summary ──────────────────────────")
    for agent_id in agents_by_id:
        state = agent_graph.get_state({"configurable": {"thread_id": agent_id}})
        if not state.values:
            continue
        name = state.values["name"]
        mood = state.values["mood"]
        stance = state.values["policy_stance"]
        opinion = state.values.get("policy_opinion", "")
        memories = state.values["memory_stream"]
        latest = memories[-1]["content"] if memories else "no memory yet"
        print(f"  {name}: mood={mood}, stance={stance:.2f}")
        print(f"    opinion: {opinion}")
        print(f"    memory:  {latest}")
    print()

async def run_simulation(agents_by_id: dict, policy: PolicyContext):
    for round_num in range(1, NUM_ROUNDS + 1):
        print(f"\n[Round {round_num}/{NUM_ROUNDS}] Processing...")

        round_events = build_round_events(round_num, policy)

        await asyncio.gather(*[
            agent_graph.ainvoke(
                {"round_events": round_events},  # type: ignore[arg-type]
                config={"configurable": {"thread_id": agent_id}}
            )
            for agent_id in agents_by_id
        ])

        summarize_round(agents_by_id, round_num)

    print("\n Simulation complete.")
