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

## 2026-09-18 - Unified wildfire command productization

- Branch: member/heimini-main-integrated. Scope: additive unified incident context, nine-stage async command workflow, deterministic scenario/resource/route planning, commander review, and three-entry product navigation.
- Main files: workflow ORM/schema/router/runtime service, scenario rule YAML files, incidentContextStore, command components, CommandCenter.vue, DisasterAssess.vue, CesiumMap.vue, AppHeader.vue, and workflowRuntime API methods.
- API: added workflow event/readiness, create/latest/detail, human verification, scenario generate/confirm, commander review, and resume endpoints under /api.
- Persistence: added workflow_runs, workflow_stage_runs, emergency_scenarios, scenario_locations, scenario_resources, scenario_resource_plans, and scenario_route_plans. Existing tables and data paths remain additive.
- Runtime validation: npm run build, Python compileall, docker compose config --quiet, API/frontend image builds, healthy PostGIS/API/frontend containers, same-origin proxy checks, legacy route checks, and Dixie end-to-end workflow.
- Dixie E2E result: data preparation 5/7 available, Sentinel/GOES explicitly Missing, human confirmation completed, spread/spatial/scenario/resource/route/commander completed, deterministic scenario rules scenario-rules-v0.2, final workflow status COMPLETED with no error.
- Scenario smoke test passed under Python 3.13 for deterministic safe locations and SCENARIO_ROUTE graph creation.
- Test limitation: pytest is not installed in the local Python environments or API image; full pytest suite was not claimable. The available unittest run passed dependency-light agent/resource/route tests but reported import errors for tests requiring uninstalled project dependencies.
- Browser visual validation limitation: the Windows CUA helper exited before a screenshot could be captured. HTTP route and bundle checks passed; no browser screenshot claim is made.
- No Git push, merge, reset, clean, volume deletion, or data deletion was performed. Local realtime demo data remains untracked and untouched.

## 2026-09-18 - Command center product semantics and Dixie Fire regression

- Branch: `member/heimini-main-integrated`
- Replaced the realtime-monitor display-only handoff sidebar with a two-column monitoring workspace so the Cesium map receives the released space.
- Reworked the command center into a compact map-centered workspace with a real fire-front timeline player. It reads the backend `fire_front_steps` only, supports pause/replay, 0.5x/1x/2x speed, and time-step selection.
- Introduced scenario rule v0.3 semantics: dynamic safe command/staging locations, deterministic exercise rescue teams, an operations approach outside the modeled fire edge, an explicitly exercise-only protected target, inventory-only resource display, and a team-to-approach scenario accessibility route.
- Normalized Commander planning input so the structured Chinese summary uses the calculated ETA and Chinese resource names rather than internal resource IDs.
- Validation: `npm run build`, `python -m compileall fire_agent_backend/app backend/forefire_api/app`, `docker compose config --quiet`, rebuilt `fire-agent-api` and `frontend`, container health checks, and a complete Dixie Fire historical workflow through the Commander review gate. Final run `wfr_70dc7bafdda74b7194` produced 7 real fire-front steps (0 to 360 minutes), completed all nine stages, and calculated the exercise team-1 to operations-approach route as 1.5917 km / 4.08 minutes / 0.2394 risk.
- Known validation limitation: browser UI automation could not start because the Windows sandbox helper returned `setup refresh had errors`; production bundle marker checks, HTTP checks, API workflow validation, and frontend logs were successful.
- No Git add, commit, or push. No volumes, data directories, compose files, or unrelated member pages were modified.

## 2026-09-18 - Command Center decision-product refinement

