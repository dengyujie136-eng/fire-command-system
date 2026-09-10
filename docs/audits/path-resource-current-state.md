# 路径规划与资源调度现有代码全面审计

日期：2026-09-10
分支：`member/hp`
审计基线：`ae5bfc4 baseline: multi-agent architecture and agent output schema`
范围：只审计，不修改业务代码、接口、数据库模型、前端行为或算法实现。

## A. 路径规划现状

当前主链路是：`/api/events/simulated/start` 创建模拟事件 -> 观测/融合 -> 火势推演 -> `/api/events/{event_id}/decision-runs` 生成决策包 -> `/api/events/{event_id}/recommendations/regenerate` 生成推荐包 -> 前端路径/资源页面消费包数据。

关键文件和入口：

- `fire_agent_backend/app/main.py:46`、`:47` 挂载 active backend 的 decisions 和 recommendations 路由。
- `fire_agent_backend/app/routers/decisions.py:25` 提供 `POST /api/events/{event_id}/decision-runs`。
- `fire_agent_backend/app/services/decision_service.py:25` 定义包类型，`:31` 包含 `route_recommendation_packet`。
- `fire_agent_backend/app/services/decision_service.py:158` 构造所有决策包，`:261` 构造 `route_options`，`:327` 输出路径推荐包。
- `fire_agent_backend/app/services/recommendation_service.py:29` 在路径缺少坐标时从火点生成 fallback geometry，`:45` 标准化路径记录，`:155` 用路径数量估算 `route_length_km`。
- `src/stores/fireEventStore.ts:110` 兼容读取 `route_package` 与 `route_recommendation_packet`。
- `src/composables/useFireEventMapSync.ts:39` 解析多种 route coordinate 形态，`:220` 只有坐标不少于 2 个点时才画路线。

输入：事件、可信火点、环境快照、火势推演摘要、风险等级。没有 active backend 路网、道路阻断、路段速度、坡度代价、避险点、保护目标图层或火场风险栅格作为路径算法输入。

输出：当前路径包主要包含固定候选项的 `id/name/type/risk/summary/reason`。`decision_service` 不计算 geometry、距离、ETA、risk_score 或算法诊断；`recommendation_service` 后置补几何线。

算法判断：active backend 当前没有真实路径规划。没有 Dijkstra、A*、路网最短路、风险代价累计、道路阻断绕行或坡度/风场耦合寻路。`fire_agent_backend/app/services/recalculation_service.py:80` 的道路不可用处理只是改 route 状态和风险描述，不重新计算路线。

建议保留：active backend 的推荐包 envelope、`RecommendationPackage`、`RoutePlan.geometry`、前端多字段兼容解析、`ScenarioDisturbance/RecalculationRun` 这些壳和契约。

建议废弃或隔离：`forest_fire_B/routers/decision.py:76` 名为 A*，但实际返回起终点插值直线；逃生/消防员路线还使用固定距离和时间，不能作为真实路径算法迁移。

建议迁移复用：`forest_fire_B/services/route_search.py:123`、`:176` 是 legacy 中最有价值的路径规划参考，包含栅格 A*、代价面、风险评分和 diagnostics。应迁移到 `fire_agent_backend` 并补测试，而不是直接让 active backend 依赖冻结目录。

## B. 资源调度现状

关键文件和入口：

- `fire_agent_backend/app/services/decision_service.py:32` 定义 `resource_recommendation_packet`。
- `decision_service.py:287` 构造固定 `dispatch_tasks`，`:332` 输出资源推荐包。
- `fire_agent_backend/app/services/recommendation_service.py:96` 提取资源包，`:202` 到 `:216` 持久化 `ResourceInventory`。
- `src/stores/fireEventStore.ts:112` 兼容读取 `resource_package` 与 `resource_recommendation_packet`。
- `src/components/BackendDrivenPage.vue:261` 使用推荐记录或 dispatch tasks，`:402` 的页面文案暗示风险、到达时间、优先级调度。

输入：同样来自事件、可信点、环境、推演和风险摘要。active backend 没有真实库存源、队站位置、车辆/人员能力、空闲状态、行驶时间矩阵、水源/避难点/保护目标容量，也没有任务分配优化器。

