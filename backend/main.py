import asyncio
from dotenv import load_dotenv
load_dotenv()

import socketio
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.news import router as news_router

fastapi_app = FastAPI()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(news_router)

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio, fastapi_app)


class SimulateRequest(BaseModel):
    policy_text: str
    n_agents: int = 12
    months: int = 3
    use_memory: bool = False
    speed: float = 1.0


@fastapi_app.post('/simulate')
async def start_simulation(body: SimulateRequest):
    asyncio.create_task(stream_simulation(body))
    return {'status': 'started'}


async def stream_simulation(body: SimulateRequest):
    try:
        from agents.policy_parser import parse_policy
        from agents.spawner import spawn_agents
        from agents.graph import run_simulation

        policy = await parse_policy(body.policy_text, source='text')
        agents_by_id = await spawn_agents(body.n_agents, policy)

        round_seconds = 60 / body.speed

        async for event in run_simulation(
            policy=policy,
            agents_by_id=agents_by_id,
            months=body.months,
            use_memory=body.use_memory,
            round_seconds=round_seconds,
        ):
            await sio.emit(event['type'], event)

    except Exception as e:
        await sio.emit('error', {'message': str(e)})


@fastapi_app.post('/simulate/upload')
async def start_simulation_upload(
    file: UploadFile = File(...),
    months: int = Form(3),
    use_memory: bool = Form(False),
):
    contents = await file.read()
    asyncio.create_task(stream_simulation_file(contents, file.filename or '', months, use_memory))
    return {'status': 'started'}


async def stream_simulation_file(contents: bytes, filename: str, months: int, use_memory: bool):
    try:
        from agents.policy_parser import parse_policy
        from agents.spawner import spawn_agents
        from agents.graph import run_simulation

        source = 'pdf' if filename.endswith('.pdf') else 'text'
        policy = await parse_policy(contents.decode('utf-8', errors='ignore'), source=source)
        agents_by_id = await spawn_agents(12, policy)

        async for event in run_simulation(
            policy=policy,
            agents_by_id=agents_by_id,
            months=months,
            use_memory=use_memory,
            round_seconds=60.0,
        ):
            await sio.emit(event['type'], event)

    except Exception as e:
        await sio.emit('error', {'message': str(e)})


@sio.event
async def connect(sid, environ):
    print(f'client connected: {sid}')


@sio.event
async def disconnect(sid):
    print(f'client disconnected: {sid}')
