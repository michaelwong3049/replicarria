import asyncio
from dotenv import load_dotenv
load_dotenv()

import socketio
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.news import router as news_router

fastapi_app = FastAPI()
fastapi_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
fastapi_app.include_router(news_router)

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio, fastapi_app)


class SimulateRequest(BaseModel):
    policy_text: str
    n_agents: int = 7
    months: int = 3
    use_memory: bool = False
    speed: float = 1.0


@fastapi_app.post('/simulate')
async def start_simulation(body: SimulateRequest):
    asyncio.create_task(stream_simulation(body))
    return {'status': 'started'}


@fastapi_app.post('/simulate/upload')
async def start_simulation_upload(
    file: UploadFile = File(...),
    months: int = Form(3),
    use_memory: bool = Form(False),
):
    contents = await file.read()
    body = SimulateRequest(
        policy_text=contents.decode('utf-8', errors='ignore'),
        months=months,
        use_memory=use_memory,
    )
    asyncio.create_task(stream_simulation(body))
    return {'status': 'started'}


async def stream_simulation(body: SimulateRequest):
    try:
        from agents.policy_parser import parse_policy
        from agents.spawner import spawn_agents
        from agents.loop import agent_graph
        from agents.runner import build_round_events

        await sio.emit('sim_status', {'status': 'spawning', 'message': f'Generating {body.n_agents} citizens...'})

        policy = await parse_policy(body.policy_text, source='text')
        agents_by_id = await spawn_agents(body.n_agents, policy)

        await sio.emit('sim_status', {'status': 'running'})

        round_seconds = 60.0 / body.speed
        n_agents = len(agents_by_id)

        unemployment = 5.4
        social_unrest = 12.0
        gov_approval = 56.0
        prices = 2.1
        businesses_open = 95.0

        for round_num in range(1, body.months + 1):
            round_events = build_round_events(round_num, policy)

            for agent_id in agents_by_id:
                try:
                    await agent_graph.ainvoke(
                        {"round_events": round_events},
                        config={"configurable": {"thread_id": agent_id}}
                    )
                except Exception as e:
                    print(f"[agent {agent_id}] round {round_num} error: {e}")
                await asyncio.sleep(0.4)

            stances = []
            for agent_id, agent in agents_by_id.items():
                state = agent_graph.get_state({"configurable": {"thread_id": agent_id}})
                if not state.values:
                    continue
                v = state.values
                stances.append(v.get("policy_stance", 0.0))

                await sio.emit('agent_speak', {
                    'type': 'agent_speak',
                    'agent_id': agent_id,
                    'name': v.get("name", agent.identity['name']),
                    'role': v.get("occupation", agent.identity['occupation']),
                    'photo_url': agent.identity.get('photo_url', ''),
                    'x': agent.position['x'],
                    'y': agent.position['y'],
                    'text': v.get("policy_opinion", ""),
                    'mood': v.get("mood", "neutral"),
                })
                await asyncio.sleep(0.1)

            if stances:
                avg_stance = sum(stances) / len(stances)
                state_list = [
                    agent_graph.get_state({"configurable": {"thread_id": aid}}).values
                    for aid in agents_by_id
                ]
                moods = [s.get("mood", "neutral") for s in state_list if s]
                upset = sum(1 for m in moods if m in ("angry", "anxious")) / max(len(moods), 1)

                gov_approval = max(0, min(100, (avg_stance + 1) / 2 * 100))
                social_unrest = min(100, upset * 100 + round_num * 2)
                unemployment = max(0, 5.4 - avg_stance * 3 + round_num * 0.3)
                prices = max(0, 2.1 + (1 - avg_stance) * 0.5 * round_num)
                businesses_open = max(0, 95 - social_unrest * 0.2)

            await sio.emit('economic_update', {
                'type': 'economic_update',
                'round': round_num,
                'month': f"Month {round_num}",
                'unemployment': round(unemployment, 1),
                'social_unrest': round(social_unrest, 1),
                'gov_approval': round(gov_approval, 1),
                'prices': round(prices / 100, 3),
                'businesses_open': round(businesses_open, 1),
            })

            if round_num < body.months:
                await asyncio.sleep(round_seconds)

        final_stance = sum(stances) / len(stances) if stances else 0.0
        verdict = "positive" if final_stance > 0.2 else "negative" if final_stance < -0.2 else "mixed"

        try:
            from anthropic import Anthropic
            _client = Anthropic()
            opinions = []
            for agent_id, agent in agents_by_id.items():
                state = agent_graph.get_state({"configurable": {"thread_id": agent_id}})
                if state.values:
                    opinions.append(f"{state.values.get('name','?')} ({state.values.get('occupation','?')}): {state.values.get('policy_opinion','')}")
            opinion_text = "\n".join(opinions[:6])
            narrative_resp = _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=180,
                messages=[{"role": "user", "content": f"""Write 2 short punchy sentences summarizing this policy simulation. Be vivid and story-like, not dry.
Policy: {body.policy_text[:150]}
Outcome: {verdict} — unemployment {round(unemployment,1)}%, approval {round(gov_approval,1)}%, unrest {round(social_unrest,1)}
Citizen voices:\n{opinion_text}
No bullet points. No headers. Just the narrative."""}]
            )
            narrative = narrative_resp.content[0].text.strip() if narrative_resp.content else ""
        except Exception:
            narrative = f"After {body.months} months, the city responded with a {verdict} verdict on this policy."

        await sio.emit('simulation_end', {
            'type': 'simulation_end',
            'verdict': verdict,
            'summary': narrative,
            'key_moments': [],
            'final_indices': {
                'unemployment': round(unemployment, 1),
                'social_unrest': round(social_unrest, 1),
                'gov_approval': round(gov_approval, 1),
                'prices': round(prices, 2),
                'businesses_open': round(businesses_open, 1),
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        await sio.emit('error', {'message': str(e)})


@sio.event
async def connect(sid, environ):
    print(f'client connected: {sid}')


@sio.event
async def disconnect(sid):
    print(f'client disconnected: {sid}')