输出：固定调度任务和摘要数字。`decision_service.py:332` 输出 `dispatch_tasks/dispatch_zones/summary_numbers`，其中人员 `48`、车辆 `8` 是硬编码。`fire_agent_backend/app/models/recommendation.py:59` 的 `ResourceInventory` 可以存 `resource_type/name/quantity/unit/status/target/metadata_json`，但缺少 location、capability、availability、ETA、assignment route、capacity、资质和消耗补给生命周期字段。

算法判断：active backend 当前没有真实资源调度优化。它生成确定性任务包并持久化，重算服务只改变状态/优先级文本，不做库存匹配、距离最短、ETA、容量约束或 route-aware dispatch。

建议保留：推荐包 JSON、`ResourceInventory.metadata_json`、前端 package-driven 展示、通用扰动/重算容器。

建议迁移复用：`forest_fire_B/models/registry.py:10` 的 UAV/resource/personnel registry 和 dispatch inventory/action log 可作为 schema 参考；`forest_fire_B/services/dispatch_state.py:330`、`:366`、`:408` 的分配逻辑可作为 demo seed/test fixture 参考；`forest_fire_B/services/resource_context.py:17` 的外部资源上下文读取可作为 future adapter 模式。

建议不要作为权威逻辑：`forest_fire_B/services/forefire_decision.py:381` 的 `ResourceDispatchAgent` 主要是固定任务模板和固定 ETA，适合参考包形态，不适合作为调度智能。

## C. 模拟、硬编码、fallback 与 demo 来源

主流程 simulated：

- `fire_agent_backend/app/routers/events.py:17` 提供 `/events/simulated/start`。
- `fire_agent_backend/app/services/event_service.py:74` 创建 simulation-mode event，`:92` 到 `:95` 写入 `is_simulated` 和 `data_source_mode=simulation`。
- `fire_agent_backend/app/services/scenario_registry.py:8` 定义默认场景。
- `fire_agent_backend/app/services/observation_service.py:38` 生成模拟观测输入，观测 schema/model 有 `is_simulated` 字段。

主流程 fallback：

- `fire_agent_backend/app/services/spread_service.py:83` 定义默认环境，`:139` 生成简化椭圆火线，`:254` 默认按 fallback 处理，ForeFire 成功后才取消。
- `fire_agent_backend/app/services/decision_service.py:178` 在 spread fallback 时写 warning。
- `fire_agent_backend/app/services/recommendation_service.py:29` 为缺坐标路线生成点位偏移线。
- `fire_agent_backend/app/services/recalculation_service.py:80` 对道路不可用做状态变更兜底。

主流程硬编码：

- `decision_service.py:261` 三条固定路线候选。
- `decision_service.py:287` 两条固定资源任务。
- `decision_service.py:332` 固定资源摘要数字。
- `recommendation_service.py:155` 按路线数量估算总里程，不是真实距离。

legacy/demo：

- `forest_fire_B/services/dispatch_state.py:33`、`:47`、`:56` 默认物资、人员、无人机库存。
- `forest_fire_B/services/forefire_decision.py:870` 资源缺失时返回 mock counts，`:880` 标记 `source=mock`。
- `forest_fire_B/services/route_search.py:477` 环境栅格缺失时使用几何兜底代价面。
- `forest_fire_B/services/resource_context.py:42` 外部资源上下文失败时使用本地默认资源。
- `forest_fire_B/routers/agent.py:151` 生成 mock drone route，属于 legacy/demo 行为。

前端 fake/demo：

- `src/composables/useFireEventMapSync.ts:414` 明确不再为 route/UAV/resource 图层生成 synthetic fallback routes。
- `src/components/BackendDrivenPage.vue:400`、`:402` 有较积极的说明文案，但实际数量来自后端包或推荐记录。
- `src/components/CesiumMap.vue:241` 附近的 demo entity 只是渲染函数，不是规划数据源。

## D. 数据模型是否支持后续升级

部分支持。现有事件、可信点、环境快照、推演、决策、AgentPacket、RecommendationPackage、RoutePlan、ResourceInventory、ScenarioDisturbance、RecalculationRun 可以承载审计链和兼容迁移。JSON 字段有利于先增量接入。

