# heimini 开发日志

## 2026-09-18｜成员丁接入统一主线

- 分支：`member/heimini-main-integrated`
- 最新提交：本地集成提交完成后以 Git 历史为准
- 任务目标：以最新 `origin/main` 为基线，迁移成员丁 Agent、规划、资源与路径能力，并打通甲候选点、乙视觉确认、丙火势/空间分析到丁指挥决策的真实闭环。

### 已完成

- 保留 Situation、Spread、Risk、Resource、Route、Commander Agent 和 MultiAgentOrchestrator。
- 保留 Dijkstra、A*、risk-aware A*、资源分配、任务规划与执行算法。
- 新增 `IncidentContext`，Agent 仅消费 DTO，不接收跨模块 ORM 对象。
- 新增 `TrustedIgnitionAdapter`，只接受乙方当前有效且状态为 confirmed 的 `fire_confirmations`。
- 新增 `SpreadAdapter`，将可信火点和甲方小时气象转换为丙方 `SpreadRunRequest`，调用现有 raster/dynamic spread service。
- 新增 `SpatialRiskAdapter`，调用丙方现有 spatial analysis service。
- 新增统一 command workflow，持久化 candidate、visual case、confirmation、spread、spatial、decision、agent packet、recommendation 的 ID 关系。
- Resource/Route 在缺少真实输入时返回 `unavailable`，不使用 synthetic inventory 或 synthetic graph 冒充真实结果。
- 视觉复核页面的一键操作改为调用现有完整 review 接口，确保生成 confirmation。
- Command Center 改为统一工作流状态页，显示执行状态、真实 ID、指挥方案和 unavailable 原因。

### 主要文件

- `fire_agent_backend/app/integrations/`：跨成员 DTO 与可信火点、火势、空间风险适配层。
- `fire_agent_backend/app/services/command_workflow_service.py`：A→B→C→D 编排与持久化。
- `fire_agent_backend/app/routers/command_workflow.py`：统一工作流 HTTP API。
- `fire_agent_backend/app/agents/`：成员丁 Agent、编排、规划与算法兼容迁移。
- `fire_agent_backend/app/models/decision.py`：DecisionRun 增加可追溯上游 ID。
- `fire_agent_backend/app/db/spatial.py`：仅新增 nullable 字段与索引的兼容升级。
- `src/views/CommandCenter.vue`：统一工作流状态与结果页面。
- `src/views/VisualVerification.vue`：完整 review 调用。
- `src/api/modules.ts`：视觉 review 与 command workflow API 客户端。
- `fire_agent_backend/tests/test_command_workflow_integration.py`：跨成员闭环测试。

### 接口变化

- 新增：`POST /api/events/{event_id}/command-workflow`。
- 请求字段：`confirmation_id` 或 `candidate_id`、`horizon_minutes`、`threat_buffer_km`、可选 `force_provider`。
- 响应字段：workflow status、完整 identifiers、confirmed point、situation、spread、spatial risk、resource、route、command plan、recommendation、agent results、warnings。
- 新增：`GET /api/events/{event_id}/command-workflow/latest`。
- 复用：`POST /api/visual-verification/candidates/{visual_case_id}/review`。
- 错误行为：没有 confirmed fire confirmation 时拒绝进入 spread；缺资源/路网不会使整体工作流失败，而是明确返回 unavailable。

### 数据库与数据变化

- `decision_runs` 新增 nullable 字段：`source_candidate_id`、`visual_case_id`、`confirmation_id`、`spread_run_id`、`spatial_analysis_id`。
- 字段升级为 additive/backward-compatible，不删除、不清空任何现有表。
- 实际运行确认甲方数据保留：hotspots 60013、clusters 11704、daily weather 105、hourly weather 2520、realtime observations 17、realtime hotspots 6363。
- 本次端到端测试使用成员甲 GOES-18 本地演示影像并明确标记 `is_simulated=true`；真实 Qwen 调用成功，未伪造模型结果。

### 配置与依赖变化

- 未新增代码依赖，未修改 compose 配置。
- 本机 `.env` 配置 Qwen、Cesium 和 FIRMS；`.env` 保持 Git ignored，密钥未写入代码或日志。
- 本地 ignored 数据仅增量同步到独立 worktree，不纳入提交。

### 验证结果

- `[通过]` 最新 main 基线：127 passed，25 warnings（Python 3.12 Docker）。
- `[通过]` 集成后端：305 passed，25 warnings（Python 3.12 Docker）。
- `[通过]` `npm run build`。
- `[通过]` `python -m compileall fire_agent_backend/app backend/forefire_api/app`。
- `[通过]` `docker compose config --quiet`。
- `[通过]` fire-agent-api 与 frontend Docker build；ForeFire 单独构建因 USTC Docker 镜像源 EOF 未完成，但 Dixie 主链使用内置 raster tool，不依赖该服务。
- `[通过]` fire-agent-api、frontend、postgis 运行；postgis 与 fire-agent-api healthy。
- `[通过]` 甲乙丙丁关键 HTTP API；真实闭环生成并持久化完整 ID 链。
- `[部分通过]` 无头浏览器确认 realtime-monitor 与 command-center 非白屏，command-center 读取真实 ID；Windows CUA helper 故障，其余页面通过 HTTP/路由但未完成可靠截图验收。

### 对其他模块的影响

- 依赖甲：candidate、weather、realtime/catalog 和 Dixie 数据。
- 依赖乙：visual case、finding、fusion 和 confirmed fire confirmation。
- 依赖丙：spread service、raster tool、spatial analysis service。
- 提供下游：可追溯 DecisionRun、AgentPacket、RecommendationPackage 和 Command Center 状态。
- 高冲突公共文件：`src/api/modules.ts`、`fire_agent_backend/app/main.py`；修改仅注册新 API 和客户端方法。

### 已知问题与下一步

- 本机缺少清单引用的 Sentinel-2 GeoTIFF，保持 Missing；没有伪装为 Available。
- 缺少真实资源 inventory，因此 ResourceAgent 在真实主链返回 unavailable。
- 缺少有效 OSM road graph，因此 RouteAgent 在真实主链返回 unavailable。
- ForeFire 镜像构建受 Docker 镜像源 EOF 影响；Dixie raster spread 已实际运行成功。

### 合并提示

- 可以交给项目负责人审查；不得直接推送或合并 main。
- 重点检查 decision_runs 的 additive 字段、command workflow 路由、VisualVerification review 调用和 Command Center 的真实/不可用状态表达。
