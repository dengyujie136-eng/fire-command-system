# 星火智援——森林火灾应急指挥系统

本项目是《GIS 综合实习》选题 8 的小组项目。当前阶段以一条统一事件链组织火情观测、证据融合、火势推演、辅助决策、资源推荐、情景重算和报告输出。

## 统一架构

```text
浏览器（Vue / Cesium）
        │ REST + WebSocket
        ▼
fire_agent_backend :8200      唯一业务编排后端
        ├── PostgreSQL/PostGIS :5432
        ├── ForeFire API :5000
        └── LLM provider
```

`forest_fire_B` 是历史实现，仅作为待迁移算法的参考，不再作为系统运行依赖。前端也不再直接访问 ForeFire；所有请求均通过 8200 后端编排。

## 推荐启动方式

需要安装 Git、Docker Desktop，并确保 Docker Desktop 已启动。

```powershell
git clone https://github.com/dengyujie136-eng/fire-command-system.git
cd fire-command-system
Copy-Item .env.example .env
docker compose up --build
```

也可以在 PowerShell 中运行：

```powershell
.\scripts\start-system.ps1
```

首次构建 ForeFire 需要编译 C++ 项目，等待时间会比普通前端构建长。服务启动后访问：

- 系统页面：http://localhost:5173
- 业务后端健康检查：http://localhost:8200/health
- 业务后端接口文档：http://localhost:8200/docs
- ForeFire 健康检查：http://localhost:5000/health
- PostgreSQL/PostGIS：`localhost:5432`

停止服务：

```powershell
.\scripts\stop-system.ps1
```

停止不会删除数据库。只有明确需要清空本地数据库时，才使用 `docker compose down -v`。

## 本地轻量开发

前端：

```powershell
npm install
npm run dev
```

Vite 会将 `/api` 和 `/ws` 统一代理到 `http://localhost:8200`。

业务后端：

```powershell
cd fire_agent_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

团队开发应优先使用 PostGIS。将 `DATABASE_URL` 留空时，后端会回退到 SQLite；该方式只适合快速接口检查，不作为课程正式数据基线。

## 配置与数据

- 前端及 Compose 配置模板：`.env.example`
- 后端独立运行模板：`fire_agent_backend/.env.example`
- 数据目录规则：`data/README.md`
- 在线 API 契约：`/docs` 和 `/openapi.json`
- 第一阶段架构与旧代码迁移清单：`docs/ARCHITECTURE_BASELINE.md`
- 课程要求基线：`COURSE_REQUIREMENTS.md`

不要提交 `.env`、模型密钥、个人数据库、大体积影像或本机绝对路径。公开样例数据应在 `data/manifest.example.json` 中登记来源、许可、坐标系和校验信息。

## 基础验证

```powershell
npm run build
python -m compileall fire_agent_backend\app
docker compose config
```

系统状态接口 `GET /api/system/status` 会返回数据库类型以及 PostGIS 是否可用，可用于检查团队成员的环境是否一致。