不足：active backend 没有路网 node/edge、道路风险、资源基地、队站、保护目标、水源、避难点、阻断路段、速度模型、ETA、路线算法 provenance、resource capability、availability window、capacity 和 assignment lifecycle 的一等模型。路线/资源输出也没有强制 `simulated/fallback/source/algorithm` 标识。

## E. 路径/资源数据依赖关系

当前真实链路：

`模拟事件/场景` -> `模拟观测与融合` -> `可信火点` -> `ForeFire 或简化火势推演` -> `Situation/Spread/Risk/Commander Agents` -> `DecisionService 固定路径/资源包` -> `RecommendationService 几何兜底与持久化` -> `RecalculationService 状态变更` -> `前端包渲染/报告`。

目标链路应变成：

`Fire Spread` -> `Risk Field` -> `Road/Terrain/Accessibility Risk Graph` -> `Route Planning` -> `Resource Dispatch` -> `CommanderAgent` -> `Recommendation Package` -> `Frontend/Report/Recalculation`。

当前项目有前半段和展示/持久化后半段，但中间的 `道路风险 -> 路径规划 -> 资源调度` 尚未在 active backend 中真正接入。

## F. 后续开发优先级

1. 先补 route/resource 输出契约，保留现有包名兼容，新增 `source/simulated/fallback/algorithm` 标识。
2. 建 active backend 的道路、风险、保护目标、资源库存 adapter。
3. 迁移或重写 `forest_fire_B/services/route_search.py` 到 `fire_agent_backend`，添加 contract/unit tests。
4. 做资源匹配服务，输入 inventory、route ETA、目标优先级和风险。
5. 让 recommendation service 调真实 route/resource service；fallback 必须显式标记。
6. 让 road/weather/resource disturbance 触发真实重算，而不是只改文本状态。
7. 后端字段稳定后再调整前端文案，避免 UI 先承诺未实现能力。

## G. 下一阶段文件级重构计划

建议新增：

- `fire_agent_backend/app/services/road_risk_service.py`
- `fire_agent_backend/app/services/route_planning_service.py`
- `fire_agent_backend/app/services/resource_dispatch_service.py`
- `fire_agent_backend/app/adapters/resource_context_adapter.py`
- `fire_agent_backend/app/schemas/route.py`
- `fire_agent_backend/app/schemas/resource_dispatch.py`
- 针对 route contract、fallback 标识、道路封闭重算、资源分配的测试文件。

建议后续修改：

- `fire_agent_backend/app/services/recommendation_service.py`：接入真实服务，停止无标识 fallback geometry。
- `fire_agent_backend/app/services/decision_service.py`：消费 route/resource 结果，不再构造固定业务包。
- `fire_agent_backend/app/services/recalculation_service.py`：对扰动触发重新规划/重新调度。
- `fire_agent_backend/app/models/recommendation.py`：契约确认后新增显式计算指标列。
- `src/components/BackendDrivenPage.vue`：等后端真实提供 risk/time/road-aware 字段后再调整文案。
- `docs/API_CONTRACT.md`：接口方案确认后更新。

建议暂不改：

- `forest_fire_B` 运行行为，只作为只读迁移参考。
- `src/api/modules.ts`，除非新增向后兼容接口调用。
- 高冲突公共 schema/API 文件，除非已有明确集成方案并写入日志。

## H. 风险

- legacy 路径代码质量不一致：`route_search.py` 有可复用 A*，`routers/decision.py` 有误导性 fake A*。
- 前端文案已经暗示道路/时间/风险调度，可能误导验收人员。
- 现有 JSON 包字段很宽松，前端可能依赖非正式字段名。
- `RecommendationService` 会从 `route_options` 和 `evacuation_routes` 合并后截断，当前二者常指向同一组路线，可能掩盖候选不足。
- 资源摘要数字不是库存计算结果，容易被误认为真实可用兵力。
- 重算服务会显示已处理道路不可用，但路线 geometry 不变。
- 迁移 `route_search.py` 需要处理 NumPy/HDF5/Shapely、`data/environment/final_input.nc` 和缺数据 fallback 策略。
- 后续 schema/model 变更会触碰高冲突公共契约，应分阶段兼容接入。