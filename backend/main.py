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

_sim_speed = {"value": 1.0}


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
    filename = file.filename or ''
    if filename.lower().endswith('.pdf'):
        try:
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                pages = [p.extract_text() or '' for p in pdf.pages[:12]]
            text = '\n\n'.join(p for p in pages if p.strip())
        except Exception as e:
            print(f'[pdf] parse error: {e}')
            text = contents.decode('utf-8', errors='ignore')
    else:
        text = contents.decode('utf-8', errors='ignore')
    body = SimulateRequest(
        policy_text=text[:6000],
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
        from agents.opinion_dynamics import apply_deffuant, push_stances, social_influence_event

        await sio.emit('sim_status', {'status': 'spawning', 'message': f'Generating {body.n_agents} citizens...'})

        policy = await parse_policy(body.policy_text, source='text')
        agents_by_id = await spawn_agents(body.n_agents, policy, use_memory=body.use_memory)

        await sio.emit('sim_status', {'status': 'running', 'message': 'Citizens forming opinions...'})

        _sim_speed["value"] = body.speed

        unemployment = 5.4
        social_unrest = 12.0
        gov_approval = 56.0
        prices = 2.1
        businesses_open = 95.0
        social_event = ""
        stances: list[float] = []
        key_moments: list[dict] = []

        for round_num in range(1, body.months + 1):
            round_events = build_round_events(round_num, policy)
            if social_event:
                round_events.append(social_event)

            stances = []
            round_notable: list[dict] = []
            for agent_id, agent in agents_by_id.items():
                try:
                    await agent_graph.ainvoke(
                        {"round_events": round_events},
                        config={"configurable": {"thread_id": agent_id}}
                    )
                except Exception as e:
                    print(f"[agent {agent_id}] round {round_num} error: {e}")

                state = agent_graph.get_state({"configurable": {"thread_id": agent_id}})
                if not state.values:
                    await asyncio.sleep(0.3)
                    continue
                v = state.values
                stance = v.get("policy_stance", 0.0)
                mood = v.get("mood", "neutral")
                opinion = v.get("policy_opinion", "")
                stances.append(stance)

                await sio.emit('agent_speak', {
                    'type': 'agent_speak',
                    'agent_id': agent_id,
                    'name': v.get("name", agent.identity['name']),
                    'role': v.get("occupation", agent.identity['occupation']),
                    'photo_url': agent.identity.get('photo_url', ''),
                    'x': agent.position['x'],
                    'y': agent.position['y'],
                    'text': opinion,
                    'mood': mood,
                })
                await asyncio.sleep(0.3)

                if mood in ("angry", "anxious", "hopeful", "optimistic") and opinion:
                    round_notable.append({
                        "round": round_num,
                        "agent": v.get("name", agent.identity['name']),
                        "quote": opinion,
                        "weight": abs(stance),
                    })

            if round_notable:
                round_notable.sort(key=lambda x: x["weight"], reverse=True)
                seen_agents = {m["agent"] for m in key_moments}
                for candidate in round_notable:
                    if candidate["agent"] not in seen_agents:
                        key_moments.append({k: candidate[k] for k in candidate if k != "weight"})
                        break

            if stances:
                avg_stance = sum(stances) / len(stances)
                state_list = [
                    agent_graph.get_state({"configurable": {"thread_id": aid}}).values
                    for aid in agents_by_id
                ]
                moods = [s.get("mood", "neutral") for s in state_list if s]
                upset = sum(1 for m in moods if m in ("angry", "anxious")) / max(len(moods), 1)

                gov_approval = max(0, min(100, (avg_stance + 1) / 2 * 100))
                social_unrest = min(100, upset * 80 + (1 - abs(avg_stance)) * 15)
                unemployment = max(0, 5.4 - avg_stance * 4)
                prices = max(0, 2.1 + (1 - avg_stance) * 1.2)
                businesses_open = max(0, min(100, 95 + avg_stance * 8 - upset * 10))

                new_stances = apply_deffuant(list(agents_by_id.keys()))
                push_stances(new_stances)
                social_event = social_influence_event(new_stances)

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

            await asyncio.sleep(15.0 / _sim_speed["value"])

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
            'key_moments': key_moments[-3:],
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
async def speed_change(sid, data):
    try:
        _sim_speed["value"] = float(data)
    except Exception:
        pass


@sio.event
async def converse_request(sid, data):
    try:
        from agents.conversation import resolve_conversation
        aid_a = data.get('agent_id_a')
        aid_b = data.get('agent_id_b')
        result = await resolve_conversation(aid_a, aid_b)
        if result:
            a_line, b_line, a_reply, b_reply = result
            await sio.emit('converse_response', {'a_line': a_line, 'b_line': b_line, 'a_reply': a_reply, 'b_reply': b_reply}, to=sid)
        else:
            await sio.emit('converse_response', {'a_line': '', 'b_line': ''}, to=sid)
    except Exception as e:
        print(f"[converse] {e}")
        await sio.emit('converse_response', {'a_line': '', 'b_line': ''}, to=sid)


@sio.event
async def connect(sid, environ):
    print(f'client connected: {sid}')


@sio.event
async def disconnect(sid):
    print(f'client disconnected: {sid}')
