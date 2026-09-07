# 第一阶段架构基线与迁移清单

## 决策记录

从本阶段开始，项目只保留两个运行后端：

1. `fire_agent_backend`（8200）：事件、数据、决策、推荐、报告和 WebSocket 的唯一业务入口。
2. `backend/forefire_api`（5000）：只负责 ForeFire 火势计算，由 8200 后端调用。

`forest_fire_B`（原 8100）冻结为历史参考代码。禁止继续向其新增业务接口，待有价值的算法迁移并验证后再移除。

## 8100 后端待迁移资产

| 优先级 | 资产 | 来源 | 目标 | 验收标准 |
|---|---|---|---|---|
| P1 | A* 代价面路径搜索 | `forest_fire_B/services/route_search.py` | `fire_agent_backend/app/services` | 8200 提供路线接口，输入障碍、坡度和火势代价，输出 GeoJSON、总长度、风险和算法参数 |
| P1 | 资源注册与任务状态 | `forest_fire_B/models/registry.py`、tasks/decision 路由 | 8200 的资源与推荐模型 | 资源可入库、查询、分派和反馈，不再使用独立 SQLite 注册表 |
| P1 | Agent 工具调用经验 | `forest_fire_B/routers/agent.py` | 8200 Agent 工作流 | 每个角色具有明确输入输出、工具调用、状态和人工批准节点 |
| P2 | 环境上下文整理 | `forest_fire_B/services/environment_context.py` | 8200 环境快照服务 | 地形、气象、植被和保护目标具有来源、时间和空间范围 |

## 明确不迁移的内容

- 旧 `/api/fire/*`、`/api/b/*`、`/api/agent/*` 兼容接口。
- 旧 `/ws/alert`、`/ws/uav` 和 8100 Agent WebSocket。
- 静态模拟列表接口和浏览器本地归档逻辑。
- 旧后端的独立 SQLite 数据库及重复的事件模型。
- 只服务于历史页面、未进入当前 Vue 主流程的封装代码。

## PostGIS 基线

Docker 环境以 PostgreSQL 16 + PostGIS 3.4 为正式数据库。应用启动时会：

1. 创建业务表。
2. 启用 PostGIS 扩展。
3. 为火点、观测点、融合点、无人机、火线和路线创建 SRID 4326 的空间列。
4. 创建 GiST 空间索引。

现有 JSON/GeoJSON 字段继续作为 API 交换格式，空间列由数据库自动生成，避免前端接口在迁移期间发生破坏性变化。

## 接口边界

- 浏览器只访问同源 `/api` 和 `/ws`。
- Nginx/Vite 将请求转发至 8200。
- 8200 可调用 5000，但浏览器不直接调用 5000。
- 当前有效接口以 8200 自动生成的 `/openapi.json` 为准。

## 第一阶段完成标准

- 新克隆项目具有统一启动说明。
- `docker compose config` 可解析完整服务拓扑。
- 前端生产构建通过。
- 后端 Python 模块编译通过，SQLite 烟雾测试仍可运行。
- PostGIS 启动时自动建立空间列和索引。
- 前端源代码不再引用 8100、旧 5000 业务接口或失效 WebSocket。
