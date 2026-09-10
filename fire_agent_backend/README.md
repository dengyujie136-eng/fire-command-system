# fire_agent_backend

星火智援系统的唯一业务编排后端，默认端口为 8200。它负责事件、场景时钟、观测与证据融合、火势推演编排、决策、推荐、重算、报告以及 WebSocket 通知。

ForeFire 是由本服务调用的专用计算服务，不是浏览器 API。`forest_fire_B` 是冻结的历史实现，不是运行依赖。

## 独立运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

正式团队基线使用 PostgreSQL/PostGIS：

```text
DATABASE_URL=postgresql+asyncpg://xinghuo:xinghuo_dev@localhost:5432/xinghuo
```

将 `DATABASE_URL` 留空会回退到 `data/fire_agent_backend.db`，仅建议用于轻量烟雾测试。

## 检查

- `GET /health`
- `GET /api/system/status`
- `GET /docs`
- `GET /openapi.json`
- `WS /ws/system`
- `WS /ws/events/{event_id}`

PostgreSQL 启动时会自动启用 PostGIS，并为主要点、火线和路线建立空间列与 GiST 索引。