- Branch: member/heimini-main-integrated. Scope: product presentation and business transparency for the existing nine-stage Dixie Fire Command Center workflow.
- Main files: src/views/CommandCenter.vue, src/components/CesiumMap.vue, src/components/command/WorkflowStatusPanel.vue, and src/components/command/CommandSituationPanel.vue.
- Interaction: the left workflow state panel now distinguishes completed, executing, waiting-for-confirmation, and failed stages; stage selection still switches the lower work area without leaving the page. Fire-front playback reports the current T+ time back to the spread stage.
- Product semantics: the command page disables the map wind-vector canvas and displays current wind speed, direction, temperature, and humidity in the right-side situation panel. The page now explains real fire-front playback metrics, risk-grid weights, scenario candidate ranking, exercise inventory, route inputs/outputs, and Chinese commander advice sections.
- Data boundary: no route, inventory, target, or candidate score was reclassified as real. Candidate scores remain the existing 95 - rank x 7 internal rule (88/81/74); real OSM roads, verified inventory, surveyed slope, water reserve rate, and real target layers remain explicitly unavailable.
- API/database/config: no API request or response contract, database schema, compose file, data file, environment variable, or dependency was changed.
- Validation: npm run build; Python compileall; docker compose config --quiet; rebuilt frontend image; PostGIS and fire-agent-api healthy; command-center, realtime-monitor, and health HTTP routes returned 200; production frontend bundle contained the new T+ playback and wind-display text.
- Dixie regression: new run wfr_6ac7d5189f1e42569d completed data preparation, human fire verification, raster spread, spatial risk, scenario recommendation, resource dispatch, route planning, and commander recommendation gate. It produced 7 fire-front steps, 0.8815 km2 final area, 321.3 degree spread direction, high risk, no resource shortage, and a 1.5917 km / 4.08 minute / 0.2394-risk A* exercise route.
- Known limitation: Windows CUA browser automation remains unavailable because its helper reports setup refresh errors. HTTP, production bundle, Docker logs, and complete backend workflow checks passed; no screenshot claim is made.
- No Git add, commit, push, merge, reset, clean, database deletion, volume deletion, or data deletion was performed.

## 2026-09-18 - Command Center workflow spread rerun

- Branch: member/heimini-main-integrated. Scope: safely expose the existing member C raster fire-spread inputs inside the unified Command Center workflow.
- Added POST /api/workflow-runs/{workflow_run_id}/spread-reruns. It requires a current human-confirmed fire point and an existing workflow spread result; it never calls the public raw spread endpoint from the client.
- The rerun path uses SpreadAdapter, which still delegates to create_spread_run and the existing Dixie raster tool. It records Command Center what-if inputs as a source, clears active spatial/scenario/resource/route/decision identifiers, recalculates spatial risk and situation, and regenerates a scenario candidate.
- Old downstream results remain persisted for traceability but are detached from the active workflow and their stages are marked invalidated. A regenerated scenario must be confirmed again before the existing resource, route, and Commander stages can run.
- Updated files: app/integrations/spread.py, app/schemas/workflow.py, app/routers/workflow_runtime.py, app/services/workflow_runtime_service.py, src/api/modules.ts, src/stores/incidentContextStore.ts, and src/views/CommandCenter.vue.
- Frontend: the spread stage has environmental what-if controls, source and model-boundary labels, and continues to render only persisted fire_front_steps through the existing Cesium timeline player.
- Validation: npm run build; python -m compileall fire_agent_backend/app backend/forefire_api/app; docker compose config --quiet; rebuilt API/frontend images; healthy postgis/API/frontend; command-center and same-origin workflow API returned 200; no traceback, ERROR, or 500 in recent service logs.
- Dixie rerun validation: changed wind to 5.0 m/s at 203 degrees for workflow wfr_e593601e2dce40dd8b. New run spr_710b3f357afe4f1cbe produced seven real steps, 0.8815 km2 final area, 219.8 degree direction, a new spatial analysis spa_cd2cfc25bcdf439992, a new scenario scn_fcb2f90643694952a7, route rtp_35142a1742dd48ae8a, and Commander decision dec_9a7c4910b023428a86.
- No database schema, compose configuration, fire-spread model, raw spread API behavior, data file, Git index, commit, or remote branch was changed.


## 2026-09-22 - Five-page local redesign and 100% zoom layout

