# fire_agent_backend

Formal backend foundation for the Xinghuo fire emergency agent system.

This backend is built to support real event flow, replaceable simulation adapters, multi-agent decision workflows, task dispatch, replanning, and report generation. Stage 1 only provides the production-shaped foundation: app structure, configuration, database initialization, health checks, errors, and a base WebSocket channel.

## Run

```powershell
cd "C:\Users\Daisy\Desktop\GIS综合实习\星火智援\fire_agent_backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Default service URL:

```text
http://localhost:8200
```

## Stage 1 Endpoints

```text
GET /health
GET /api/system/status
GET /api/system/connections
WS  /ws/system
```

## Database

By default the backend creates:

```text
fire_agent_backend/data/fire_agent_backend.db
```

Set `DATABASE_URL` to switch to PostgreSQL or another SQLAlchemy-compatible database.
