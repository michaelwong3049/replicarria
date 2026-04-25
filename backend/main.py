import asyncio
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.policy_parser import parse_policy
from agents.spawner import spawn_agents
from agents.runner import run_simulation

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulateRequest(BaseModel):
    policy_text: str
    n_agents: int = 25
    city_id: str = "default"
    use_memory: bool = False

@app.post("/simulate")
async def start_simulation(body: SimulateRequest):
    policy = await parse_policy(body.policy_text, source="text")
    agents_by_id = await spawn_agents(body.n_agents, policy)
    asyncio.create_task(run_simulation(agents_by_id, policy))
    agents = [a.identity for a in agents_by_id.values()]
    return {"policy": policy, "agents": agents}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