- Branch: member/heimini-main-integrated. Goal: implement monitoring, verification, simulation, planning and assessment in the local project actually serving port 5173, with a persistent right business/chat dock and compact 100% zoom layout.
- Completed: five-item header navigation; monitoring retains historical replay and real-time fire data while its satellite-image demo option moves to verification; verification combines GOES-18 target detection and candidate screening with the existing Qwen-VL review; simulation retains Command Center workflow; planning exposes route/resource tabs; assessment adds local before/after image review, manually marked impacts and evidence-linked reconstruction suggestions.
- Right dock: existing Command Center situation, BackendDrivenPage agent, Qwen verification evidence, satellite candidate detail, and assessment evidence panels switch with the persistent local conversation interface. Business state and map remain visible across the five workflows.
- Layout: reduced header, panels, typography, form controls and Command Center markers; changed Command Center grid rows to preserve a scrollable lower workspace at 100% browser zoom.
- Main files: src/App.vue, src/components/{AppHeader,AgentChat,BackendDrivenPage}.vue, src/components/command/{WorkflowStatusPanel,CommandSituationPanel}.vue, src/router/index.ts, src/views/{RealtimeMonitor,CommandCenter,VisualVerification,VerificationWorkspace,SatelliteVerification,Planning,DisasterAssess,AssessmentWorkspace}.vue, fire_agent_backend/app/{main.py,routers/assistant.py}.
- API: POST /api/assistant/chat accepts message (1-1000 characters), page and a compact client-side context (event ID/name, mode, workflow status/stage, confirmation and result IDs). Response is {ok:true,data:{message,source_mode,navigate_to?}}. Invalid request returns FastAPI 422. Endpoint does local status/navigation routing only; it does not call a third-party model or transmit event data outside the local backend.
- Database/data/config/dependencies: no changes. Existing untracked realtime demo data and other WIP preserved. No new environment variable is required.
- Validation: npm run build passed; python -m compileall -q fire_agent_backend/app passed; docker compose config --quiet passed; git diff --check passed. Local API and frontend images rebuilt; API healthy; frontend /command-center returned 200; /api/assistant/chat appears in local OpenAPI. Browser screenshot verification remains unvalidated because CUA helper exited and headless Chrome did not produce a screenshot.
- Pending: confirm visual spacing interactively at 100% in the user's browser; current assessment is an explicit manual image interpretation workflow and does not claim automatic change detection or computed loss area. The local conversation interface reports loaded state and routes to pages; open-ended model conversation is not connected.
- Integration attention: src/App.vue, src/components/AppHeader.vue, src/router/index.ts, src/views/CommandCenter.vue, and fire_agent_backend/app/main.py are high-conflict UI/backend entry points. New assistant route is local only. No Git sync, add, commit, push or upload.

## 2026-09-22 - Five workspaces separated in the local browser project

- Branch: member/heimini-main-integrated. Goal: apply the user's corrected page ownership and left navigation locally; no branch synchronization or upload.
- Completed: moved the five navigation items into a fixed left sidebar; / redirects to monitoring and legacy page routes redirect to the matching workspace. Monitoring owns historical replay, real-time hotspots and event preparation. Verification owns satellite candidate detection, professional object detection output, Qwen-VL visual result and human confirmation. Simulation uses the member/wydze style FirePredict workbench for fire spread with manual weather inputs. Planning owns scenario, resource, route and commander stages. Assessment is a single before/after image workspace.
- Main frontend files: src/App.vue, src/components/AppSidebar.vue, src/components/AppHeader.vue, src/router/index.ts, src/views/RealtimeMonitor.vue, src/views/VerificationWorkspace.vue, src/views/VisualVerification.vue, src/views/FirePredict.vue, src/views/Planning.vue, src/views/CommandCenter.vue and src/views/AssessmentWorkspace.vue.
- API: verification reuses existing /api/visual-verification/candidates/{visual_case_id}/review, which returns professional_run, professional, visual, confirmation and warnings. The local assistant /api/assistant/chat supplies navigation targets and time-window query fields; it does not call an external LLM. No new API contract was added in this final frontend pass.
- Data/database/config/dependencies: no changes in this pass. New affected-point and firefighter-position markers and water/food request fields are local UI state; they are not included in route or resource computations. Assessment imagery stays local to the browser; automatic Qwen assessment and damaged-area extraction await imagery and an API.
- Validation: npm run build, Python compileall, docker compose config --quiet and git diff --check passed. API/frontend containers rebuilt and started; API health returned 200, all five frontend routes returned 200, same-origin workflow events returned 200, and the served bundle contains left navigation and assistant labels.
- Unverified: 100% zoom visual screenshot. The Windows computer-use node kernel again failed with "setup refresh had errors"; no screenshot or pixel-level layout claim is made.
- Known gaps: automatic arbitrary-data download with a one-minute link, scheduled hourly/two-hour weather refresh, recomputation for newly clicked affected points and firefighter supplies, and Qwen disaster-area extraction are not yet implemented. UI labels describe these states explicitly rather than presenting fabricated results.
- Integration attention: shared router, App layout, CommandCenter, and visual verification workflow are high-conflict files. No Git sync, add, commit, push, or upload.

