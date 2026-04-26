# Replicarria

A real-time economic simulation engine that shows how the general population reacts to policy decisions before they happen.

Feed it any policy headline or PDF. Watch a city of AI citizens react, argue, and move real economic indicators across simulated months.

## Setup

**Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in your keys in .env
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Keys needed

Copy `.env.example` to `backend/.env` and fill in:

```
ANTHROPIC_API_KEY   # anthropic.com
NEWSAPI_KEY         # newsapi.org (free tier)
```

## How it works

Seven AI citizens with real randomuser.me identities process a policy through a memory-retrieve-reflect-plan loop every simulated month. Post-round, all agent pairs run the Deffuant bounded confidence model to update stances. Five economic indices (gov approval, unemployment, social unrest, price index, business survival) respond in real time to agent sentiment. Agents converse when they cross paths on the city map, updating each other's beliefs and memories.

**Fresh City** starts agents from scratch every run. **Living City** agents remember previous simulations.
