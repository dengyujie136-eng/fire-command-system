# API 契约

业务 API 的唯一权威定义由 `fire_agent_backend` 的 FastAPI OpenAPI 文档生成：

- 人类可读文档：`GET http://localhost:8200/docs`
- 机器可读契约：`GET http://localhost:8200/openapi.json`

## 当前稳定资源

- `/health`：服务、模型和数据库配置摘要。
- `/api/system/*`：运行状态与连接数。
- `/api/scenarios`：场景列表。
- `/api/events/*`：事件创建、查询、时间线和关闭。
- `/api/events/{event_id}/clock/*`：场景时钟。
- `/api/events/{event_id}/observations*`：观测、证据链、融合结果和可信火点。
- `/api/events/{event_id}/spread-runs*`：火势推演。
- `/api/events/{event_id}/decision-runs*`：决策运行与 Agent 数据包。
- `/api/events/{event_id}/recommendations*`：路线、无人机和资源推荐包。
- `/api/events/{event_id}/recalculate`：扰动情景重算。
- `/api/events/{event_id}/reports*`：报告生成与下载。
- `/ws/system`、`/ws/events/{event_id}`：系统和事件通道。

旧 5000/8100 业务接口不属于当前契约。新增前端功能前，应先在 8200 中定义 Pydantic 请求/响应模型，再通过自动文档检查契约。