## 2026-09-22 - Monitoring wind, team routes, and timed spread output

- Branch: member/heimini-main-integrated. Goal: apply the user's six UI corrections locally in the project served at localhost:5173. No branch sync or upload.
- Frontend: monitoring now uses CesiumMap wind particles instead of diagonal CSS stripes and adds flowing trails at close zoom; navigation is 72 px wide without top/bottom captions; header title is 星火智援. Verification disables rerunning a confirmed/rejected visual case and explains HTTP 409. Planning was replaced by firefighter starts and task targets with map picking, generated teams, mismatch/reserve warnings, route cards and water/food request fields. Assistant chat has a persistent spread-output card with status, area, direction and fireline extent. Simulation has an independent 1-24 hour horizon selector.
- Backend: POST /api/planning/preview accepts event_id, teams[], targets[] and optional fire_center, each point with longitude and latitude. It returns source_mode=simulated, synthetic grid network label, A* plan routes, unassigned target indexes, reserve team indexes and limitations. This endpoint uses the existing routing calculation unit; it does not claim real roads. Assistant POST /api/assistant/chat may now return action={type:run_spread,horizon_minutes}; phrases such as four hours later and explicit start map to 240 minutes. Existing workflow rerun endpoint executes the model asynchronously.
- Resource rules: new exercise scenarios omit UAV from all size templates; RESOURCE_RULE_VERSION changed to v0.4. Existing persisted scenarios are unchanged; the planning UI also filters out old UAV inventory entries.
- Database/data/config/dependencies: no table, data-file, environment variable, dependency or Compose changes. The new preview endpoint does not persist plans. Selected points and supply requests are local UI state.
- Validation: npm run build, Python compileall, docker compose config --quiet, git diff --check passed. Python 3.12 container ran 27 routing/planning tests successfully. A simulated 2-team/3-target API request returned two calculated routes and unassigned target index 2. Local assistant parser returned a 240-minute action for both '开始推演Dixie Fire' and '帮我预测四个小时之后火势会蔓延到哪里'. The current Dixie visual candidate was confirmed by read-only API check, matching the reported 409. API/frontend containers were rebuilt and healthy; all five frontend paths responded 200.
- Limitation: hourly/two-hour weather checks are UI settings; the current spread rerun uses one weather input across the selected horizon. Automatic hour-by-hour weather replacement is not implemented. The preview route is an exercise grid, not verified road navigation; water and food entries are requests rather than calculated delivery. 100% zoom screenshot validation remains unavailable because the Windows UI automation helper exits with setup refresh errors.
- Integration attention: AppHeader, AppSidebar, RealtimeMonitor, FirePredict, CesiumMap, Planning, AgentChat, assistant router, main router registration and scenario resource rules. No Git add, commit, push, merge, reset, clean or upload.


## 2026-09-23 - Historical imagery data agent and real assistant orchestration

- Branch: `member/heimini-main-integrated`. Scope: local-only implementation in the project served at port 5173; no branch synchronization, commit, push, upload or Git cleanup.
- Fixed simulation rerun: the Dixie page can rerun the persisted historical raster pipeline when no human-confirmed workflow exists, while a confirmed workflow uses the existing what-if rerun endpoint and manual weather fields. The assistant now parses a 1-24 hour horizon plus wind speed, wind direction, temperature and humidity and transfers those values into the actual simulation request.
- Assistant orchestration: POST `/api/assistant/chat` now returns executable actions for a full workflow, imagery acquisition, verification, spread, planning and assessment. AgentChat starts/polls persisted workflows and imagery tasks, shows actual stage IDs/status/errors, routes pages, keeps the existing human verification and scenario gates, and resumes automatic verification/assessment when downloaded imagery becomes available.
- Historical database/data agent: added the persisted `imagery_acquisition_tasks` table and `/api/data-agent/imagery` routes for California event listing/registration, catalog lookup, trusted STAC search, local reuse, Sentinel-2/Landsat five-band download, checksum and GeoTIFF validation, aligned AOI product creation, local registration/upload and task status. After 60 seconds the task status includes the selected scene or official portal URL and the real manual import directory `data/raw/imagery/import`.
- Data integrity: primary verification searches are constrained to the event and a continuous 24-hour window; missing contemporaneous scenes are returned as `no_match` rather than substituted by another date. Band requirements are B02/B03/B04/B08/B12. Real products are marked `is_simulated=false`; the existing exercise grid planner remains labelled simulated.
- Verification/assessment: real five-band products are attached to real visual cases, the existing image derivative/professional detector/Qwen review chain is reused, and the assessment page runs the existing dNBR/dNDVI raster change endpoint before calling Qwen-VL for visible-impact and reconstruction text. The model is not asked to invent damage area or loss amounts.
- Planning: reads the latest persisted fire-front result, displays and maps that perimeter, recommends 2-6 targets from real area/intensity/radius properties independently of fire-team count, accepts manual targets, and sends the current fire radius into A* exercise-grid routing. UAV is excluded; water and food remain explicit operator requests.
- Main files: `fire_agent_backend/app/models/imagery.py`, `routers/{assistant,imagery_agent,planning_preview}.py`, `services/{imagery_products,workflow_runtime_service}.py`, visual image processing, `src/components/AgentChat.vue`, `src/stores/assistantTaskStore.ts`, and `src/views/{FirePredict,Planning,VisualVerification,AssessmentWorkspace}.vue`.
- Validation passed: backend compileall; `npm run build`; `docker compose config --quiet`; `git diff --check`; API/frontend rebuild; healthy PostGIS/API/frontend; all five frontend routes returned 200. A temporary container test built a 60x60 five-band product with descriptions B4/B3/B2/B8/B12.
- API validation: exact request “执行Dixie Fire的完整历史火灾推演” returns `start_workflow` with 240 minutes and imagery acquisition. A real workflow `wfr_e52ca34b2237422594` imported FIRMS candidate `dixie_fire_2021-firms-viirs_snpp-20210714T091100Z-39.871940--121.382410`, completed data preparation and correctly paused at fire verification. The initial SQL failure was fixed by using the actual `confidence_score` column.
- Spread/planning validation: real historical raster run `spr_defcac7afdd541bd85` completed with the Copernicus DEM + ESA WorldCover landscape (`is_simulated=false`), 3 steps, 0.1375 km2 area and 0.2698 km radius. A 4-team/3-target preview returned three calculated routes and no unassigned target.
- Exception validation: an intentionally impossible two-minute 1900 comparison window returned `no_match`, all five bands missing, the Copernicus official search URL and `data/raw/imagery/import`. It did not substitute a false date.
- Not fully exercised: downloading a full real five-band satellite scene was not run to completion because it can transfer hundreds of MB; no suitable two-date local products currently exist, so the actual Qwen post-fire assessment was not invoked. The UI reports these as data requirements instead of showing fabricated output. Pixel-level browser screenshot validation remains unavailable because the Windows CUA helper fails during setup.
- High-conflict integration files changed: `fire_agent_backend/app/main.py`, `fire_agent_backend/app/db/session.py`, `src/api/modules.ts`. Review their additive router/model/API registrations during integration.


## 2026-09-23 - member/heimini release handoff

- User authorized committing and pushing the complete local five-page version to `member/heimini`.
- Added `docs/MEMBER_HEIMINI_SETUP_PROMPT.md` with exact branch clone, local `.env` configuration, Docker startup, full Dixie data package import, verification, five-page usage, assistant examples and troubleshooting.
- README now links to the handoff prompt.
- Git includes source code, schemas, SQL, manifests, download/import scripts and the small realtime demo README files. Ignored local `.env`, secrets, PostGIS volumes, downloaded imagery and about 305 MB of local raw/processed GIS data remain excluded as required by repository policy.
- The full data prompt explicitly requires the separate `xinghuo-full-data-v1` handoff package or the documented official-source download/import scripts before claiming complete Dixie historical inference.
